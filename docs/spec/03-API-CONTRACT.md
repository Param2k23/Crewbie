# API contract (v1)

Base URL: `CREWBIE_PUBLIC_URL` (HTTPS). All bodies JSON, UTF-8. Times are ISO 8601 with offset.

## 1. Conventions

- Auth: `Authorization: Bearer <install token>` unless marked public or admin.
- Idempotency: `POST /v1/intents` and `POST /v1/offers/{id}/accept|decline` accept `Idempotency-Key`
  (UUID). Same key + same install within 24 h returns the stored response.
- Errors:

```json
{ "error": { "code": "OFFER_STALE", "message": "The crew changed. A new offer is on its way.", "details": {} } }
```

| Code | HTTP | Meaning |
|---|---|---|
| `UNAUTHORIZED` | 401 | Missing or unknown token |
| `RATE_LIMITED` | 429 | Includes `Retry-After` |
| `VALIDATION_FAILED` | 422 | `details.fields` lists problems |
| `NOT_FOUND` | 404 | Resource missing or not owned by caller |
| `LINK_REQUIRED` | 409 | `details.link_code`, `details.invite_url`, `details.expires_at` |
| `ALREADY_IN_ROOM` | 409 | Install already a member of a room for this event |
| `OFFER_EXPIRED` | 410 | Offer past expiry |
| `OFFER_STALE` | 409 | Room changed; rematching started; watch updates |
| `OFFER_CLOSED` | 409 | Offer already accepted or declined |
| `EVENT_STARTED` | 409 | Room or event window already started |
| `INTERNAL` | 500 | Includes `request_id` |

- Every response has header `X-Request-Id`.

## 2. Endpoints

### `GET /healthz` (public)

```json
{ "status": "ok", "db": "ok", "discord": "connected", "outbox_backlog": 0, "llm_mode": "on" }
```

### `POST /v1/installs`

Body: `{ "client": "crew.py/1.0" }`. Token comes from the bearer header.

Response 201 (or 200 if existing): `{ "install_id": "8c1e...", "discord_linked": false }`

### `GET /v1/installs/me`

`{ "install_id": "...", "discord_linked": true, "discord_username": "dhaval" }`

### `DELETE /v1/installs/me`

204. Deletes per NFR-PRV-03.

### `POST /v1/installs/me/link-codes`

`{ "code": "K7QX2M", "expires_at": "...", "invite_url": "https://discord.gg/abcd", "command": "/crew link code:K7QX2M" }`

### `GET /v1/rooms`

Query: `event_key` or (`source_url`, `date`, `start_time`).

```json
{
  "event_key": "3f9a1c0b7d2e4a11",
  "rooms": [
    { "room_id": "r_01", "size": 2, "status": "active",
      "window": { "start": "2026-10-30T16:00:00-07:00", "end": "2026-10-30T18:00:00-07:00" },
      "vibe": "chill", "budget_band": "low", "top_interests": ["board-games", "strategy"] }
  ]
}
```

### `POST /v1/rooms/lookup`

Batch form of the above. Body: `{ "events": [ {"ref":"a","source_url":"...","date":"...","start_time":"18:00"} ] }`
(max 5). Response: `{ "results": [ {"ref":"a","event_key":"...","rooms":[...]} ] }`.

### `POST /v1/intents`

```json
{
  "event": {
    "source_url": "https://lib.asu.edu/events/board-game-night",
    "title": "Board game night",
    "location_label": "Hayden Library, Tempe",
    "date": "2026-10-30",
    "start_time": "18:00",
    "end_time": "21:00"
  },
  "shared": {
    "window": { "start": "2026-10-30T18:00:00-07:00", "end": "2026-10-30T20:00:00-07:00" },
    "activity_min_minutes": 90,
    "budget_band": "low",
    "vibe": "chill",
    "interests": ["board-games", "strategy"]
  },
  "private": {
    "flex": { "earliest": "2026-10-30T17:30:00-07:00", "latest": "2026-10-30T20:30:00-07:00" },
    "budget_cap_usd": 15
  }
}
```

Response 201, matched within budget:

```json
{
  "intent_id": "i_7f2",
  "state": "offered",
  "offer": {
    "offer_id": "o_19a",
    "type": "join",
    "expires_at": "2026-10-25T20:15:00Z",
    "room": { "room_id": "r_01", "size": 2, "vibe": "chill", "budget_band": "low",
              "top_interests": ["board-games"] },
    "proposal": { "start": "2026-10-30T18:00:00-07:00", "end": "2026-10-30T19:30:00-07:00" },
    "window_changed_for_room": false
  }
}
```

`type: "new_room"` has `room: null` and `proposal` equal to the student's window.

Response 202 when matching continues: `{ "intent_id": "i_7f2", "state": "matching" }`.

### `GET /v1/intents/{id}`

`{ "intent_id": "...", "state": "joined", "room_id": "r_01", "thread_url": "https://discord.com/channels/..." }`
(no private fields).

### `POST /v1/intents/{id}/withdraw`

`{ "intent_id": "...", "state": "withdrawn" }`

### `POST /v1/offers/{id}/accept`

200:

```json
{ "state": "joined", "room": { "room_id": "r_01", "size": 3, "status": "active" },
  "thread_url": "https://discord.com/channels/<guild>/<thread>" }
```

`thread_url` is null while the thread job is pending or the room has one member; the `room_active` update
carries it later.

### `POST /v1/offers/{id}/decline`

`{ "state": "declined" }`

### `GET /v1/updates?cursor=<int>&limit=<int ≤ 50>`

```json
{
  "cursor": 42,
  "updates": [
    { "seq": 41, "kind": "member_joined", "intent_id": "i_7f2", "event_title": "Board game night",
      "room": { "size": 3 } },
    { "seq": 42, "kind": "window_changed", "intent_id": "i_7f2", "event_title": "Board game night",
      "window": { "start": "...", "end": "..." } }
  ]
}
```

Kinds: `offer_ready`, `joined`, `room_active`, `member_joined`, `member_left`, `window_changed`, `room_closed`,
`link_required`, `offer_expired`.

### `GET /v1/stream` (public, read-only)

SSE. `event: <type>` and `data: <public-safe JSON>`. Supports `Last-Event-ID`.

### Admin (`X-Admin-Token`)

- `GET /v1/admin/rooms`: rooms with member aliases, sizes, outbox status.
- `POST /v1/admin/rooms/{id}/close`
- `POST /v1/admin/seed` (refused when `CREWBIE_ENV=prod`)
- `GET /v1/admin/outbox?state=failed`

## 3. Internal service calls from the bot

The bot calls application services directly (same process), not HTTP:
`linking.complete(code, discord_user_id, username)`, `installs.ensure_discord_install(discord_user_id)`,
`intents.submit(...)`, `offers.accept(...)`, `rooms.leave(...)`. Keep these signatures identical to what the HTTP
routers call so the bot can move to HTTP later.
