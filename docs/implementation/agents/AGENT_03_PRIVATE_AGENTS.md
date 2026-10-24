# Agent 03 — Private Student Profiles, Consent & Matching

**Branch:** `feat/a3-profiles-consent`  
**Exclusive owner:** `services/participants/`, `tests/participants/`, `docs/participants/`  
**Mission:** Represent each student as a permissioned private agent; make matching safe, and give A4 a *private feasibility oracle* without exposing personal constraints.

## Your system prompt / job

> You are Agent 03, owner of privacy-preserving participant context, activity-scoped consent, opt-in matching, and private proposal evaluations. Read the project spec, contracts and synthetic fixtures. Work only in owned paths. Never expose raw budgets, private calendar descriptions, identity tokens or hidden reason fields to group/chat/UI. Design to prevent inference through repeated feasibility probes. All external calls must pass through explicit interface methods with fake providers for testing. Return typed, redacted signals to the negotiator.

## Product responsibility

- Store `PrivateParticipantProfile` records *scoped to an activity*, using an in-memory repository for offline demo and clearly defined durable-store interface.
- Explicit opt-in and revocation states for agent participation, public matching, introduction and compromise-history tracking.
- Opt-in pool for opportunity companionship (candidate matches based on authorized campus/time/interests); never claim a social relationship without mutual consent.
- `evaluate_plan_private(student_ref, plan)` checks a user's budget, blocked time, required conditions and configurable soft preferences privately; internal results go only to trusted A4.
- `propose_private_counteroffer(...)` suggests *bounded/coarse* alternate plan characteristics without revealing exact hard caps.
- Optional opt-in burden history for fairness ranking; record only necessary aggregate burden, not reasons.

## Explicit ownership boundary

You own privacy *inputs* and private evaluations, **not** the multi-agent orchestration loop (A4), the approval state machine (A5), Cubbie adapters (A1) or UI (A6).

## Interfaces

- `opt_in(student_ref, activity_scope, consents)` and `revoke(...)`.
- `find_mutual_candidates(activity_scope, opportunity_id, limit)`; requires matching opt-in, returns safe public candidate IDs with permissioned tags only.
- `evaluate_plan_private(student_ref, CandidatePlan) -> PrivateEvaluation`.
- `propose_private_counteroffer(student_ref, CandidatePlan) -> coarse hints`.
- Internal optional `record_compromise_result(...)` only after confirmed and consented outcome.

`PrivateEvaluation` is **internal trusted-server output**. Neither exact hard caps nor issue codes can become group chat messages or A6 SSE events.

## Implementation phases

### Phase 0 — Data classification and threat model

1. Enumerate public/shared vs private fields from `CONTRACTS.md`.
2. Implement storage adapter and activity-scoped consent state model; expired or revoked consent blocks evaluation and matching.
3. Define authorization boundary: `student_ref` alone is not authentication; production uses user identity from integrator/provider, mock mode uses explicit demo tokens.
4. Add tests showing that group-visible serializers exclude private fields.

**Gate:** no demo serialization exposes budget caps, blocked-window descriptions, or private justification strings.

### Phase 1 — Matching and private feasibility

1. Implement opted-in candidate query for same opportunity/campus/time range; all introductions remain separately consent-gated.
2. Implement deterministic hard budget, availability and basic access feasibility checks.
3. Return normalized soft preference penalty for trusted ranking, with coarse counteroffer hints.
4. Apply query budget/rate limiting and auditing to defend against repeated budget inference.
5. Seed four canonical Flagstaff participants plus two food-event companions from fixtures, with synthetic markings.

**Gate:** A4 mock can call each student's private evaluator and receive an answer without knowing their actual budget or work reason.

### Phase 2 — Independent agent personalities? NO: independent policies

1. Represent each student with an agent policy object (authorized goals, hard vs soft preferences, willingness to propose alternatives).
2. Offer structured counteroffers: adjust departure after a time window, suggest a cheaper plan, remove an inaccessible event; do not broadcast private minimum/maximum thresholds.
3. Handle private exception prompts: a hard-constraint override requires explicit student approval and activity/version binding; never let coordinator self-approve.
4. Validate consent revocation while negotiation is ongoing.

**Gate:** $70 estimated participant cost fails for student with $60 cap until explicit authorized exception; audit log is private.

### Phase 3 — Integration and security review

1. Bind A4's `PrivateEvaluator` protocol to this module without importing A4 internals.
2. Provide safe candidate display objects to A5 only after required introduction consent.
3. Add adversarial tests for disclosure, repeated probe attempts, swapped student IDs, stale scopes, revoked approvals.
4. Supply data retention/purge notes for integrator and offline-demo loader.

## Must-pass tests

- Consent absent -> `CONSENT_REQUIRED`; no discovery or introduction.
- Student A may join opportunity X but not automatically Y; scopes do not leak.
- $60 hard cap vs $70 cost -> infeasible and no silent increase.
- Blocked Saturday work -> reject matching trip time; never expose shift details.
- Soft "avoid before 9" changes ranking but does not imply hard refusal unless explicitly declared hard.
- Repeated feasibility probes are bounded and private issue codes are absent from public serializers.
- Revoking opt-in excludes candidate from subsequent matching.

## Standalone demo / handoff

Deliver a fixture-driven command showing a public match result, a private infeasible evaluation and sanitized public output. Document auth placeholder vs production expectations. Include contract examples and tests. Do not create or edit chat or negotiation code.
