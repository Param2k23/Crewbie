# Agent 04 — Multi-Agent Negotiation, Constraints & Fairness Engine

**Branch:** `feat/a4-negotiation`  
**Exclusive owner:** `services/negotiation/`, `tests/negotiation/`, `docs/negotiation/`  
**Mission:** Implement Crewbie's core technical differentiator: independently constrained student agents reach validated, privacy-respecting proposals with genuine counteroffers, fairness ranking, and honest failure states.

## Your system prompt / job

> You are Agent 04, negotiation and feasibility coordinator owner. Read `PROJECT_SPEC.md`, `CONTRACTS.md`, scenarios and this file. Work only in owned paths. Never rely on multiple LLMs talking merely for appearance; use structured proposals plus deterministic validators, private feasibility checks via an injected `PrivateEvaluator`, explicit state transitions, versioning, bounded search and testable fairness. Emit safe structured events via `EventSink`. Do not reveal exact private budgets, work reasons or hidden reasoning. No auto-confirm; delegate all human approvals to Agent 05's commitment gateway.

## Product responsibility

- `start_negotiation(...)` and `revise_negotiation(...)` session lifecycle and persistent versioned candidate state.
- Generate multiple candidate plans satisfying structural/event requirements and verify cost/time/eligibility before invoking private evaluators.
- For each participant, call A3 `evaluate_plan_private`, accept only coarse revision hints and generate counteroffers.
- Apply feasibility first, then transparent fairness ranking among feasible candidates. Track optional burden history supplied through permissioned A3 interface.
- Guard against unbounded loops and repeated private information probing; return `NO_FEASIBLE_PLAN` when warranted.
- Emit a safe event stream for Mission Control (A6) and sanitize public plan snapshots for A5.
- Invalidate old plan versions and notify A5 when material facts change; **A5 exclusively marks a proposal confirmed**.

## Important division of labor

A3 owns actual private profile data and per-student hard checks. You own *orchestration + group-level consistency + optimization*; use a fake `PrivateEvaluator` for standalone tests. A5 owns approvals, and A6 owns visual rendering/event transport. Do not implement Discord bots or 3D UI.

## Interfaces

- Input `start_negotiation(session_request) -> session_id` including group references, proposed activity, candidate time window and allowable transport/activity assumptions.
- `revise_negotiation(session_id, changed_constraint_ref)` produces new plan version and calls commitment invalidation.
- `get_public_snapshot(session_id)` provides redacted state and group-safe proposal.
- Inject `PrivateEvaluator`, `CommitmentGateway`, `EventSink` (all defined in `CONTRACTS.md`).
- Event names must exactly match allowed `AgentEvent.type` values.

## Implementation phases

### Phase 0 — State machine and deterministic test harness

1. Define allowed states: `created`, `negotiating`, `proposed`, `approval_pending`, `confirmed` (via A5), `renegotiating`, `failed`, `cancelled`.
2. Build typed plan model and a deterministic candidate generator from synthetic itinerary options, *not external invented prices*.
3. Build fake private evaluators for four fixture students, fake commitment gateway, and `MemoryEventSink`.
4. Specify max rounds, candidate count, timeout and cancellation semantics in config.

**Gate:** standalone scenario deterministically reaches a feasible plan or explicit failure with a structured event trace.

### Phase 1 — Hard validation and real counteroffers

1. Validate structure, event access, required attendees/roles, time range and group rules.
2. Ask each participant's evaluator whether a candidate is valid; fail if anyone rejects a hard constraint.
3. Use coarse counteroffer hints to produce revised candidates; every revision must be revalidated by all required participants.
4. Ensure no "agent agreement" is mistaken for **human confirmation**.
5. Emit `candidate_proposed`, `proposal_rejected`, `counteroffer_proposed`, `proposal_ready` as they actually occur.

**Gate:** changing $60 cap scenario with $70 plan fails; a cheaper candidate can succeed or engine says no solution.

### Phase 2 — Fairness ranking and human check-in

1. Rank only feasible plans; document formula such as `group_preference_penalty + weighted_inconvenience_variance + consented_history_penalty`.
2. Implement deterministic tie-breaking for equal scores so demo repeatable.
3. For small improvements that violate a hard cap, **do not show as feasible**; route a private exception request through A3 and await user input.
4. Rank tradeoffs without exposing individual reasons to A5/A6.
5. Add a 2-session fairness test showing burden distribution can improve while hard constraints remain obeyed.

**Gate:** fairness must never turn invalid->valid; private history is opt-in only.

### Phase 3 — Versioning, replanning and event integrity

1. Material revisions increment `version` and invalidate prior relevant approvals using `CommitmentGateway`.
2. Emit `proposal_revised` with version information; no raw budget in public payload.
3. Handle participant withdrawal, stale messages, feasibility timeout and no-feasible-plan termination.
4. Run contract tests with A3's real evaluator and A5's approval gateway once integrated.
5. Publish redacted trace replay fixture for A6 to render.

## Must-pass tests

- Four private agent checks actually called; cannot accept candidate with one hard failure.
- A rejected proposal produces a retry/counteroffer and a bounded terminal outcome.
- Soft early-morning preference influences ranking only among valid plans.
- Fairness-history test does not override budget/work constraints.
- Approval never appears in coordinator until A5 gateway says all required members accepted same version.
- Changing material itinerary creates version N+1 and invalidates relevant N approvals.
- Event trace has only whitelisted public types and no private values/reasons.

## Standalone demo / handoff

Provide a CLI replay (e.g. `python -m services.negotiation.demo`) with `--scenario flagstaff` and `--change-budget`, producing deterministic redacted events as JSONL. Supply fairness formula, state chart, test commands, coverage report and known tradeoffs. Integrator wires actual A3/A5/A6 adapters later.
