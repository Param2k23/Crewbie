# Agent 02 — Campus Pulse Opportunity Data & Discovery

**Branch:** `feat/a2-campus-events`  
**Exclusive owner:** `services/opportunities/`, `tests/opportunities/`, `docs/opportunities/`  
**Mission:** Make the free-food hook **accurate, source-grounded and usable**, without relying on inaccessible ASU pages or inventing "free right now" information.

## Your system prompt / job

> You are Agent 02, the campus opportunity source and discovery owner. Read the project spec, contracts and fixtures. Work only in owned paths. Immediately verify whether ASU Sun Devil Central data is lawfully available via public listing/detail pages or approved sources; honor robots, account controls and rate limits. Never bypass a login or imply exhaustive/live inventory. Build a reliable fixture mode with visibly synthetic opportunities and an evidence-aware event model. Expose a catalog API to Agent 01 and a candidate list for the rest of the stack.

## Product responsibility

- Parse and normalize authorized events into canonical `Opportunity` records.
- Record: title, campus, timezone, time range, venue when public, organizer if visible, food-tag evidence, dietary uncertainty, access/RSVP requirements, source link, last-checked timestamp and synthetic marker.
- Provide filter/list by campus, time window and `food_status`; expose freshness and data-quality status.
- Prevent duplicates and stale claims; keep clear distinction between food mentioned, organizer confirmation and actual availability.
- Provide a deterministic fallback catalog for offline hackathon demos with prominent "DEMO" labels.

## Exclusions

No private sign-in bypass, credential scraping, login session reuse without authorization, live inventory claims, student preferences (A1/A3), mapping UI (A6), or bots messaging students.

## Inputs / outputs

- Input: public/authorized feed + raw structured event info; configurable fixture mode.
- Output: `list_opportunities(campus, starts_after, ends_before, food_only)` and `get_opportunity(id)` returning contract `Opportunity` objects.
- Data errors: `SOURCE_UNAVAILABLE`, `EVENT_UNVERIFIED` and normalized unknown values.

## Implementation phases

### Phase 0 — Source-access spike (first hour)

1. Document that current ASU student organization portal is Sun Devil Central (not retired Sun Devil Sync).
2. Test non-auth public event detail pages, RSS/ICS/open data if actually available, venue/food metadata access and terms.
3. Record sources and an access matrix: unauthenticated public / authenticated with authorized access / inaccessible.
4. Choose one primary permitted source and immediate truthful fallback. Avoid creating broad scraping scripts before access/terms are confirmed.

**Gate:** `docs/opportunities/SOURCE_AUDIT.md` with real observed access, no assumptions.

### Phase 1 — Reliable event catalog

1. Create `Opportunity` validators; times must include local offsets; reject impossible duration or no provenance for real events.
2. Normalize `Food Provided` vs free meal vs unknown. Diet and food inventory default to unknown unless verified.
3. Implement a local JSON fixture source and catalog interface with filtering by time/campus/food.
4. Deduplicate by stable source URL + time; include stale-item warning and unknown venue handling.
5. Provide offline example of a lunch-overlap query and source-aware event card.

**Gate:** A1 can use your catalog *without your live data source*.

### Phase 2 — Authorized live ingestion (conditional)

1. Add a single permitted public/authorized adapter, with network timeout, backoff, caching and logging of retrieval freshness.
2. Parse at least one known explicit food listing if available; do not treat "Free RSVP" as food evidence.
3. Filter results that are restricted, past or have unverifiable food claims; preserve them only when labeled correctly.
4. No hardcoded fabricated venues or live-looking synthetic sources.

**Gate:** live verified event entries are clearly distinguishable from fixtures, with evidence.

### Phase 3 — Integration + robustness

1. Wire HTTP router or provider to integrator registration; make search predictable and paginated if necessary.
2. Provide event freshness in output so A1 can caveat alert wording.
3. Add tests for login redirect, missing food field, inaccessible source, expired event, unknown diet and private location.
4. Prepare a three-event curated backup dataset labeled demo-only if source fails during judging.

## Must-pass tests

- "Food Provided" -> `food_status=listed`, not promise remaining/free food.
- No food evidence -> `unknown` or `none`, never invent pizza or tacos.
- Unknown dietary options remain unknown.
- Auth-wall response triggers `SOURCE_UNAVAILABLE`, not unauthorized browser session harvesting.
- `checked_at` recorded and clearly stale data flagged.
- Query for a different campus does not return Tempe events.
- Source URL retained and real event cannot use `example.org` demo placeholder.

## Standalone demo / handoff

Deliver a runnable catalog CLI/test server, source-access audit, and a one-command query against fixtures. Include expected request/response JSON, tests and rate-limit/permissions notes. Never change A1's provider code or root configuration.
