# Private participants: Agent 03

Branch: `agent-03-privacy`. All records and examples are synthetic. No external services, credentials or packages are needed.

Run from the repository root:

```powershell
python -m unittest discover -s tests/participants -v
python -m services.participants.demo
python -m services.participants.social_demo
```

The service is a runnable in-process Python component, the transport-neutral option in CONTRACTS.md. Tested on Python 3.9.5; it also targets the team's Python 3.12 runtime. There is no publicly mounted profile HTTP route.

## Phase 0: design and boundaries

Canonical profiles are held behind `ProfileRepository`; `MemoryRepository` returns defensive copies. The primary key is `(student_ref, activity_scope)`. Private fields include budget, calendar, hard conditions, soft preferences, consent details and any private metadata. They are never serialized as group payloads. Shared interests are an explicit permissioned list, not inferred interests. Only opaque candidate IDs and the intersection of permissioned interests go to a requesting student's private matching view. That candidate list is not a public stream or an introduction.

Only trusted application composition receives `ParticipantService`. After authenticating the student, it issues `service.owner(verified_student_ref)`. Never accept a request's `user_id` as that verified identity. After authenticating the coordinator, composition binds a session to a scope and exact members, then gives A4 only `service.evaluator(session_id)`. This object implements both frozen `PrivateEvaluator` methods without importing negotiation internals. Capability constructors are not network endpoints; Python object encapsulation is not a sandbox against malicious code in the same process.

`identity.py` provides an injectable `IdentityProvider` protocol and `OwnerGateway`; the demo uses explicitly labeled `DemoIdentityProvider` tokens. Unknown tokens and student IDs used as credentials are rejected. The provider neither logs nor serializes credentials. Production composition must supply its actual identity provider.

Use one opportunity-specific scope for strangers. Register its catalog opportunity with `register_opportunity(scope, opportunity)`. Matching requires active consent on both sides, matching campus, an explicitly available interval covering the event, and no blocked overlap. An unknown opportunity fails closed. General introduction consent alone is insufficient: both owners must also approve the exact other participant and opportunity via `approve_introduction`. `introduction` rechecks current matching eligibility and both approvals before producing member IDs for the host.

The service enforces one registered opportunity per scope. Replacing its content returns `PROPOSAL_STALE`; create a fresh scope and obtain new consent for changed event details. A coordinator cannot evaluate an opportunity under a different scope. Explicitly empty `available_windows` means no availability; absence of that optional field means only blocked intervals restrict trip availability.

`opt_in(student_ref, activity_scope, consents)` keeps participation, matching, introduction, negotiation and history flags separate. Consents carry a required `request_id`, and optionally an aware `expires_at`. Revocation/withdrawal is immediate. Consent and preference mutations increment profile revision, invalidating old exceptions and introduction grants. Expired consent blocks evaluation and discovery; rejoining needs fresh introduction approvals. A replayed old opt-in never undoes a newer revocation. Conflicting use of the same request ID is rejected.

General social discovery, explicit enrollment, durable activity declines, private exception inboxes and 90-minute/two-day examples are described in [SOCIAL_EXTENSIONS.md](SOCIAL_EXTENSIONS.md). That document proposes the local optional metadata for integration; no frozen schema was edited. Existing-group negotiation and finding a new crew use separate consent workflows.

## Phase 1: profiles and consent

`load_demo()` reads the four canonical trip profiles and both trip plans from `docs/implementation/fixtures/scenarios.json`. Two separate campus profiles derive from the first two synthetic students and the fixture lunch brief; they start opted out. This produces six scoped records for four people. Campus opportunities come from `opportunities.json`. The demo explicitly grants both matching and introduction consent, proves pair approval is still needed, then approves both directions.

Owner methods include `opt_in`, `revoke`/`withdraw`, `update_preferences`, `find_mutual_candidates`, `approve_introduction`, `introduction`, `approve_private_exception`, and `purge`. Mutations use request IDs for idempotency. Preference updates cannot change identity, scope, authorization or arbitrary private metadata.

`revoke_private_exception(scope, plan, request_id)` revokes only the exact plan exception. Replaying its old approval request cannot restore it. Expiry accepts only an aware timestamp; null, empty strings and falsey non-timestamp values cannot silently remove expiry. Malformed preference updates fail atomically. Canonical plan envelopes, costs for every member, membership uniqueness and trusted boolean condition facts are validated before reading private policy.

## Phase 2: evaluator integration

```python
service.bind_session("session_trip_001", "trip_flagstaff_001", member_refs)
private_evaluator = service.evaluator("session_trip_001")
result = private_evaluator.evaluate_plan_private("stu_alex", candidate_plan)
hints = private_evaluator.propose_private_counteroffer("stu_alex", candidate_plan)
```

Evaluation returns exactly the canonical PrivateEvaluation keys. A4 receives feasibility, internal issue categories, a normalized soft penalty and coarse hints. No budget thresholds, calendar descriptions, private reasons or raw profile fields are returned. Hints include `prefer_lower_cost`, `try_alternate_day` and `verify_required_access`; no exact windows or thresholds. Soft preference scores use a fixed low-cost category and student-local departure hour, without exposing cap-relative ratios. Fixed UTC offset defaults to Phoenix (-420 minutes).

Hard checks cover budget, blocked intervals, optional allowed intervals, and optional required conditions. A condition must have a trusted affirmative fact in `verified_conditions`; absence fails closed. The integrator must supply verified facts, never untrusted model assertions. All blocking issues are reported to the trusted coordinator. An exception requires `explicit_approval is True` on the owner's capability and binds to scope, student, profile revision and SHA-256 of the entire plan, including version. Changes cannot inherit that exception. Exception approval is not group plan acceptance; A5 still owns commitments.

The oracle allows eight evaluations per student/activity for the service lifetime, across sessions and revisions. Counteroffer calls consume the same allowance. A lock serializes consent changes and evaluation; exhaustion returns `EVALUATION_LIMIT_REACHED`. There are no automatic query-budget resets. Protected audit entries are fixed operation labels without values or reasons. `public_evaluation` is an allowlist serializer returning only a generic category and synthetic label; A4 remains responsible for safe event aggregation without attribution.

## Phase 3: security and retention

Tests cover budget non-disclosure, unconsented matching, pair approval, revoked consent, expiry, withdrawal, swapped identities/sessions, conflicting hard constraints, malformed costs/timestamps, soft preferences, required access, query exhaustion across sessions, version/content-bound exceptions, idempotent replay, defensive copies, purge, atomic profile validation and canonical response keys.

Additional adversarial tests cover demo token authentication, empty availability, falsey expiry attacks, opportunity rebinding, exact exception revocation, concurrent probes sharing one allowance, a fixture-backed fake coordinator, candidate campus/calendar filtering and a disclosure scan of the full demo output. See `test-results.txt` and `demo-output.json` for the recorded run. This is offline protocol integration evidence, not a live A4/A5 integration.

`purge` deletes a scoped profile and related grants. Existing evaluator capabilities then fail closed. It retains only request fingerprints and probe counts to prevent replay and query-budget reset. Full process teardown clears all in-memory data. Production must define retention for these pseudonymous tombstones, replace memory storage with transactional encrypted storage, and enforce authenticated capability issuance. The current lock and counters apply to one process only.

## Interface notes for the integrator

No canonical contracts were edited. The following ambiguities need integration decisions:

- CandidatePlan has `session_id` but no `activity_scope`. Trusted `bind_session` supplies the mapping. Example: a `session_trip_001` plan cannot authorize itself for `trip_flagstaff_001`.
- The frozen candidate query lacks requester identity. Bind it to an owner capability; do not expose a global match pool.
- The opt-in signature lacks a separate request ID; it is carried in the `consents` envelope. Introduction approval and exception methods are local supplementary interfaces, not changes to canonical payloads.
- The schema does not describe hard access/role evidence, calendar availability or consent expiry. These use private extensions (`required_conditions`, `available_windows`, `expires_at`, `utc_offset_minutes`) and optional trusted plan evidence (`verified_conditions`). Canonical required fields remain intact. Agree on evidence provenance with A4 before using access checks in integration.
- `EVALUATION_LIMIT_REACHED`, `AUTHORIZATION_FAILED`, `INVALID_INPUT`, and request-ID errors are local adapter errors; map them to safe transport errors at composition. Frozen shared error codes remain unchanged.

Limitations: this is a synthetic offline service, not production authentication, persistent storage or calendar synchronization. Bounded boolean queries still leak coarse feasibility information; eight queries mitigate but do not eliminate inference. Soft history tracking is separately consented but history recording/ranking is deferred. No real messaging, live event verification, full timezone database or A5 commitment invalidation is implemented here. The integrator must trigger A4 revision and A5 approval invalidation after preference changes; this module immediately rechecks constraints and invalidates its own private grants.
