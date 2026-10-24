import type { JudgeAdapter, JudgeRequest, JudgeResponse } from "../adapters/judge";
import type { ReplayController } from "../replay/controller";
import type { PlanPreview, ScenarioDef } from "./types";

/**
 * Local stand-in for the negotiation backend, used ONLY in explicit demo mode. It never mutates UI
 * state: it queues recorded-style events onto the replay controller, which the reducer then folds
 * like any other source. Its thresholds are internal and never rendered.
 */
export class LocalSimulator implements JudgeAdapter {
  readonly label = "Local simulator (not the negotiation engine)";
  readonly simulated = true;
  private n = 100;
  private version: number;
  private accepted: Set<string>;
  private required: number;
  private withdrawn = new Set<string>();
  readonly previews: Record<number, PlanPreview>;

  constructor(private readonly def: ScenarioDef, private readonly ctl: () => ReplayController, private readonly latencyMs = 700) {
    this.version = def.initialVersion;
    this.accepted = new Set(def.initialAccepted);
    this.required = def.initialRequired;
    this.previews = { ...def.previews };
  }

  resetState() {
    this.n = 100;
    this.version = this.def.initialVersion;
    this.accepted = new Set(this.def.initialAccepted);
    this.required = this.def.initialRequired;
    this.withdrawn.clear();
    for (const k of Object.keys(this.previews)) delete this.previews[Number(k)];
    Object.assign(this.previews, this.def.previews);
  }

  private prefix = () => (this.def.id === "quick" ? "quick" : "wknd");
  private planId = (v: number) => `plan_${this.prefix()}_${String(v).padStart(3, "0")}`;
  private active = () => this.def.members.filter((m) => !this.withdrawn.has(m));

  private ev(type: string, payload: Record<string, unknown>, actor = "local_simulator") {
    this.n++;
    return {
      event_id: `${this.prefix()}_${String(this.n).padStart(4, "0")}`,
      session_id: this.def.session,
      timestamp: new Date(Date.UTC(2026, 9, 24, 20, 0, this.n)).toISOString(),
      type, actor_ref: actor, visibility: "group_safe", payload, synthetic: true,
    };
  }

  /** Demo-only affordance: remaining active members answer the live version (scripted, not engine output). */
  remainingMembersAccept(): void {
    const live = { plan_id: this.planId(this.version), version: this.version };
    const rest = this.active().filter((m) => !this.accepted.has(m));
    rest.forEach((m) => this.accepted.add(m));
    const c = this.ctl();
    c.append([
      ...rest.map((m) => this.ev("member_response_received", { ...live, member_ref: m, state: "accepted" }, "group_host")),
      this.ev("proposal_confirmed", { ...live, accepted_count: this.accepted.size, required_count: this.required }),
    ]);
    c.release();
    c.play();
  }

  async submit(req: JudgeRequest): Promise<JudgeResponse> {
    await new Promise((r) => setTimeout(r, this.latencyMs));
    const { member_ref, kind, value } = req.changed_constraint_ref;
    const rid = { request_id: req.request_id };
    const reject = (message: string): JudgeResponse => ({ request_id: req.request_id, status: "rejected", message });
    if (req.session_id !== this.def.session || !this.def.members.includes(member_ref)) return reject("Simulator only accepts the synthetic demo profiles.");
    if (this.withdrawn.has(member_ref)) return reject("That participant has already withdrawn.");

    const old = { plan_id: this.planId(this.version), version: this.version };
    const events: unknown[] = [];
    let category = "constraint_conflict";
    let infeasible = false;
    let kindSlug: string;

    if (kind === "hard_budget") {
      const cents = Number(value);
      if (!Number.isFinite(cents) || cents <= 0) return reject("Invalid budget value.");
      if (cents >= this.def.budgetCurrentPlanCents) {
        return { request_id: req.request_id, status: "accepted", message: "Constraint recorded. Re-validation found the current plan still satisfies it, so no new events were produced." };
      }
      infeasible = cents < this.def.budgetCheapestPlanCents;
      category = "budget_conflict";
      kindSlug = "hard_budget";
    } else if (kind === "block_window") {
      const preset = this.def.windows.find((w) => w.id === value);
      if (!preset) return reject("Unknown time window.");
      infeasible = !preset.feasible;
      category = "availability_conflict";
      kindSlug = "availability";
    } else if (kind === "withdraw") {
      kindSlug = "withdrawal";
      this.withdrawn.add(member_ref);
      this.accepted.delete(member_ref);
      events.push(this.ev("member_response_received", { ...old, member_ref, state: "withdrawn", changed_constraint_kind: kindSlug, ...rid }));
      infeasible = this.active().length < 2;
    } else {
      return reject("Unsupported change.");
    }

    if (kind !== "withdraw") {
      events.push(this.ev("proposal_rejected", { ...old, reason_category: category, changed_constraint_kind: kindSlug, ...rid }));
    }
    if (infeasible) {
      events.push(this.ev("negotiation_failed", { failure_code: "NO_FEASIBLE_PLAN", changed_constraint_kind: kindSlug, ...rid }));
    } else {
      const base = this.previews[this.version]!;
      const rev = this.def.revised[kind];
      this.version++;
      this.accepted = new Set();
      this.required = this.active().length;
      this.previews[this.version] = rev.preview(base);
      const nw = { plan_id: this.planId(this.version), version: this.version };
      events.push(
        this.ev("proposal_revised", { ...nw, summary: rev.summary, changed_constraint_kind: kindSlug, ...rid }),
        this.ev("fairness_evaluated", { ...nw, fairness_category: "balanced" }),
        this.ev("proposal_ready", { ...nw, approval_state: "pending" }),
        this.ev("approval_requested", { ...nw, required_count: this.required }),
      );
    }
    const c = this.ctl();
    c.append(events);
    c.release();
    c.play();
    return { request_id: req.request_id, status: "accepted", message: "Simulator accepted the request and queued the resulting events (not yet shown)." };
  }
}
