# Integration audit

Phase 0 baseline: 2026-10-24. Clean integration/crewbie initially at origin/master 2aec391a86605efd2cb0f3de4643456abb20ff78. All remote refs fetched and verified. Sources inspected in archive copies under ignored .integration-audit; source-agent worktrees untouched. Pins below are the merge inputs even if remote branches advance. No implementation edited before this audit.

| Agent / branch / pinned commit | Implemented features | Tests actually run | External dependencies | Real / mocked | Contract mismatches | Readiness / blockers |
|---|---|---|---|---|---|---|
| A03 origin/agent-03-privacy `fd2439ba1fb6bac6b1db50da48ece1f3fac32237` | Scoped private capabilities, consent, matching, hard feasibility, social planning | python -B -m unittest discover -s tests/participants -v: 61 passed | stdlib; synthetic-only profiles | Real policy engine; demo identity and memory repository | Full roster cost validation conflicts with A4 minimized view; hint/error vocabulary adapters needed | Mergeable; composition required. Live accounts/providers unverified. |
| A02 origin/agent-02-events `e7c3d5c53ca53ad4c6c610ab78ac7d675a6f50b9` | Source catalog, provenance, activity discovery, freshness, authorized imports | python -B -m unittest discover -s tests/opportunities -v: 38 passed | stdlib; authorized source importer | Real normalization/discovery; default fixtures and manually observed source snapshot | Discovery envelope is additive, not canonical Opportunity for unsourced ideas | Mergeable; composition required. Live accounts/providers unverified. |
| A04 origin/agent-04-negotiation `e4f8acd65aec30a3a780f5ac6101d63ec61ec4f1` | Bounded negotiation, deterministic generation, validation, fairness, versioning | python -B -m unittest discover -s tests/negotiation -v: 153 passed | stdlib; injected A3/A5/sink | Real coordinator; standalone mock agents/gateway and synthetic prices | Nested public snapshot; A5 expects flat validated snapshot; hint names/probe budgets differ | Mergeable; composition required. Live accounts/providers unverified. |
| A05 origin/agent-05-chat `fb49967b2f388800029636b76d8add6ee10cccf3` | Host, conservative parsing, explicit versioned commitments, introductions | python -B -m unittest discover -s tests/commitments -v: 71 passed | stdlib; authorized messaging provider | Real commitment state machine; mock delivery, consent and A4 snapshots | Flat snapshot; structured confirmation summary satisfies A4 proposed contract; no Discord implementation | Mergeable; composition required. Live accounts/providers unverified. |
| A06 origin/agent-06-visuals `8bbd1425ce9011dcd08cc58841330babec450da8` | Next/React 3D and accessible 2D, SSE sink, reducer, judge client | python -B -m unittest discover -s tests/realtime -v: 17 realtime (exit 0; socket warnings); frontend pending passed | Node22/npm; Next15 React19 Three/Vitest; optional FastAPI | Real UI/transport; local synthetic simulator; judge bridge returns 501 | Event payload allowlist drops A4 fields; no snapshot/catalog fetcher or writable judge backend | Mergeable; composition required. Live accounts/providers unverified. |
| A01 origin/agent-01-cubbie `8a09636657d8961d5d7461427e12946003208113` | Standalone Unlocks Skill, planner/handoff, protected commitments, tone consent | python -B -m unittest discover -s tests/cubbie -v: 64 passed | stdlib locally; native Cubbie account for real execution | Real instruction package/policy models; simulator and unavailable provider adapter | Consent handoff is not a verified native-to-backend bridge | Mergeable; composition required. Live accounts/providers unverified. |

## Architecture decision

Keep the existing Python modules in one trusted composition process with injected evaluator, commitment gateway and validated realtime sink; mount a small local API. Keep Next.js and native Cubbie Skill independent. Use only synthetic profiles because A3 intentionally rejects real profiles. External source fixtures, synthetic venue/price estimates, mock chat delivery and Cubbie handoff are explicitly labeled. No claims of live enrollment, booking or account execution.

## Findings and release gates

- A3 and A1 completion claims are verified only for local source/tests; neither establishes live account operation. Other four branches contain substantial source and passing Python suites.
- A3 caps private probes at eight lifetime evaluations per participant/scope; A4 allows more and A3 hint calls spend another probe. Adapt hint reuse and use bounded searches; never raise the A3 cap.
- A4 can emit approval_requested before chat delivery and duplicate proposal_confirmed with A5. Composition must give A5 delivery/confirmation event authority.
- Revalidate consent on each private evaluation, intro and approval; invalidate commitments before replan. No public profile route.
- Live Discord requires an invited bot, token, allowed channel and verified provider IDs. No credentials were supplied or inspected.
- Frontend dependency install/build is a separate gate; package versions must be verified against registry.
- Official hackathon instructions fetched via HTTPS (web reader failed, curl succeeded); official creator kit cloned read-only for validation. Real Cubbie testing requires an authorized student.
- Do not equate fixture unit suites with integrated or live operation. Integration scenarios and boundary tests remain to be built.

## Integration milestones and corrections

- All six pinned branch tips were merged sequentially, preserving history: A3 -> A2 -> A4 -> A5 -> A6 -> A1. No conflicts occurred. Each affected Python suite passed after its merge: 61 / 38 / 153 / 71 / 17 / 64. Realtime tests emitted preexisting socket/disconnect warnings despite passing.
- PM independently merged A1 into master and renamed the Skill. Inspected `cccfa06c4c76734a96c52681af92594b7fe1f0ce` and merged that PM revision into integration. Agent branch pins remain unchanged; install path is now skills/crewbie-unlocks. No integration-to-master merge was performed.
- A6 baseline frontend: npm ci succeeded; 96 tests and typecheck passed. npm audit initially found two affected packages (Next/PostCSS). A scoped PostCSS 8.5.31 override preserves Next15; subsequent audit reports zero vulnerabilities and production build passes.
- The first minimized-cost A3 change made an old malformed-envelope case permissive. Regression caught it. The final change is an explicit trusted-bootstrap evaluator option; default validation remains strict. All 61 original A3 tests pass unchanged.
- Cross-module implementation uses actual A1 parsing/handoff gates, A2 discovery, A3 private evaluations/matching/introduction checks, A4 negotiation/counteroffer generation, A5 Host/commitment records and A6 sink/SSE. Private probe caps are preserved.
- Integrated traces exposed A6's highest-version-wins assumption. The reducer now follows A4's explicitly selected winner and revision floor. Four frontend tests consume traces generated by actual Python modules.
- Real Discord transport is implemented as a separate entrypoint with a provider-event allowlist and acknowledged channel sends. No account credentials were supplied; only fake external Discord transport was tested. The original provider_from_env default remains mock and its legacy discord choice still fails closed; use apps.chat_bot.discord_live for the new connector.
- Scenario A uses a public ASU Library game-resource description from https://lib.asu.edu/services/undergraduate-students. The schedule, students, consent script and inventory are synthetic. It is not a live benefit reservation or a native Cubbie handoff.
- The official creator kit validator passes after the PM rename. Kit revision bc505e9c41ea91de77f7a8b57214fd10901a100f supersedes older PDF notes about manifest requirements and install limits; no manifest or script connector is shipped.
- Two shell verification invocations were initially launched from apps/web instead of the root (or vice versa), causing path/package errors; reruns used explicit correct working directories. These were command invocation errors, not passing product checks.

See TEST_REPORT.md for final counts and commands and BLOCKERS.md for unverified external behavior.
