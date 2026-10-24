import type { Opportunity } from "../opportunities/types";
import type { PlanPreview, ScenarioDef } from "./types";

/**
 * EXPLICIT DEMO MODE. Everything here is scripted, synthetic and labelled (actor_ref
 * "demo_script"/"local_simulator"). It stands in for the real negotiation engine until A4/A5 are
 * integrated and is never presented as engine output.
 */
export const DEMO_MEMBERS = ["stu_alex", "stu_maya", "stu_jordan", "stu_taylor"] as const;

const mkEvent = (session: string, prefix: string) => (n: number, minute: number, type: string, payload: Record<string, unknown>, actor = "demo_script") => ({
  event_id: `${prefix}_${String(n).padStart(4, "0")}`,
  session_id: session,
  timestamp: `2026-10-24T19:${String(minute).padStart(2, "0")}:00Z`,
  type,
  actor_ref: actor,
  visibility: "group_safe",
  payload,
  synthetic: true,
});

const opt = (o: Partial<Opportunity> & Pick<Opportunity, "opportunity_id" | "title" | "start_at" | "end_at">): Opportunity => ({
  campus: "Tempe", location_label: null, food_status: "unknown", food_detail: "No food information in the demo description",
  dietary_suitability: "unknown", access_status: "unknown", rsvp_required: null, source_url: "https://example.org/crewbie-demo/option",
  checked_at: "2026-10-24T18:00:00Z", synthetic: true, ...o,
});

// ---------------------------------------------------------------- Quick Plan
const q = mkEvent("session_quick_001", "quick");
const quickPreviews: Record<number, PlanPreview> = {
  1: { title: "Dinner then game night (v1)", start: "2026-10-30T18:00:00-07:00", end: "2026-10-30T22:30:00-07:00", budgetNote: "Group estimate about $90 (synthetic)",
    activities: [{ label: "Dinner", start: "2026-10-30T18:00:00-07:00", end: "2026-10-30T19:30:00-07:00" }, { label: "Game night", start: "2026-10-30T20:00:00-07:00", end: "2026-10-30T22:30:00-07:00" }] },
  2: { title: "Late dinner and board games (v2)", start: "2026-10-30T19:00:00-07:00", end: "2026-10-30T22:30:00-07:00", budgetNote: "Group estimate about $70 (synthetic)",
    activities: [{ label: "Dinner", start: "2026-10-30T19:00:00-07:00", end: "2026-10-30T20:30:00-07:00" }, { label: "Board games", start: "2026-10-30T20:45:00-07:00", end: "2026-10-30T22:30:00-07:00" }] },
};
export const quickPlan: ScenarioDef = {
  id: "quick", label: "Quick Plan", session: "session_quick_001",
  intent: {
    activity: "Dinner or a game night", kind: "quick", horizonLabel: "Tonight · about 6 hours",
    horizonStart: "2026-10-30T17:00:00-07:00", horizonEnd: "2026-10-30T23:00:00-07:00",
    groupNote: "Four consenting students, conflicting evening availability",
    options: [
      opt({ opportunity_id: "opt_q_games", title: "Board game cafe table (DEMO)", start_at: "2026-10-30T19:00:00-07:00", end_at: "2026-10-30T23:00:00-07:00", location_label: "Sample cafe — NOT A REAL LISTING", access_status: "public", food_status: "listed", food_detail: "Demo listing mentions snacks; menu and availability unverified" }),
      opt({ opportunity_id: "opt_q_dinner", title: "Group dinner near campus (DEMO)", start_at: "2026-10-30T18:00:00-07:00", end_at: "2026-10-30T21:00:00-07:00", location_label: null, food_status: "unknown", rsvp_required: true }),
      opt({ opportunity_id: "opt_q_arcade", title: "Student arcade night (DEMO)", start_at: "2026-10-30T20:00:00-07:00", end_at: "2026-10-30T22:30:00-07:00", location_label: "Sample union — NOT A REAL LISTING", food_status: "none", food_detail: "No food listed", access_status: "restricted" }),
    ],
  },
  members: DEMO_MEMBERS,
  baseEvents: [
    q(1, 0, "negotiation_started", { group_size: 4 }),
    q(2, 1, "candidate_proposed", { plan_id: "plan_quick_001", version: 1 }),
    q(3, 2, "proposal_rejected", { plan_id: "plan_quick_001", version: 1, reason_category: "availability_conflict" }),
    q(4, 3, "counteroffer_proposed", { plan_id: "plan_quick_002", version: 2, summary: "Later start and a shorter dinner" }),
    q(5, 4, "fairness_evaluated", { plan_id: "plan_quick_002", version: 2, fairness_category: "balanced" }),
    q(6, 5, "proposal_ready", { plan_id: "plan_quick_002", version: 2, approval_state: "pending" }),
    q(7, 6, "approval_requested", { plan_id: "plan_quick_002", version: 2, required_count: 4 }),
    q(8, 7, "member_response_received", { plan_id: "plan_quick_002", version: 2, member_ref: "stu_alex", state: "accepted" }, "group_host"),
    q(9, 8, "member_response_received", { plan_id: "plan_quick_002", version: 2, member_ref: "stu_maya", state: "conditional", condition_category: "needs_time_change" }, "group_host"),
    q(10, 9, "member_response_received", { plan_id: "plan_quick_002", version: 2, member_ref: "stu_jordan", state: "accepted" }, "group_host"),
  ],
  holdMessage: "Paused: 2 accepted, 1 conditional, 1 not yet responded. Nothing is confirmed. Change a constraint as the judge, or let the others respond.",
  initialAccepted: ["stu_alex", "stu_jordan"], initialVersion: 2, initialRequired: 4,
  previews: quickPreviews,
  windows: [
    { id: "block_dinner_hour", label: "Block 7:00–8:00 PM for one student", feasible: true },
    { id: "block_all_evening", label: "Block the whole evening for one student", feasible: false },
  ],
  budgetCurrentPlanCents: 1800, budgetCheapestPlanCents: 900,
  revised: {
    hard_budget: { summary: "Cheaper dinner spot within the changed limit", preview: (b) => ({ ...b, title: "Budget dinner and games", budgetNote: "Group estimate about $45 (synthetic)" }) },
    block_window: { summary: "Dinner moved to 8:00 PM around the blocked hour", preview: (b) => ({ ...b, title: "Later dinner and games", notes: "Dinner shifted around a blocked window (details private)", activities: b.activities.map((a, i) => i === 0 ? { ...a, start: "2026-10-30T20:00:00-07:00", end: "2026-10-30T21:15:00-07:00" } : { ...a, start: "2026-10-30T21:30:00-07:00", end: "2026-10-30T22:45:00-07:00" }), end: "2026-10-30T22:45:00-07:00" }) },
    withdraw: { summary: "Plan adjusted for a group of three", preview: (b) => ({ ...b, title: "Smaller group dinner", budgetNote: "Group estimate about $55 (synthetic)", notes: "One participant withdrew" }) },
  },
};

// ---------------------------------------------------------------- Weekend Plan
const w = mkEvent("session_weekend_001", "wknd");
const weekendPreviews: Record<number, PlanPreview> = {
  1: { title: "Two-day Flagstaff trip (v1)", start: "2026-11-07T07:00:00-07:00", end: "2026-11-08T20:00:00-07:00", budgetNote: "Group estimate about $720 including lodging (synthetic)",
    activities: [{ label: "Drive + scenic stop", start: "2026-11-07T07:00:00-07:00", end: "2026-11-07T12:00:00-07:00" }, { label: "Hike + dinner", start: "2026-11-07T13:00:00-07:00", end: "2026-11-07T21:00:00-07:00" }, { label: "Lodging", start: "2026-11-07T21:00:00-07:00", end: "2026-11-08T09:00:00-07:00" }, { label: "Town + return", start: "2026-11-08T10:00:00-07:00", end: "2026-11-08T20:00:00-07:00" }] },
  2: { title: "Flagstaff, shared lodging (v2)", start: "2026-11-07T08:00:00-07:00", end: "2026-11-08T19:00:00-07:00", budgetNote: "Group estimate about $520 (synthetic)",
    activities: [{ label: "Drive", start: "2026-11-07T08:00:00-07:00", end: "2026-11-07T11:30:00-07:00" }, { label: "Hike + dinner", start: "2026-11-07T12:00:00-07:00", end: "2026-11-07T20:00:00-07:00" }, { label: "Lodging", start: "2026-11-07T20:00:00-07:00", end: "2026-11-08T09:00:00-07:00" }, { label: "Return", start: "2026-11-08T14:00:00-07:00", end: "2026-11-08T19:00:00-07:00" }] },
  3: { title: "Flagstaff, 10:00 departure (v3)", start: "2026-11-07T10:00:00-07:00", end: "2026-11-08T18:00:00-07:00", budgetNote: "Group estimate about $480 (synthetic)",
    activities: [{ label: "Drive", start: "2026-11-07T10:00:00-07:00", end: "2026-11-07T13:30:00-07:00" }, { label: "Hike + dinner", start: "2026-11-07T14:00:00-07:00", end: "2026-11-07T21:00:00-07:00" }, { label: "Lodging", start: "2026-11-07T21:00:00-07:00", end: "2026-11-08T10:00:00-07:00" }, { label: "Brunch + return", start: "2026-11-08T11:00:00-07:00", end: "2026-11-08T18:00:00-07:00" }] },
};
export const weekendPlan: ScenarioDef = {
  id: "weekend", label: "Weekend Plan", session: "session_weekend_001",
  intent: {
    activity: "Two-day trip", kind: "weekend", horizonLabel: "Sat–Sun · 2 days",
    horizonStart: "2026-11-07T06:00:00-07:00", horizonEnd: "2026-11-08T23:00:00-07:00",
    groupNote: "Four consenting students, conflicting budgets, departure preferences and calendars",
    options: [
      opt({ opportunity_id: "opt_w_flag", title: "Flagstaff scenic day + overnight (DEMO)", campus: "Flagstaff", start_at: "2026-11-07T08:00:00-07:00", end_at: "2026-11-08T18:00:00-07:00", location_label: "Sample destination — NOT A REAL LISTING", access_status: "public", food_detail: "No food information; costs and drive times are demonstration estimates" }),
      opt({ opportunity_id: "opt_w_canyon", title: "Canyon day hike (DEMO)", campus: "Tempe", start_at: "2026-11-08T07:00:00-07:00", end_at: "2026-11-08T17:00:00-07:00", location_label: null, access_status: "unknown" }),
    ],
  },
  members: DEMO_MEMBERS,
  baseEvents: [
    w(1, 0, "negotiation_started", { group_size: 4 }),
    w(2, 1, "candidate_proposed", { plan_id: "plan_wknd_001", version: 1 }),
    w(3, 2, "proposal_rejected", { plan_id: "plan_wknd_001", version: 1, reason_category: "budget_conflict" }),
    w(4, 3, "counteroffer_proposed", { plan_id: "plan_wknd_002", version: 2, summary: "Shared lodging and lower estimated cost" }),
    w(5, 4, "proposal_rejected", { plan_id: "plan_wknd_002", version: 2, reason_category: "departure_conflict" }),
    w(6, 5, "counteroffer_proposed", { plan_id: "plan_wknd_003", version: 3, summary: "Later Saturday departure and earlier Sunday return" }),
    w(7, 6, "fairness_evaluated", { plan_id: "plan_wknd_003", version: 3, fairness_category: "balanced" }),
    w(8, 7, "proposal_ready", { plan_id: "plan_wknd_003", version: 3, approval_state: "pending" }),
    w(9, 8, "approval_requested", { plan_id: "plan_wknd_003", version: 3, required_count: 4 }),
    w(10, 9, "member_response_received", { plan_id: "plan_wknd_003", version: 3, member_ref: "stu_alex", state: "accepted" }, "group_host"),
    w(11, 10, "member_response_received", { plan_id: "plan_wknd_003", version: 3, member_ref: "stu_maya", state: "accepted" }, "group_host"),
    w(12, 11, "member_response_received", { plan_id: "plan_wknd_003", version: 3, member_ref: "stu_jordan", state: "conditional", condition_category: "needs_cost_clarity" }, "group_host"),
  ],
  holdMessage: "Paused: 2 accepted, 1 conditional, 1 not yet responded. Nothing is confirmed. Change a constraint as the judge, or let the others respond.",
  initialAccepted: ["stu_alex", "stu_maya"], initialVersion: 3, initialRequired: 4,
  previews: weekendPreviews,
  windows: [
    { id: "block_saturday_morning", label: "Block Saturday morning for one student", feasible: true },
    { id: "block_whole_weekend", label: "Block the whole weekend for one student", feasible: false },
  ],
  budgetCurrentPlanCents: 12000, budgetCheapestPlanCents: 8000,
  revised: {
    hard_budget: { summary: "Camping-style lodging within the changed limit", preview: (b) => ({ ...b, title: "Budget Flagstaff weekend", budgetNote: "Group estimate about $340 (synthetic)" }) },
    block_window: { summary: "Departure moved to Saturday afternoon", preview: (b) => ({ ...b, title: "Afternoon-departure trip", start: "2026-11-07T13:00:00-07:00", notes: "Saturday morning unavailable for one participant (details private)", activities: b.activities.map((a, i) => i === 0 ? { ...a, start: "2026-11-07T13:00:00-07:00", end: "2026-11-07T16:30:00-07:00" } : i === 1 ? { ...a, start: "2026-11-07T17:00:00-07:00", end: "2026-11-07T21:30:00-07:00" } : a) }) },
    withdraw: { summary: "Plan adjusted for a group of three", preview: (b) => ({ ...b, title: "Three-person weekend", budgetNote: "Group estimate about $400 (synthetic)", notes: "One participant withdrew" }) },
  },
};

export const SCENARIOS: Record<"quick" | "weekend", ScenarioDef> = { quick: quickPlan, weekend: weekendPlan };
