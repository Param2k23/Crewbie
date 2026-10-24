# Crewbie Planner handoff

Current product scope: time-first and intent-first personal/social planning, with
campus food retained as an optional category. Start with [PLANNER_HANDOFF.md](PLANNER_HANDOFF.md)
for the audit, new private planner, consent gate, compatible extension proposal and
local demo. The install/update identifier remains campus-pulse.

Campus Pulse now has two separate components: the native instruction-only Skill at `skills/campus-pulse/SKILL.md`, and the preserved deterministic Python simulator with a truthful unavailable-provider adapter. The October 19, 2026 hackathon guide confirms native browsing, memory and scheduled check-ins. See [NATIVE_SKILL.md](NATIVE_SKILL.md) for public GitHub installation, real-account testing and future service integration, and [VERIFICATION.md](VERIFICATION.md) for documented versus observed capabilities. No shared contracts or fixtures were changed.

## Setup and local commands

Run from the repository root. No third-party dependencies, network, credentials or environment variables are needed. Implemented using the standard library; tested on the available Python 3.9.5. The project target is Python 3.12; that interpreter was not available for validation.

```powershell
python -B -m unittest discover -s tests/cubbie -v
python -B -m integrations.cubbie.demo
python -B -m integrations.cubbie.demo --simulate-schedule
python -B -m integrations.cubbie.validate_skill skills/campus-pulse
python -B -m integrations.cubbie.planner_demo
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

## Actual Track 1 demo procedure (not executed)

Follow the six-case checklist in [NATIVE_SKILL.md](NATIVE_SKILL.md). Publish only with the user's explicit approval, then text Cubbie the public Skill folder link, inspect the commit-pinned installation summary and reply yes. Ask for campus events directly and authorize a daily check-in through native abilities. No Python bridge or event backend is necessary. Capture real evidence and update VERIFICATION.md only after installation and execution succeed.

## Delivered evidence and remaining work

The original 18 tests and demo are preserved; six additional package tests validate standalone installation boundaries and offline structure. See [DEMO_TRANSCRIPT.md](DEMO_TRANSCRIPT.md) for historical simulator output and NATIVE_SKILL.md for the new package validation evidence. Native Skill authoring and local validation are complete; publication and real-account installation/execution remain unverified. No contract changes requested. Work remains on agent-01-cubbie. No push or merge performed.
