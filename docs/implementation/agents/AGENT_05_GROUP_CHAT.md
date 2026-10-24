# Agent 05 — Group Chat Host & Commitment Protocol

**Branch:** `feat/a5-group-host`  
**Exclusive owner:** `services/commitments/`, `apps/chat_bot/`, `tests/commitments/`, `docs/commitments/`  
**Mission:** Make Crewbie a group assistant students would actually invite: friendly introductions, privacy-safe icebreakers, clear plan alternatives and **explicit versioned commitments**, rather than a generic summarization bot.

## Your system prompt / job

> You are Agent 05, owner of the group commitment protocol and messaging provider adapter. Read the master spec, contracts and fixtures. Work only in assigned paths. A single visible bot speaks for Crewbie; never expose inter-agent conversation or private constraints. Parse social language conservatively, request clarification for uncertainty, require explicit acceptance of the same proposal version, and invalidate approvals when relevant plan details change. Implement provider-free simulator first; add a real Discord or other approved messaging integration only after access is validated. Never pretend a message was sent without provider acknowledgment.

## Product responsibility

- A conversational shared Crewbie Host in an opt-in chat; can run on a simulator and optional actual messaging provider.
- Generate a short, contextual, consent-approved introduction and icebreaker after mutual consent; no personal sensitive profile reveal.
- Consume A4 `get_public_snapshot`; ask questions needed to settle a plan without exposing private evaluations.
- Track each required participant's `pending | interested | tentative | conditional | accepted | declined | withdrawn` state.
- Maintain immutable proposal version references for approvals. Handle "maybe", ambiguous "sure", silence, conditional yes, role changes, member withdrawal and revised itineraries.
- Only return confirmed group state when every required student explicitly accepts same version and proposal remains validated.
- Notify A4/Integrator of rejection or withdrawal; emit public `approval_requested`, `member_response_received`, `proposal_confirmed` events through injected sink.

## Exclusions

No actual agent negotiation (A4), no private database read (A3), no Cubbie outgoing alerts (A1), no front-end visuals (A6), no assumption Discord DMs/message IDs can be read without proper permission.

## Interfaces

- `handle_chat_message(platform_message)` returns an intent/action and optional safe response.
- `record_approval(session_id, plan_id, version, member_ref, response)` writes normalized `CommitmentRecord`.
- `get_commitment_summary(session_id, plan_id, version)` returns counts and proposal-level state, not private member constraints.
- `invalidate_version(session_id, old_version, new_version)` clears affected acceptances and requests renewed approvals.
- `send_group_message(...)` behind `MessagingProvider` abstraction with `MockMessagingProvider` fixture default.

## Implementation phases

### Phase 0 — Provider decision + logic-first harness

1. Audit intended chat platform bot access, invitation/authorization flow, read/send limitations and rate limits; record verified capability vs assumption.
2. Implement `MockMessagingProvider` and fixture transcript runner; all business logic must work without Discord token.
3. Model proposals, versions, member receipts, idempotency and normalized reply states.
4. Define safe reply copy: no budgets, personal circumstances or unapproved social descriptions.

**Gate:** simulator can replay a group thread and produce predictable commitment state without external network.

### Phase 1 — Robust commitment state machine

1. Implement explicit approval capture with current version context. "Maybe" -> tentative, "if" -> conditional, "no" -> declined.
2. If reply is uncertain or lacks plan reference, ask clarification rather than marking accepted.
3. All approvals uniquely keyed by participant + proposal version; duplicates ignored, stale version replies rejected.
4. Require all *required* participants to accept current validated version before `proposal_confirmed`.
5. Implement changes: material update invalidates approvals and restarts confirmation flow.

**Gate:** no mixed-version, silence, or conditional confirmation paths.

### Phase 2 — Human social experience

1. Create consent-gated introduction for two students based only on approved shareable interests.
2. Add contextual icebreaker (event food/club/hackathon or Flagstaff planning) as optional suggestion, never forced disclosure.
3. Write concise action-oriented messages and helpful refusal/no-solution copy.
4. Present a *redacted group plan* with sufficient detail for real consent; provide private exception prompts through a private provider adapter rather than group channel.
5. Provide realistic test chat transcript for judge demo.

**Gate:** existing four-friend chat works standalone with mocked A4 snapshots, including no-solution and change-case UX.

### Phase 3 — Provider integration and event binding

1. Attach optional actual messaging provider and explicit invite/permission workflow; no secrets in code.
2. Connect to A4's public plan and its version-invalidation callback.
3. Emit only safe event types; persist message->request deduplication state.
4. Prove a final 4-person confirmation using actual chat if supported, or clearly labeled mock transcript if not.

## Must-pass tests

- `"maybe"` -> tentative; `"yes if it stays below my budget"` -> conditional; silence -> pending.
- Older plan version approval -> `PROPOSAL_STALE`.
- Validated current proposal with 3/4 approvals remains `approval_pending`.
- Final valid 4/4 approvals -> `proposal_confirmed` exactly once.
- Plan cost/date change -> old approvals invalidated; no automatic confirmation.
- Absent introduction consent -> no stranger group/icebreaker.
- Public chat output must not contain exact private budget, work details, underlying LLM thoughts.

## Standalone demo / handoff

Provide `python -m apps.chat_bot.demo` (or equivalent) with `--transcript fixtures/chat_transcript.json` that shows pending, conditional, rejection, revision and confirmation. Document provider capabilities and exact environment variables (values never committed). Only edit owned paths.
