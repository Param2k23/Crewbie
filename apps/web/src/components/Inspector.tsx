"use client";
import { REASON_LABELS, labelFor, FAILURE_LABELS } from "@/lib/events/describe";
import type { MissionView } from "@/lib/events/types";
import { buildSceneModel, STATE_GLYPH, STATUS_TEXT } from "@/lib/scene/model";

export function StatusPanel({ view }: { view: MissionView }) {
  const live = view.versions.find((v) => v.version === view.currentVersion);
  const m = buildSceneModel(view);
  const big = view.confirmed
    ? { t: "Confirmed", cls: "pill-good", note: "Backend signalled confirmation and the stream shows every required acceptance." }
    : view.phase === "failed"
      ? { t: "No plan", cls: "pill-bad", note: labelFor(FAILURE_LABELS, view.failureCode) }
      : view.phase === "awaiting_approval"
        ? { t: "Pending approvals", cls: "pill-warn", note: "Not confirmed. Confirmation requires the backend to signal it after all required members accept this exact version." }
        : view.phase === "idle"
          ? { t: "Idle", cls: "", note: "No events yet." }
          : { t: "Negotiating", cls: "pill-info", note: "Agents are still searching for a plan that meets every hard constraint." };
  return (
    <section className="panel" aria-labelledby="status-h">
      <h2 id="status-h">Current state</h2>
      <div className="status-big"><span className={`pill ${big.cls}`} style={{ fontSize: "1rem" }}>{big.t}</span>{live && <span>Plan v{live.version}</span>}</div>
      <p style={{ margin: "6px 0 0", fontSize: "0.9rem", color: "var(--ink-2)" }}>{big.note}</p>
      {view.requiredCount !== null && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: "0.85rem" }}>Approvals for v{view.currentVersion}: <b>{view.acceptedCount} / {view.requiredCount}</b></div>
          <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={view.requiredCount} aria-valuenow={view.acceptedCount} aria-label="Accepted approvals">
            <i style={{ width: `${(view.acceptedCount / Math.max(view.requiredCount, 1)) * 100}%`, background: "var(--good)" }} />
          </div>
        </div>
      )}
      {m.conflict && <div className="alert" role="status"><b>Conflict:</b> {m.conflict.text}</div>}
      {view.warnings.map((w, i) => (
        <div className="alert warn" role="alert" key={i}><b>Sync warning ({w.code}):</b> {w.message}</div>
      ))}
      <ul className="members" aria-label="Agents">
        {m.nodes.map((n) => (
          <li key={n.slot} className={`s-${n.state === "unknown" ? "pending" : n.state}`}>
            <span className="glyph" aria-hidden><span>{STATE_GLYPH[n.state]}</span></span>
            <span><b>{n.label}</b> <span style={{ color: "var(--ink-2)" }}>{n.stateText}</span></span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function VersionsPanel({ view }: { view: MissionView }) {
  return (
    <section className="panel" aria-labelledby="ver-h">
      <h2 id="ver-h">Plan versions</h2>
      {view.versions.length === 0 ? <p style={{ margin: 0, color: "var(--ink-2)" }}>No proposals yet.</p> : (
        <ul className="vlist">
          {view.versions.map((v) => (
            <li key={v.version} aria-current={v.version === view.currentVersion ? "true" : undefined}>
              <b>v{v.version}</b>
              <span style={{ flex: 1 }}>
                {STATUS_TEXT[v.status]}
                {v.reason_category && <> · {labelFor(REASON_LABELS, v.reason_category)}</>}
                {v.summary && <div style={{ color: "var(--ink-2)", fontSize: "0.82rem" }}>{v.summary}</div>}
                {v.fairness_category && <div style={{ color: "var(--ink-2)", fontSize: "0.82rem" }}>Fairness: {v.fairness_category.replace(/_/g, " ")}</div>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function Legend() {
  return (
    <section className="panel" aria-labelledby="leg-h">
      <h2 id="leg-h">How to read the arena</h2>
      <ul className="legend">
        <li><b>Center:</b> the current plan version. Wireframe = proposed, shattered = rejected, translucent pulsing = awaiting approvals, solid green with locked ring = confirmed by the backend.</li>
        <li><b>Outer nodes:</b> one per agent. Solid green ✓ = accepted this version. Hollow … = no response. Ringed ? = conditional (not an acceptance). ✕ = declined.</li>
        <li><b>Lines:</b> drawn only once approval is requested. Dashed = waiting, solid = member answered.</li>
        <li><b>Red fracture:</b> a hard-constraint conflict. Who or what is deliberately not shown.</li>
        <li><b>Left spine:</b> every plan version; a new version resets approvals.</li>
      </ul>
    </section>
  );
}
