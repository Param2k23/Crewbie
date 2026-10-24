# Campus Pulse provider verification

Checked: 2026-10-24. **Actual Cubbie Skill execution: UNVERIFIED. Track 1 eligibility is unmet pending an official runtime test.** The local simulator is not a submitted or installed sponsor Skill.

## Evidence and discovery

Read PROJECT_SPEC.md, CONTRACTS.md, COORDINATION.md, AGENT_01_CUBBIE_SKILL.md and the fixture files. No sponsor developer URL, SDK, credential instructions or executable Skill example was supplied in those materials. Repository file discovery found only the implementation specifications and fixtures at baseline.

Public searches used `Cubbie DevHacks ASU skills developer documentation API`, `"Cubbie" "DevHacks"`, and `"Cubbie" "skills" assistant developer`. These did not establish a sponsor-linked Skill specification. Search results are discovery evidence, not proof that documentation does not exist.

Opened [Cubbie API developer documentation](https://www.cubbie.com/developers). It documents software procurement/catalog and buyer-organization workflows. Its relationship to the hackathon sponsor is **not established**. This page is not evidence of an installable campus-assistant Skill, student preference memory, or student scheduled messaging. No interface from that page is used in this component. No authentication attempts, outbound messages or private listing access occurred.

## Capability table

| Capability | Status | Evidence / limitation |
|---|---|---|
| Frozen OpportunityBrief parser | VERIFIED locally | Fixture scenario and parser tests; not sponsor execution |
| Campus/time/food/freshness selection | VERIFIED locally | Automated tests against shared fictional opportunities |
| Private source-linked preview and uncertainty copy | VERIFIED locally | Runnable demo, source/diet/access tests |
| User-authorized campus, dietary and cadence parsing | VERIFIED locally | Context and message parser; no persistent sponsor memory |
| Scheduling, duplicate requests, cancellation, revocation | VERIFIED mock only | In-memory, explicitly invoked, one-occurrence due simulation; never sends |
| Official Skill package format / manifest | UNVERIFIED | Sponsor-linked docs and example required |
| Invocation / input and output schema | UNVERIFIED | No verified trigger or runtime |
| Provider identity and preference read/write scopes | UNVERIFIED | No student auth or memory contract supplied |
| Scheduled proactive messages and recurrence | UNVERIFIED | No sponsor schedule, timezone, quiet-hour or delivery guarantees established |
| External service calls from Skill | UNVERIFIED | Egress allowlist, HTTP/tool interface and secrets handling required |
| Install, test, submission and rate limits | UNVERIFIED | Sponsor instructions and sandbox access required |
| Actual Track 1 runtime invocation | UNVERIFIED / BLOCKED | No real run, screenshot, receipt or provider log exists |

## Exact external requirements

Integrator must obtain the sponsor-confirmed documentation URL and version; minimal working Skill package; install/development workspace and test user; invocation input/output example; authenticated student identity mapping; preference scopes, consent and revocation semantics; permitted external service mechanism; secret provisioning method; and any limits on execution time, payload size and calls.

For proactive alerts also obtain the documented schedule/register/cancel/status interfaces, opt-in scope, timezone/recurrence semantics, idempotency guarantees, retry and delivery receipts, quiet-hour policy, and revocation behavior. Missing schedule support should leave preview/manual invocation available without claiming proactive delivery.

Then implement the official bridge inside integrations/cubbie using those exact interfaces. Run the native invocation procedure in README.md, capture redacted evidence and update this table. Do not use procurement APIs or invent a manifest to bypass this blocker.
