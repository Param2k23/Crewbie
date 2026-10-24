# Activity discovery handoff

Crewbie — The AI that makes plans actually happen.

## Phase 0: implementation audit

The prior implementation has fixture/mock/authorized structured import providers, canonical normalization, offset-aware validation, deterministic deduplication, stale/expired exclusion, food/diet/RSVP/distance filters, and 19 passing tests. These remain supported. Public source constraints remain those in [SOURCE_AUDIT.md](SOURCE_AUDIT.md); this extension performs no new live access and does not reinterpret public readability as automated collection permission.

The canonical Opportunity requires event times, campus and evidence URLs. Timeless general ideas cannot truthfully satisfy that shape. They therefore use a separate discovery envelope, never invented event dates or placeholder real URLs. Existing catalog defaults, food fixtures and callable signatures are preserved. Optional nested activity metadata carries categories, interests, duration estimates, source-backed price and explicit opening intervals.

## Stable Agent 01 / coordinator interface

```python
from services.opportunities import ActivityFixtureProvider, OpportunityCatalog, DiscoveryService
from services.opportunities.models import timestamp

catalog = OpportunityCatalog(ActivityFixtureProvider(), now=lambda: timestamp("2026-10-24T19:00:00Z"))
discovery = DiscoveryService(catalog)
response = discovery.recommend(
    "2026-10-26T12:00:00-07:00", "2026-10-26T14:00:00-07:00",
    campus="Tempe", interests=["social"], budget_preference_cents=2000,
)
```

`recommend(starts_after, ends_before, *, intent=None, categories=None, campus=None, interests=(), budget_preference_cents=None, allow_unknown_price=True, food_only=False, free_food_only=False, include_ideas=True, distances=None, max_distance_m=None, location_context=None, limit=10)` returns JSON-compatible `{query_mode, window_horizon, recommendations, diagnostics, notice}`. It uses an injected catalog and clock. No participant data is retained or echoed. The budget preference is never hard-constraint approval. Source errors propagate unless the catalog has an explicit synthetic fallback, whose diagnostic remains visible. Empty source results can still yield general ideas; set `include_ideas=False` for source-only discovery.

Each recommendation has:

- `record_type`: `verified_real`, `planning_idea` or `synthetic_fixture`; preserve this label in any client.
- `candidate_id`, title, categories, horizon, synthetic flag and source URL (null for unsourced ideas).
- `known`: location/campus context and price in integer US cents or null; source quotations where supplied.
- `fit`: basis, duration, a proposed slot when grounded, and `availability_confirmed=false` in every case.
- `requires_verification`: unresolved price, transport, schedule, venue, admission and other checks.
- `opportunity` only for source/fixture candidates, containing the canonical object for downstream lookups. An idea is not an Opportunity and must not be passed to old alert/event consumers as one.

`verified_real` means a trusted importer attested source verification and provided a description quotation alongside a genuine evidence URL and retrieval timestamp. It does not mean current availability, organizer confirmation, lawful unrestricted admission, or independent automated verification of the quotation. Unit tests use test-only records, never real-world recommendations. No new live venue inventory is included.

## Metadata and feasibility

`activity` supports `kind=event|venue`, category/interest lists, `location_context=local|regional|unknown`, `duration_minutes=[min,max]`, `price_cents`, `opening_windows=[{start_at,end_at}]`, `source_verified` and `source_claims`. Claims use description/opening_windows/price/location quotations. Real prices and opening windows are discarded without their specific supporting quotations. Real discovery records without description verification are excluded with `EVENT_UNVERIFIED`; legacy catalog retrieval still works.

For events, original start/end remain listed event times, and the entire future event must fit the query window. For venues, canonical start/end define the source's validity interval, **not opening hours**; explicit opening intervals are additionally required. The smallest estimated visit duration must fit completely into one intersection of query, validity and opening intervals. Venue proposals use UTC offsets consistently; event timestamps retain source offsets. Adjacent closed intervals are not joined to manufacture a visit. Unknown hours or duration cannot establish venue suitability.

Ideas have general duration estimates: 60–90 minutes, 3–4 hours, half-day, two-day or longer-break ranges. The minimum must fit the elapsed query time; the output retains the full estimate range and does not reserve the rest of the window. A two-day idea requires at least 2,880 elapsed minutes; DST changes therefore matter. Ideas have no proposed slot, price or venue. They require schedule, travel, admission and possibly lodging verification. They are not synthetic fixtures merely because they are general suggestions.

Time-first omits intent; intent-first passes controlled category vocabulary (coffee, games, lunch, dinner, movies, bowling, sports, meetup, event, workshop, outdoors, hike, day_out, trip, getaway, etc.). Aliases include `weekend trip`, `day out`, `hiking`, `free food`. Categories are matched explicitly, not by invented natural-language source claims. A dinner category does not imply food is included/free. Non-food records retain canonical `food_status=unknown` unless actual absence is evidenced.

Campus filtering applies to source records. General ideas do not assert a campus or destination; `location_context` filters both ideas and explicit source context. Unknown context is excluded when a context is requested. Caller-provided grounded distances filter source results; a distance cap excludes ideas because no venue/distance is known. Demo distances are synthetic examples, not real map measurements. No travel time or transport capacity is inferred.

Missing prices remain null and require checking. `allow_unknown_price=False` excludes them, including ideas. Known prices above a budget preference are excluded; no fees, transport costs or totals are fabricated. Known source price is never a guarantee of final total.

Ranking is lexicographic: real verified records, fixtures, ideas; interest matches; known/low listed price when budget preference exists; duration fit to window; stable candidate ID. No food preference is imposed unless requested. Catalog duplicate rules remain unchanged; ideas dedupe by ID. Horizons classify duration as short_break (≤120 minutes), evening (≤240), half_day (≤720), weekend (≤4320), long_break. They describe duration, not an assumption that an arbitrary date is Saturday or an evening.

## Offline demonstrations and exact PowerShell commands

From repository root with Python on PATH:

```powershell
python -B -m unittest discover -s tests/opportunities -v
python -B -m services.opportunities.demo A
python -B -m services.opportunities.demo B
```

The same commands run in bash using `python3` when that is the installed executable. Validation here used Linux/Python 3.13.14; PowerShell itself was not available/run. There are 38 tests (19 preserved, 19 added). They cover short/multi-day/DST/offset windows, incompatible times/hours, unknown prices and budgets, duplicates, stale/expired events, unverified claims, optional food, empty results, denied sources and fallback.

Scenario A: two hours free, Tempe local context, synthetic distances ≤500 metres; returns exactly `demo_games` and `demo_coffee`, visibly fictional. Coffee's 90-minute visit is an estimate within fictional opening hours. Scenario B: a 48-hour free weekend and trip intent; returns `demo_weekend` (fictional scheduled candidate) and `idea_weekend` (general unconfirmed idea). Saved [A output](scenario_a.json) and [B output](scenario_b.json) provide known fields, sources and verification requirements. Fixed demo clock avoids aging out dated fixtures; production uses actual UTC.

## Completion and remaining work

Phases 0–3 completed for the independently testable discovery service. No third-party packages, keys, network or other agents required. All edits stay in the three owned directories. Source adapters remain structured imports; automated live retrieval still requires permitted access/terms/robots validation and a bounded transport adapter. Integrator owns API mounting and negotiation wiring. The coordinator must verify transport, costs and participant constraints; discovery does not declare a plan feasible or book anything. See [contract proposal](CONTRACT_PROPOSAL.md) before exposing the new envelope across agents.
