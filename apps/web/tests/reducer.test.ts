import { describe, expect, it } from "vitest";
import { initialState, missionReducer, compareSnapshot } from "@/lib/events/reducer";
import { fixtureEvents } from "@/lib/fixtures";
import { buildSceneModel } from "@/lib/scene/model";
import { approvalFlow, ev, feed } from "./helpers";

describe("event reducer", () => {
  it("proposal_rejected marks the version rejected and exposes the conflict category", () => {
    const s = feed(approvalFlow().slice(0, 3));
    expect(s.view.versions[0]).toMatchObject({ version: 1, status: "rejected", reason_category: "constraint_conflict" });
    expect(s.view.conflictCategory).toBe("constraint_conflict");
  });

  it("counteroffer produces a new version and supersedes without hiding the rejection", () => {
    const s = feed(approvalFlow().slice(0, 4));
    expect(s.view.currentVersion).toBe(2);
    expect(s.view.versions.map((v) => v.status)).toEqual(["rejected", "proposed"]);
    expect(s.view.conflictCategory).toBeNull();
  });

  it("confirmation is shown only after backend proposal_confirmed AND consistent approvals", () => {
    const flow = approvalFlow();
    const before = feed(flow);
    expect(before.view.acceptedCount).toBe(4);
    expect(before.view.confirmed).toBe(false); // all accepted, but backend has not confirmed
    expect(before.view.phase).toBe("awaiting_approval");
    const after = feed([ev(20, "proposal_confirmed", { plan_id: "p2", version: 2, accepted_count: 4, required_count: 4 })], before);
    expect(after.view.confirmed).toBe(true);
    expect(after.view.phase).toBe("confirmed");
  });

  it("does not show confirmed when the stream lacks the acceptances (sync warning instead)", () => {
    const s = feed([...approvalFlow(2, ["a", "b"]), ev(20, "proposal_confirmed", { plan_id: "p2", version: 2, accepted_count: 4, required_count: 4 })]);
    expect(s.view.confirmed).toBe(false);
    expect(s.view.warnings.map((w) => w.code)).toContain("CONFIRM_MISMATCH");
  });

  it("conditional / pending members never count toward acceptance", () => {
    const s = feed([
      ...approvalFlow(2, ["a", "b"]),
      ev(30, "member_response_received", { plan_id: "p2", version: 2, member_ref: "c", state: "conditional" }),
    ]);
    expect(s.view.acceptedCount).toBe(2);
    expect(s.view.commitments.c).toBe("conditional");
    expect(s.view.confirmed).toBe(false);
  });

  it("duplicate and out-of-order delivery does not double-apply a confirmation", () => {
    const flow = [...approvalFlow(), ev(20, "proposal_confirmed", { plan_id: "p2", version: 2, accepted_count: 4, required_count: 4 })];
    const once = feed(flow);
    const dup = feed([...flow, ...flow]);
    expect(dup.duplicates).toBe(flow.length);
    expect(dup.view).toEqual(once.view);
    const shuffled = feed([...flow].reverse());
    expect(shuffled.view).toEqual(once.view);
    // a second, distinct confirmation event is a no-op
    const again = feed([ev(21, "proposal_confirmed", { plan_id: "p2", version: 2, accepted_count: 4, required_count: 4 })], once);
    expect(again.view.confirmed).toBe(true);
    expect(again.view.timeline.at(-1)?.ignoredReason).toMatch(/Already confirmed/);
  });

  it("late-arriving earlier event is re-ordered into the fold", () => {
    const flow = approvalFlow();
    const late = flow[2]!;
    const s = feed([...flow.filter((e) => e !== late), late]);
    expect(s.view).toEqual(feed(flow).view);
  });

  it("a material revision invalidates earlier approvals and confirmation", () => {
    const confirmed = feed([...approvalFlow(), ev(20, "proposal_confirmed", { plan_id: "p2", version: 2, accepted_count: 4, required_count: 4 })]);
    const revised = feed(
      [
        ev(21, "proposal_rejected", { plan_id: "p2", version: 2, reason_category: "constraint_conflict", changed_constraint_kind: "hard_budget" }),
        ev(22, "proposal_revised", { plan_id: "p3", version: 3, summary: "lower cost" }),
        ev(23, "approval_requested", { plan_id: "p3", version: 3, required_count: 4 }),
      ],
      confirmed,
    );
    expect(revised.view.confirmed).toBe(false);
    expect(revised.view.currentVersion).toBe(3);
    expect(revised.view.acceptedCount).toBe(0);
    expect(revised.view.commitmentsByVersion[2]).toBeDefined(); // history kept, but not counted
    expect(revised.view.phase).toBe("awaiting_approval");
  });

  it("stale responses for an older version are ignored with a warning", () => {
    const s = feed([
      ...approvalFlow(2, []),
      ev(20, "proposal_revised", { plan_id: "p3", version: 3 }),
      ev(21, "member_response_received", { plan_id: "p2", version: 2, member_ref: "a", state: "accepted" }),
    ]);
    expect(s.view.acceptedCount).toBe(0);
    expect(s.view.warnings.map((w) => w.code)).toContain("STALE_VERSION");
  });

  it("confirmation for a non-current version is ignored", () => {
    const s = feed([...approvalFlow(), ev(20, "proposal_revised", { plan_id: "p3", version: 3 }), ev(21, "proposal_confirmed", { plan_id: "p2", version: 2, accepted_count: 4, required_count: 4 })]);
    expect(s.view.confirmed).toBe(false);
    expect(s.view.warnings.map((w) => w.code)).toContain("CONFIRM_STALE");
  });

  it("negotiation_failed is an honest terminal state", () => {
    const s = feed([...approvalFlow(2, ["a"]), ev(20, "negotiation_failed", { failure_code: "NO_FEASIBLE_PLAN" })]);
    expect(s.view.phase).toBe("failed");
    expect(s.view.failureCode).toBe("NO_FEASIBLE_PLAN");
    expect(s.view.confirmed).toBe(false);
    expect(s.view.versions.at(-1)?.status).toBe("failed");
  });

  it("approvals on a rejected or failed version stop counting but stay in history", () => {
    const s = feed([...approvalFlow(2, ["a", "b"]), ev(20, "proposal_rejected", { plan_id: "p2", version: 2, reason_category: "constraint_conflict" })]);
    expect(s.view.acceptedCount).toBe(0);
    expect(s.view.commitments).toEqual({});
    expect(s.view.commitmentsByVersion[2]).toEqual({ a: "accepted", b: "accepted" });
    const f = feed([ev(21, "negotiation_failed", { failure_code: "NO_FEASIBLE_PLAN" })], s);
    expect(f.view.acceptedCount).toBe(0);
    expect(buildSceneModelProgress(f.view)).toBeNull();
  });

  it("private / non-group_safe events are rejected and never rendered", () => {
    const s = feed([ev(1, "negotiation_started", { group_size: 4 }, { visibility: "internal" }), ev(2, "candidate_proposed", { version: 1, hard_budget_cap_cents: 6000 })]);
    expect(s.log).toHaveLength(0);
    expect(s.rejected.map((r) => r.code)).toEqual(["NOT_GROUP_SAFE", "FORBIDDEN_KEY"]);
    expect(s.view.timeline).toHaveLength(0);
  });

  it("events from another session are not merged into the view", () => {
    const s = feed([ev(1, "negotiation_started", { group_size: 4 }), ev(2, "proposal_confirmed", { version: 1 }, { session_id: "other" })]);
    expect(s.view.warnings.map((w) => w.code)).toContain("SESSION_MISMATCH");
    expect(s.view.confirmed).toBe(false);
  });

  it("replaying the canonical fixture ends in a consistent confirmed state", () => {
    const s = feed(fixtureEvents);
    expect(s.rejected).toHaveLength(0);
    expect(s.view.currentVersion).toBe(2);
    expect(s.view.versions[0]?.status).toBe("rejected");
    expect(s.view.confirmed).toBe(true);
    expect(s.view.acceptedCount).toBe(4);
    expect(s.view.warnings).toEqual([]);
  });

  it("is deterministic: same events yield identical state at every prefix", () => {
    for (let i = 0; i <= fixtureEvents.length; i++) {
      expect(feed(fixtureEvents.slice(0, i)).view).toEqual(feed([...fixtureEvents.slice(0, i)].reverse()).view);
    }
  });

  it("reset clears everything", () => {
    expect(missionReducer(feed(fixtureEvents), { type: "reset" }).log).toHaveLength(0);
    expect(initialState().view.phase).toBe("idle");
  });
});

describe("snapshot comparison", () => {
  const confirmed = feed(fixtureEvents);
  it("warns instead of agreeing when snapshot and stream disagree", () => {
    const w = compareSnapshot(confirmed.view, { session_id: "session_trip_001", current_version: 3, status: "awaiting_approval" });
    expect(w.length).toBe(2);
  });
  it("is silent when they agree", () => {
    expect(compareSnapshot(confirmed.view, { session_id: "session_trip_001", current_version: 2, status: "confirmed" })).toEqual([]);
  });
  it("snapshot action surfaces warnings in the view", () => {
    const s = missionReducer(confirmed, { type: "snapshot", snapshot: { session_id: "session_trip_001", current_version: 2, status: "negotiating" } });
    expect(s.view.warnings.some((x) => x.code === "SNAPSHOT_MISMATCH")).toBe(true);
  });
});

const buildSceneModelProgress = (v: Parameters<typeof buildSceneModel>[0]) => buildSceneModel(v).core.progress;

describe("stress", () => {
  it("handles 500 shuffled, duplicated events quickly and deterministically", () => {
    const at = (n: number) => ({ timestamp: new Date(Date.UTC(2026, 9, 24, 18, 0, n)).toISOString() });
    const events: unknown[] = [];
    let n = 100;
    for (let v = 1; v <= 100; v++) {
      events.push(
        ev(n++, "proposal_revised", { plan_id: `p${v}`, version: v }, at(n)),
        ev(n++, "approval_requested", { plan_id: `p${v}`, version: v, required_count: 4 }, at(n)),
        ...["a", "b", "c"].map((m) => ev(n++, "member_response_received", { plan_id: `p${v}`, version: v, member_ref: m, state: "accepted" }, at(n))),
      );
    }
    const all = [...events, ...events.slice(0, 200)];
    const mixed = all.map((e, i) => [e, (i * 7919) % 503] as const).sort((x, y) => x[1] - y[1]).map(([e]) => e);
    const t0 = performance.now();
    const s = feed(mixed);
    expect(performance.now() - t0).toBeLessThan(5000);
    expect(s.view.currentVersion).toBe(100);
    expect(s.view.confirmed).toBe(false);
    expect(s.view.acceptedCount).toBe(3);
    expect(s.duplicates).toBe(200);
    expect(s.view).toEqual(feed(events).view);
  });
});
