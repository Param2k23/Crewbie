# General social planning: local extension proposal

This document proposes optional metadata and local capabilities for integrator review. Frozen schemas and other agents' files are unchanged. The implementation is intentionally restricted to synthetic records and in-process interfaces. The canonical `PrivateParticipantProfile` required fields, `PrivateEvaluation` keys and four contract call signatures remain intact. No new mandatory cross-agent payload is claimed.

## Discovery and enrollment are separate

`register_activity(discovery_scope, activity_request)` registers an immutable local search request, not a live event. `find_mutual_candidates(activity_scope, opportunity_id, limit)` retains its frozen signature; for this local extension its opaque lookup argument can reference a registered `activity_id`. The integrator must explicitly choose this lookup mapping when composing the general-social workflow. Legacy campus `Opportunity` lookup continues to work unchanged.

Discovery profiles must have active participation processing consent (`authorized`) and `matching_opt_in`. Interests alone never suffice. Both requester and candidates must explicitly indicate `willingness: interested`, have the selected interest/rough area, cover the complete interval, have no overlapping block and satisfy duration, travel and group-size limits. The response contains only the existing candidate ID, the intersection of deliberately shareable tags, and `synthetic: true`. A student's private interests, rejected activities, limits and reasons do not appear in that response. Queries return at most 20 candidates and are limited to eight attempts per requester/discovery scope, without consent/revision resets.

A discovery profile defaults to no negotiation permission. The owner calls `join_activity(discovery_scope, activity_id, participation_scope, request_id)` to explicitly authorize a particular activity. This creates a new, separately scoped canonical profile with negotiation enabled and matching, introduction and history disabled. It copies private constraints, not grants or exceptions. The registered request fingerprint binds the chosen activity kind, rough area, interval and group size. Changing them requires a new explicit enrollment; plan versions/costs may still be privately evaluated. Existing target records cannot be overwritten by joining. Matching does not book a place, introduce strangers, enroll a student or accept a plan.

An existing friend group uses preselected member IDs and a separate activity scope. Each owner explicitly grants `negotiation_opt_in` in that scope. No public matching or stranger introduction consent is required for these private evaluations. The integrator binds its session to the immutable activity ID with `bind_session(..., activity_id=...)`. Social evaluations require this binding; IDs cannot be renamed or omitted to evade a decline. Legacy canonical profiles without social metadata preserve their existing `authorized` negotiation semantics. Any explicit `negotiation_opt_in: false` blocks negotiation, including on legacy profiles.

Stranger introductions still require both current matching consent and introduction consent, plus pair-specific approval. Negotiation consent does not replace either introduction gate. A5 still owns human plan acceptance; this service never marks anyone confirmed.

## Proposed private-profile metadata

| Local optional field | Meaning and visibility |
| --- | --- |
| `negotiation_opt_in` | Separate scoped boolean permission to evaluate plans; private consent state. Defaults false for social profiles. |
| `social_preferences.activity_interests` | Private list of activity categories such as games, dinner, hiking or travel. Discovery filter; a different interest is a soft negotiation preference, not inferred refusal. |
| `social_preferences.rough_areas` | Allowed broad areas, without precise coordinates. Required for discovery; a hard area restriction when supplied in negotiation. |
| `social_preferences.willingness` | `interested` or `unavailable` for discovery. Neither implies enrollment or plan acceptance. |
| `social_preferences.min_group_size`, `max_group_size` | Desired allowed total group size, including the requester; hard bounds when supplied. Defaults 2–20. |
| `social_preferences.max_duration_minutes` | Hard total elapsed duration limit when provided. Duration includes overnight intervals. |
| `social_preferences.max_travel_minutes` | Hard total proposed travel tolerance when provided. Missing travel evidence fails closed. |
| `joined_activity` | Service-created private enrollment binding: discovery scope, activity ID and request fingerprint. Owners cannot set this via preference management. |

Existing optional calendar windows, required conditions, expiry and offset remain supported. Preference and consent updates are scoped, not global changes to every copy of a student's profile. Owners should update or withdraw each active participation scope affected by a changed private limit. Revoking discovery permissions stops future discovery/sharing in that scope; separately granted existing-group participation permissions remain independently controlled.

## Local ActivitySearch request

```json
{
  "activity_id": "evening_games",
  "activity_kind": "games",
  "rough_area": "Tempe",
  "start_at": "2026-10-30T18:00:00-07:00",
  "end_at": "2026-10-30T19:30:00-07:00",
  "group_size": 2,
  "estimated_travel_minutes": 20,
  "synthetic": true
}
```

The owner approves a scope/purpose, not every plan mentioning a category. Activity IDs and immutable query content are necessary for rejection safety. `decline_activity(scope, activity_id, request_id)` records an opaque rejection tombstone. Re-opt-in, new plan versions, private exceptions and joined profile copies do not erase it. A source activity decline also blocks its joined participation profile. A different activity remains independently eligible. The current API intentionally has no automatic undecline; deliberate reconsideration would need a separately designed owner-only flow.

## Proposed optional CandidatePlan metadata

`activity_id`, `activity_kind`, `rough_area` and `estimated_travel_minutes_by_ref` are local optional extensions. The last is a complete map of nonnegative integer minute estimates for every required member; it is sensitive and must not enter group output. These fields do not replace canonical `activities`, start/end or estimated-cost fields. Without optional travel estimates a private travel limit cannot be considered satisfied. Unknown fields never enter the public serializer. Access evidence remains trusted `verified_conditions`; it is not inferred from prose or LLM output.

Hard checks use the full timezone-aware requested interval, including blocks strictly between departure and return. Two endpoint checks are insufficient for a two-day trip. Soft activity penalties add only a fixed coarse increment; exact limits never appear in hints. New internal categories (`HARD_DURATION`, `HARD_GROUP_SIZE`, `HARD_AREA`, `HARD_TRAVEL`) are free-form issue strings permitted by the existing schema and stay on the trusted server. New hints are coarse directions only; A4 must sanitize all trusted evaluation output before public events.

## Private exceptions and stale permissions

The evaluator's supplementary `request_private_exception(student_ref, plan, request_id)` queues an owner-only inbox entry and returns only `status` plus a synthetic marker. It sends no external messages and changes no constraints. The owner reads `pending_private_exceptions(scope)` and explicitly calls `respond_private_exception(scope, pending_request_id, approved, request_id)`. Only this owner capability sees the proposed personal cost and times in the inbox; other owners and the coordinator cannot read it. Private caps, calendar titles and refusal reasons are never included.

Identical requests with different IDs produce one owner prompt. A refusal remains refused on repeat requests for the same plan/profile revision. Consent revocation blocks requests, inbox access and responses. Profile revisions make old requests stale. Approvals bind exact plan content, student, scope, version and private-profile revision; they cannot waive participation declines or authorization failures. Revoking an exception immediately overrides cached status. Purge deletes private request snapshots and grants. Opaque decline, replay and query-budget tombstones remain to prevent reset attacks; no private refusal explanation is retained.

The coordinator remains responsible for tracking its latest material proposal revision and A5 approval invalidation. This component can reject mismatched authorizations and exact grant reuse; it has no live A4 version feed and does not pretend to invalidate the group's commitments.

## Standalone evidence

```powershell
python -m unittest discover -s tests/participants -v
python -m services.participants.demo
python -m services.participants.social_demo
```

The original campus/trip demo still works. The social demo uses four students from the canonical fixture with additional private synthetic policy data under `services/participants/fixtures/`. Scenario A finds an evening game companion and requires mutual introduction approval. Dinner matching is independently tested. Scenario B privately rejects a 48-hour trip with a budget conflict and an interior Saturday work block, then accepts a revised 48-hour option while a soft activity preference remains unsatisfied. Public output contains only aggregate feasibility and approved matching/introduction information. Exception requests remain pending until the affected owner responds.

All evidence is offline. No live Cubbie, negotiation engine, chat provider, calendar or frontend connection is claimed. Production identity, transactional storage, distributed budgets, retention policy and integrator approval of extension usage remain necessary. A finite boolean oracle can still reveal coarse feasibility information; bounded queries and hints reduce inference but cannot promise zero inference. Optional compromise-history recording remains outside this implementation.
