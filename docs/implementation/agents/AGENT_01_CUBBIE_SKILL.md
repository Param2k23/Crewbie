# Agent 01 — Cubbie Skill & Proactive Personal Assistant

**Branch:** `feat/a1-cubbie-skill`  
**Exclusive owner:** `integrations/cubbie/`, `tests/cubbie/`, `docs/integrations/cubbie/`  
**Mission:** Make Crewbie work as a *real Cubbie Skill* and deliver the strongest independently valuable Track 1 submission: timely, useful Campus Pulse opportunities and intent-to-action requests.

## Your system prompt / job

> You are Agent 01, the Cubbie Skills implementation owner. Read `PROJECT_SPEC.md`, `CONTRACTS.md`, `fixtures/`, and this file. Work ONLY in owned paths. First establish what Cubbie actually supports through sponsor documentation; do not hallucinate SDKs, endpoints, Cubbie memory reads, scheduled sends, or outbound messaging abilities. Build a deterministic, testable local mock path while verifying real integration. Finish mandatory Track 1 before adding optional UX polish. Share only contract-compliant `OpportunityBrief` and safe preview output. Report provider constraints and missing credentials without blocking other agents.

## Product responsibility

- Translate natural-language Cubbie requests into typed `OpportunityBrief`: e.g., "Find free food near Tempe tomorrow at lunch" or "I want someone to go to the event with".
- Respect user-specified campus, lunch availability, food preferences and cadence, subject to explicit permission and sponsor API capabilities.
- Consume **A2 event data** through an injected adapter (fixture-backed until available); create short alerts referencing actual event sources, food uncertainty, access rules and freshness.
- Support *preview* of an alert even when real scheduled send is unavailable.
- For "find company", output an `OpportunityBrief` with `wants_companion=true` to the integrator; do not directly introduce strangers.
- Provide Track 1 standalone value without A3/A4/A5/A6: source-backed personalized event notice with an actionable next step.

## Exclusions

No unauthorized Google/Calendar access, no payment/bookings, no scraping events yourself (A2 owns it), no casual read of other students' profiles, no claim of proactive delivery until actual schedule API validated.

## Inputs / outputs (frozen)

- Input: student message + identity and authorized context; event list via `OpportunityCatalog` adapter.
- Output: `parse_student_intent(...) -> OpportunityBrief`, `preview_cubbie_alert(...) -> AlertPreview`; error `PROVIDER_UNAVAILABLE` / `SOURCE_UNAVAILABLE` / missing permissions.
- External bridge is a separate `CubbieProvider` adapter, with `MockCubbieProvider` and (if documented) `OfficialCubbieProvider` implementations.
- Messages must use `food_status`, `dietary_suitability`, `access_status`, and `source_url` exactly as described in `CONTRACTS.md`.

## Implementation phases

### Phase 0 — Sponsor spike (highest priority, first hour)

1. Read organizer Skill docs and available examples; record exact tool schema, permission/scopes, install/test/submission process, outbound schedule support and limits.
2. Create `docs/integrations/cubbie/VERIFICATION.md`: **confirmed**, **unconfirmed**, **blocked** items with source references / observed evidence.
3. Build minimal "hello" Skill using only verified capabilities; produce evidence of running it in Cubbie.
4. If sponsor docs unavailable, create a local simulator and a one-page concrete blocker report. Do not invent integration code.

**Gate:** actual Skill runs OR a truthful blocker report with a working simulator; required Track 1 status remains clearly unverified until official test succeeds.

### Phase 1 — Standalone skill MVP

1. Implement validated input parser with allowed intents and timezone-aware lunch windows.
2. Implement event ranking by campus, overlap, freshness and explicit food signals.
3. Implement source-grounded alert preview with uncertainty language and clear event link.
4. Implement interactive reply "Find company" -> typed intent for A3, but do not auto-share student identity.
5. Add tests for unknown diet, restricted venue, missing event location, expired listing and ambiguous time.

**Gate:** offline Skill simulator outputs safe, typed alerts from fixture events, without provider credentials.

### Phase 2 — Real Cubbie integration

1. Map parser/previews onto actual Cubbie Skill interface.
2. Implement supported reminder registration **only if API supports it**; otherwise hand off a suggested reminder or documented manual workflow.
3. Ensure permission revocation, cancellation and message deduplication where available.
4. Produce reproducible Track 1 submission instruction: Skill install, invocation, test, screenshot/log.

**Gate:** demonstrated real invocation with explicitly recorded limitations.

### Phase 3 — Integration and polish

1. Inject A2 catalog and A3 match initiation through interfaces, not direct storage imports.
2. Tune concise student-facing copy, source links and privacy guardrails.
3. Add graceful fallback if provider is down, and ensure no notification is sent in simulator unless test explicitly requests it.
4. Handoff integration checklist, exact env vars, test evidence, demo transcript.

## Must-pass tests

- Input "free pizza" returns `find_campus_food` and **does not** claim guaranteed food.
- Vegetarian preference + unknown menu results in **diet not verified** wording.
- Restricted/public unknown listing gets a disclosure.
- Missing event `source_url` excluded from real alert (fixture may be labeled as such).
- "Find a friend" without matching permission creates **request for consent**, not a stranger introduction.
- Duplicate scheduling request does not create duplicate alert registration (if scheduled-send API exists).
- Real Skill execution status is clearly displayed in `VERIFICATION.md`.

## Standalone demo / handoff

Deliver `python -m integrations.cubbie.demo` (or equivalent) that takes `fixtures/opportunities.json` and prints an alert and `OpportunityBrief`. Include provider verification notes, test command and one Track 1-ready transcript. **Do not touch the root application entrypoint**; integrator mounts your adapter.
