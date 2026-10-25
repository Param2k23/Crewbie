/** Public, group-safe types mirroring docs/implementation/CONTRACTS.md. */

export const PUBLIC_EVENT_TYPES = [
  "opportunity_discovered",
  "match_requested",
  "match_suggested",
  "consent_requested",
  "consent_granted",
  "negotiation_started",
  "candidate_proposed",
  "proposal_rejected",
  "counteroffer_proposed",
  "fairness_evaluated",
  "proposal_ready",
  "approval_requested",
  "member_response_received",
  "proposal_confirmed",
  "proposal_revised",
  "negotiation_failed",
  "session_completed",
] as const;
export type PublicEventType = (typeof PUBLIC_EVENT_TYPES)[number];

export const COMMITMENT_STATES = [
  "pending",
  "interested",
  "tentative",
  "conditional",
  "accepted",
  "declined",
  "withdrawn",
] as const;
export type CommitmentState = (typeof COMMITMENT_STATES)[number];

/** Payload after sanitization: only allowlisted, typed, length-bounded fields. */
export interface PublicPayload {
  plan_id?: string;
  version?: number;
  group_size?: number;
  reason_category?: string;
  summary?: string;
  approval_state?: string;
  required_count?: number;
  accepted_count?: number;
  member_ref?: string;
  state?: CommitmentState;
  condition_category?: string;
  fairness_category?: string;
  failure_code?: string;
  changed_constraint_kind?: string;
  opportunity_id?: string;
  /** Optional correlation id echoing a judge request (proposed optional field, see integrator notes). */
  request_id?: string;
}

export interface AgentEvent {
  event_id: string;
  session_id: string;
  timestamp: string;
  type: PublicEventType;
  actor_ref: string;
  visibility: "group_safe";
  payload: PublicPayload;
  synthetic: boolean;
}

export type PlanStatus =
  | "proposed" // candidate_proposed / counteroffer_proposed, no readiness signal yet
  | "rejected"
  | "ready" // proposal_ready, approvals not yet requested
  | "awaiting_approval"
  | "confirmed"
  | "superseded" // a later version exists
  | "failed";

export interface PlanVersion {
  version: number;
  plan_id: string | null;
  status: PlanStatus;
  summary: string | null;
  reason_category: string | null;
  fairness_category: string | null;
  required_count: number | null;
  /** Backend-reported accepted count carried on proposal_confirmed. */
  reported_accepted_count: number | null;
  firstEventId: string;
}

export type Phase =
  | "idle"
  | "negotiating"
  | "awaiting_approval"
  | "confirmed"
  | "failed"
  | "completed";

export interface TimelineEntry {
  event: AgentEvent;
  /** Short plain-language explanation of what the UI transition means. */
  title: string;
  tone: "neutral" | "good" | "warn" | "bad" | "info";
  /** Set when the reducer refused to apply the event's effect. */
  ignoredReason?: string;
}

export type WarningCode =
  | "STALE_VERSION"
  | "CONFIRM_MISMATCH"
  | "CONFIRM_STALE"
  | "SNAPSHOT_MISMATCH"
  | "UNKNOWN_MEMBER_OVERFLOW"
  | "SESSION_MISMATCH";

export interface SyncWarning {
  code: WarningCode;
  message: string;
  eventId?: string;
}

export interface MissionView {
  sessionId: string | null;
  synthetic: boolean;
  phase: Phase;
  groupSize: number | null;
  /** Known member refs in first-seen order. */
  members: string[];
  versions: PlanVersion[];
  currentVersion: number | null;
  /** Commitment states for the *current* version only, per member. */
  commitments: Record<string, CommitmentState>;
  /** Per-version commitments, so invalidated approvals stay visible as history. */
  commitmentsByVersion: Record<number, Record<string, CommitmentState>>;
  acceptedCount: number;
  requiredCount: number | null;
  conflictCategory: string | null;
  failureCode: string | null;
  /** True when proposal_confirmed was received and passes consistency checks. */
  confirmed: boolean;
  timeline: TimelineEntry[];
  warnings: SyncWarning[];
  /** Whether any non-synthetic event exists. A false value enables judge controls. */
  allSynthetic: boolean;
}

/** Public snapshot shape assumed from A4 get_public_snapshot (see integrator notes). */
export interface PublicSnapshot {
  session_id: string;
  current_version: number | null;
  status: "negotiating" | "awaiting_approval" | "confirmed" | "failed" | "completed";
  accepted_count?: number;
  required_count?: number;
}
