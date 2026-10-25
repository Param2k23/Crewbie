# Discord bot

Library: `discord.py` (the legacy prototype pins 2.6.4; check for a newer stable release at least two weeks old
and pin exactly). Uses application (slash) commands, buttons and modals. No privileged intents (C-4).

## 1. Guild layout (created by the owner, see 08-INPUTS-FROM-OWNER.md)

| Channel | Purpose | Bot permissions |
|---|---|---|
| `#welcome` | Explains Crewbie and `/crew link` | Send Messages |
| `#crew-board` | One card per open/active room; read-only for members | Send Messages, Embed Links, Manage Messages |
| `#crews` | Parent text channel for private room threads; members cannot post at top level | Create Private Threads, Send Messages in Threads, Manage Threads |

Gateway intents: `Intents.default()` minus `message_content`. Messages that mention the bot and DMs still carry
content.

## 2. Commands

| Command | Where | Behavior |
|---|---|---|
| `/crew link code:<CODE>` | anywhere | FR-LNK-02. Ephemeral reply. |
| `/crew status` | anywhere | Ephemeral list of the caller's crews: event, window, size, thread link |
| `/crew leave` | room thread | Withdraw caller's intent for this room; confirm with a button first |
| `/crew meetpoint` | room thread | P2: poll with up to 3 options typed by the caller |
| `/crew help` | anywhere | Ephemeral explanation |

Commands are synced to the guild (`CREWBIE_DISCORD_GUILD_ID`) on startup for instant availability.

## 3. Outbox jobs

| Kind | Payload | Action | Idempotency |
|---|---|---|---|
| `create_thread` | `room_id` | Create private thread in `#crews`, `invitable=False`; store id on room | Skip if `rooms.discord_thread_id` set |
| `add_member` | `room_id`, `install_id` | `thread.add_user` | Discord ignores duplicates |
| `remove_member` | `room_id`, `install_id` | `thread.remove_user` | Same |
| `post_message` | `room_id`, `template`, `vars` | Render from `messages.py` and post | `dedupe_key` per logical message |
| `dm_user` | `install_id`, `template`, `vars` | DM; on `Forbidden` (DMs closed) write `link_required`-style update so Cubbie relays instead | `dedupe_key` |
| `upsert_board_card` | `room_id` | Create or edit the card; delete when room closes | Card id stored on room |
| `archive_thread` | `room_id` | Lock and archive | Skip if archived |

Synthetic installs (`is_synthetic`) are skipped by `add_member` and `dm_user`.

Worker loop: select due jobs (`state in (pending, retry) and next_attempt_at <= now`) ordered by id, batch of 20,
process sequentially per room (jobs for one room keep order), backoff per NFR-REL-01. Handle Discord 429 by
honoring `retry_after`.

## 4. Icebreaker

Trigger: `create_thread` completes. Inputs (public-safe only): event title, location label, date, room window,
room vibe, top interests with counts, member display names (Discord usernames of non-synthetic members).

LLM prompt (when `CREWBIE_LLM_MODE=on`) produces at most 900 characters with: a one-line welcome naming the
event and time, one question tied to the most shared interest, and one light logistics prompt ("where should
you meet?"). Tone follows room vibe: chill (low key), social (warm), active (energetic). No emojis beyond two.
No claims about free food, prices or availability. Fallback template in `messages.py`:

```
Welcome, crew. You're all going to {event_title} on {date_label}, {window_label} at {location_label}.
{interest_count} of you are into {top_interest}. What got you into it?
Pick a meeting spot: reply with one, or use /crew meetpoint.
```

## 5. Facilitation

- Welcome message when a member joins an active room: `"{username} joined. Plan: {window_label}."`
- Window change notice (FR-ROM-04).
- Reminder 60 minutes before window start (FR-BOT-07), via `workers/reminders.py` writing a `post_message` job.
- Mention Q&A (FR-BOT-08): when a message in a room thread mentions the bot, answer using only event public
  fields and room derived state. Message text is untrusted: wrap in `<member_message>` data tags; refuse requests
  to reveal other members' info, change the plan, or contact anyone. Without LLM: reply with the plan summary.
- Quiet nudge (P2): if a thread has no human messages 3 hours before window start, post one nudge.

## 6. Board card

Embed: event title, date, window, size, vibe, budget band, top interests, "Join" button (custom id
`crew-join:<room_id>`). Updated on every room version change. Removed when the room closes.

Join flow (FR-BOT-06): button → modal fields: "Earliest you can start" (HH:MM), "Latest you can stay" (HH:MM),
"Minimum time you want there (minutes)", "Budget: low / mid / high", "Vibe: chill / social / active". The
student's window is set to the room window clipped to their earliest/latest; flex equals the earliest/latest
they typed. Then matching runs against that room only, and an ephemeral confirm button accepts the offer.

## 7. Messages

All user-facing strings live in `discord_bot/messages.py` as templates with named variables. No string literals
in handlers. All posts use `AllowedMentions.none()`; mentions of members are added only through explicit user
mention objects the bot constructs for its own welcome messages.
