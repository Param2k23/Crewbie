import { describe, expect, it, vi } from "vitest";
import { DemoAdapter } from "@/lib/adapters";
import { HttpJudgeAdapter, JudgeRequest } from "@/lib/adapters/judge";
import { SCENARIOS } from "@/lib/demo/scenarios";
import type { ScenarioDef } from "@/lib/demo/types";
import { initialState, missionReducer } from "@/lib/events/reducer";

function demo(def: ScenarioDef = SCENARIOS.quick) {
  const adapter = new DemoAdapter(def);
  let state = initialState();
  adapter.connect({ onEvent: (raw) => (state = missionReducer(state, { type: "ingest", raw })), onReset: () => (state = initialState()), onStatus: () => {}, onMalformed: () => {} });
  const toHold = () => { while (adapter.replay.getSnapshot().cursor < def.baseEvents.length) adapter.replay.step(); };
  toHold();
  const req = (member_ref: string, kind: JudgeRequest["changed_constraint_ref"]["kind"], value: number | string, session_id = def.session, request_id = "r1"): JudgeRequest => ({
    request_id, session_id, changed_constraint_ref: { member_ref, kind, value }, synthetic_confirmed: true,
  });
  return { adapter, get: () => state, req, toHold, def };
}
const drain = (a: DemoAdapter) => { while (a.replay.step()); };

describe.each([["quick"], ["weekend"]] as const)("%s scenario", (id) => {
  const def = SCENARIOS[id];

  it("reaches the hold with earlier failed proposals, a conditional approval and nothing confirmed", () => {
    const { adapter, get } = demo(def);
    const v = get().view;
    expect(v.sessionId).toBe(def.session);
    expect(v.versions[0]?.status).toBe("rejected");
    expect(v.currentVersion).toBe(def.initialVersion);
    expect(v.acceptedCount).toBe(2);
    expect(Object.values(v.commitments)).toContain("conditional");
    expect(v.confirmed).toBe(false);
    expect(v.allSynthetic).toBe(true);
    expect(adapter.replay.getSnapshot().holdMessage).toMatch(/Nothing is confirmed/);
    expect(adapter.previews()[def.initialVersion]).toBeDefined();
    expect(get().rejected).toEqual([]);
  });

  it("every conflict category is generic: no member identity or amount in rejection events", () => {
    const { get } = demo(def);
    for (const e of get().log.filter((x) => x.type === "proposal_rejected")) {
      expect(e.payload.member_ref).toBeUndefined();
      expect(JSON.stringify({ ...e.payload, plan_id: "" })).not.toMatch(/\d{3,}/);
    }
  });

  it("a request alone changes nothing until simulator events are revealed (no optimistic update)", async () => {
    const { adapter, get, req } = demo(def);
    const before = get().view;
    const p = adapter.judge.submit(req("stu_alex", "hard_budget", 1500));
    expect(get().view).toEqual(before);
    await p;
    expect(get().view).toEqual(before);
    drain(adapter);
  });

  it("budget between thresholds: rejection, new version, approvals reset, preview for the new version", async () => {
    const { adapter, get, req } = demo(def);
    const mid = Math.round((def.budgetCurrentPlanCents + def.budgetCheapestPlanCents) / 2);
    expect((await adapter.judge.submit(req("stu_alex", "hard_budget", mid))).status).toBe("accepted");
    drain(adapter);
    const v = get().view;
    expect(v.versions.find((x) => x.version === def.initialVersion)?.status).toBe("rejected");
    expect(v.currentVersion).toBe(def.initialVersion + 1);
    expect(v.acceptedCount).toBe(0);
    expect(v.requiredCount).toBe(4);
    expect(v.commitmentsByVersion[def.initialVersion]).toBeDefined();
    expect(v.phase).toBe("awaiting_approval");
    expect(v.confirmed).toBe(false);
    expect(get().log.some((e) => e.payload.request_id === "r1")).toBe(true);
    expect(adapter.previews()[def.initialVersion + 1]).toBeDefined();
  });

  it("impossible budget ends honestly with NO_FEASIBLE_PLAN", async () => {
    const { adapter, get, req } = demo(def);
    await adapter.judge.submit(req("stu_alex", "hard_budget", 100));
    drain(adapter);
    expect(get().view.phase).toBe("failed");
    expect(get().view.failureCode).toBe("NO_FEASIBLE_PLAN");
    expect(get().view.confirmed).toBe(false);
  });

  it("a cap the current plan satisfies produces no events", async () => {
    const { adapter, get, req } = demo(def);
    const n = get().log.length;
    const res = await adapter.judge.submit(req("stu_alex", "hard_budget", def.budgetCurrentPlanCents + 1));
    expect(res.message).toMatch(/no new events/);
    drain(adapter);
    expect(get().log.length).toBe(n);
  });

  it("blocking a feasible window replans; blocking everything fails honestly", async () => {
    const a = demo(def);
    await a.adapter.judge.submit(a.req("stu_maya", "block_window", def.windows[0]!.id));
    drain(a.adapter);
    expect(a.get().view.currentVersion).toBe(def.initialVersion + 1);
    expect(a.get().view.acceptedCount).toBe(0);
    const b = demo(def);
    await b.adapter.judge.submit(b.req("stu_maya", "block_window", def.windows[1]!.id));
    drain(b.adapter);
    expect(b.get().view.phase).toBe("failed");
  });

  it("withdrawal keeps the member withdrawn, shrinks the required count, and still needs new approvals", async () => {
    const { adapter, get, req } = demo(def);
    await adapter.judge.submit(req("stu_taylor", "withdraw", "withdraw"));
    drain(adapter);
    const v = get().view;
    expect(v.currentVersion).toBe(def.initialVersion + 1);
    expect(v.commitments.stu_taylor).toBe("withdrawn");
    expect(v.requiredCount).toBe(3);
    expect(v.acceptedCount).toBe(0);
    adapter.actions[0]!.run();
    drain(adapter);
    const done = get().view;
    expect(done.confirmed).toBe(true);
    expect(done.acceptedCount).toBe(3);
    expect(done.commitments.stu_taylor).toBe("withdrawn");
  });

  it("refuses profiles or sessions outside the synthetic scenario", async () => {
    const { adapter, get, req } = demo(def);
    const n = get().log.length;
    expect((await adapter.judge.submit(req("stu_real_person", "hard_budget", 1000))).status).toBe("rejected");
    expect((await adapter.judge.submit(req("stu_alex", "hard_budget", 1000, "some_other_session"))).status).toBe("rejected");
    expect((await adapter.judge.submit(req("stu_alex", "block_window", "nope"))).status).toBe("rejected");
    drain(adapter);
    expect(get().log.length).toBe(n);
  });

  it("confirmed only after consistent scripted acceptances, never by a judge request", async () => {
    const { adapter, get } = demo(def);
    adapter.actions[0]!.run();
    expect(get().view.confirmed).toBe(false);
    drain(adapter);
    expect(get().view.confirmed).toBe(true);
    expect(get().view.acceptedCount).toBe(4);
  });

  it("successive changes keep versioning; reset restores the scenario deterministically", async () => {
    const { adapter, get, req, toHold } = demo(def);
    const snap = get().view;
    await adapter.judge.submit(req("stu_maya", "block_window", def.windows[0]!.id));
    drain(adapter);
    await adapter.judge.submit(req("stu_alex", "hard_budget", def.budgetCheapestPlanCents + 1, def.session, "r2"));
    drain(adapter);
    expect(get().view.currentVersion).toBe(def.initialVersion + 2);
    adapter.replay.reset();
    toHold();
    expect(get().view).toEqual(snap);
    expect(adapter.previews()[def.initialVersion + 1]).toBeUndefined();
  });
});

describe("weekend scenario specifics", () => {
  it("shows two failed proposals with redacted budget and departure categories", () => {
    const { get } = demo(SCENARIOS.weekend);
    const rej = get().view.versions.filter((v) => v.status === "rejected");
    expect(rej.map((v) => v.reason_category)).toEqual(["budget_conflict", "departure_conflict"]);
  });
});

describe("HttpJudgeAdapter never turns failure into success", () => {
  const r: JudgeRequest = { request_id: "r1", session_id: "session_trip_001", changed_constraint_ref: { member_ref: "stu_alex", kind: "hard_budget", value: 4500 }, synthetic_confirmed: true };
  it.each([[404, "unavailable"], [501, "unavailable"], [500, "rejected"], [400, "rejected"], [202, "accepted"]])("HTTP %i -> %s", async (code, status) => {
    const a = new HttpJudgeAdapter("http://x", vi.fn().mockResolvedValue(new Response("", { status: code })) as unknown as typeof fetch);
    expect((await a.submit(r)).status).toBe(status);
  });
  it("network error -> unavailable", async () => {
    const a = new HttpJudgeAdapter("http://x", vi.fn().mockRejectedValue(new Error("down")) as unknown as typeof fetch);
    expect((await a.submit(r)).status).toBe("unavailable");
  });
  it("sends an idempotency key to the session route", async () => {
    const f = vi.fn().mockResolvedValue(new Response("", { status: 202 }));
    await new HttpJudgeAdapter("http://x", f as unknown as typeof fetch).submit(r);
    expect(f.mock.calls[0]![0]).toBe("http://x/v1/sessions/session_trip_001/constraint-changes");
    expect((f.mock.calls[0]![1] as RequestInit).headers).toMatchObject({ "idempotency-key": "r1" });
  });
});
