import { CONDITION_LABELS, labelFor, REASON_LABELS, FAILURE_LABELS } from "../events/describe";
import type { CommitmentState, MissionView, PlanStatus } from "../events/types";

/**
 * The single place that turns a MissionView into scene primitives. Both the 3D scene and the
 * 2D fallback read this, so they cannot disagree. Everything originates from event fields.
 */
export interface NodeModel {
  slot: number;
  ref: string | null;
  label: string;
  state: CommitmentState | "unknown";
  /** Stable text for assistive tech and 2D labels. */
  stateText: string;
  glyph: string;
}

export interface EdgeModel {
  slot: number;
  /** requested: approval asked but no response yet; responded: member answered on this version. */
  kind: "requested" | "responded";
  state: CommitmentState | "pending";
}

export interface VersionModel {
  version: number;
  status: PlanStatus;
  statusText: string;
  current: boolean;
}

export interface SceneModel {
  nodes: NodeModel[];
  edges: EdgeModel[];
  versions: VersionModel[];
  core: { status: PlanStatus | "none"; text: string; progress: number | null };
  conflict: { active: boolean; text: string } | null;
  summary: string;
}

export const STATE_GLYPH: Record<CommitmentState | "unknown", string> = {
  accepted: "✓",
  pending: "…",
  conditional: "?",
  interested: "~",
  tentative: "~",
  declined: "✕",
  withdrawn: "✕",
  unknown: "·",
};
export const STATE_TEXT: Record<CommitmentState | "unknown", string> = {
  accepted: "accepted this version",
  pending: "no response yet",
  conditional: "conditional (not an acceptance)",
  interested: "interested (not an acceptance)",
  tentative: "tentative (not an acceptance)",
  declined: "declined",
  withdrawn: "withdrew",
  unknown: "agent not yet identified",
};
export const STATUS_SHORT: Record<PlanStatus | "none", string> = {
  none: "none", proposed: "proposed", rejected: "rejected", ready: "ready", awaiting_approval: "awaiting approval",
  confirmed: "confirmed", superseded: "superseded", failed: "no plan",
};
export const STATUS_TEXT: Record<PlanStatus | "none", string> = {
  none: "No plan yet",
  proposed: "Proposed, not yet validated for approval",
  rejected: "Rejected",
  ready: "Ready; approvals not yet requested",
  awaiting_approval: "Awaiting approvals (pending, not confirmed)",
  confirmed: "Confirmed by backend",
  superseded: "Superseded by a newer version",
  failed: "Negotiation ended without a plan",
};

export function buildSceneModel(view: MissionView): SceneModel {
  const count = Math.max(view.groupSize ?? 0, view.members.length, view.members.length === 0 && view.sessionId ? 4 : 0);
  const live = view.versions.find((v) => v.version === view.currentVersion);
  const requested = live?.status === "awaiting_approval" || live?.status === "confirmed";

  const nodes: NodeModel[] = Array.from({ length: count }, (_, slot) => {
    const ref = view.members[slot] ?? null;
    const state: NodeModel["state"] = ref ? (view.commitments[ref] ?? "pending") : "unknown";
    return { slot, ref, label: ref ?? `Agent ${slot + 1}`, state, stateText: requested && !(ref && view.commitments[ref]) ? `${STATE_TEXT.pending}${ref ? "" : " (agent id not yet shown in events)"}` : STATE_TEXT[state], glyph: STATE_GLYPH[state] };
  });
  const edges: EdgeModel[] = requested
    ? nodes.map((n) => (n.ref && view.commitments[n.ref] ? { slot: n.slot, kind: "responded" as const, state: view.commitments[n.ref]! } : { slot: n.slot, kind: "requested" as const, state: "pending" as const }))
    : [];
  const versions = view.versions.map((v) => ({ version: v.version, status: v.status, statusText: STATUS_TEXT[v.status], current: v.version === view.currentVersion }));
  const core = {
    status: (live?.status ?? "none") as PlanStatus | "none",
    text: live ? `v${live.version}: ${STATUS_TEXT[live.status]}` : STATUS_TEXT.none,
    progress: live && live.required_count && (live.status === "awaiting_approval" || live.status === "confirmed") ? view.acceptedCount / live.required_count : null,
  };
  const conflict = view.conflictCategory
    ? { active: true, text: labelFor(REASON_LABELS, view.conflictCategory) }
    : view.failureCode
      ? { active: true, text: labelFor(FAILURE_LABELS, view.failureCode) }
      : null;

  let summary = "Waiting for events.";
  if (live) {
    summary = `Plan version ${live.version}: ${STATUS_TEXT[live.status].toLowerCase()}.`;
    if (live.required_count) summary += ` ${view.acceptedCount} of ${live.required_count} required members accepted.`;
    const cond = Object.values(view.commitments).filter((s) => s === "conditional").length;
    if (cond) summary += ` ${cond} conditional.`;
  }
  if (conflict) summary += ` ${conflict.text}.`;
  return { nodes, edges, versions, core, conflict, summary };
}

export function conditionNote(cat: string | undefined) {
  return cat ? labelFor(CONDITION_LABELS, cat) : "";
}

/** Ring layout shared by 2D and 3D (unit circle, slot 0 at the top). */
export function ringPosition(slot: number, count: number): [number, number] {
  const a = -Math.PI / 2 + (slot / Math.max(count, 1)) * Math.PI * 2;
  return [Math.cos(a), Math.sin(a)];
}
