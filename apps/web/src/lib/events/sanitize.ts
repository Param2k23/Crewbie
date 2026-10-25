import {
  AgentEvent,
  COMMITMENT_STATES,
  CommitmentState,
  PUBLIC_EVENT_TYPES,
  PublicEventType,
  PublicPayload,
} from "./types";

export type SanitizeResult =
  | { ok: true; event: AgentEvent }
  | { ok: false; code: SanitizeCode; detail: string };

export type SanitizeCode =
  | "NOT_OBJECT"
  | "BAD_FIELD"
  | "BAD_TYPE"
  | "NOT_GROUP_SAFE"
  | "FORBIDDEN_KEY"
  | "BAD_PAYLOAD";

/** Any key matching this anywhere in the payload means a producer leak: reject the whole event. */
const FORBIDDEN_KEY = /(budget|cap_cents|cost|price|calendar|blocked|window|prompt|reasoning|chain_of_thought|token|secret|password|diet|private|internal|hidden|raw_|llm)/i;

const REF = /^[A-Za-z0-9_.:-]{1,64}$/;
const SLUG = /^[a-z0-9_]{1,48}$/;
const MAX_TEXT = 280;

/** Per-field validators. Unknown payload keys are dropped, never forwarded. */
const FIELD_RULES: Record<keyof PublicPayload, (v: unknown) => unknown | undefined> = {
  plan_id: (v) => (typeof v === "string" && REF.test(v) ? v : undefined),
  request_id: (v) => (typeof v === "string" && REF.test(v) ? v : undefined),
  opportunity_id: (v) => (typeof v === "string" && REF.test(v) ? v : undefined),
  member_ref: (v) => (typeof v === "string" && REF.test(v) ? v : undefined),
  version: (v) => (Number.isInteger(v) && (v as number) >= 0 && (v as number) < 10_000 ? v : undefined),
  group_size: (v) => (Number.isInteger(v) && (v as number) >= 1 && (v as number) <= 12 ? v : undefined),
  required_count: (v) => (Number.isInteger(v) && (v as number) >= 0 && (v as number) <= 12 ? v : undefined),
  accepted_count: (v) => (Number.isInteger(v) && (v as number) >= 0 && (v as number) <= 12 ? v : undefined),
  reason_category: (v) => (typeof v === "string" && SLUG.test(v) ? v : undefined),
  condition_category: (v) => (typeof v === "string" && SLUG.test(v) ? v : undefined),
  fairness_category: (v) => (typeof v === "string" && SLUG.test(v) ? v : undefined),
  failure_code: (v) => (typeof v === "string" && /^[A-Z_]{1,48}$/.test(v) ? v : undefined),
  changed_constraint_kind: (v) => (typeof v === "string" && SLUG.test(v) ? v : undefined),
  approval_state: (v) => (typeof v === "string" && SLUG.test(v) ? v : undefined),
  state: (v) => (typeof v === "string" && (COMMITMENT_STATES as readonly string[]).includes(v) ? v : undefined),
  summary: (v) => (typeof v === "string" ? cleanText(v) : undefined),
};

/** Free text is rendered as React text only; we also strip markup characters and control chars. */
export function cleanText(s: string): string | undefined {
  // eslint-disable-next-line no-control-regex
  const t = s.replace(/[\u0000-\u001f\u007f<>]/g, " ").replace(/\s+/g, " ").trim().slice(0, MAX_TEXT);
  return t.length ? t : undefined;
}

function findForbiddenKey(value: unknown, depth = 0): string | null {
  if (depth > 6 || value === null || typeof value !== "object") return null;
  for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
    if (FORBIDDEN_KEY.test(k)) return k;
    const nested = findForbiddenKey(v, depth + 1);
    if (nested) return nested;
  }
  return null;
}

const fail = (code: SanitizeCode, detail: string): SanitizeResult => ({ ok: false, code, detail });

export function sanitizeEvent(raw: unknown): SanitizeResult {
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) return fail("NOT_OBJECT", "event is not an object");
  const r = raw as Record<string, unknown>;

  // Visibility gate comes first so private diagnostics are never even inspected further.
  if (r.visibility !== "group_safe") return fail("NOT_GROUP_SAFE", `visibility=${String(r.visibility).slice(0, 24)}`);

  for (const f of ["event_id", "session_id", "actor_ref"] as const) {
    if (typeof r[f] !== "string" || !REF.test(r[f] as string)) return fail("BAD_FIELD", `invalid ${f}`);
  }
  if (typeof r.timestamp !== "string" || !/(Z|[+-]\d{2}:\d{2})$/.test(r.timestamp) || Number.isNaN(Date.parse(r.timestamp))) {
    return fail("BAD_FIELD", "timestamp must be ISO 8601 with timezone");
  }
  if (typeof r.type !== "string" || !(PUBLIC_EVENT_TYPES as readonly string[]).includes(r.type)) {
    return fail("BAD_TYPE", `unknown type ${String(r.type).slice(0, 32)}`);
  }
  if (r.payload === null || typeof r.payload !== "object" || Array.isArray(r.payload)) {
    return fail("BAD_PAYLOAD", "payload must be an object");
  }
  const leak = findForbiddenKey(r.payload);
  if (leak) return fail("FORBIDDEN_KEY", `payload contains disallowed key "${leak.slice(0, 32)}"`);

  const payload: PublicPayload = {};
  for (const [key, rule] of Object.entries(FIELD_RULES)) {
    if (!(key in (r.payload as object))) continue;
    const cleaned = rule((r.payload as Record<string, unknown>)[key]);
    if (cleaned === undefined) return fail("BAD_PAYLOAD", `invalid payload.${key}`);
    (payload as Record<string, unknown>)[key] = cleaned as string | number | CommitmentState;
  }

  return {
    ok: true,
    event: {
      event_id: r.event_id as string,
      session_id: r.session_id as string,
      timestamp: r.timestamp,
      type: r.type as PublicEventType,
      actor_ref: r.actor_ref as string,
      visibility: "group_safe",
      payload,
      synthetic: r.synthetic === true,
    },
  };
}
