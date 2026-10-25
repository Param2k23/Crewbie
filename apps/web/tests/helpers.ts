import { initialState, missionReducer, MissionState } from "@/lib/events/reducer";

export const ev = (n: number, type: string, payload: Record<string, unknown> = {}, extra: Record<string, unknown> = {}) => ({
  event_id: `ev_${String(n).padStart(4, "0")}`,
  session_id: "s1",
  timestamp: `2026-10-24T18:${String(n).padStart(2, "0")}:00Z`,
  type,
  actor_ref: "coordination_engine",
  visibility: "group_safe",
  payload,
  synthetic: true,
  ...extra,
});

export const feed = (events: unknown[], from: MissionState = initialState()) =>
  events.reduce<MissionState>((s, raw) => missionReducer(s, { type: "ingest", raw }), from);

export const approvalFlow = (version = 2, accepts = ["a", "b", "c", "d"]) => [
  ev(1, "negotiation_started", { group_size: 4 }),
  ev(2, "candidate_proposed", { plan_id: "p1", version: 1 }),
  ev(3, "proposal_rejected", { plan_id: "p1", version: 1, reason_category: "constraint_conflict" }),
  ev(4, "counteroffer_proposed", { version, summary: "cheaper" }),
  ev(5, "proposal_ready", { plan_id: "p2", version, approval_state: "pending" }),
  ev(6, "approval_requested", { plan_id: "p2", version, required_count: 4 }),
  ...accepts.map((m, i) => ev(7 + i, "member_response_received", { plan_id: "p2", version, member_ref: m, state: "accepted" })),
];
