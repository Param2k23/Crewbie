"use client";
import dynamic from "next/dynamic";
import { Component, ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { MissionAdapter } from "@/lib/adapters";
import type { AgentEvent, MissionView } from "@/lib/events/types";
import { useMissionControl } from "@/lib/useMissionControl";
import { ArenaFallback } from "./ArenaFallback";
import type { ArenaSceneHandle } from "./ArenaScene";
import { JudgePanel } from "./JudgePanel";
import { IntentPanel, ItineraryPanel, OptionsPanel } from "./PlanPanels";
import { Legend, StatusPanel, VersionsPanel } from "./Inspector";
import { buildSceneModel } from "@/lib/scene/model";

const ArenaScene = dynamic(() => import("./ArenaScene"), { ssr: false, loading: () => <div className="fallback" role="status">Loading 3D scene…</div> });

class SceneBoundary extends Component<{ children: ReactNode; onError: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch() { this.props.onError(); }
  render() { return this.state.failed ? null : this.props.children; }
}

function webglAvailable(): boolean {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

function usePrefersReducedMotion() {
  const [r, setR] = useState(false);
  useEffect(() => {
    const q = window.matchMedia("(prefers-reduced-motion: reduce)");
    setR(q.matches);
    const f = () => setR(q.matches);
    q.addEventListener("change", f);
    return () => q.removeEventListener("change", f);
  }, []);
  return r;
}

/** What to look at next, derived from the event-derived view (never from a timer). */
export function guideFor(view: MissionView): string {
  const live = view.versions.find((v) => v.version === view.currentVersion);
  if (!live) return "Press Play or Step. Each step reveals one recorded event.";
  if (view.phase === "failed") return "The engine reported no feasible plan. That is a valid, honest outcome: nothing is confirmed and nobody is committed.";
  if (view.confirmed) return "Confirmed: every required member accepted this exact version and the backend signalled it.";
  if (live.status === "rejected") return "A proposal broke a hard constraint and was rejected. The red fracture shows a conflict; the private reason stays private.";
  if (live.status === "awaiting_approval") {
    const cond = Object.values(view.commitments).filter((s) => s === "conditional").length;
    return `Approvals are pending. ${cond ? "A conditional answer is not an acceptance. " : ""}Try the judge panel: change one hard constraint and watch the plan version change.`;
  }
  if (view.versions.some((v) => v.status === "rejected")) return "The agents are counter-proposing after the rejection.";
  return "Agents are negotiating.";
}

export function MissionControl({ adapter, initialView }: { adapter: MissionAdapter; initialView?: "2d" | "3d" }) {
  const { state, view, status, malformed, replay, judgeState, submitJudge, reflectedInStream, judgeBlockedReason } = useMissionControl(adapter);
  const reduced = usePrefersReducedMotion();
  const [mode3d, setMode3d] = useState<boolean>(initialView !== "2d");
  const [webgl, setWebgl] = useState<boolean | null>(null);
  const [sceneFailed, setSceneFailed] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const handle = useRef<ArenaSceneHandle | null>(null);

  useEffect(() => {
    setWebgl(webglAvailable());
    try {
      if (initialView === undefined && localStorage.getItem("crewbie.view") === "2d") setMode3d(false);
    } catch { /* storage unavailable: ignore */ }
  }, [initialView]);

  const toggleView = useCallback(() => {
    setMode3d((m) => {
      try { localStorage.setItem("crewbie.view", m ? "2d" : "3d"); } catch { /* ignore */ }
      return !m;
    });
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.closest("input,select,textarea,button,a,[role=tab]") || e.metaKey || e.ctrlKey || e.altKey) return;
      const r = adapter.replay;
      if (e.key === " " && r) { e.preventDefault(); r.getSnapshot().playing ? r.pause() : r.play(); }
      else if (e.key === "ArrowRight" && r) r.step();
      else if (e.key.toLowerCase() === "r" && r) r.reset();
      else if (e.key.toLowerCase() === "v") toggleView();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [adapter, toggleView]);

  const use3d = mode3d && webgl === true && !sceneFailed;
  const model = useMemo(() => buildSceneModel(view), [view]);
  const lastTitle = view.timeline.at(-1)?.title ?? "";
  const selectedEntry = view.timeline.find((t) => t.event.event_id === selected) ?? null;

  return (
    <div className="mc-body" data-testid="mission-control">
      {replay.holdMessage && <div className="hold" role="status"><b>Waiting.</b> {replay.holdMessage}</div>}
      <ConnectionBanner kind={adapter.kind} status={status} empty={view.timeline.length === 0} />
      <div className="controls" role="toolbar" aria-label="Playback controls">
        {adapter.replay ? (
          <>
            <button className="btn btn-primary" onClick={() => (replay.playing ? adapter.replay!.pause() : adapter.replay!.play())} disabled={replay.cursor >= replay.total && !replay.playing}>
              {replay.playing ? "Pause" : replay.cursor === 0 ? "Play" : "Resume"} <kbd className="sr-only">Space</kbd>
            </button>
            <button className="btn" onClick={() => adapter.replay!.step()} disabled={replay.cursor >= replay.total}>Step →</button>
            <button className="btn" onClick={() => adapter.replay!.reset()}>Reset</button>
            <label style={{ fontSize: "0.85rem", display: "flex", gap: 6, alignItems: "center" }}>
              Speed
              <select value={replay.speed} onChange={(e) => adapter.replay!.setSpeed(Number(e.target.value))} style={{ font: "inherit" }}>
                {[0.5, 1, 2, 4].map((s) => <option key={s} value={s}>{s}×</option>)}
              </select>
            </label>
            <div className="progress" role="progressbar" aria-label="Replay position" aria-valuemin={0} aria-valuemax={replay.total} aria-valuenow={replay.cursor}>
              <i style={{ width: `${replay.total ? (replay.cursor / replay.total) * 100 : 0}%` }} />
            </div>
            <span style={{ fontSize: "0.85rem", color: "var(--ink-2)" }}>{replay.cursor}/{replay.total} events</span>
          </>
        ) : (
          <span className={`pill ${status === "open" ? "pill-good" : status === "reconnecting" || status === "connecting" ? "pill-warn" : "pill-bad"}`}>Stream: {status}</span>
        )}
        {adapter.actions.map((a) => (
          <button key={a.id} className="btn" title={a.hint} onClick={a.run} disabled={view.phase === "idle"}>{a.label}</button>
        ))}
        <span className="grow" />
        <button className="btn" onClick={toggleView} aria-pressed={!use3d}>{use3d ? "Switch to 2D view" : "Switch to 3D view"}</button>
        <span style={{ fontSize: "0.78rem", color: "var(--ink-2)" }} aria-hidden>Keys: Space play · → step · R reset · V 2D/3D</span>
      </div>

      <div className="mc-grid">
        <div>
          <div className="stage" data-view={use3d ? "3d" : "2d"}>
            <div className="stage-badge">
              <span className={`pill ${view.synthetic ? "pill-synth" : "pill-info"}`}>{view.sessionId ? (view.synthetic ? "SYNTHETIC DATA" : "LIVE SESSION") : "NO SESSION"}</span>
              <span className="pill">{adapter.label}</span>
              {adapter.kind === "demo" && <span className="pill pill-warn">NOT THE REAL ENGINE</span>}
            </div>
            {use3d && (
              <div className="stage-tools">
                <button className="btn btn-sm" onClick={() => handle.current?.rotate(-30)} aria-label="Rotate view left">◀</button>
                <button className="btn btn-sm" onClick={() => handle.current?.reset()}>Reset camera</button>
                <button className="btn btn-sm" onClick={() => handle.current?.rotate(30)} aria-label="Rotate view right">▶</button>
              </div>
            )}
            {use3d ? (
              <SceneBoundary onError={() => setSceneFailed(true)}>
                <ArenaScene view={view} reduced={reduced} handleRef={handle} />
              </SceneBoundary>
            ) : (
              <ArenaFallback view={view} />
            )}
            <div className="stage-caption" aria-hidden>{model.summary}</div>
          </div>
          {!use3d && webgl === false && <p className="cta-note" role="status">3D is unavailable in this browser (WebGL not supported). The 2D view shows the same state.</p>}
          {sceneFailed && <p className="cta-note" role="alert">The 3D scene failed to start; showing the 2D view with the same state.</p>}
          <p className="guide" style={{ marginTop: 12 }}>{guideFor(view)}</p>
          <div className="sr-only" aria-live="polite" role="log">{lastTitle}</div>
          <div className="two">
            <IntentPanel intent={adapter.intent} view={view} label={adapter.label} />
            <ItineraryPanel intent={adapter.intent} view={view} previews={adapter.previews()} />
          </div>
          <JudgePanel judge={adapter.judge} options={adapter.judgeOptions} blockedReason={judgeBlockedReason} state={judgeState} reflected={reflectedInStream} members={view.members} onSubmit={submitJudge} />
        </div>

        <aside aria-label="Inspector">
          <StatusPanel view={view} />
          <VersionsPanel view={view} />
          <section className="panel" aria-labelledby="tl-h">
            <h2 id="tl-h">Event timeline</h2>
            {view.timeline.length === 0 ? <p style={{ margin: 0, color: "var(--ink-2)" }}>No events yet.</p> : (
              <ol className="timeline" aria-label="Events in order">
                {[...view.timeline].reverse().map((t) => (
                  <li key={t.event.event_id} role="button" tabIndex={0} aria-current={selected === t.event.event_id ? "true" : undefined}
                    onClick={() => setSelected(t.event.event_id)} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), setSelected(t.event.event_id))}>
                    <span className={`dot ${t.tone}`} aria-hidden />
                    <span>
                      {t.title}
                      <div className="tl-meta">{t.event.type} · {t.event.event_id}{t.event.synthetic ? " · synthetic" : ""}</div>
                      {t.ignoredReason && <div className="tl-ignored">Not applied: {t.ignoredReason}</div>}
                    </span>
                  </li>
                ))}
              </ol>
            )}
            {selectedEntry && <EventDetail e={selectedEntry.event} />}
            {(state.rejected.length > 0 || malformed > 0 || state.duplicates > 0) && (
              <p className="cta-note" role="status">
                Safety filter: {state.rejected.length} blocked event(s){state.rejected.length ? ` (${[...new Set(state.rejected.map((r) => r.code))].join(", ")})` : ""}, {malformed} malformed frame(s), {state.duplicates} duplicate(s) ignored. Blocked contents are never displayed.
              </p>
            )}
          </section>
          <OptionsPanel intent={adapter.intent} />
          <Legend />
        </aside>
      </div>
    </div>
  );
}

function ConnectionBanner({ kind, status, empty }: { kind: MissionAdapter["kind"]; status: string; empty: boolean }) {
  if (kind !== "network") return null;
  if (status === "connecting") return <div className="banner" role="status">Connecting to the event stream…</div>;
  if (status === "reconnecting") return <div className="banner warn" role="status">Connection lost. Reconnecting; already received events are kept and duplicates are ignored.</div>;
  if (status === "closed" || status === "error") return <div className="banner bad" role="alert">The event stream is closed. Check the API URL and that the server allows this origin, then Connect again.</div>;
  if (status === "open" && empty) return <div className="banner" role="status">Connected. Waiting for the first event for this session. Nothing is shown until the backend emits it.</div>;
  return null;
}

function EventDetail({ e }: { e: AgentEvent }) {
  return (
    <dl className="kv" aria-label="Selected event fields">
      <dt>event_id</dt><dd>{e.event_id}</dd>
      <dt>type</dt><dd>{e.type}</dd>
      <dt>actor_ref</dt><dd>{e.actor_ref}</dd>
      <dt>timestamp</dt><dd>{e.timestamp}</dd>
      {Object.entries(e.payload).map(([k, v]) => (<><dt key={`k${k}`}>{k}</dt><dd key={`v${k}`}>{String(v)}</dd></>))}
    </dl>
  );
}
