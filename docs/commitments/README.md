# Crewbie Host and Commitment Protocol (Agent 05)

One visible group-chat assistant plus a versioned commitment state machine for general social planning (meals, games, events, multi-day trips, new or existing groups). Python 3.12+, stdlib only, no network.

## Run

From the repo root (`services/` and `apps/` are namespace packages, so run from the root):

```bash
python -m apps.chat_bot.demo                       # scripted 4-student chat: pending, conditional, decline, revision, confirm
python -m apps.chat_bot.demo --transcript docs/implementation/fixtures/chat_transcript.json   # replay + check expected_state
python -m apps.chat_bot.demo --scenario weekend    # "Let's do something this weekend" -> plan -> 4 confirms -> change -> approvals reset
python -m apps.chat_bot.demo --scenario dinner     # evening meetup, yes/maybe/conditional/silence, cost change
python -m apps.chat_bot.demo --scenario newgroup   # consent-gated group formation and opt-in icebreaker
python -m unittest discover -s tests/commitments -t .                                         # 71 tests (pytest also works)
```

The demo exits non-zero if the replay mismatches an `expected_state` or the plan does not confirm exactly once.

## Layout

| Path | Role |
|---|---|
| `services/commitments/parser.py` | Rule-based reply classifier (no model call) |
| `services/commitments/service.py` | `CommitmentService`: versions, records, confirmation gate, persistence |
| `services/commitments/snapshot.py`, `privacy.py` | Public-snapshot intake, private-field rejection, outbound text guard |
| `services/commitments/events.py`, `consent.py` | `EventSink` / listener protocols, consent gateway stub |
| `apps/chat_bot/host.py` | `CrewbieHost`: proposals, replies, intros, icebreakers, follow-ups |
| `services/commitments/intent.py`, `negotiation_port.py` | Planning-request recognition; A4 client protocol |
| `apps/chat_bot/groups.py` | Consent-gated group formation (private invites, then intro) |
| `apps/chat_bot/mock_negotiation.py`, `scenarios.py` | Synthetic A4 stand-in and scripted scenarios |
| `apps/chat_bot/providers.py` | `MessagingProvider` protocol, `MockMessagingProvider`, `provider_from_env` |
| `apps/chat_bot/data/public_snapshots.json` | Synthetic stand-in for A4 `get_public_snapshot` |

## State machine

Member states: `pending | interested | tentative | conditional | accepted | declined | withdrawn`. (The brief's "rejected" is the contract's `declined`.)
Proposal states: `awaiting_validation`, `approval_pending`, `blocked` (a required member declined or withdrew), `confirmed`, `superseded`, `revoked` (a member retracted after confirmation).

| Message | Result |
|---|---|
| "I accept version 2", "I confirm plan version 2", "I accept this plan" | `accepted`, the only state that can confirm |
| "maybe", "not sure", "I guess", "can't confirm yet" | `tentative` |
| "yes if...", "I accept but...", "unless" | `conditional` (condition text is not stored or echoed) |
| "sounds fun", "sure", "ok", bare "yes" | `interested` plus one clarification prompt per member per version |
| "no", "I decline" | `declined` |
| "I'm out", "count me out" | `withdrawn` |
| silence | stays `pending`; one rate-limited group nudge (default 6h interval, max 2) |
| a question mark, unrecognised text | no state change, clarification |

Bare "yes" or "I'm in" counts only if the provider flags the message as a reply to the proposal message (`reply_to_proposal`). Otherwise it is `interested`.

Rules enforced in `CommitmentService`:

- Approvals are keyed by `(session, plan_id, version, member)`. A named older version, a provider-referenced older version, or a message sent before the current version was shown returns `PROPOSAL_STALE`.
- A new version supersedes the active one and clears every approval; none are carried forward, material or not. Same version with different content raises `VERSION_CONFLICT`.
- `proposal_confirmed` fires once, only when every required member has an explicit `accepted` record on the active, validated, acknowledged-as-presented version with `plan_acceptance` consent still held.
- Messages are deduplicated by `request_id`, and out-of-order messages are resolved by `sent_at` (later send wins). The cache is persisted when `state_path` is set.
- Consent revocation marks the member `withdrawn`, voids any confirmation and notifies the listener.

## Planning conversations

`handle_chat_message` recognises, without any model call:

| Message | Action |
|---|---|
| "Anyone free for dinner tomorrow?", "Let's play badminton this weekend.", "We should go somewhere over fall break.", "Let's do something this weekend" | Structured `request_proposal` to A4 (`activity_type`, `activity_label`, `timeframe_text`, `requested_by`, `member_refs`). Raw text is never forwarded. Further asks while one is in flight get a short "working on it". |
| "Can we move this plan to Saturday?", "can we make it cheaper?" | Sender becomes `conditional` (voiding a confirmation if one existed), `change_requested` callback with coarse `aspects` (`date`, `time`, `cost`, `location`, `people`), and `request_revision` to A4. |
| "Let's cancel the trip" | Sender counts as `declined`, `cancellation_requested` callback. The chat never closes a plan itself; the integrator calls `cancel_proposal`. |
| "I need to cancel" | Personal withdrawal via the reply parser. |

With an open proposal, new-plan phrasing is ignored so approvals are never mistaken for new plans. After a plan is confirmed, a different request starts a fresh request.
The Host never judges feasibility. It posts only snapshots with `validated: true`. If A4 or the provider is unreachable it says so and keeps state unchanged. Failed group messages are queued (`undelivered`, retry with `flush_undelivered()`).

## Group formation

`host.groups.form_group(...)` checks `introduction` consent per **activity scope**, so being matched for one activity says nothing about another. Members without consent are not invited, named or contacted. Consenting members get a private invitation that names nobody. The group intro is posted once everyone has answered, names only those who joined, re-checks consent at that moment, and mentions only interests that all joiners approved. The icebreaker is an offer; one is posted only when a member asks for it. Group formation state is in memory only.
Cubbie's own Skill can message its own student; this Host never assumes it can text other participants. Any external group chat needs a separately authorised provider.

## Integration

- **Out, requests to A4** (`NegotiationClient`: `request_proposal`, `request_revision`). `MockNegotiationService` stands in until A4 exists.
- **In (A4):** `CrewbieHost.present_proposal(snapshot)` / `CommitmentService.register_proposal(snapshot)`. The snapshot must be public and carry `validated: true`. Required keys: `session_id, plan_id, version, member_refs`. Optional: `title, start_at, end_at, activities, cost_summary, estimate_disclaimer, open_questions, activity_scope, required_member_refs`. Keys such as `hard_budget_cap_cents`, `estimated_cost_cents_by_ref` or `internal_issue_codes` are rejected with `PRIVATE_FIELD_IN_SNAPSHOT`.
- **Out, events** (`EventSink`, `actor_ref: group_host`, `group_safe`): `approval_requested` (only after the provider acknowledges the post), `member_response_received`, `proposal_confirmed`.
- **Out, structured callbacks** (`CommitmentListener.on_commitment_event`, no reasons or text): `member_declined`, `member_withdrawn`, `conditional_response`, `consent_revoked`, `approvals_invalidated`, `confirmation_revoked`, `proposal_confirmed`, `approval_recorded`, `change_requested`, `cancellation_requested`, `proposal_cancelled`.
- **Gateway** (A4 calls): `invalidate_version`, `get_commitment_summary`, plus `record_approval`. `handle_chat_message` is `CrewbieHost.handle_chat_message`.
- Identity: only messages whose `identity_source` is trusted (`mock` in demo, `provider_verified` for a real provider) are processed. Client-supplied user ids alone are ignored.

## Messaging provider status

| Provider | Status |
|---|---|
| Mock | Implemented, default, tested. Acknowledges every send; supports forced failure. |
| Discord | **Not implemented.** No bot token, invite or verified API access was available or authorised in this build. `CREWBIE_CHAT_PROVIDER=discord` raises `PROVIDER_UNAVAILABLE`; nothing pretends to send. |

Assumptions to verify before building a Discord adapter (not verified here): reading message text in a guild needs the Message Content privileged intent or a mention/reply; group replies can reference the bot's message id (this maps to `reply_to_proposal` / `referenced_version`); the bot needs send-message permission in the channel and DMs need a shared server or user opt-in; rate limits apply per route.
Env vars: `CREWBIE_CHAT_PROVIDER` (`mock` default). A real adapter would also need `DISCORD_BOT_TOKEN` and a channel id. Values are never committed.

## Privacy checks (tested)

Snapshots with private keys are rejected. Outbound text is blocked if it has budget-cap wording or an unapproved dollar figure. Conditional or decline text is never stored or echoed (only a rule name and a 16-char digest). Private exception prompts go through `send_private_message` only. Introductions and icebreakers for non-friends need `introduction` consent from every member, and use only the intersection of approved interests.

## Known limitations

- Classifier is English keyword rules. Sarcasm or unusual phrasing falls to `unclear` (safe) and a rare phrasing may be misread as non-accept. It never auto-accepts on fuzzy matches.
- Consent gateway and A4 snapshots are stubs; field names for `validated` and cost text are my assumption and need integrator confirmation.
- The transcript fixture's m7 (Taylor "I confirm plan version 2" after a conditional) is treated as a valid explicit acceptance, matching `expected_state`.
- Mock A4 snapshots are fixtures; the `activity_type` and `location_label` snapshot fields are optional additions A4 may ignore.
- Group formation state and the in-flight planning flag are not persisted.
- Per-member timezone and quiet hours for nudges are not modelled.
