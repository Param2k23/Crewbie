# Architecture

## 1. Components

| Component | Responsibility | Location |
|---|---|---|
| Cubbie Skill | Talks to the student, collects consent, runs `crew.py` | `skills/crewbie-unlocks/` |
| `crew.py` | Stateless HTTPS client with local credential and cursor storage | `skills/crewbie-unlocks/scripts/crew.py` |
| API | HTTP surface, auth, validation, rate limits | `src/crewbie/api/` |
| Application services | Use cases: submit intent, accept offer, link account, leave | `src/crewbie/services/` |
| Domain | Pure logic: event key, windows, room derivation, offer rules | `src/crewbie/domain/` |
| Matcher | Candidate selection, negotiation orchestration, offer creation | `src/crewbie/matching/` |
| Agents | Delegate and host policies; optional LLM layer | `src/crewbie/agents/` |
| Persistence | SQLAlchemy models, repositories, unit of work | `src/crewbie/persistence/` |
| Outbox | Durable queue of Discord side effects | `src/crewbie/persistence/outbox.py` + `src/crewbie/discord_bot/worker.py` |
| Discord bot | Slash commands, buttons, modals, thread management, facilitation | `src/crewbie/discord_bot/` |
| Telemetry | Public-safe event log and SSE stream | `src/crewbie/telemetry/` |
| Mission Control | Visualization (existing Next.js app) | `apps/web/` |

API and bot run in one process (`python -m crewbie`): Uvicorn serves FastAPI, and the discord.py client plus the
outbox worker run as asyncio tasks started in the FastAPI lifespan. They share the database, never in-memory
state, so they can be split into two processes later without code changes.

## 2. Directory structure

```
.
├── CLAUDE.md
├── README.md
├── pyproject.toml                  # uv, ruff, mypy, pytest config
├── uv.lock
├── Dockerfile
├── .env.example
├── src/
│   └── crewbie/
│       ├── __init__.py
│       ├── __main__.py             # entrypoint: runs uvicorn with app factory
│       ├── config.py               # pydantic-settings; `python -m crewbie.config check`
│       ├── logging.py              # JSON logging, redaction filter
│       ├── domain/                 # pure, no IO, fully typed
│       │   ├── event_key.py
│       │   ├── windows.py          # TimeWindow value object: overlap, intersect, hull, duration
│       │   ├── budget.py           # BudgetBand enum + ordering
│       │   ├── vibe.py
│       │   ├── intent.py           # SharedIntent, PrivateEnvelope (frozen dataclasses)
│       │   ├── room.py             # derive_room_state(memberships) -> RoomState
│       │   ├── offer.py            # Offer rules: expiry, staleness
│       │   └── errors.py           # DomainError subclasses with stable codes
│       ├── agents/
│       │   ├── protocol.py         # Proposal, Verdict, Reply (no reason field)
│       │   ├── delegate.py         # DelegatePolicy (deterministic guard + optional LLM chooser)
│       │   ├── host.py             # HostPolicy: fan-out to member delegates, merge counters
│       │   ├── llm/
│       │   │   ├── client.py       # thin Anthropic wrapper, timeouts, retries
│       │   │   ├── schemas.py      # strict output schemas
│       │   │   └── prompts/        # .md prompt templates with delimited data blocks
│       │   └── aliases.py          # per-room opaque actor refs (member-1, member-2)
│       ├── matching/
│       │   ├── prescore.py
│       │   ├── negotiation.py      # run_negotiation(joiner, host, max_rounds)
│       │   └── matcher.py          # match_intent(intent) -> Offer
│       ├── services/               # application layer; one module per use case
│       │   ├── installs.py
│       │   ├── linking.py
│       │   ├── discovery.py
│       │   ├── intents.py
│       │   ├── offers.py
│       │   ├── rooms.py
│       │   └── updates.py
│       ├── persistence/
│       │   ├── db.py               # engine, session factory, migrations bootstrap
│       │   ├── tables.py           # SQLAlchemy 2.0 typed mappings
│       │   ├── crypto.py           # Fernet envelope encryption
│       │   ├── unit_of_work.py
│       │   ├── outbox.py
│       │   └── repositories/
│       │       ├── installs.py
│       │       ├── events.py
│       │       ├── intents.py
│       │       ├── rooms.py
│       │       ├── offers.py
│       │       └── updates.py
│       ├── api/
│       │   ├── app.py              # create_app(); lifespan starts bot + workers
│       │   ├── auth.py             # bearer token -> Install
│       │   ├── rate_limit.py
│       │   ├── errors.py           # DomainError -> HTTP mapping
│       │   ├── schemas.py          # request/response models
│       │   └── routers/
│       │       ├── health.py
│       │       ├── installs.py
│       │       ├── rooms.py
│       │       ├── intents.py
│       │       ├── offers.py
│       │       ├── updates.py
│       │       ├── stream.py
│       │       └── admin.py
│       ├── discord_bot/
│       │   ├── client.py           # discord.Client subclass, command tree sync
│       │   ├── commands/
│       │   │   ├── link.py
│       │   │   └── crew.py         # /crew leave, /crew status, /crew meetpoint
│       │   ├── views/
│       │   │   ├── board_card.py   # Join button
│       │   │   └── join_modal.py
│       │   ├── worker.py           # outbox consumer
│       │   ├── icebreaker.py
│       │   ├── facilitation.py     # reminders, mention Q&A
│       │   └── messages.py         # all user-facing strings in one place
│       ├── workers/
│       │   ├── offer_sweeper.py
│       │   ├── room_lifecycle.py   # close/archive by time
│       │   └── reminders.py
│       └── telemetry/
│           ├── public_events.py    # allowlisted serializer
│           └── sse.py
├── skills/
│   └── crewbie-unlocks/
│       ├── SKILL.md
│       └── scripts/
│           └── crew.py
├── apps/
│   └── web/                        # Mission Control (existing)
├── scripts/
│   └── dev/
│       ├── seed.py
│       └── simulate.py             # drive N synthetic intents against a local server
├── tests/
│   ├── conftest.py
│   ├── unit/                       # domain, agents, matching
│   ├── integration/                # api + db, bot worker with fake Discord
│   ├── privacy/                    # envelope leak tests
│   ├── skill/                      # crew.py against a test server
│   └── e2e/                        # marked e2e; needs running server
├── docs/
│   └── spec/
└── legacy/                         # previous prototype, read-only reference
    ├── services/
    ├── integrations/
    ├── apps_chat_bot/
    └── tests/
```

## 3. Data model

Mermaid ERD (all timestamps UTC in storage; displayed in `America/Phoenix`):

```mermaid
erDiagram
  INSTALL ||--o{ INTENT : submits
  INSTALL ||--o| DISCORD_LINK : has
  INSTALL ||--o{ LINK_CODE : requests
  INSTALL ||--o{ UPDATE : receives
  EVENT ||--o{ INTENT : for
  EVENT ||--o{ ROOM : for
  INTENT ||--|| ENVELOPE : has_private
  INTENT ||--o{ OFFER : receives
  INTENT ||--o| MEMBERSHIP : becomes
  ROOM ||--o{ MEMBERSHIP : contains
  ROOM ||--o{ NEGOTIATION : hosts
  NEGOTIATION ||--o{ NEGOTIATION_STEP : records
```

Tables (columns abbreviated; all have `created_at`, `updated_at`):

| Table | Key columns |
|---|---|
| `installs` | `id` (uuid), `token_hash` (unique), `kind` (`cubbie`/`discord`), `is_synthetic` |
| `discord_links` | `install_id` (pk, fk), `discord_user_id` (unique), `discord_username` |
| `link_codes` | `code` (pk), `install_id`, `expires_at`, `used_at` |
| `events` | `event_key` (pk), `source_url`, `title`, `location_label`, `date`, `start_time`, `end_time` |
| `intents` | `id`, `install_id`, `event_key`, `window_start`, `window_end`, `activity_min_minutes`, `budget_band`, `vibe`, `interests` (json), `state`, unique(`install_id`,`event_key`) where state live |
| `envelopes` | `intent_id` (pk), `ciphertext` (Fernet of `{flex_earliest, flex_latest, budget_cap_usd}`) |
| `rooms` | `id`, `event_key`, `status`, `version`, derived: `window_start`, `window_end`, `budget_band`, `vibe`, `top_interests`, `size`; `discord_thread_id`, `board_message_id` |
| `memberships` | `id`, `room_id`, `intent_id` (unique), `alias` (`member-N`), `effective_start`, `effective_end`, `joined_at`, `left_at` |
| `offers` | `id`, `intent_id`, `type`, `room_id` (nullable), `room_version`, `proposal_start`, `proposal_end`, `expires_at`, `state` |
| `negotiations` | `id`, `intent_id`, `room_id`, `outcome`, `rounds` |
| `negotiation_steps` | `negotiation_id`, `round`, `actor_kind`, `actor_alias`, `proposal_start`, `proposal_end`, `verdict` |
| `updates` | `seq` (autoincrement), `install_id`, `kind`, `payload` (json, public-safe), `created_at` |
| `outbox` | `id`, `kind`, `payload` (json), `dedupe_key` (unique), `state`, `attempts`, `next_attempt_at`, `last_error` |
| `public_events` | `seq`, `type`, `payload` (json, allowlisted), `created_at` |

Rules:

- Only `services/` opens transactions (unit of work). Repositories never commit.
- Every state change that needs a Discord action writes an `outbox` row in the same transaction.
- Every state change the student should hear about writes an `updates` row in the same transaction.

## 4. Data flows

### 4.1 Register and link

```mermaid
sequenceDiagram
  participant S as Student
  participant C as Cubbie
  participant P as crew.py
  participant A as API
  participant D as Discord bot
  C->>P: crew.py register
  P->>P: generate token, save ~/.config/crewbie/install.json
  P->>A: POST /v1/installs (Bearer token)
  A-->>P: install_id
  C->>P: crew.py link
  P->>A: POST /v1/installs/me/link-codes
  A-->>P: code K7QX2M, invite URL, expires_at
  P-->>C: LINK_CODE K7QX2M / INVITE https://discord.gg/...
  C-->>S: "Join the Crewbie server and type /crew link K7QX2M"
  S->>D: /crew link code:K7QX2M
  D->>A: linking.complete(code, discord_user_id) (in-process service call)
  A-->>D: ok
  D-->>S: ephemeral "Linked. Cubbie can now add you to crews."
```

### 4.2 Discovery during recommendations

```mermaid
sequenceDiagram
  participant C as Cubbie
  participant P as crew.py
  participant A as API
  C->>P: crew.py rooms --event '{source_url,date,start_time}' (up to 5)
  P->>A: GET /v1/rooms?... (one call per event or batch)
  A->>A: compute event_key, query rooms status in (open, active)
  A-->>P: [{size:2, window:"16:00-18:00", vibe:chill, budget_band:low, top_interests:[...]}]
  P-->>C: ROOMS <event_ref> 1 / ROOM size=2 window=4:00-6:00pm vibe=chill
  C->>C: add "2 students going, chill" to that card
```

### 4.3 Submit, negotiate, offer

```mermaid
sequenceDiagram
  participant C as Cubbie
  participant P as crew.py
  participant A as API
  participant M as Matcher
  participant J as Joiner delegate
  participant H as Room host
  participant MD as Member delegates
  C->>C: student confirms activity and says yes to matching
  C->>P: crew.py submit --file intent.json
  P->>A: POST /v1/intents
  A->>A: validate, upsert event, store intent + encrypted envelope
  A->>M: match_intent(intent) (time budget 10 s)
  M->>M: load rooms for event_key, hard filters, prescore, top 3
  loop each candidate room (max 3)
    M->>J: propose(initial = overlap or joiner window)
    J-->>M: Proposal P1
    M->>H: evaluate(P1)
    H->>MD: evaluate(P1) each
    MD-->>H: accept / counter / reject
    H-->>M: Reply
    Note over M: up to 3 rounds, alternate turns, record steps
  end
  M->>A: best agreement or none
  A->>A: create offer (join or new_room), updates row offer_ready
  A-->>P: {intent_id, offer}
  P-->>C: OFFER ... / CREW size=2 window=5:00-6:30pm vibe=chill
  C-->>S: "There's a crew: 2 people, 5:00 to 6:30, chill. Join?"
```

### 4.4 Accept and thread creation

```mermaid
sequenceDiagram
  participant C as Cubbie
  participant P as crew.py
  participant A as API
  participant O as Outbox
  participant D as Discord bot
  C->>P: crew.py accept --offer <id>
  P->>A: POST /v1/offers/{id}/accept (Idempotency-Key)
  A->>A: check linked, not expired, room.version unchanged
  A->>A: tx: membership, extend effective windows, derive room, version++
  alt room size becomes 2
    A->>O: create_thread, add_member x2, post_message(icebreaker), dm_user x2, upsert_board_card
  else room size > 2
    A->>O: add_member, post_message(welcome), dm_user, upsert_board_card
  else room size 1 (new_room)
    A->>O: upsert_board_card
  end
  A->>A: updates rows: joined / room_active / window_changed for affected installs
  A-->>P: {state: joined, room, thread_url or null}
  D->>O: poll jobs
  D->>D: create private thread, add users, post icebreaker, DM links
  D->>A: store discord_thread_id, mark jobs done
```

### 4.5 Scheduled check-in

```mermaid
sequenceDiagram
  participant C as Cubbie (check-in)
  participant P as crew.py
  participant A as API
  C->>P: crew.py updates
  P->>A: GET /v1/updates?cursor=<saved>
  A-->>P: [{kind: room_active, thread_url}, ...], cursor
  P->>P: save cursor
  P-->>C: UPDATE room_active "Board game night" THREAD https://discord.com/channels/...
  C-->>S: "Someone joined your crew for board game night. Chat: <link>"
```

### 4.6 Leave

`crew.py leave --intent <id>` or `/crew leave` in the thread → `services.rooms.leave` → membership `left_at` set,
room derived again, `version++`, outbox `remove_member` + `post_message` ("member-2 left; plan is now 4:00 to
6:30"), updates `window_changed` for remaining members, status `closed` if empty.

### 4.7 Discord-only join from the board

Join button → modal → `services.intents.submit` with a Discord install (created on first use) → matching scoped
to that board room first (it is the only candidate) → if agreement, ephemeral "Join this crew? [Confirm]" →
confirm calls `services.offers.accept`. If no agreement, ephemeral explanation that the timing does not fit and an
offer to start a new crew.

## 5. State machines

Intent:

```mermaid
stateDiagram-v2
  [*] --> matching
  matching --> offered
  offered --> joined: accept
  offered --> declined: decline
  offered --> matching: stale
  offered --> expired: timeout
  joined --> withdrawn: leave
  expired --> matching: resubmit
```

Offer: `open → accepted | declined | expired | stale`.

Room:

```mermaid
stateDiagram-v2
  [*] --> open: first member
  open --> active: 2nd member (thread created)
  active --> active: join / leave (size >= 2)
  active --> open: leave to size 1 (thread kept)
  open --> closed: size 0
  active --> closed: window end + 2h
  closed --> archived: window end + 24h
```

## 6. Process model and concurrency

- One Uvicorn worker. SQLite in WAL mode. All writes go through the unit of work.
- Accept and matching for the same room are serialized with a per-room `asyncio.Lock` registry plus the
  `room.version` check (optimistic concurrency) so a future multi-process deployment stays correct.
- LLM calls run outside DB transactions. The matcher snapshots room state, negotiates, then the offer stores the
  `room_version` it used.

## 7. Reuse from the previous prototype

| Legacy module | Reuse |
|---|---|
| `legacy/services/participants/` | Ideas: scoped consent, probe caps, minimized views. Do not import. |
| `legacy/services/negotiation/coordinator.py` | Ideas: bounded rounds, event emission. Rewrite smaller. |
| `legacy/services/realtime/schema.py` | Copy the allowlist approach into `telemetry/public_events.py`. |
| `legacy/apps_chat_bot/discord_live.py` | Reference for discord.py setup and `AllowedMentions.none()`. |
| `skills/crewbie-unlocks/SKILL.md` | Kept; "Find a crew" section rewritten per 06-CUBBIE-SKILL.md. |
| `apps/web/` | Kept; add an adapter for the new stream in Phase 7. |
