# Campus Pulse handoff

Campus Pulse provides a deterministic, independently runnable Campus Pulse core and a truthful unavailable-provider adapter. Native Cubbie integration is blocked; see [VERIFICATION.md](VERIFICATION.md). No shared contracts or fixtures were changed.

## Setup and local commands

Run from the repository root. No third-party dependencies, network, credentials or environment variables are needed. Implemented using the standard library; tested on the available Python 3.9.5. The project target is Python 3.12; that interpreter was not available for validation.

```powershell
python -B -m unittest discover -s tests/cubbie -v
python -B -m integrations.cubbie.demo
python -B -m integrations.cubbie.demo --simulate-schedule
```

The fixture path can be overridden with `--fixtures PATH`. The fixture adapter rejects non-synthetic events. Demo clock is pinned to 2026-10-26 09:00 Phoenix to make the supplied fictional events reproducible. The simulator loads the three supplied opportunities and selects the Tempe lunch event; the evening social and West Valley workshop do not fit that request.

## Integration interface

- `parse_student_intent(message, consent_context)` returns exactly the canonical OpportunityBrief fields. Context is a trusted internal mapping with `authorized: true`, `student_ref`, `campus`, timezone-aware `availability_start` and `availability_end`; optional `dietary_preferences` list, `cadence`, `opportunity_id`, `synthetic`, `matching_opt_in`, `activity_scope`, and timezone-aware `now` for today/tomorrow. Raw client identity and authorization flags are not authentication. The eventual provider bridge must validate identity before constructing context.
- `parse_preferences(message, context)` in core.py returns private campus, diet and cadence preferences. Persistence and consented preference updates belong in the trusted composition layer; messages do not grant alert permission. Supported campuses are Tempe, West Valley, Downtown Phoenix and Polytechnic. Cadences are off/daily/weekly. Free-form clock times request clarification; lunch uses an explicitly supplied gap. Today/tomorrow must agree with the gap. This bounded parser is not a general language model.
- `select_opportunities(brief, opportunities, now=...)` performs independent validation, overlap filtering and ranking. Default minimum overlap is 20 minutes, transit buffer zero, freshness limit three days. Callers can configure those policies. Equal duplicate IDs collapse; conflicting duplicate IDs are excluded. Known-unsuitable diets are excluded. Missing/invalid dates, evidence links, enums, title or campus are excluded. Synthetic sources must remain visibly labeled. A source URL's presence is not verification of its content; A2 owns provenance validation.
- `preview_cubbie_alert(student_ref, opportunities, brief=brief, now=...)` returns a private local AlertPreview mapping with text, opportunity IDs, mode, visibility, synthetic and sent fields. CONTRACTS.md does not freeze an AlertPreview schema, so these are local component fields. It never sends. It reports food status, unknown diet/access/RSVP, missing venue, source and checked time, and uses Phoenix offset for display. Known-suitable catalog data must be evaluated by A2 for this exact student's preferences; generic menu labels cannot establish suitability.
- Inject A2 through `OpportunityCatalog.list_opportunities(campus, starts_after, ends_before, food_only)` and `get_opportunity(id)`. The fixture catalog implements bounded queries. Core can rank partial overlaps if the integrator supplies candidates covering a wider window. No A2 storage or service imports are needed. On upstream errors, the composition layer should return SOURCE_UNAVAILABLE; it must explicitly choose labeled fixtures rather than silently presenting them as live.
- `Find company` returns `find_companion`, `wants_companion: true` and `matching_consent` unless trusted scoped matching permission exists. This component never calls matching, introduces strangers or shares a student identity. Integrator passes the private brief to A3 only after scoped consent; A3 independently verifies it and mutual introduction consent.
- `UnavailableCubbieProvider` raises `PulseError` with `code=PROVIDER_UNAVAILABLE`. `CubbieProvider` is our application protocol, not an official sponsor interface. There is no invented OfficialCubbieProvider or sponsor endpoint.
- `MockCubbieProvider` registers synthetic private previews only with explicit trusted alerts consent. Requests use `(student_ref, request_id)` idempotency; changed content under a reused ID fails. Cancellation is idempotent. Dispatch rechecks consent, due time and event presence/expiry; it emits a mock due notice, never previously prepared event claims or an external message. Daily/weekly cadence is metadata; recurrence and durable scheduling are not implemented. Cancellation takes an internal trusted student identity; it is not an authenticated HTTP endpoint.

All briefs, preferences and previews are private: do not publish them to A5/A6 or public logs. Error details never echo the original student message. There are no public events, external calls or profile reads in this component. Production integrations require authentication, persistent idempotency, fresh catalog evaluation at delivery, verified provider permissions and approved privacy handling.

## Actual Track 1 demo procedure (blocked, not executed)

1. Obtain the sponsor requirements listed in VERIFICATION.md, implement their official adapter, and install with their documented procedure. There is currently no known valid install command.
2. In the real Cubbie test workspace, authenticate a consenting synthetic student and provide Tempe, a timezone-aware lunch window, vegetarian preference and explicit alert opt-in through supported controls.
3. Invoke Campus Pulse using the documented trigger. Supply the labeled fixture catalog or verified A2 catalog through the permitted external service interface.
4. Capture the real rendered source-linked alert with diet/access uncertainty, invocation receipt and adapter version. Never call fixtures live ASU events.
5. Reply Find company and prove it requests matching consent before any handoff. If scheduling is supported, register a test notice, retry the same request ID, cancel, revoke permission and verify delivery/cancellation receipts. Otherwise show a manual preview and explicitly state scheduling is unavailable.
6. Store redacted sponsor evidence under docs/integrations/cubbie and update capability statuses only after observing execution.

## Delivered evidence and remaining work

The local test and demo run completed successfully; see [DEMO_TRANSCRIPT.md](DEMO_TRANSCRIPT.md). Phase 0 discovery and blocker report, Phase 1 core, and Phase 3 local reliability are delivered. Phase 2 native integration remains blocked by sponsor docs/workspace/permissions. No contract changes requested. Changes are uncommitted on agent-01-cubbie; baseline commit is 2aec391a86605efd2cb0f3de4643456abb20ff78. No push or merge performed.
