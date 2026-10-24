# CREWBIE — Frozen Cross-Agent Contracts (v0.1)

**Purpose:** Allow all six coding agents to work in parallel. This document is the **single source of truth for exchanged payloads, state names and endpoints**. The implementation can be modular Python functions, FastAPI routers, or HTTP calls; the payload semantics cannot change without integrator approval.

## 1. Universal rules

- All IDs are opaque strings. `created_at`/`timestamp` use ISO 8601 with timezone (`Z` for UTC). Currency is integer US cents (`estimated_cost_cents`), never float dollars.
- Public API responses/events never contain student exact budget caps, calendar item titles/descriptions, private diet or work reasons, raw prompts, access tokens or hidden reasoning.
- Public demo data is explicitly labeled `synthetic: true`; live events retain a source URL, retrieval time and access status.
- Client-provided `user_id` alone is **not proof of authorization**; production authorization must be supplied by authenticated session/provider identity. In demo mode, mock identity tokens and labels are acceptable only when clearly flagged.
- Repeated requests are idempotent using `request_id` where an action changes state. Never auto-act on uncertain LLM output.
- Schema changes require a written change proposal (field, purpose, safety, compatibility) approved by integrator. New **optional** fields allowed only when older clients ignore them safely.

## 2. Canonical data objects

### Opportunity

```json
{
  "opportunity_id": "opp_pizza_001",
  "title": "Engineering Club Meetup (DEMO)",
  "campus": "Tempe",
  "start_at": "2026-10-26T12:00:00-07:00",
  "end_at": "2026-10-26T13:00:00-07:00",
  "location_label": "Public campus location — DEMO",
  "food_status": "listed",
  "food_detail": "Pizza mentioned in listing; remaining quantity unknown",
  "dietary_suitability": "unknown",
  "access_status": "unknown",
  "rsvp_required": null,
  "source_url": "https://example.org/demo-event",
  "checked_at": "2026-10-24T18:00:00Z",
  "synthetic": true
}
```

`food_status`: `none | listed | confirmed_by_organizer | unknown`. `confirmed_by_organizer` still does **not** assert inventory available now. `dietary_suitability`: `known_suitable | known_unsuitable | unknown` **per user's preference** and only with specific evidence. `access_status`: `public | restricted | unknown`. Missing location is `null`, not an invented room number. Actual events use verified source links; `example.org` is fixture-only.

### OpportunityBrief (A1 output / A2 input may enrich)

```json
{
  "brief_id": "brief_001",
  "student_ref": "stu_alex",
  "intent": "find_campus_food",
  "campus": "Tempe",
  "availability_start": "2026-10-26T12:00:00-07:00",
  "availability_end": "2026-10-26T13:30:00-07:00",
  "opportunity_id": "opp_pizza_001",
  "wants_companion": false,
  "requirements_to_verify": ["vegetarian_options", "event_entry_policy"],
  "source": "cubbie_skill",
  "synthetic": true
}
```

`intent`: `find_campus_food | find_companion | plan_group_activity`; unrecognized intents become a safe validation error. An observed event may have `opportunity_id: null` while a search runs.

### PrivateParticipantProfile (A3 private only, NEVER A5/A6 group payload)

```json
{
  "student_ref": "stu_alex",
  "activity_scope": "trip_flagstaff_001",
  "authorized": true,
  "matching_opt_in": true,
  "introduction_opt_in": false,
  "hard_budget_cap_cents": 6000,
  "blocked_windows": [{"start_at": "2026-10-31T09:00:00-07:00", "end_at": "2026-10-31T17:00:00-07:00"}],
  "soft_preferences": {"avoid_before_local_hour": 9, "prefers_low_cost": true},
  "shareable_interests": ["hiking", "hackathons"],
  "synthetic": true
}
```

Profiles are scoped to a purpose and revocable. These fields cannot appear in public events. Consent is **per activity** and separate for matching, introduction, and plan acceptance.

### CandidatePlan (A4 to A3/A5, public only after sanitization)

```json
{
  "plan_id": "plan_flagstaff_001",
  "session_id": "session_trip_001",
  "version": 2,
  "opportunity_id": null,
  "title": "Flagstaff day trip (DEMO)",
  "member_refs": ["stu_alex", "stu_maya", "stu_jordan", "stu_taylor"],
  "start_at": "2026-11-01T10:00:00-08:00",
  "end_at": "2026-11-01T19:00:00-08:00",
  "estimated_cost_cents_by_ref": {"stu_alex": 5200, "stu_maya": 5200, "stu_jordan": 5200, "stu_taylor": 5200},
  "activities": ["Scenic stop", "Low-cost lunch", "Return trip"],
  "estimate_disclaimer": "Costs and travel times are demonstration estimates, not live offers",
  "synthetic": true
}
```

Estimated cost *for each member* is sensitive: do not publish per-member costs to group or UI unless every relevant student authorizes it. A5 gets a sanitized group plan containing a per-person *estimate only if approved*, otherwise an aggregate or redacted description. Agent 4 owns redaction of plan before emitting public events.

### PrivateEvaluation (A3 internal response, NEVER A5/A6)

```json
{
  "session_id": "session_trip_001",
  "plan_id": "plan_flagstaff_001",
  "version": 2,
  "student_ref": "stu_alex",
  "feasible": false,
  "requires_private_exception": false,
  "internal_issue_codes": ["HARD_BUDGET"],
  "soft_penalty": 0.2,
  "counteroffer_hints": ["prefer_lower_cost"],
  "synthetic": true
}
```

`internal_issue_codes` and penalties **never leave trusted coordinator**. They are not automatically group-safe. A4 may publish a generic `constraint_conflict` event without the student's identity or issue. Limit iterative evaluations to prevent reverse-engineering precise caps.

### CommitmentRecord (A5)

```json
{
  "session_id": "session_trip_001",
  "plan_id": "plan_flagstaff_001",
  "version": 2,
  "member_ref": "stu_jordan",
  "state": "pending",
  "explicit_acceptance": false,
  "last_changed_at": "2026-10-24T18:02:00Z",
  "request_id": "chatmsg_0003"
}
```

`state`: `pending | interested | tentative | conditional | accepted | declined | withdrawn`. `accepted` requires positive unambiguous approval to the exact proposal version. `confirmed` is a *proposal-level state* set only when all required members have valid `accepted` records. A material revision invalidates prior approvals and requires new votes.

### AgentEvent (A4/A5 produce, A6 renders)

```json
{
  "event_id": "ev_0006",
  "session_id": "session_trip_001",
  "timestamp": "2026-10-24T18:02:15Z",
  "type": "proposal_rejected",
  "actor_ref": "coordination_engine",
  "visibility": "group_safe",
  "payload": {"plan_id": "plan_flagstaff_001", "version": 2, "reason_category": "constraint_conflict"},
  "synthetic": true
}
```

Valid public event `type`: `opportunity_discovered | match_requested | match_suggested | consent_requested | consent_granted | negotiation_started | candidate_proposed | proposal_rejected | counteroffer_proposed | fairness_evaluated | proposal_ready | approval_requested | member_response_received | proposal_confirmed | proposal_revised | negotiation_failed | session_completed`.

`visibility` must equal `group_safe` for events entering the public event stream. Private agent diagnostics remain in separate protected logs, are never emitted as `AgentEvent`, and should be disabled in demo telemetry by default.

## 3. Proposed module/API boundaries

These are the agreed contract-level entry points, not claims that sponsor endpoints exist. The integrator mounts Python routers to an app; component owners supply adapters and tests.

| Owner | API / callable | Purpose |
|---|---|---|
| A1 | `parse_student_intent(message, consent_context) -> OpportunityBrief` | Skill intent and preferences extraction |
| A1 | `preview_cubbie_alert(student_ref, opportunities) -> AlertPreview` | Grounded message, no unauthorized send |
| A2 | `list_opportunities(campus, starts_after, ends_before, food_only)` | Source-attributed catalog |
| A2 | `get_opportunity(opportunity_id)` | Evidence and source freshness |
| A3 | `opt_in(student_ref, activity_scope, consents)` | Consent-gated participation |
| A3 | `find_mutual_candidates(activity_scope, opportunity_id, limit)` | Opt-in matches only |
| A3 | `evaluate_plan_private(student_ref, plan) -> PrivateEvaluation` | Secure internal feasibility check |
| A3 | `propose_private_counteroffer(student_ref, plan) -> hints` | Bounded changes without disclosure |
| A4 | `start_negotiation(session_request) -> session_id` | Bounded coordinator loop |
| A4 | `revise_negotiation(session_id, changed_constraint_ref)` | New version, revalidation |
| A4 | `get_public_snapshot(session_id) -> safe state` | Sanitized read model for UI/chat |
| A5 | `handle_chat_message(platform_message) -> action` | One group host, no auto-confirm |
| A5 | `record_approval(session_id, plan_id, version, member_ref, response)` | Human-confirmed versioned acceptance |
| A5 | `get_commitment_summary(session_id, plan_id, version)` | Confirmation gate |
| A6 | `GET /v1/sessions/{session_id}/events` | SSE with only group-safe events |
| A6 | `MissionControl(session_id)` | 3D client visualizing stream |

### Python shared interface shape (reference)

```python
from typing import Protocol, Mapping, Any

class EventSink(Protocol):
    def emit(self, event: Mapping[str, Any]) -> None: ...

class PrivateEvaluator(Protocol):
    def evaluate_plan_private(self, student_ref: str, plan: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def propose_private_counteroffer(self, student_ref: str, plan: Mapping[str, Any]) -> Mapping[str, Any]: ...

class CommitmentGateway(Protocol):
    def invalidate_version(self, session_id: str, old_version: int, new_version: int) -> None: ...
    def get_commitment_summary(self, session_id: str, plan_id: str, version: int) -> Mapping[str, Any]: ...
```

**Owner obligations:** A4 must not decide final confirmation without A5's commitment gateway; A5 must not declare a plan feasible without A4's validated snapshot. In stand-alone mock mode, providers return fixture-backed stub responses clearly identified as such.

## 4. Event stream and transport

A4 and A5 emit events to an injected `EventSink`, never directly mutate frontend state. A6 implements `EventSink` adapter + read-only SSE bridge under `services/realtime/`, but each module can use a local `MemoryEventSink` during tests. Integrator wires sink providers when all modules merge. SSE reconnect supports `Last-Event-ID`, duplicate IDs are discarded. Events are ordered per `session_id` and represent recorded transitions, **not hidden LLM chain-of-thought**.

## 5. Shared errors / safe failure paths

- `CONSENT_REQUIRED` — matching/introduction or activity scope not approved.
- `SOURCE_UNAVAILABLE` — campus source inaccessible; use labeled fixtures, not undocumented scraping.
- `EVENT_UNVERIFIED` — insufficient evidence for an event claim.
- `HARD_CONSTRAINT_FAILED` — proposal invalid; group gets redacted explanation.
- `PRIVATE_EXCEPTION_PENDING` — exception request sent only to affected participant, not silently applied.
- `NO_FEASIBLE_PLAN` — valid terminal outcome after bounded search.
- `APPROVAL_INCOMPLETE` — group confirmation must not fire.
- `PROPOSAL_STALE` — approval targeted older version.
- `PROVIDER_UNAVAILABLE` — Cubbie/messaging integration temporarily unavailable; run mock simulator.

## 6. Merge/test invariants

1. `private_budget` never appears in an SSE event or bot group message.
2. Explicit approval for version N cannot be carried to N+1 when material content changes.
3. `food_status: listed` never maps to “guaranteed food available.”
4. Failed Cubbie API experiments cannot block local Skill simulation.
5. A6 never relies on timers to fake negotiation success.
6. Group chat reply classification must support low-confidence cases by requesting confirmation.
7. All six parts can be tested with `fixtures/scenarios.json` and `fixtures/opportunities.json`.
