"use client";
import { useMemo, useState } from "react";
import { SCENARIOS } from "@/lib/demo/scenarios";
import { DemoAdapter, FixtureAdapter, MissionAdapter, NetworkAdapter } from "@/lib/adapters";
import { MissionControl } from "./MissionControl";

type Mode = "quick" | "weekend" | "fixture" | "live";
const ENV_API = process.env.NEXT_PUBLIC_CREWBIE_API_URL ?? "";

const DESCRIPTIONS: Record<Mode, string> = {
  quick: "Explicit demo mode. Four students plan an evening; one proposal fails, a counteroffer gets mixed approvals, then you change a constraint. Responses come from a labeled local simulator.",
  weekend: "Explicit demo mode. Four students negotiate a two-day trip with conflicting budgets, departures and calendars (all redacted). Responses come from a labeled local simulator.",
  fixture: "Canonical agent_events.json replayed unchanged. Read-only.",
  live: "Read-only SSE from the realtime service or integrated backend. Judge requests go to the backend and are reported as it answers.",
};

export function MissionControlApp({ initialMode = "quick", initialView }: { initialMode?: Mode; initialView?: "2d" | "3d" }) {
  const [mode, setMode] = useState<Mode>(initialMode);
  const [api, setApi] = useState(ENV_API || "http://127.0.0.1:8787");
  const [session, setSession] = useState("session_trip_001");
  const [applied, setApplied] = useState<{ api: string; session: string } | null>(null);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  async function createSession(scenario: "evening" | "weekend" | "unlocks") {
    setCreating(true); setCreateError("");
    try {
      const response = await fetch(`${api.replace(/\/$/, "")}/v1/demo/sessions`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario, request_id: `demo_${Date.now()}`, synthetic_confirmed: true,
          matching_opt_in: true, sharing_opt_in: true, introduction_opt_in: true }),
      });
      if (!response.ok) throw new Error();
      const s = await response.json();
      setSession(s.session_id); setApplied({ api, session: s.session_id });
    } catch { setCreateError("Backend unavailable. No session success assumed."); }
    finally { setCreating(false); }
  }

  const adapter: MissionAdapter | null = useMemo(() => {
    if (mode === "quick" || mode === "weekend") return new DemoAdapter(SCENARIOS[mode]);
    if (mode === "fixture") return new FixtureAdapter();
    return applied ? NetworkAdapter.create(applied.api, applied.session) : null;
  }, [mode, applied]);

  return (
    <div className="mc">
      <div className="mc-head">
        <h1>Mission Control</h1>
        <div className="tabs" role="tablist" aria-label="Data source">
          {(["quick", "weekend", "fixture", "live"] as Mode[]).map((m) => (
            <button key={m} role="tab" className="tab" aria-selected={mode === m} onClick={() => setMode(m)}>
              {m === "quick" ? "Quick Plan" : m === "weekend" ? "Weekend Plan" : m === "fixture" ? "Fixture replay" : "Live stream"}
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
          <span>Backend scenarios · synthetic students, scripted consent</span>
          {(["evening", "weekend", "unlocks"] as const).map((s) => <button key={s} className="btn" type="button" disabled={creating} onClick={() => void createSession(s)}>Start {s}</button>)}
          {createError && <span role="alert">{createError}</span>}
          {applied && !adapter && <span className="pill pill-bad" role="alert">Invalid URL or session id</span>}
        </form>
      )}
      {adapter ? <MissionControl key={`${mode}-${applied?.api}-${applied?.session}`} adapter={adapter} initialView={initialView} /> : (
        <div className="panel">Enter a base URL and session id, then Connect. Nothing is requested until you do.</div>
      )}
    </div>
  );
}
