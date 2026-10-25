# Crewbie Unlocks

Current Track 1 identity: **Crewbie Unlocks**. The Skill name and folder are `crewbie-unlocks`, matching the
installation/update commands. Native Cubbie handles
research, connected-account permissions, memory, reminders and check-ins; the Skill
contains instructions only. There are no scripts, dependencies, manifest, service
hosts or secrets in the installed folder. Tracks 2/3 are optional extensions.

## Native workflow

Use authorized calendar and Canvas to understand fixed commitments, busy periods,
academic obligations and possible gaps. Empty or inaccessible data never proves
availability. Confirm an actual window and appropriate preparation/travel buffers.
Protect essential commitments, support, meals, sleep and rest; preserve private
details. Manual availability is supported without linking accounts.

Research original campus, organizer and merchant sources for underused resources,
student benefits, equipment/access, discounts, events and local experiences. Preserve
food and general planning as categories. Each concise Unlock Card states what it is,
why it fits, eligibility, verified cost or unknown price, source link, restrictions,
next action and check time. Exclude ineligible/expired claims and retain uncertainty
about live availability, hours, reservations, diet and travel. A fresh page check
does not establish redemption capacity or that this student qualifies.

Chill is default. Playful changes tone only. Roast Me requires explicit opt-in,
honored on every response and revoked immediately; humor targets a hidden perk,
never finances, grades, essential commitments, support needs, identity or rest.
No guilt or pressure to participate. No data sharing consent follows from tone.

Real-account feedback refinement: the Skill now asks Chill / Playful / Roast Me
as its first setup question, with a nonblocking Chill fallback and permissioned
memory. It searches and ranks verified usable student-exclusive access/offers/
pricing ahead of general public options. If none fit, the main public suggestion
can end with one relevant verified near-match explaining the optional constraint
change; hard limits and protected commitments remain intact. Any relevant activity,
need, purchase or goal triggers domain-specific student-benefit research: identify
the need, find appropriate memberships/discounts/access/resources, verify provider
terms and compare total cost. Shopping and entertainment are examples, not special
cases or limits. No brand or active offer is hard-coded. Offer consent-gated pairing
when useful for the actual activity, with a solo or invitation-draft fallback.

Manual acceptance cases for this refinement: first setup asks tone before planning;
skip proceeds in Chill; returning permitted preference avoids repetitive setup;
a fitting verified student offer appears before a public option; a public venue's
student rate is described accurately; no-match output offers only relevant verified
near-matches with clear cost/time differences and permission to adjust; a fixed
budget is preserved; research across domains checks original provider terms and pairing
does not claim a match or send a message. These instruction changes still need
retesting in real Cubbie; local structural validation is not behavioral proof.

Offer cadence/time/timezone/notification choices; obtain consent for exact settings,
use native check-ins, recheck sources/permissions every run and avoid duplicate
legacy tasks. Honor quiet hours and stop requests. Offering a reminder is not
creating one. Do not report creation, cancellation or delivery without native
confirmation; if unavailable, provide a manual reminder suggestion.

Find a Crew / Start a Crew are optional, scoped and consent-gated. Existing local
`request_handoff` gates matching/coordination and redacts private planning details.
The integrator selects the action: finding companions needs matching consent;
starting an existing-friend coordination session needs separate coordination
permission. Neither grants consent for other participants. No direct student
messaging or access to others' accounts is assumed. Without the backend, provide
the solo plan, a generic invitation the student may send, or a consented reminder.

## Local test model (not shared contracts or native APIs)

`integrations/cubbie/unlocks.py` provides:

- `assess_window(context)`: trusted authorized context with timezone-aware bounds,
  explicit window_confirmed, user-supplied protected_windows, and optional minimal
  calendar/Canvas snapshots. Account data is consumed only when its `_authorized`
  flag is true and `_status` is available. Calendar data consists of busy start/end
  intervals. Canvas obligations use due_at, completed and a student-approved
  reserve_minutes; unknown preparation triggers clarification. Producer supplies
  current relevant obligations for the planning horizon. Rest and support reasons
  are never returned. Outcomes are conflict, needs_confirmation or student_confirmed;
  student-confirmed means availability, not that the entire activity is feasible.
- `personality(context)`: exact supported modes; Roast Me without roast_opt_in falls
  back to Chill. Only a fixed harmless perk joke is used in the local renderer.
- `unlock_card(item, context, now=...)`: local evidence record with title, category,
  source_url, checked_at, synthetic, eligibility (eligible/ineligible/unknown),
  restrictions and next_step. Optional duration_minutes, travel_minutes_each_way,
  event start/end, expires_at, cost_cents and cost_verified. This local shape is
  **not** an extension to canonical Opportunity. Upstream/native browsing must
  establish evidence and per-student eligibility; URL presence is not verification.
  Local policy excludes sources checked over 24 hours ago, future checks and expired
  offers, known ineligibility, window conflicts and known over-budget candidates.
  Unknown price/eligibility/travel/availability stays tentative. Even a candidate
  is not a booking or guarantee. The private card never enters group/SSE payloads.
- `checkin_draft(...)`: authorized, alerts_opt_in and an exact approved_checkin
  settings mapping are required. Daily/weekdays/weekly, local_time (HH:MM), timezone,
  text/silent and brief/silent empty preference are modeled. Weekly additionally
  requires weekday 0–6. Returns a native instruction draft with scheduled=false;
  no new scheduler/API is invented. America/Phoenix and UTC need no tzdata; other
  valid IANA zones require local system timezone data. Native Cubbie resolves its
  own supported schedule settings, including any daylight-saving ambiguities.
- `solo_fallback()`: standalone next steps, a generic invitation draft without
  private schedules/budgets, and an optional reminder suggestion; nothing is sent.

All snapshots, flags and evidence are trusted internal inputs, not authentication
claims accepted directly from a public client. These helpers do not access accounts
or enforce real provider permissions. They do not persist sensitive profiles.
Existing planner and event core remain available and their prior tests are intact.

## Run and expected results

```powershell
python -B -m unittest discover -s tests/cubbie -v
python -B -m integrations.cubbie.validate_skill skills/crewbie-unlocks
python -B -m integrations.cubbie.unlocks_demo
python -B -m integrations.cubbie.planner_demo
python -B -m integrations.cubbie.demo --simulate-schedule
```

The combined suite includes all 40 prior tests plus 24 Unlocks tests. It checks
calendar conflicts, student-protected commitments, Canvas preparation/deadlines,
empty/unavailable/unauthorized accounts, half-open boundaries, short/multi-day
windows, travel, opt-in/revoked roast, unchanged facts across tone, restrictions,
eligibility/expiry, unknown cost, source freshness, budgets, exact proactive consent,
weekly day/timezone settings, solo fallback and canonical crew intents. The package
validator checks standalone valid YAML subset/paths/size and absence of executable
permissions. Neither proves the native runtime followed the instructions.

unlocks_demo shows a fictional resource card with unknown eligibility/cost, a
non-shaming opt-in joke, confirmation required for a blank calendar, standalone
solo/invitation/reminder options and a scheduling **draft**, never delivery.

Observed on agent-01-cubbie: **64/64 tests passed**, package validator accepted
one SKILL.md (17,297 bytes), all three demos exited successfully and git diff
whitespace validation passed. Changes stay within Agent 01 ownership. No live
account access, external notification, publication, push or merge was performed.

## Real-account installation and acceptance (UNVERIFIED)

Use the installation steps in [NATIVE_SKILL.md](NATIVE_SKILL.md): publish only with
approval to a public GitHub branch, text the folder URL to Cubbie, inspect summary
and exact commit, reply yes. Existing installations use `update crewbie-unlocks` and
confirm the new commit summary. The branch target is
`https://github.com/Param2k23/Crewbie/tree/agent-01-cubbie/skills/crewbie-unlocks`;
this document does not establish remote publication or public visibility.

On a consenting real account verify: authorized calendar/Canvas versus manual
fallback; a busy window versus an empty calendar; Canvas deadline/prep and protected
rest; a current original-source benefit card with eligibility/exclusions; unknown
food/diet/cost; all tone modes and roast revocation; selected daily/weekly cadence,
quiet hours, duplicate prevention, one actual delivery and cancellation; Find/Start
a Crew with denied consent and absent backend; complete solo planning and authorized
reminder. Record redacted actual results and installed commit in VERIFICATION.md.
No native account reads, installations, deliveries, bookings or real matching have
been observed in this implementation session.
