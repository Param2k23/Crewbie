import { describeEvent } from "./describe";
import { sanitizeEvent, SanitizeCode } from "./sanitize";
import {
  AgentEvent,
  CommitmentState,
  MissionView,
  Phase,
  PlanStatus,
  PlanVersion,
  PublicSnapshot,
  SyncWarning,
  TimelineEntry,
} from "./types";

export interface RejectedRecord {
  code: SanitizeCode;
  detail: string;
}

export interface MissionState {
  /** Unique accepted events sorted by (timestamp, event_id). The view is a pure fold of this log. */
  log: AgentEvent[];
  rejected: RejectedRecord[];
  duplicates: number;
  snapshot: PublicSnapshot | null;
  view: MissionView;
}

export type MissionAction =
  | { type: "ingest"; raw: unknown }
  | { type: "ingest_many"; raw: unknown[] }
  | { type: "snapshot"; snapshot: PublicSnapshot | null }
  | { type: "reset" };

const cmp = (a: AgentEvent, b: AgentEvent) =>
  Date.parse(a.timestamp) - Date.parse(b.timestamp) || (a.event_id < b.event_id ? -1 : a.event_id > b.event_id ? 1 : 0);

export function initialState(): MissionState {
  return { log: [], rejected: [], duplicates: 0, snapshot: null, view: deriveView([], null) };
}

export function missionReducer(state: MissionState, action: MissionAction): MissionState {
  switch (action.type) {
    case "reset":
      return initialState();
    case "snapshot":
      return { ...state, snapshot: action.snapshot, view: deriveView(state.log, action.snapshot) };
    case "ingest":
      return ingest(state, [action.raw]);
    case "ingest_many":
      return ingest(state, action.raw);
  }
}

function ingest(state: MissionState, raws: unknown[]): MissionState {
  const seen = new Set(state.log.map((e) => e.event_id));
  const added: AgentEvent[] = [];
  const rejected = [...state.rejected];
  let duplicates = state.duplicates;
  for (const raw of raws) {
    const res = sanitizeEvent(raw);
    if (!res.ok) {
      rejected.push({ code: res.code, detail: res.detail });
      continue;
    }
    if (seen.has(res.event.event_id)) {
      duplicates++;
      continue;
    }
    seen.add(res.event.event_id);
    added.push(res.event);
  }
  if (added.length === 0) return { ...state, rejected, duplicates };
  const log = [...state.log, ...added].sort(cmp);
  return { ...state, log, rejected, duplicates, view: deriveView(log, state.snapshot) };
}

export function emptyView(): MissionView {
  return {
    sessionId: null,
    synthetic: true,
    phase: "idle",
    groupSize: null,
    members: [],
    versions: [],
    currentVersion: null,
    commitments: {},
    commitmentsByVersion: {},
    acceptedCount: 0,
    requiredCount: null,
    conflictCategory: null,
    failureCode: null,
    confirmed: false,
    timeline: [],
    warnings: [],
    allSynthetic: true,
  };
}

/** Deterministic fold: the same set of events always yields the same view, regardless of arrival order. */
export function deriveView(log: AgentEvent[], snapshot: PublicSnapshot | null): MissionView {
  const view = emptyView();
  const versions = new Map<number, PlanVersion>();
  const warnings: SyncWarning[] = [];
  const timeline: TimelineEntry[] = [];
  let phase: Phase = "idle";
  /** Members who withdrew stay withdrawn on later versions unless they respond again. */
  const withdrawnAt = new Map<string, number>();

  const ensure = (version: number, planId: string | null | undefined, eventId: string, status: PlanStatus): PlanVersion => {
    let pv = versions.get(version);
    if (!pv) {
      pv = {
        version,
        plan_id: planId ?? null,
        status,
        summary: null,
        reason_category: null,
        fairness_category: null,
        required_count: null,
        reported_accepted_count: null,
        firstEventId: eventId,
      };
      versions.set(version, pv);
    } else if (planId && !pv.plan_id) pv.plan_id = planId;
    return pv;
  };
  /** Newer version supersedes older ones that were still live. */
  const supersede = (newer: number) => {
    for (const pv of versions.values()) {
      if (pv.version < newer && (pv.status === "proposed" || pv.status === "ready" || pv.status === "awaiting_approval" || pv.status === "confirmed")) {
        pv.status = "superseded";
      }
    }
  };
  const current = (): PlanVersion | undefined => {
    let best: PlanVersion | undefined;
    for (const pv of versions.values()) if (!best || pv.version > best.version) best = pv;
    return best;
  };
  const observedAccepted = (version: number) =>
    Object.values(view.commitmentsByVersion[version] ?? {}).filter((s) => s === "accepted").length;

  for (const e of log) {
    if (view.sessionId === null) view.sessionId = e.session_id;
    const base = describeEvent(e);
    const entry: TimelineEntry = { event: e, ...base };
    timeline.push(entry);
    if (e.session_id !== view.sessionId) {
      entry.ignoredReason = "Event belongs to a different session";
      warnings.push({ code: "SESSION_MISMATCH", message: `Ignored event ${e.event_id} from another session`, eventId: e.event_id });
      continue;
    }
    view.allSynthetic &&= e.synthetic;
    const p = e.payload;
    const cur = current();
    const targetVersion = p.version ?? cur?.version;

    switch (e.type) {
      case "negotiation_started":
        phase = "negotiating";
        if (p.group_size) view.groupSize = p.group_size;
        break;
      case "candidate_proposed": {
        if (p.version === undefined) break;
        ensure(p.version, p.plan_id, e.event_id, "proposed");
        supersede(p.version);
        if (phase === "idle") phase = "negotiating";
        break;
      }
      case "counteroffer_proposed":
      case "proposal_revised": {
        if (p.version === undefined) break;
        const pv = ensure(p.version, p.plan_id, e.event_id, "proposed");
        if (p.summary) pv.summary = p.summary;
        supersede(p.version);
        phase = "negotiating";
        break;
      }
      case "proposal_rejected": {
        if (targetVersion === undefined) break;
        const pv = ensure(targetVersion, p.plan_id, e.event_id, "proposed");
        pv.status = "rejected";
        pv.reason_category = p.reason_category ?? null;
        phase = "negotiating";
        break;
      }
      case "fairness_evaluated": {
        if (targetVersion === undefined) break;
        const pv = versions.get(targetVersion);
        if (pv) {
          if (p.fairness_category) pv.fairness_category = p.fairness_category;
          if (p.summary) pv.summary = p.summary;
        }
        break;
      }
      case "proposal_ready": {
        if (targetVersion === undefined) break;
        const pv = ensure(targetVersion, p.plan_id, e.event_id, "ready");
        if (pv.status === "proposed") pv.status = "ready";
        supersede(targetVersion);
        break;
      }
      case "approval_requested": {
        if (targetVersion === undefined) break;
        const pv = ensure(targetVersion, p.plan_id, e.event_id, "awaiting_approval");
        if (pv.status === "proposed" || pv.status === "ready") pv.status = "awaiting_approval";
        if (p.required_count !== undefined) pv.required_count = p.required_count;
        supersede(targetVersion);
        phase = "awaiting_approval";
        break;
      }
      case "member_response_received": {
        const ref = p.member_ref;
        const state = p.state;
        const pv = p.version !== undefined ? versions.get(p.version) : undefined;
        if (!ref || !state || p.version === undefined) {
          entry.ignoredReason = "Response missing member, state or version";
          break;
        }
        if (!pv || pv.version !== current()?.version || pv.status === "rejected" || pv.status === "superseded" || pv.status === "failed") {
          entry.ignoredReason = `Stale: v${p.version} is not the live version, so this response does not count`;
          warnings.push({ code: "STALE_VERSION", message: `Response from ${ref} targeted v${p.version}, which is not current`, eventId: e.event_id });
          break;
        }
        (view.commitmentsByVersion[p.version] ??= {})[ref] = state;
        if (state === "withdrawn") withdrawnAt.set(ref, p.version);
        else withdrawnAt.delete(ref);
        if (!view.members.includes(ref)) view.members.push(ref);
        break;
      }
      case "proposal_confirmed": {
        const live = current();
        if (p.version === undefined || !live || p.version !== live.version) {
          entry.ignoredReason = "Confirmation targets a version that is not current";
          warnings.push({ code: "CONFIRM_STALE", message: `proposal_confirmed for v${p.version ?? "?"} ignored; current is v${live?.version ?? "none"}`, eventId: e.event_id });
          break;
        }
        if (live.status === "confirmed") {
          entry.ignoredReason = "Already confirmed; duplicate confirmation has no further effect";
          break;
        }
        const required = p.required_count ?? live.required_count;
        const seenAccepted = observedAccepted(live.version);
        if (live.status === "rejected" || live.status === "failed" || required === null || required === undefined || seenAccepted < required || (p.accepted_count !== undefined && p.accepted_count !== seenAccepted)) {
          entry.ignoredReason = "Confirmation disagrees with observed approvals; not shown as confirmed";
          entry.tone = "warn";
          live.reported_accepted_count = p.accepted_count ?? null;
          warnings.push({
            code: "CONFIRM_MISMATCH",
            message: `Backend reported v${live.version} confirmed (${p.accepted_count ?? "?"}/${required ?? "?"}) but ${seenAccepted} acceptances were observed in the stream. Waiting for consistent state.`,
            eventId: e.event_id,
          });
          break;
        }
        live.status = "confirmed";
        live.reported_accepted_count = p.accepted_count ?? seenAccepted;
        phase = "confirmed";
        break;
      }
      case "negotiation_failed": {
        phase = "failed";
        view.failureCode = p.failure_code ?? p.reason_category?.toUpperCase() ?? "NO_FEASIBLE_PLAN";
        const live = current();
        if (live && live.status !== "confirmed") live.status = "failed";
        break;
      }
      case "session_completed":
        if (phase !== "failed" && phase !== "confirmed") phase = "completed";
        break;
      default:
        break;
    }
  }

  const live = current();
  view.versions = [...versions.values()].sort((a, b) => a.version - b.version);
  view.currentVersion = live?.version ?? null;
  // Approvals only count while their version is live; a rejected/failed version keeps history in commitmentsByVersion.
  const countable = live && (live.status === "awaiting_approval" || live.status === "confirmed" || live.status === "ready" || live.status === "proposed");
  view.commitments = countable ? { ...(view.commitmentsByVersion[live.version] ?? {}) } : {};
  if (countable) for (const [ref, v] of withdrawnAt) if (v <= live.version && !view.commitments[ref]) view.commitments[ref] = "withdrawn";
  view.acceptedCount = Object.values(view.commitments).filter((s) => s === "accepted").length;
  view.requiredCount = live?.required_count ?? null;
  view.confirmed = live?.status === "confirmed";
  view.conflictCategory = live?.status === "rejected" ? live.reason_category : null;
  if (phase === "confirmed" && !view.confirmed) phase = "awaiting_approval";
  if (live && live.status === "rejected" && phase === "awaiting_approval") phase = "negotiating";
  view.phase = phase;
  view.timeline = timeline;
  view.synthetic = view.allSynthetic;
  if (view.groupSize !== null && view.members.length > view.groupSize) {
    warnings.push({ code: "UNKNOWN_MEMBER_OVERFLOW", message: `${view.members.length} members seen but group_size is ${view.groupSize}` });
  }
  warnings.push(...compareSnapshot(view, snapshot));
  view.warnings = warnings;
  return view;
}

/** Compare the event-derived view with a public snapshot; disagreement is surfaced, never smoothed over. */
export function compareSnapshot(view: MissionView, snap: PublicSnapshot | null): SyncWarning[] {
  if (!snap || (view.sessionId && snap.session_id !== view.sessionId)) return [];
  const out: SyncWarning[] = [];
  if (snap.current_version !== view.currentVersion) {
    out.push({ code: "SNAPSHOT_MISMATCH", message: `Snapshot says current version is ${snap.current_version ?? "none"}, event stream shows ${view.currentVersion ?? "none"}. Stream may be behind.` });
  }
  const derived = view.phase === "idle" ? "negotiating" : view.phase;
  if (snap.status !== derived) {
    out.push({ code: "SNAPSHOT_MISMATCH", message: `Snapshot status is "${snap.status}" but the event stream shows "${derived}". Not claiming either is correct.` });
  }
  return out;
}

export function commitmentOf(view: MissionView, ref: string): CommitmentState {
  return view.commitments[ref] ?? "pending";
}
