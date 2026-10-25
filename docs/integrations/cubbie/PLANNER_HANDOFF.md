# Crewbie Planner implementation and handoff

Crewbie — The AI that makes plans actually happen. Current user-facing identity
is Crewbie Unlocks; `crewbie-unlocks` is the install/update identifier and folder.
The final Agent 01 prompt supersedes food-first product scope. Food discovery is
preserved as an optional category; no canonical intent or schema was changed.

## Phase 0 audit

Baseline on agent-01-cubbie: commit b02a456, clean worktree. Existing core parses
food, companion and trip keywords, checks timezone-aware gaps, selects source-linked
campus events, and produces private uncertain-diet previews. Existing mock supports
explicit opt-in, idempotent registration, cancellation, revocation and never sends.
The 18 core tests and six package tests passed in the prior delivery.

Missing at baseline: time-first routing, dinner/sports/general activity requests,
private planning details outside the frozen brief, multi-day constraint conversation,
and an injectable consent gate for A3/A4. Native Skill was still campus-event focused.
No real Cubbie runtime, live planning provider or backend was configured.

## Current callable boundaries

- `parse_student_intent(message, consent_context)` still returns only the canonical
  OpportunityBrief. Food searches map to find_campus_food; Find a crew / Find people
  to join map to find_companion; time-first, dinner, sports, events and trips map to
  plan_group_activity, including solo planning as the existing generic planning enum.
  No new intent value was invented. Explicit dates, campus and timezone-aware start/
  end remain required at this boundary. Weekday/relative-date conflicts raise a
  validation error. The bounded local parser is not a general natural-language model.
- `plan_request(message, context, opportunities=(), now=None)` is a **private local
  conversation envelope**, not a shared payload. Missing campus or exact dates returns
  `brief: null` plus questions rather than fabricating availability. Explicit one/two/
  three/numeric hour/day durations are recognized; longer-than-window requests need
  clarification. Short gaps get nearby tentative ideas; trips gather destination,
  transport and overnight constraints. Questions can be displayed one or two at a time
  by the host. Native Cubbie handles broader language and arbitrary starting locations.
- Optional trusted private context fields: location, integer budget_cents (US cents),
  interests and activity_types string lists, integer travel_tolerance_minutes each way,
  and positive integer group_size. Unknown values remain unknown. They are validated
  and retained in the private sidecar only. The local legacy brief boundary still uses
  one of the four supported ASU campus values, even for a trip's starting campus.
- Supplied A2 Opportunity candidates are independently filtered for source, freshness,
  campus, time and suitability. The planner excludes partial event fits. Local candidates
  are **not guaranteed feasible**: no shared schema currently carries verified prices,
  travel estimates or capacity. Output explicitly marks price/hours/reservations/diet/
  travel unknown. Without source-backed candidates, generic ideas are tentative and
  contain no invented venue, source, price or booking. Native Cubbie browses original
  sources and checks hard constraints before claiming a plan fits.
- `request_handoff(brief, context, request_id, action='matching', gateway=None)` requires
  trusted authorized identity, matching student_ref, sharing_opt_in, an activity_scope,
  consent_scope equal to that activity_scope and consent_brief_id equal to this brief.
  Matching additionally requires matching_opt_in and wants_companion; coordination
  separately requires coordination_opt_in. These internal flags must come from a trusted
  identity/consent adapter, not raw client data. Consent is checked before every retry.
  No budget, diet or local details are forwarded. Only canonical brief fields pass;
  requirements_to_verify are reduced to the approved entry/consent requirements.
- PlanningGateway is a **local composition protocol**, not an A3/A4 endpoint or Cubbie
  API. Its envelope contains request_id, activity_scope, action and the minimal private
  brief. The default returns PROVIDER_UNAVAILABLE. MockPlanningGateway accepts synthetic
  briefs only, records process-local idempotent requests and returns mock_received with
  matched/confirmed/sent false. It neither negotiates nor finds real people.

No new reminder API is implemented: native Skill instructions use Cubbie's reminders
and scheduled check-ins, require authorization, handle failure, check existing tasks
and verify creation/cancellation before reporting success. Existing Python scheduling
simulation remains separate. No implicit reminder is created by plan_request.

## Compatible extension proposal — not applied

To preserve the frozen schema, all additional preferences currently stay local. If the
integrator needs richer planning, propose an optional **private planning_context**
alongside OpportunityBrief: starting_location, requested_activity, duration_minutes,
interests, activity_types, travel_tolerance_minutes, group_size, budget_cents and a
per-person/total budget scope. Define destination timezone and date-specific windows
for trips, plus verified cost/travel provenance in a separate candidate model. Each
field must distinguish unknown from zero and keep private constraints out of group/SSE
payloads. Older clients must be able to ignore the extension. Exact budgets and private
availability belong with A3's private evaluator, not public chat. Do not forward this
proposal until integrator approval and explicit field-level sharing consent.

## A3/A4 readiness

Integrator supplies an authenticated PlanningGateway mapping matching to A3's canonical
opt_in/find_mutual_candidates functions. A3 independently verifies current scoped opt-in
and mutual introduction consent. Map coordination requests to A4 start_negotiation using
its approved session_request, not this local envelope directly; participant authorization,
private feasibility evaluations and required members must be composed by the integrator.
A4/A5 own feasibility/versioned unanimous acceptance. A local handoff receipt never
means matched, messaged or confirmed. Use request_id for durable production idempotency.
No service host/SDK/authentication interface has been invented. If the backend is down,
report failure and continue the student's personal plan; an invitation can be drafted
for the student to share. This Skill never directly messages another student.

## Commands and evidence

```powershell
python -B -m unittest discover -s tests/cubbie -v
python -B -m integrations.cubbie.validate_skill skills/crewbie-unlocks
python -B -m integrations.cubbie.planner_demo
python -B -m integrations.cubbie.demo --simulate-schedule
```

Observed locally: 40 tests passed (18 original, six package, 16 new planner tests).
The new tests cover short/multi-day windows, duration/date conflicts, explicit activity
requests, missing preferences, private sidecar boundaries, candidate uncertainty,
consent rejection, scope changes/revocation, mock idempotency/redaction, separate
coordination permission, no implicit reminders and absent backend. An initial event
test exposed literal matching of the generic word "events" against titles; this was
fixed so general event requests do not filter out valid listings. All tests now pass.

planner_demo shows: two free hours yields a personal planning brief and tentative
nearby coffee/walk ideas; a two-day trip without dates gathers constraints; Find people
to join is consent-gated; an absent backend returns PROVIDER_UNAVAILABLE; an explicit
mock returns matched=false, confirmed=false, sent=false. The legacy demo remains intact.
This is offline local evidence, not source verification or native Cubbie execution.

Local commit attempt after verification was blocked: `git add` could not create
`D:/VS/Crewbie/.git/worktrees/crewbie-agent-01/index.lock` (Permission denied).
The worktree's Git metadata lies outside this session's writable workspace. No
staging, commit, push or merge was performed. Granting write access to that existing
worktree metadata is required to complete the requested local commit; no alternate
repository or permission bypass was attempted.

## Real-account installation and test

Use [NATIVE_SKILL.md](NATIVE_SKILL.md) for the exact GitHub installation/update steps.
On a real account additionally try "I have two free hours", "Plan a two-day trip",
"Plan dinner Friday" and "Find people to join". Expect clarification of missing
dates/constraints, source-backed practical options, honest price/hour/reservation/
diet/travel estimates, consent before sharing/scheduling, and standalone personal
planning when Crewbie services are unavailable. Exercise an authorized one-time reminder,
recurring creation/duplicate/update/cancellation, connected-calendar refusal and offline
browsing. **None of those native behaviors has been executed here.**
