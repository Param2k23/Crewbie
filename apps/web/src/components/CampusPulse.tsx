"use client";
import { useMemo, useState } from "react";
import { fixtureOpportunities, opportunitiesNotice, campusPulseBrief } from "@/lib/fixtures";
import type { Opportunity } from "@/lib/opportunities/types";
import { accessBadge, availabilityMatch, dietBadge, foodBadge, formatCampusTime } from "@/lib/opportunities/wording";

const MATCH_LABEL = { fits: "Fits your free window", partial: "Partly overlaps your free window", none: "Outside your free window" } as const;

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
        {formatCampusTime(o.start_at)} – {formatCampusTime(o.end_at, false)} <abbr title="Arizona time, no daylight saving">campus time</abbr> · {o.campus}
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
        <dd>{formatCampusTime(o.checked_at)} campus time</dd>
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
      <h1>Campus Pulse</h1>
      <p className="lede">
        Opportunities that might fit your free time. Every card shows what the source actually says and what is still unknown.
        {win && <> Your demo free window: {formatCampusTime(win.start)} – {formatCampusTime(win.end, false)}.</>}
      </p>
      <div className="notice" role="note">{opportunitiesNotice}</div>
      <div className="filters">
        <label><input type="checkbox" checked={foodOnly} onChange={(e) => setFoodOnly(e.target.checked)} /> Food mentioned only</label>
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
        <ul className="cards">{list.map((o) => <OpportunityCard key={o.opportunity_id} o={o} window={win} />)}</ul>
      )}
    </div>
  );
}
