import { describe, expect, it, vi } from "vitest";
import { DemoAdapter } from "@/lib/adapters";
import { HttpJudgeAdapter, JudgeRequest } from "@/lib/adapters/judge";
import { DEMO_SESSION, DEMO_HOLD_INDEX } from "@/lib/demo/scenario";
import { initialState, missionReducer } from "@/lib/events/reducer";

function demo() {
  const adapter = new DemoAdapter();
  let state = initialState();
  adapter.connect({ onEvent: (raw) => (state = missionReducer(state, { type: "ingest", raw })), onReset: () => (state = initialState()), onStatus: () => {}, onMalformed: () => {} });
  while (adapter.replay.getSnapshot().cursor < DEMO_HOLD_INDEX) adapter.replay.step();
  return { adapter, get: () => state };
}
const req = (member_ref: string, kind: "hard_budget" | "availability", value: number | string, session_id = DEMO_SESSION): JudgeRequest => ({
  request_id: "r1", session_id, changed_constraint_ref: { member_ref, kind, value }, synthetic_confirmed: true,
});
const drain = (a: DemoAdapter) => { while (a.replay.step()); };

describe("demo scenario (wow moment)", () => {
  it("reaches the hold with failed v1, conditional approval and nothing confirmed", () => {
    const { adapter, get } = demo();
    const v = get().view;
    expect(v.versions[0]?.status).toBe("rejected");
    expect(v.currentVersion).toBe(2);
    expect(v.commitments).toMatchObject({ stu_alex: "accepted", stu_maya: "conditional", stu_jordan: "accepted" });
    expect(v.acceptedCount).toBe(2);
    expect(v.confirmed).toBe(false);
    expect(adapter.replay.getSnapshot().holdMessage).toMatch(/Nothing is confirmed/);
  });

  it("submitting a request alone changes nothing until simulator events are revealed", async () => {
    const { adapter, get } = demo();
    const before = get().view;
    const p = adapter.judge.submit(req("stu_alex", "hard_budget", 4500));
    expect(get().view).toEqual(before); // no optimistic update
    await p;
    expect(get().view).toEqual(before); // accepted, queued, not yet revealed
    drain(adapter);
  });

  it("budget between thresholds: v2 rejected, v3 proposed, old approvals invalidated", async () => {
    const { adapter, get } = demo();
    const res = await adapter.judge.submit(req("stu_alex", "hard_budget", 4500));
    expect(res.status).toBe("accepted");
    drain(adapter);
    const v = get().view;
    expect(v.versions.find((x) => x.version === 2)?.status).toBe("rejected");
    expect(v.currentVersion).toBe(3);
    expect(v.acceptedCount).toBe(0);
    expect(v.commitmentsByVersion[2]).toBeDefined();
    expect(v.phase).toBe("awaiting_approval");
    expect(v.confirmed).toBe(false);
    expect(get().log.some((e) => e.payload.request_id === "r1")).toBe(true);
  });

  it("impossible budget ends honestly with NO_FEASIBLE_PLAN", async () => {
    const { adapter, get } = demo();
    await adapter.judge.submit(req("stu_alex", "hard_budget", 2000));
    drain(adapter);
    expect(get().view.phase).toBe("failed");
    expect(get().view.failureCode).toBe("NO_FEASIBLE_PLAN");
    expect(get().view.confirmed).toBe(false);
  });

  it("a cap the current plan already satisfies produces no events", async () => {
    const { adapter, get } = demo();
    const n = get().log.length;
    const res = await adapter.judge.submit(req("stu_alex", "hard_budget", 9000));
    expect(res.message).toMatch(/no new events/);
    drain(adapter);
    expect(get().log.length).toBe(n);
  });

  it("refuses profiles outside the synthetic demo set", async () => {
    const { adapter, get } = demo();
    const n = get().log.length;
    expect((await adapter.judge.submit(req("stu_real_person", "hard_budget", 1000))).status).toBe("rejected");
    expect((await adapter.judge.submit(req("stu_alex", "hard_budget", 1000, "some_other_session"))).status).toBe("rejected");
    drain(adapter);
    expect(get().log.length).toBe(n);
  });

  it("confirmed only after consistent scripted acceptances, never by the judge request", async () => {
    const { adapter, get } = demo();
    adapter.actions[0]!.run();
    expect(get().view.confirmed).toBe(false);
    drain(adapter);
    expect(get().view.confirmed).toBe(true);
    expect(get().view.acceptedCount).toBe(4);
  });

  it("availability change replans; second change replans again to v4", async () => {
    const { adapter, get } = demo();
    await adapter.judge.submit(req("stu_maya", "availability", "blocks_current_day"));
    drain(adapter);
    expect(get().view.currentVersion).toBe(3);
    await adapter.judge.submit({ ...req("stu_maya", "hard_budget", 4200), request_id: "r2" });
    drain(adapter);
    expect(get().view.currentVersion).toBe(4);
  });

  it("reset restores the initial scenario deterministically", async () => {
    const { adapter, get } = demo();
    const snap = get().view;
    await adapter.judge.submit(req("stu_alex", "hard_budget", 4500));
    drain(adapter);
    adapter.replay.reset();
    while (adapter.replay.getSnapshot().cursor < DEMO_HOLD_INDEX) adapter.replay.step();
    expect(get().view).toEqual(snap);
  });
});

describe("HttpJudgeAdapter never turns failure into success", () => {
  const r = req("stu_alex", "hard_budget", 4500, "session_trip_001");
  it.each([[404, "unavailable"], [501, "unavailable"], [500, "rejected"], [400, "rejected"], [202, "accepted"]])("HTTP %i -> %s", async (code, status) => {
    const a = new HttpJudgeAdapter("http://x", vi.fn().mockResolvedValue(new Response("", { status: code })) as unknown as typeof fetch);
    expect((await a.submit(r)).status).toBe(status);
  });
  it("network error -> unavailable", async () => {
    const a = new HttpJudgeAdapter("http://x", vi.fn().mockRejectedValue(new Error("down")) as unknown as typeof fetch);
    expect((await a.submit(r)).status).toBe("unavailable");
  });
  it("sends an idempotency key and the request body only to the session route", async () => {
    const f = vi.fn().mockResolvedValue(new Response("", { status: 202 }));
    await new HttpJudgeAdapter("http://x", f as unknown as typeof fetch).submit(r);
    expect(f.mock.calls[0]![0]).toBe("http://x/v1/sessions/session_trip_001/constraint-changes");
    expect((f.mock.calls[0]![1] as RequestInit).headers).toMatchObject({ "idempotency-key": "r1" });
  });
});
