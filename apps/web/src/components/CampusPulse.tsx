"use client";
import { useMemo, useState } from "react";
import { fixtureOpportunities, opportunitiesNotice, campusPulseBrief } from "@/lib/fixtures";
import { SCENARIOS } from "@/lib/demo/scenarios";
import type { Opportunity } from "@/lib/opportunities/types";
import { accessBadge, availabilityMatch, dietBadge, foodBadge, formatCampusTime } from "@/lib/opportunities/wording";

const demoOptions = [...SCENARIOS.quick.intent.options, ...SCENARIOS.weekend.intent.options];
const MATCH_LABEL = { fits: "Fits your free window", partial: "Partly overlaps your free window", none: "Outside your free window" } as const;

export function OpportunityBadges({ o }: { o: Opportunity }) {
  const food = foodBadge(o);
  return (
    <>
      {o.food_status !== "none" && o.food_status !== "unknown" && <span className={`pill pill-${food.tone}`}>{food.label}</span>}
      <span className="pill">{dietBadge(o)}</span>
    </>
  );
}

export function OpportunityCard({ o, window }: { o: Opportunity; window?: { start: string; end: string } }) {
  const food = foodBadge(o);
  const match = window ? availabilityMatch(o, window.start, window.end) : null;
  return (
    <li className="card" aria-labelledby={`t-${o.opportunity_id}`}>
      <div className="badges">
        {o.synthetic && <span className="pill pill-synth">Demo listing, not real</span>}
        {match && <span className={`pill ${match === "fits" ? "pill-good" : match === "partial" ? "pill-warn" : ""}`}>{MATCH_LABEL[match]}</span>}
      </div>
      <h2 id={`t-${o.opportunity_id}`}>{o.title}</h2>
      <div className="when">
        {formatCampusTime(o.start_at)} – {formatCampusTime(o.end_at, false)} <abbr title="Arizona time, no daylight saving">Arizona time</abbr> · {o.campus}
        <br />
        {o.location_label ?? "Location not listed"}
      </div>
      <div className="badges">
        <span className={`pill pill-${food.tone}`}>{food.label}</span>
        <span className="pill">{dietBadge(o)}</span>
        <span className="pill">{accessBadge(o)}</span>
      </div>
      <p style={{ margin: 0, fontSize: "0.9rem" }}>{o.food_detail}</p>
      <dl className="evidence">
        <dt>Source:</dt>
        <dd>
          <a href={o.source_url} target="_blank" rel="noreferrer noopener">{o.source_url}</a>
          {o.synthetic && " (fixture link)"}
        </dd>
        <dt>Last checked:</dt>
        <dd>{formatCampusTime(o.checked_at)} Arizona time</dd>
      </dl>
      <div>
        <button className="btn" disabled aria-describedby={`cta-${o.opportunity_id}`}>Find company</button>
        <p className="cta-note" id={`cta-${o.opportunity_id}`}>
          Unavailable: needs your opt-in for matching and a connected matching service (not connected in this build). No one is contacted.
        </p>
      </div>
    </li>
  );
}

export function CampusPulse() {
  const [foodOnly, setFoodOnly] = useState(false);
  const [campus, setCampus] = useState("all");
  const campuses = useMemo(() => [...new Set(fixtureOpportunities.map((o) => o.campus))], []);
  const win = campusPulseBrief ? { start: campusPulseBrief.availability_start, end: campusPulseBrief.availability_end } : undefined;
  const list = fixtureOpportunities.filter((o) => (!foodOnly || o.food_status !== "none" && o.food_status !== "unknown") && (campus === "all" || o.campus === campus));
  return (
    <div className="pulse">
      <h1>Discover</h1>
      <p className="lede">
        Activities and opportunities that might fit your free time, then people to do them with. Every card shows what the source actually says and what is still unknown.
        {win && <> Your demo free window: {formatCampusTime(win.start)} – {formatCampusTime(win.end, false)}.</>}
      </p>
      <div className="notice" role="note">{opportunitiesNotice}</div>
      <div className="filters">
        <label><input type="checkbox" checked={foodOnly} onChange={(e) => setFoodOnly(e.target.checked)} /> Only listings that mention food</label>
        <label>
          Campus
          <select value={campus} onChange={(e) => setCampus(e.target.value)}>
            <option value="all">All</option>
            {campuses.map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
        <span aria-live="polite" className="lede" style={{ margin: 0 }}>{list.length} shown</span>
      </div>
      {list.length === 0 ? (
        <div className="empty">No listings match these filters.</div>
      ) : (
        <ul className="cards" aria-label="Opportunities">{list.map((o) => <OpportunityCard key={o.opportunity_id} o={o} window={win} />)}</ul>
      )}
      <h2 style={{ marginTop: 32 }}>Ideas the demo plans consider</h2>
      <p className="lede">Synthetic activity options authored for the Quick Plan and Weekend Plan demos. <a href="/arena?mode=quick">Open Quick Plan</a> or <a href="/arena?mode=weekend">Weekend Plan</a>.</p>
      <ul className="cards" aria-label="Demo activity ideas">{demoOptions.map((o) => <OpportunityCard key={o.opportunity_id} o={o} />)}</ul>
    </div>
  );
}
