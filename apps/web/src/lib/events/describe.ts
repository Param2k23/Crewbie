import { AgentEvent, TimelineEntry } from "./types";

export const REASON_LABELS: Record<string, string> = {
  constraint_conflict: "A hard constraint of at least one member is not met (details stay private)",
  no_feasible_plan: "No plan satisfied every hard constraint within the search limit",
  availability_conflict: "A member's availability conflicts with the plan (details stay private)",
};

export const CONDITION_LABELS: Record<string, string> = {
  needs_cost_clarity: "Conditional: wants cost clarity",
  needs_time_change: "Conditional: wants a different time",
  needs_review: "Conditional: wants to review details",
};

export const FAILURE_LABELS: Record<string, string> = {
  NO_FEASIBLE_PLAN: "No feasible plan: a valid terminal outcome, not an error",
  HARD_CONSTRAINT_FAILED: "A hard constraint failed; the group gets a redacted explanation",
  APPROVAL_INCOMPLETE: "Approval incomplete: confirmation must not fire",
  PROPOSAL_STALE: "Approval targeted an older version",
};

export function labelFor(map: Record<string, string>, key: string | undefined | null): string {
  if (!key) return "";
  return map[key] ?? key.replace(/_/g, " ");
}

/** Plain-language title + tone for each event; text is built only from sanitized fields. */
export function describeEvent(e: AgentEvent): Pick<TimelineEntry, "title" | "tone"> {
  const p = e.payload;
  const v = p.version !== undefined ? ` v${p.version}` : "";
  switch (e.type) {
    case "negotiation_started":
      return { title: `Negotiation started${p.group_size ? ` with ${p.group_size} agents` : ""}`, tone: "info" };
    case "candidate_proposed":
      return { title: `Candidate plan${v} proposed`, tone: "neutral" };
    case "proposal_rejected":
      return { title: `Plan${v} rejected: ${labelFor(REASON_LABELS, p.reason_category) || "reason not given"}`, tone: "bad" };
    case "counteroffer_proposed":
      return { title: `Counteroffer${v}${p.summary ? `: ${p.summary}` : ""}`, tone: "info" };
    case "proposal_revised":
      return { title: `Plan revised to${v}; earlier approvals no longer count${p.summary ? `: ${p.summary}` : ""}`, tone: "warn" };
    case "fairness_evaluated":
      return { title: `Fairness evaluated${v}${p.fairness_category ? `: ${p.fairness_category.replace(/_/g, " ")}` : ""}`, tone: "info" };
    case "proposal_ready":
      return { title: `Plan${v} ready; approval ${p.approval_state ?? "state"} not yet confirmed`, tone: "neutral" };
    case "approval_requested":
      return { title: `Approval requested for${v}${p.required_count ? ` (${p.required_count} required)` : ""}`, tone: "warn" };
    case "member_response_received":
      return { title: `${p.member_ref ?? "Member"} responded: ${p.state ?? "unknown"}${v ? ` on${v}` : ""}${p.condition_category ? ` (${labelFor(CONDITION_LABELS, p.condition_category)})` : ""}`, tone: p.state === "accepted" ? "good" : p.state === "declined" || p.state === "withdrawn" ? "bad" : "warn" };
    case "proposal_confirmed":
      return { title: `Backend confirmed plan${v}${p.accepted_count !== undefined ? ` (${p.accepted_count}/${p.required_count ?? "?"} accepted)` : ""}`, tone: "good" };
    case "negotiation_failed":
      return { title: `Negotiation ended: ${labelFor(FAILURE_LABELS, p.failure_code ?? "NO_FEASIBLE_PLAN")}`, tone: "bad" };
    case "session_completed":
      return { title: "Session completed", tone: "info" };
    case "opportunity_discovered":
      return { title: "Opportunity discovered", tone: "info" };
    case "match_requested":
      return { title: "Match requested", tone: "neutral" };
    case "match_suggested":
      return { title: "Match suggested (introduction needs consent)", tone: "neutral" };
    case "consent_requested":
      return { title: "Consent requested", tone: "warn" };
    case "consent_granted":
      return { title: "Consent granted", tone: "good" };
  }
}
