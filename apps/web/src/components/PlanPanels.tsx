"use client";
import type { PlanPreview, PlanningIntent } from "@/lib/demo/types";
import type { MissionView } from "@/lib/events/types";
import { accessBadge, formatCampusTime } from "@/lib/opportunities/wording";
import { STATUS_SHORT } from "@/lib/scene/model";
import { OpportunityBadges } from "./CampusPulse";


/** Maps [a,b] onto a 0..100 scale of the horizon, clamped. */
function pct(t: string, h0: number, h1: number) {
  return Math.max(0, Math.min(100, ((Date.parse(t) - h0) / (h1 - h0)) * 100));
}

export function IntentPanel({ intent, view, label }: { intent: PlanningIntent | null; view: MissionView; label: string }) {
  return (
    <section className="panel" aria-labelledby="intent-h">
      <h2 id="intent-h">Planning intent</h2>
      {intent ? (
        <>
          <div className="status-big" style={{ fontSize: "1.05rem" }}>
            {intent.activity}
            <span className="pill pill-info">{intent.kind === "quick" ? "Quick plan" : "Weekend plan"}</span>
          </div>
          <dl className="kv">
            <dt>Horizon</dt><dd>{intent.horizonLabel}</dd>
            <dt>Window</dt><dd>{formatCampusTime(intent.horizonStart)} – {formatCampusTime(intent.horizonEnd)}</dd>
            <dt>Group</dt><dd>{intent.groupNote}</dd>
            <dt>Source</dt><dd>{label}</dd>
          </dl>
        </>
      ) : (
        <>
          <p style={{ margin: 0, color: "var(--ink-2)" }}>This source does not publish the planning intent. Only public events are shown.</p>
          <dl className="kv">
            <dt>Group</dt><dd>{view.groupSize ? `${view.groupSize} agents` : "not yet reported"}</dd>
            <dt>Source</dt><dd>{label}</dd>
          </dl>
        </>
      )}
    </section>
  );
}

export function ItineraryPanel({ intent, view, previews }: { intent: PlanningIntent | null; view: MissionView; previews: Record<number, PlanPreview> }) {
  const v = view.currentVersion;
  const live = view.versions.find((x) => x.version === v);
  const preview = v !== null ? previews[v] : undefined;
  const h0 = intent ? Date.parse(intent.horizonStart) : preview ? Date.parse(preview.start) : 0;
  const h1 = intent ? Date.parse(intent.horizonEnd) : preview ? Date.parse(preview.end) : 1;
  return (
    <section className="panel" aria-labelledby="itin-h">
      <h2 id="itin-h">Proposed itinerary{live ? ` · v${live.version}` : ""}</h2>
      {!live ? (
        <p style={{ margin: 0, color: "var(--ink-2)" }}>No proposal yet.</p>
      ) : (
        <>
          <p style={{ margin: "0 0 6px" }}>
            <span className={`pill ${live.status === "confirmed" ? "pill-good" : live.status === "rejected" || live.status === "failed" ? "pill-bad" : "pill-warn"}`}>{STATUS_SHORT[live.status]}</span>{" "}
            {live.summary && <span style={{ fontSize: "0.9rem" }}>{live.summary}</span>}
          </p>
          {preview ? (
            <>
              <div style={{ fontWeight: 700 }}>{preview.title}</div>
              <div className="tl-meta" style={{ marginBottom: 6 }}>{formatCampusTime(preview.start)} – {formatCampusTime(preview.end)} Arizona time</div>
              <ol className="gantt" aria-label="Itinerary on the planning horizon" style={{ listStyle: "none", padding: 0, margin: 0 }}>
                {preview.activities.map((a) => (
                  <li key={a.label} className="gantt-row">
                    <span className="gantt-label">{a.label}</span>
                    <span className="gantt-track" aria-hidden>
                      <i style={{ left: `${pct(a.start, h0, h1)}%`, width: `${Math.max(2, pct(a.end, h0, h1) - pct(a.start, h0, h1))}%` }} />
                    </span>
                    <span className="gantt-time">{formatCampusTime(a.start, false)}</span>
                  </li>
                ))}
              </ol>
              <p className="cta-note" style={{ marginTop: 6 }}>{preview.budgetNote}{preview.notes ? ` · ${preview.notes}` : ""}</p>
              <p className="cta-note">Public itinerary preview. Estimates are demonstration figures; per-member costs and private constraints are never shown.</p>
            </>
          ) : (
            <p className="cta-note">This stream did not supply an itinerary preview for v{live.version}. A public plan snapshot from the negotiation service is needed to show it.</p>
          )}
        </>
      )}
    </section>
  );
}

export function OptionsPanel({ intent }: { intent: PlanningIntent | null }) {
  if (!intent) return null;
  return (
    <section className="panel" aria-labelledby="opt-h">
      <h2 id="opt-h">Options considered</h2>
      <ul className="vlist">
        {intent.options.map((o) => (
          <li key={o.opportunity_id} style={{ display: "block" }}>
            <b>{o.title}</b>
            <div className="badges" style={{ marginTop: 4 }}><OpportunityBadges o={o} /></div>
            <div className="tl-meta" style={{ marginTop: 4 }}>{accessBadge(o)} · source: {o.source_url} (fixture link) · checked {formatCampusTime(o.checked_at)}</div>
          </li>
        ))}
      </ul>
    </section>
  );
}
