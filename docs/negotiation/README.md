# Negotiation, Constraints & Fairness Engine (Agent 04)

Owner paths: `services/negotiation/`, `tests/negotiation/`, `docs/negotiation/`.
Everything is synthetic and runs offline: no network, credentials, or language model.

## Run it

```bash
# tests (stdlib unittest; pytest also collects them)
python -m unittest discover -s tests/negotiation -p "test_neg_*.py" -v

# demo (deterministic clock => repeatable output)
python -m services.negotiation.demo                          # negotiate, "maybe" stays pending
python -m services.negotiation.demo --change-budget          # judge lowers a private cap -> re-plan -> confirm
python -m services.negotiation.demo --change-budget 3000     # below every option -> private exception request
python -m services.negotiation.demo --change-budget 3000 --exception no   # honest NO_FEASIBLE_PLAN
python -m services.negotiation.demo --change-availability
python -m services.negotiation.demo --withdraw stu_taylor
python -m services.negotiation.demo --change-budget --jsonl  # only the group-safe AgentEvent stream
```

`trace_flagstaff_budget_change.jsonl` is the redacted replay fixture for Mission Control (A6). A test
regenerates it from the live engine and fails if it drifts; regenerate with
`python -m services.negotiation.demo --change-budget --jsonl > docs/negotiation/trace_flagstaff_budget_change.jsonl`.

## General social planning (time-first and intent-first)

The engine plans any shared activity: dinner, games, sports, hiking, local events, day trips, multi-day travel.
Duration is a property of an activity template, never the thing that selects the category.

| `mode` | Meaning | Candidate source |
|---|---|---|
| `time_first` | The group has free time and wants suggestions | `ActivityCatalog.seeds`: every template whose whole interval fits the planning window, round-robin across kinds |
| `intent_first` | The group chose an activity (`intent.kind`, optional `intent.title`) | only that kind, enumerated over the window's days and start hours; unknown kind => `INVALID_REQUEST` |
| `seeded` | The caller supplies `seed_plans` (the original Flagstaff flow) | the supplied plans |

`group_origin` is `existing` or `matched`. A matched group is only negotiated when `consent_context.introduction_consent_refs`
covers every member; otherwise the session fails `CONSENT_REQUIRED` before any private probe. Private agents never receive other
members' cost lines (data minimisation), so a matched stranger's agent learns nothing about the others' profiles.

Plan fields added (all optional for callers; derived ones are recomputed by the engine and never trusted):
`activity_kind`, `overnight`, `nights` (computed from the dates), `logistics{transport,lodging}`, `venue_hours{opens_at,closes_at}`,
`requires_transport`, `venue_bound`, `unverified_items`.

Deterministic general-feasibility rules (`validator.validate_plan`), in addition to the earlier ones:

* the entire interval must fit the window and every member's availability (multi-day trips are checked end to end);
* transport is never assumed: `booked`/`confirmed` or `not_needed` for an activity that needs travel is rejected (`LOGISTICS_ASSUMED`, `TRANSPORT_ASSUMED`);
* an overnight plan cannot claim lodging is unnecessary (`LODGING_ASSUMED`); `overnight`/`nights` come from the dates;
* known venue hours must cover the interval (`VENUE_CLOSED`);
* anything unknown is listed in `unverified_items` (`transport`, `lodging`, `venue_hours`) in the public snapshot so the
  group host can tell humans what still needs checking. Every cost is an estimate (`estimate_disclaimer`), never a booking.

Counteroffer operators (coarse hints): `prefer_shorter_trip` (drops the overnight stay, scales the estimate), `prefer_different_day`,
`prefer_lower_cost` (variant 0 = one price tier down, variant 1 = two), `prefer_later_start`. On a revision, counteroffers to the
previously published plan are tried first; fresh catalog options are only considered once those dry up.

## Verification scenarios

```bash
python -m services.negotiation.demo --scenario dinner                       # A: early slots fail, valid alternative found
python -m services.negotiation.demo --scenario trip                         # B: full-length dates fail; counteroffers reach a valid version
python -m services.negotiation.demo --scenario trip --impossible            # B: honest NO_FEASIBLE_PLAN
python -m services.negotiation.demo --scenario dinner --change-availability # C: hard constraint changes mid-plan => real replan
python -m services.negotiation.demo --scenario trip --change-budget         # C: lowered cap => shorter/cheaper version
```

Replay fixtures (drift-tested against the live engine): `trace_dinner_game_availability_change.jsonl`,
`trace_two_day_trip_budget_change.jsonl`, `trace_flagstaff_budget_change.jsonl`.

## How a negotiation works

```
start_negotiation(request)
   seeds (request.seed_plans, or deterministic default)
   round 1..max_rounds:
      for each queued candidate (version = next integer, plan_id = <slug>_<version>):
          emit candidate_proposed | counteroffer_proposed
          1. deterministic public validation (members, costs, time, window, roles, access)  -- no private probe if it fails
          2. evaluate_plan_private(student, plan) for EVERY current member (+ propose_private_counteroffer for failing ones)
          3. all feasible -> FEASIBLE; any hard failure -> REJECTED (emit proposal_rejected: constraint_conflict)
      stop early when target_feasible reached
      expand: REJECTED -> counteroffers from the union of coarse hints; FEASIBLE -> soft refinements;
              optional CandidateSuggester (LLM) adds untrusted candidates to the same queue
   conclude: feasible pool -> fairness rank -> proposal_ready -> approval_requested
             none, but only waivable hard limits -> private exception request to that student only
             none -> negotiation_failed NO_FEASIBLE_PLAN
```

### State chart

```
created -> negotiating -> proposed -> approval_pending -> confirmed*
              |  \            |             |  \             |
              |   \           v             v   v            v
              |    +--> awaiting_exception  renegotiating <--+   (revise / withdrawal; any approval invalidated)
              v            |   |                |
           failed <--------+   +--> negotiating |--> proposed | awaiting_exception | failed
              |
              +--> renegotiating (a constraint relaxed) ;  any non-terminal state -> cancelled (terminal)
```

`*` `confirmed` is entered only inside `confirm_if_approved`, after A5's gateway reports that every current member
accepted this exact `(plan_id, version)`. `awaiting_exception` is publicly presented as `negotiating`.
The full table is `models.TRANSITIONS`; illegal moves raise `NegotiationError("INVALID_TRANSITION")`.

### Versioning

* Every candidate takes the next integer version (`v1` rejected, `v2` counteroffer, ...). Versions only increase.
* The published proposal keeps its own `plan_id` and `version`; other feasible candidates are discarded.
  **A5 must treat an approval as valid only if `version == get_public_snapshot().version`.**
* `revise_negotiation` / `withdraw_participant` calls `CommitmentGateway.invalidate_version(session, old_version, new_floor)`
  where `new_floor` is the first version of the new epoch (the published winner may be higher). The previous plan is
  re-proposed as the first candidate of the new epoch, so Mission Control sees it *fail validation* when it no longer fits.
  Unconditionally resetting approvals on any revision is a deliberate simplicity/safety choice.

## Fairness

Only feasible plans are ranked (`rank_feasible` raises on anything else, so ranking can never turn invalid into valid).

```
score = 1.0 * mean(p) + 2.0 * var(p) + 1.0 * mean(h * p)      lower is better
```

* `p_i` soft burden of member *i* in [0,1] (their own evaluator's `soft_penalty`; never published)
* `var` population variance: spreading compromises beats piling them on one member
* `h_i` consented burden-history share in [0,1] (`FairnessHistory`); members who did not opt in contribute 0
* tie-break: max(p), total estimated cost, start time, content signature (deterministic)

History is recorded only when A5's gateway confirms the plan, once per session, and only for opted-in members.
Public `fairness_evaluated` events carry rank, count and a coarse `balanced|uneven` label, nothing else.
Weights live in `NegotiationConfig`.

## Privacy model

| Data | Where it lives | Never appears in |
|---|---|---|
| Caps, blocked windows, soft prefs | A3 evaluators | coordinator state, events, snapshots, logs |
| `internal_issue_codes`, `soft_penalty`, hints | `CandidateRecord.evaluations` (in memory) | events, snapshots |
| Per-member cost lines | plan (coordinator only); each evaluator sees only **its own** line | events; snapshot unless every member called `authorize_cost_disclosure` (otherwise `estimated_total_cents` aggregate) |
| Why a plan was rejected | not retained beyond internal codes | events: `reason_category` is `constraint_conflict` (private) or `group_rule_violation` (public rule) |

* Event payloads are built by `events.build_event` against a per-type key whitelist with scalar-only, character-restricted values.
* Hints are reduced to three coarse tokens (`prefer_lower_cost`, `prefer_different_day`, `prefer_later_start`); anything else is dropped.
  Counteroffer steps are whole tiers / hours / days, and a per-member lifetime probe cap
  (`max_evaluations_per_member_per_session`) limits probing of a boundary across repeated revisions.
* A private exception is requested only from the affected student through `PrivateExceptionGateway`; no public event is emitted.
  A waiver counts only when that student's own evaluator then re-validates the same plan.
* Evaluator output is parsed fail-closed: wrong student/plan/version/session, non-bool `feasible`, NaN, or `feasible=true` alongside a `HARD_*` code all mean infeasible.

## Integration contracts

Implemented as `typing.Protocol`s in `protocols.py`; payloads follow `CONTRACTS.md`.

| Interface | Direction | Notes |
|---|---|---|
| `start_negotiation(session_request) -> session_id` | caller -> A4 | dict or `SessionRequest`; idempotent on `request_id`. Fields: `request_id, member_refs, window_start, window_end, mode, intent?, group_origin?, consent_context?, cost_tiers_cents?, slot_limit?, seed_plans[], session_id?, plan_slug?, title?, rules{min_attendees, essential_member_refs, member_roles, required_roles, max_duration_hours, earliest_start_local_hour, latest_end_local_hour, group_max_cost_per_person_cents, requires_verified_public_access}, opportunity?` |
| `revise_negotiation(session_id, {kind, student_ref?, request_id?})` | caller -> A4 | `kind` in `budget|availability|preference|itinerary|other`. The new **value is never sent**; it lives with A3. |
| `withdraw_participant(session_id, member_ref)` | caller -> A4 | extension; fails honestly if attendance/essential/role rules cannot hold |
| `record_member_decline(session_id, member_ref)` | A5 -> A4 | extension; vetoes the declined content, re-validates ranked runners-up at a new version, invalidates approvals |
| `expire_pending_exceptions(session_id)` | caller -> A4 | extension; unanswered exception stays infeasible (`exception_expired`) |
| `resolve_private_exception(session_id, student_ref, approved)` | A3 -> A4 | extension; answer comes from the student's own channel |
| `confirm_if_approved(session_id, plan_id?, version?) -> ConfirmationResult` | A5 -> A4 | polls the gateway; A4 never confirms on its own |
| `get_public_snapshot(session_id)` | A5/A6 <- A4 | state, version, sanitized plan, `error_code`, counters |
| `PrivateEvaluator.evaluate_plan_private / propose_private_counteroffer` | A4 -> A3 | `propose_private_counteroffer` returns `{"hints": [...]}`; called only for members whose verdict was infeasible. The plan passed contains only that student's cost line (data minimisation). |
| `CommitmentGateway.invalidate_version / get_commitment_summary` | A4 -> A5 | see assumption 1 |
| `EventSink.emit` | A4 -> A6 | exceptions are swallowed and counted (`sink_errors`) so a UI failure cannot corrupt negotiation |
| OPTIONAL `PrivateExceptionGateway.request_private_exception(student, session, plan_id, version)` | A4 -> A3 | without it, waivable conflicts simply end as `NO_FEASIBLE_PLAN` |
| OPTIONAL `ExceptionAwareEvaluator.record_exception_decision(...)` | A4 -> A3 | lets the student's side record a waiver before re-evaluation |
| OPTIONAL `CandidateSuggester.suggest(public_context)` | A4 -> LLM | context has no private data; output is whitelisted, re-identified (ids/versions overwritten) and fully validated |
| OPTIONAL `FairnessHistory.burden_shares / record_outcome` | A4 -> A3 | opt-in only |

### Public events emitted

`negotiation_started`, `candidate_proposed`, `counteroffer_proposed`, `proposal_rejected`, `fairness_evaluated`,
`proposal_ready`, `approval_requested`, `proposal_revised`, `proposal_confirmed`, `negotiation_failed`, `session_completed`
(all `visibility: group_safe`, `actor_ref: coordination_engine`). `member_response_received` is A5's. Payload keys per type are in
`events.PAYLOAD_KEYS`.

### Assumptions / contract-change requests for the integrator

1. **Commitment summary shape** is not specified in `CONTRACTS.md`. A4 requires
   `{plan_id, version, required_count, accepted_count}` (optional `confirmed`, `declined_count`, `withdrawn_count`) and treats any
   mismatch, `required_count != current member count`, or any decline/withdrawal as not confirmed. Please freeze this.
2. New **optional** payload fields not in the fixtures: `derived_from_version` on `counteroffer_proposed`; `previous_plan_id`,
   `previous_version`, `version`, `reason_category`, `approvals_reset` on `proposal_revised`; `rank`, `feasible_count`, `balance`
   on `fairness_evaluated`; `reason_category` and counters on `negotiation_failed`; `activity_kind` and `overnight` on `candidate_proposed` / `counteroffer_proposed`. New `reason_category` values:
   `group_rule_violation`, `attendance_requirement`, `search_exhausted`, `search_bounds_reached`, `exception_declined`,
   `participant_change`, `member_declined`, `exception_expired`, `constraint_changed`, `itinerary_changed`. Older clients can ignore them.
3. Event ids are per session (`ev_0001`, ...), matching the fixture. If A6 de-duplicates globally it must key on `(session_id, event_id)`.
4. Extra state `awaiting_exception` (publicly shown as `negotiating`) was added to the Phase 0 list.
5. Default `min_attendees` is `min(2, group size)` so one dropout does not silently kill a plan; set it to the group size to require everyone.

## Known limitations / tradeoffs

* Search is synchronous and in-process; concurrency control across processes (and persistence) is the integrator's concern.
  Evaluator timeouts use a daemon thread per call: a hung evaluator is abandoned, not killed.
* The coordinator cannot detect an evaluator that lies about `feasible: true`; it can only reject malformed/inconsistent replies.
* Even coarse public signals (a rejection, a "reduced estimated cost" summary) leak that *some* constraint bound. Per-member attribution is never published.
* Plan windows are checked in each plan's own UTC offset; there is no timezone database (fixture offsets are used as given).
* The catalog, price ladders and template hours are synthetic demonstration data; real venues, prices and transport are out of scope.
* Catalog slots are enumerated on the planning window's whole days at fixed start hours; the window itself is public and coarse.
* The default lifetime probe cap (40 per member) is deliberately tight: after about three full re-plans a session ends with `search_bounds_reached` unless the integrator raises it.
* All costs are synthetic tier estimates (`NegotiationConfig.cost_tiers_cents`), not quotes. `LOCAL_HOURS` and other group rules are demo defaults.
* Mock evaluators use fixed illustrative penalty formulas (`mocks.MockParticipantAgent._assess`); A3's real scoring will differ.
