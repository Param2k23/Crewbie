/**
 * Judge intervention contract. The UI only ever *submits a request*. It never writes events
 * or flips plan state; any consequence must arrive afterwards as AgentEvents from the backend.
 */
export type ConstraintKind = "hard_budget" | "availability";

export interface JudgeRequest {
  request_id: string;
  session_id: string;
  changed_constraint_ref: {
    member_ref: string;
    kind: ConstraintKind;
    /** hard_budget: new cap in integer US cents. availability: opaque preset id. */
    value: number | string;
  };
  /** The judge explicitly confirmed this targets a synthetic sandbox profile. */
  synthetic_confirmed: true;
}

export interface JudgeResponse {
  request_id: string;
  status: "accepted" | "rejected" | "unavailable";
  /** Short public-safe message from the server. */
  message: string;
}

export interface JudgeAdapter {
  readonly label: string;
  /** True when this adapter is a local stand-in rather than the real negotiation backend. */
  readonly simulated: boolean;
  submit(req: JudgeRequest): Promise<JudgeResponse>;
}

export const AVAILABILITY_PRESETS = [
  { id: "blocks_current_day", label: "Member becomes unavailable on the planned day" },
  { id: "blocks_all_days", label: "Member becomes unavailable on every candidate day" },
] as const;

export function newRequestId(prefix = "judge"): string {
  const rnd = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID().slice(0, 8) : Math.random().toString(36).slice(2, 10);
  return `${prefix}_${rnd}`;
}

/** HTTP adapter for the future A4 route. Failures are reported as-is, never converted to success. */
export class HttpJudgeAdapter implements JudgeAdapter {
  readonly label: string;
  readonly simulated = false;
  constructor(private readonly baseUrl: string, private readonly fetchImpl: typeof fetch = (...a) => fetch(...a)) {
    this.label = `Backend at ${baseUrl}`;
  }
  async submit(req: JudgeRequest): Promise<JudgeResponse> {
    try {
      const res = await this.fetchImpl(`${this.baseUrl}/v1/sessions/${encodeURIComponent(req.session_id)}/constraint-changes`, {
        method: "POST",
        headers: { "content-type": "application/json", "idempotency-key": req.request_id },
        body: JSON.stringify(req),
      });
      if (res.status === 404 || res.status === 501) {
        return { request_id: req.request_id, status: "unavailable", message: `Backend has no constraint-change route yet (HTTP ${res.status}). Nothing was changed.` };
      }
      if (!res.ok) {
        return { request_id: req.request_id, status: "rejected", message: `Backend refused the request (HTTP ${res.status}). Nothing was changed.` };
      }
      return { request_id: req.request_id, status: "accepted", message: "Backend accepted the request. Waiting for events from the negotiation engine." };
    } catch {
      return { request_id: req.request_id, status: "unavailable", message: "Could not reach the backend. Nothing was changed." };
    }
  }
}
