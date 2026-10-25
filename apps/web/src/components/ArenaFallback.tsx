"use client";
import { useMemo } from "react";
import type { MissionView } from "@/lib/events/types";
import { buildSceneModel, ringPosition, STATUS_SHORT } from "@/lib/scene/model";

const C = { accepted: "var(--good)", pending: "var(--warn)", conditional: "#c4b5fd", interested: "var(--info)", tentative: "var(--info)", declined: "var(--bad)", withdrawn: "var(--bad)", unknown: "var(--ink-2)" } as const;
const CORE: Record<string, string> = { none: "var(--ink-2)", proposed: "var(--info)", rejected: "var(--bad)", ready: "var(--warn)", awaiting_approval: "var(--warn)", confirmed: "var(--good)", superseded: "var(--ink-2)", failed: "var(--ink-2)" };

/** Static SVG of the same SceneModel as the 3D view. No WebGL, no animation. */
export function ArenaFallback({ view }: { view: MissionView }) {
  const m = useMemo(() => buildSceneModel(view), [view]);
  const n = m.nodes.length;
  const S = 150;
  return (
    <div className="fallback" data-testid="arena-2d">
      <svg viewBox="-260 -190 520 380" role="img" aria-label={`2D negotiation view. ${m.summary}`}>
        <circle r={S} fill="none" stroke="var(--line)" strokeWidth={1} />
        {m.edges.map((e) => {
          const [x, y] = ringPosition(e.slot, n);
          return <line key={e.slot} x1={0} y1={0} x2={x * S} y2={y * S} stroke={C[e.state]} strokeWidth={e.kind === "responded" ? 3 : 1.5} strokeDasharray={e.kind === "requested" || e.state === "conditional" ? "6 5" : undefined} />;
        })}
        {m.core.progress !== null && (
          <circle r={44} fill="none" stroke="var(--good)" strokeWidth={5} strokeDasharray={`${Math.min(1, m.core.progress) * 276} 276`} transform="rotate(-90)" />
        )}
        <g>
          {m.core.status === "rejected" ? (
            <path d="M-26 -18 L-6 -8 L-10 -30 M26 -18 L8 -4 L28 4 M-22 22 L-4 6 L6 30" stroke={CORE.rejected} strokeWidth={4} fill="none" strokeLinecap="round" />
          ) : (
            <circle r={26} fill={m.core.status === "confirmed" ? CORE.confirmed : "none"} stroke={CORE[m.core.status]} strokeWidth={4} strokeDasharray={m.core.status === "proposed" ? "5 4" : m.core.status === "awaiting_approval" || m.core.status === "ready" ? "2 4" : undefined} />
          )}
          <text y={60} textAnchor="middle" style={{ fill: CORE[m.core.status], fontWeight: 700 }}>{m.core.text}</text>
        </g>
        {m.nodes.map((nd) => {
          const [x, y] = ringPosition(nd.slot, n);
          const cx = x * S, cy = y * S, col = C[nd.state];
          return (
            <g key={nd.slot} transform={`translate(${cx} ${cy})`}>
              {nd.state === "declined" || nd.state === "withdrawn" ? <rect x={-14} y={-14} width={28} height={28} fill={col} /> : <circle r={15} fill={nd.state === "accepted" ? col : "var(--surface)"} stroke={col} strokeWidth={3} strokeDasharray={nd.state === "pending" || nd.state === "unknown" ? "4 3" : undefined} />}
              <text textAnchor="middle" dy={5} style={{ fill: nd.state === "accepted" || nd.state === "declined" || nd.state === "withdrawn" ? "#04130a" : col, fontWeight: 800 }}>{nd.glyph}</text>
              <text textAnchor="middle" y={32}>{nd.label}</text>
              <text textAnchor="middle" y={45} className="sub">{nd.state === "unknown" ? "unidentified" : nd.state}</text>
            </g>
          );
        })}
        <g transform="translate(-250 -170)">
          {m.versions.map((v, i) => (
            <text key={v.version} y={i * 16} style={{ fill: CORE[v.status], fontWeight: v.current ? 800 : 400 }}>v{v.version} · {STATUS_SHORT[v.status]}</text>
          ))}
        </g>
      </svg>
      {m.conflict && <div className="alert" role="status"><b>Conflict:</b> {m.conflict.text}</div>}
    </div>
  );
}
