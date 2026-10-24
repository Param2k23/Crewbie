"use client";
import { useState } from "react";
import type { JudgeOptions } from "@/lib/adapters";
import type { ConstraintKind, JudgeAdapter } from "@/lib/adapters/judge";
import type { JudgeUiState } from "@/lib/useMissionControl";

interface Props {
  judge: JudgeAdapter | null;
  options: JudgeOptions;
  blockedReason: string | null;
  state: JudgeUiState;
  reflected: boolean;
  /** Members known from events (fallback when the adapter does not list any). */
  members: string[];
  onSubmit: (c: { member_ref: string; kind: ConstraintKind; value: number | string }) => void;
}

const KIND_LABEL: Record<ConstraintKind, string> = {
  hard_budget: "Change one student's hard budget",
  block_window: "Block an available time window",
  withdraw: "Withdraw one participant",
};

/**
 * Sends a constraint-change *request*. The panel shows the request lifecycle (sent, answered,
 * reflected in the stream) but never changes plan state itself.
 */
export function JudgePanel({ judge, options, blockedReason, state, reflected, members, onSubmit }: Props) {
  const choices = options.members.length ? [...options.members] : members;
  const [member, setMember] = useState("");
  const [kind, setKind] = useState<ConstraintKind>("hard_budget");
  const [dollars, setDollars] = useState("45");
  const [preset, setPreset] = useState("");
  const [ack, setAck] = useState(false);
  const target = member || choices[0] || "";
  const windowId = preset || options.windows[0]?.id || "";
  const cents = Math.round(Number(dollars) * 100);
  const valid = kind === "withdraw" || (kind === "block_window" ? windowId !== "" : Number.isFinite(cents) && cents > 0 && cents < 1_000_000);
  const disabled = blockedReason !== null || !ack || !valid || state.phase === "pending" || !target;
  const off = blockedReason !== null;

  return (
    <section className="panel judge" aria-labelledby="judge-h">
      <h2 id="judge-h">Judge intervention</h2>
      {judge && (
        <p style={{ margin: "0 0 6px", fontSize: "0.85rem" }}>
          <span className={`pill ${judge.simulated ? "pill-warn" : "pill-info"}`}>{judge.simulated ? "SIMULATOR" : "BACKEND"}</span> {judge.label}
        </p>
      )}
      {blockedReason && <div className="alert warn" role="status">{blockedReason}</div>}
      {judge && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (disabled) return;
            onSubmit({ member_ref: target, kind, value: kind === "hard_budget" ? cents : kind === "block_window" ? windowId : "withdraw" });
          }}
        >
          <label>
            Change
            <select value={kind} onChange={(e) => setKind(e.target.value as ConstraintKind)} disabled={off}>
              {(Object.keys(KIND_LABEL) as ConstraintKind[]).map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}
            </select>
          </label>
          <label>
            Synthetic profile
            <select value={target} onChange={(e) => setMember(e.target.value)} disabled={off}>
              {choices.map((m) => <option key={m}>{m}</option>)}
            </select>
          </label>
          {kind === "hard_budget" && (
            <label>
              New hard cap (USD, sent to the engine; not shown in the feed)
              <input type="number" min={1} step={1} value={dollars} onChange={(e) => setDollars(e.target.value)} disabled={off} />
            </label>
          )}
          {kind === "block_window" && (
            <label>
              Window
              <select value={windowId} onChange={(e) => setPreset(e.target.value)} disabled={off}>
                {options.windows.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
              </select>
            </label>
          )}
          <label className="check">
            <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} disabled={off} />
            <span>This targets a synthetic sandbox profile, not a real student.</span>
          </label>
          <div style={{ marginTop: 10 }}>
            <button className="btn btn-primary" type="submit" disabled={disabled}>
              {state.phase === "pending" ? "Request sent…" : "Send change request"}
            </button>
          </div>
        </form>
      )}
      <div className="judge-status" role="status" aria-live="polite">
        {state.phase === "pending" && <>Waiting for the server to answer. Nothing has changed yet.</>}
        {state.phase === "answered" && (
          <>
            <span className={`pill pill-${state.response.status === "accepted" ? "info" : "bad"}`}>Server: {state.response.status}</span> {state.response.message}
            {state.response.status === "accepted" && (
              <div style={{ marginTop: 4 }}>
                {reflected ? <span className="pill pill-good">Reflected in the event stream</span> : <span className="pill pill-warn">Not yet reflected in the event stream</span>}
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
