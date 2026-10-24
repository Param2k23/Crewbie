// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DemoAdapter, FixtureAdapter, MissionAdapter } from "@/lib/adapters";
import type { JudgeAdapter, JudgeResponse } from "@/lib/adapters/judge";
import { useMissionControl } from "@/lib/useMissionControl";
import { ev } from "./helpers";

function liveAdapter(events: unknown[], judge: JudgeAdapter): { adapter: MissionAdapter; push: () => void } {
  let h: Parameters<MissionAdapter["connect"]>[0] | null = null;
  const adapter: MissionAdapter = {
    kind: "network", label: "test", description: "", sessionId: "s1", replay: null, judge, actions: [], localSynthetic: false,
    connect: (handlers) => { h = handlers; handlers.onStatus("open"); return () => {}; },
  };
  return { adapter, push: () => events.forEach((e) => h!.onEvent(e)) };
}

describe("useMissionControl judge gating", () => {
  it("fixture replay is read-only", () => {
    const a = new FixtureAdapter();
    const { result } = renderHook(() => useMissionControl(a));
    expect(result.current.judgeBlockedReason).toMatch(/read-only/);
  });

  it("blocks judge changes when any event is non-synthetic", () => {
    const judge: JudgeAdapter = { label: "x", simulated: false, submit: async (r) => ({ request_id: r.request_id, status: "accepted", message: "" }) };
    const { adapter, push } = liveAdapter([ev(1, "negotiation_started", { group_size: 2 }, { synthetic: false })], judge);
    const { result } = renderHook(() => useMissionControl(adapter));
    act(push);
    expect(result.current.judgeBlockedReason).toMatch(/non-synthetic/);
  });

  it("shows pending until the server answers, and never marks success from the answer alone", async () => {
    let release!: (r: JudgeResponse) => void;
    const judge: JudgeAdapter = { label: "x", simulated: false, submit: () => new Promise((res) => (release = res)) };
    const { adapter, push } = liveAdapter([ev(1, "negotiation_started", { group_size: 2 })], judge);
    const { result } = renderHook(() => useMissionControl(adapter));
    act(push);
    expect(result.current.judgeBlockedReason).toBeNull();
    let p!: Promise<void>;
    act(() => { p = result.current.submitJudge({ member_ref: "stu_a", kind: "hard_budget", value: 4000 }); });
    expect(result.current.judgeState.phase).toBe("pending");
    await act(async () => { release({ request_id: "x", status: "accepted", message: "ok" }); await p; });
    expect(result.current.judgeState.phase).toBe("answered");
    expect(result.current.reflectedInStream).toBe(false); // no event carried the request id
    expect(result.current.view.phase).toBe("negotiating"); // plan state untouched
  });

  it("a thrown adapter error becomes an honest 'unavailable' answer", async () => {
    const judge: JudgeAdapter = { label: "x", simulated: false, submit: async () => { throw new Error("boom"); } };
    const { adapter, push } = liveAdapter([ev(1, "negotiation_started", { group_size: 2 })], judge);
    const { result } = renderHook(() => useMissionControl(adapter));
    act(push);
    await act(async () => { await result.current.submitJudge({ member_ref: "a", kind: "hard_budget", value: 1 }); });
    const s = result.current.judgeState;
    expect(s.phase === "answered" && s.response.status).toBe("unavailable");
  });

  it("demo adapter exposes the judge only after the session starts", () => {
    const a = new DemoAdapter();
    const { result } = renderHook(() => useMissionControl(a));
    expect(result.current.judgeBlockedReason).toMatch(/Waiting for the session/);
  });
});
