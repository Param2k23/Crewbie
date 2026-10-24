"use client";
import { useMemo, useState } from "react";
import { DemoAdapter, FixtureAdapter, MissionAdapter, NetworkAdapter } from "@/lib/adapters";
import { MissionControl } from "./MissionControl";

type Mode = "demo" | "fixture" | "live";
const ENV_API = process.env.NEXT_PUBLIC_CREWBIE_API_URL ?? "";

const DESCRIPTIONS: Record<Mode, string> = {
  demo: "Explicit demo mode. A scripted four-agent trip with a failed proposal, mixed approvals and a judge-triggered change. Responses come from a labeled local simulator.",
  fixture: "Canonical agent_events.json replayed unchanged. Read-only.",
  live: "Read-only SSE from the realtime service or integrated backend. Judge requests go to the backend and are reported as it answers.",
};

export function MissionControlApp({ initialMode = "demo", initialView }: { initialMode?: Mode; initialView?: "2d" | "3d" }) {
  const [mode, setMode] = useState<Mode>(initialMode);
  const [api, setApi] = useState(ENV_API || "http://127.0.0.1:8787");
  const [session, setSession] = useState("session_trip_001");
  const [applied, setApplied] = useState<{ api: string; session: string } | null>(null);

  const adapter: MissionAdapter | null = useMemo(() => {
    if (mode === "demo") return new DemoAdapter();
    if (mode === "fixture") return new FixtureAdapter();
    return applied ? NetworkAdapter.create(applied.api, applied.session) : null;
  }, [mode, applied]);

  return (
    <div className="mc">
      <div className="mc-head">
        <h1>Mission Control</h1>
        <div className="tabs" role="tablist" aria-label="Data source">
          {(["demo", "fixture", "live"] as Mode[]).map((m) => (
            <button key={m} role="tab" className="tab" aria-selected={mode === m} onClick={() => setMode(m)}>
              {m === "demo" ? "Demo scenario" : m === "fixture" ? "Fixture replay" : "Live stream"}
            </button>
          ))}
        </div>
        <span style={{ color: "var(--ink-2)", fontSize: "0.88rem", flex: 1, minWidth: 260 }}>{DESCRIPTIONS[mode]}</span>
      </div>
      {mode === "live" && (
        <form className="controls" onSubmit={(e) => { e.preventDefault(); setApplied({ api, session }); }}>
          <label style={{ fontSize: "0.85rem" }}>API base URL <input type="text" value={api} onChange={(e) => setApi(e.target.value)} style={{ font: "inherit", width: 260 }} /></label>
          <label style={{ fontSize: "0.85rem" }}>Session id <input type="text" value={session} onChange={(e) => setSession(e.target.value)} style={{ font: "inherit", width: 200 }} /></label>
          <button className="btn btn-primary" type="submit">Connect</button>
          {applied && !adapter && <span className="pill pill-bad" role="alert">Invalid URL or session id</span>}
        </form>
      )}
      {adapter ? <MissionControl key={`${mode}-${applied?.api}-${applied?.session}`} adapter={adapter} initialView={initialView} /> : (
        <div className="panel">Enter a base URL and session id, then Connect. Nothing is requested until you do.</div>
      )}
    </div>
  );
}
