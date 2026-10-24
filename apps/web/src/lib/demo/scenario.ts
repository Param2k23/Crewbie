import type { JudgeAdapter, JudgeRequest, JudgeResponse } from "../adapters/judge";
import { ReplayController } from "../replay/controller";

/**
 * EXPLICIT DEMO MODE. Everything here is scripted, synthetic, and labeled as such
 * (actor_ref "demo_script" / "local_simulator"). It exists to show the UI's transitions
 * when the real negotiation engine is not connected. It is not output of that engine.
 */
export const DEMO_SESSION = "session_demo_wow";
export const DEMO_MEMBERS = ["stu_alex", "stu_maya", "stu_jordan", "stu_taylor"] as const;

const mk = (n: number, minute: number, type: string, payload: Record<string, unknown>, actor = "demo_script") => ({
  event_id: `demo_${String(n).padStart(4, "0")}`,
  session_id: DEMO_SESSION,
  timestamp: `2026-10-24T19:${String(minute).padStart(2, "0")}:00Z`,
  type,
  actor_ref: actor,
  visibility: "group_safe",
  payload,
  synthetic: true,
});

export const demoBaseEvents: unknown[] = [
  mk(1, 0, "negotiation_started", { group_size: 4 }),
  mk(2, 1, "candidate_proposed", { plan_id: "plan_demo_001", version: 1 }),
  mk(3, 2, "proposal_rejected", { plan_id: "plan_demo_001", version: 1, reason_category: "constraint_conflict" }),
  mk(4, 3, "counteroffer_proposed", { plan_id: "plan_demo_002", version: 2, summary: "Alternative day and reduced estimated cost" }),
  mk(5, 4, "fairness_evaluated", { plan_id: "plan_demo_002", version: 2, fairness_category: "balanced" }),
  mk(6, 5, "proposal_ready", { plan_id: "plan_demo_002", version: 2, approval_state: "pending" }),
  mk(7, 6, "approval_requested", { plan_id: "plan_demo_002", version: 2, required_count: 4 }),
  mk(8, 7, "member_response_received", { plan_id: "plan_demo_002", version: 2, member_ref: "stu_alex", state: "accepted" }, "group_host"),
  mk(9, 8, "member_response_received", { plan_id: "plan_demo_002", version: 2, member_ref: "stu_maya", state: "conditional", condition_category: "needs_time_change" }, "group_host"),
  mk(10, 9, "member_response_received", { plan_id: "plan_demo_002", version: 2, member_ref: "stu_jordan", state: "accepted" }, "group_host"),
];

/** Playback pauses here: 2 accepted, 1 conditional, 1 silent. Nothing is confirmed. */
export const DEMO_HOLD_INDEX = demoBaseEvents.length;
export const DEMO_HOLD_MESSAGE =
  "Paused: 2 accepted, 1 conditional, 1 not yet responded. Nothing is confirmed. Change a constraint as the judge, or let the last member respond.";

/** Hidden thresholds of the *simulator only*. They are intentionally never rendered. */
const SIM_BUDGET_CURRENT_PLAN_CENTS = 5200;
const SIM_BUDGET_CHEAPEST_PLAN_CENTS = 4000;

export class LocalSimulator implements JudgeAdapter {
  readonly label = "Local simulator (not the negotiation engine)";
  readonly simulated = true;
  private n = 100;
  private minute = 20;
  private version = 2;
  constructor(private readonly ctl: () => ReplayController, private readonly latencyMs = 700) {}

  private ev(type: string, payload: Record<string, unknown>, actor = "local_simulator") {
    this.n++;
    return mk(this.n, this.minute++, type, payload, actor);
  }

  resetCounters() {
    this.n = 100;
    this.minute = 20;
    this.version = 2;
  }

  private plan = () => ({ plan_id: `plan_demo_${String(this.version).padStart(3, "0")}`, version: this.version });

  /** Demo-only affordance: remaining members answer the live version. Recorded as scripted events, never as engine output. */
  remainingMembersAccept(): void {
    const c = this.ctl();
    const live = this.plan();
    const have = this.version === 2 ? ["stu_alex", "stu_jordan"] : [];
    const rest = DEMO_MEMBERS.filter((m) => !have.includes(m));
    c.append([
      ...rest.map((m) => this.ev("member_response_received", { ...live, member_ref: m, state: "accepted" }, "group_host")),
      this.ev("proposal_confirmed", { ...live, accepted_count: 4, required_count: 4 }),
    ]);
    c.release();
    c.play();
  }

  async submit(req: JudgeRequest): Promise<JudgeResponse> {
    await new Promise((r) => setTimeout(r, this.latencyMs));
    const ref = req.changed_constraint_ref;
    if (!(DEMO_MEMBERS as readonly string[]).includes(ref.member_ref) || req.session_id !== DEMO_SESSION) {
      return { request_id: req.request_id, status: "rejected", message: "Simulator only accepts the synthetic demo profiles." };
    }
    const rid = { request_id: req.request_id };
    let infeasible: boolean;
    if (ref.kind === "hard_budget") {
      const cents = Number(ref.value);
      if (!Number.isFinite(cents) || cents <= 0) {
        return { request_id: req.request_id, status: "rejected", message: "Invalid budget value." };
      }
      if (cents >= SIM_BUDGET_CURRENT_PLAN_CENTS) {
        return { request_id: req.request_id, status: "accepted", message: "Constraint recorded. Re-validation found the current plan still satisfies it, so no new events were produced." };
      }
      infeasible = cents < SIM_BUDGET_CHEAPEST_PLAN_CENTS;
    } else {
      infeasible = ref.value === "blocks_all_days";
    }
    const kind = ref.kind === "hard_budget" ? "hard_budget" : "availability";
    const old = this.plan();
    const events: unknown[] = [
      this.ev("proposal_rejected", { ...old, reason_category: "constraint_conflict", changed_constraint_kind: kind, ...rid }),
    ];
    if (infeasible) {
      events.push(this.ev("negotiation_failed", { failure_code: "NO_FEASIBLE_PLAN", changed_constraint_kind: kind, ...rid }));
    } else {
      this.version++;
      const nw = this.plan();
      events.push(
        this.ev("proposal_revised", { ...nw, summary: kind === "hard_budget" ? "Lower-cost itinerary within the changed limit" : "Shifted to an alternative day", changed_constraint_kind: kind, ...rid }),
        this.ev("fairness_evaluated", { ...nw, fairness_category: "balanced" }),
        this.ev("proposal_ready", { ...nw, approval_state: "pending" }),
        this.ev("approval_requested", { ...nw, required_count: 4 }),
      );
    }
    const c = this.ctl();
    c.append(events);
    c.release();
    c.play();
    return { request_id: req.request_id, status: "accepted", message: "Simulator accepted the request and queued the resulting events (not yet shown)." };
  }
}

