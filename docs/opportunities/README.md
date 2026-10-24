# Crewbie activity and opportunity discovery (Agent 02)

Activity-agnostic discovery is documented in [ACTIVITY_DISCOVERY.md](ACTIVITY_DISCOVERY.md), including two offline demos, integration interface and a proposed cross-agent envelope. The original food catalog below remains supported unchanged.

Branch: `agent-02-events`. Python standard library only; intended for Python 3.12+, tested here on Python 3.13.14. No root configuration, shared contracts or fixtures modified. No external service, credentials or Agent 01 required.

From repository root:

```bash
python3 -B -m unittest discover -s tests/opportunities -v
python3 -B -m services.opportunities --now 2026-10-24T19:00:00Z --campus Tempe --starts-after 2026-10-26T12:00:00-07:00 --ends-before 2026-10-26T13:30:00-07:00 --food-only
```

The demo uses an explicit clock because shared fixtures have fixed dates and retrieval times. Without `--now`, actual current UTC applies and old data disappears from recommendations. `--overlap` selects any positive overlap instead of requiring the entire event to fit the window. Output is JSON with DEMO labels and warnings. [Saved example](sample_output.json) contains one pizza fixture result; [source audit](SOURCE_AUDIT.md) records actual public observations and access blockers.

## Agent 01 integration

```python
from services.opportunities import OpportunityCatalog, FixtureProvider

catalog = OpportunityCatalog(FixtureProvider())  # explicit offline mode
events = catalog.list_opportunities(
    "Tempe", "2026-10-26T12:00:00-07:00", "2026-10-26T13:30:00-07:00", True,
)
event = catalog.get_opportunity("opp_demo_pizza")
```

The same functions are exported at package level with the frozen four positional parameters. They return JSON mappings/list of mappings; missing IDs return `None`. For an injected clock/provider, use a catalog instance. Provider `load()` returns raw canonical records; `refresh()` explicitly reloads. Reads do not fetch or mutate provider state. Failed refresh raises and retains the prior snapshot; its original timestamps still govern freshness. Integrator may mount these callables in its own HTTP composition layer.

`OpportunityError.code` is `SOURCE_UNAVAILABLE` for inaccessible providers or `EVENT_UNVERIFIED` for invalid normalization. Catalog skips malformed records and exposes safe `diagnostics`; raw records, secrets and user preferences are not logged. Evidence text must be event-public content supplied by a trusted importer.

Optional output metadata is additive under the contract's `additionalProperties`: organizer, access_restrictions, evidence, provenance, free_food_evidence, food_availability (always unknown), stale, expired, warnings and query-only distance. Canonical `food_status` expresses food evidence; `food_detail` retains source detail. These implement the requested foodProvided/foodDetails semantics without renaming shared fields. No required contract changes requested. Display warnings and synthetic labels with every event card.

## Authorized structured imports

```python
from services.opportunities import AuthorizedImportProvider, OpportunityCatalog, FixtureProvider

document = {
    "access": "public_or_authorized",
    "http_status": 200,
    "opportunities": [],  # canonical records checked by authorized importer
}
provider = AuthorizedImportProvider(document, permitted=True)
catalog = OpportunityCatalog(provider, fallback=FixtureProvider())
```

Permission is caller attestation, not an authentication system. Set it only after source authorization. Metadata `login_redirect`, `captcha`, `redirect_url` or non-200 status rejects the document. Unavailable source errors propagate unless a synthetic fallback is explicitly supplied. Empty successful results do not trigger fallback. Imported real food claims require `evidence.food_quote`; organizer confirmation also needs `evidence.organizer_confirmation=true`. The importer must distinguish explicit food evidence from a food-related title or a free registration label. The adapter does no language model inference or HTML scraping.

[Observed public import](observed_public_import.json) is a manually transcribed genuine Central detail observation, kept separate from default synthetic fixtures. It preserves the hidden venue, officer audience and uncertain RSVP requirement. It is excluded by default because entry is restricted; inspect using `allow_restricted=True`, and reverify after its check becomes stale. It is an audit snapshot, not a continuously updated source.

## Search and ranking semantics

- Campus comparison ignores case. Time bounds use aware timestamps; contained by default, strict positive overlap optionally. Missing required times/title/campus/provenance invalidates a record; missing venue/RSVP stays null.
- `food_only=True` allows listed/organizer-confirmed food, with unknown inventory. `free_food_only=True` additionally requires an explicit `evidence.free_food_quote`; fixture pizza/taco mentions alone do not meet that test.
- Restricted events are excluded unless `allow_restricted=True`; unknown entry policy stays visible with a warning. `rsvp_policy='not_required'` requires explicit false, while `'required'` requires true; default `'any'` retains unknown.
- Dietary status defaults to unknown even if a record contains a global suitable claim. Only a query's `dietary_preference` and matching `evidence.dietary` entry establish suitability. Keys use lower case (e.g. vegetarian), values contain `status` and a specific `quote`. Known unsuitable is excluded; `allow_unknown_diet=False` also excludes unknown. Suitability is a listing claim, never allergy safety certification.
- `distances={id: metres}` accepts only caller-grounded finite nonnegative values. `max_distance_m` excludes unknown/out-of-range distance. No venue coordinates, routing or travel time are inferred. Caller is responsible for basis and origin.
- Default excludes ended and stale/future-checked records; `include_past` / `include_stale` permit explicit inspection. `get_opportunity` always includes those flags and warnings.
- Stable order: fresh checks, known dietary suitability, explicit free-food evidence, food evidence strength, public entry, no RSVP requirement, grounded distance, earliest start, opaque ID. These are lexicographic priorities, not a probability score. `offset` / `limit` apply afterward.
- Deduplication uses normalized source URL plus start instant and synthetic status, then opaque ID. URL fragments/trailing slashes are ignored, query parameters retained because some sources identify events there. Newest check wins as one complete record; ties use stable JSON order. Cross-source fuzzy matches are deliberately not merged; rescheduled events sharing an ID retain the latest observation. No certainty is combined across records.

## Handoff and limits

Implemented: model validation, fixture/mock/authorized structured provider boundaries, deterministic catalog/filter/ranking, explicit fallback, CLI, tests, saved output and source audit. Automated live ingestion is blocked on permission/robots/feed validation, as detailed in the audit. No automatic RSVP, external messaging, student storage or network dependencies. Unknown RSVP, hidden locations and dietary uncertainty require organizer follow-up before attendance. No events are guaranteed to have food remaining.

Modified files are entirely under `services/opportunities/`, `tests/opportunities/`, and `docs/opportunities/`. Verified work is committed locally on `agent-02-events`; no push or merge performed.
