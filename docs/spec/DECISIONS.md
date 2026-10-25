# Decisions

| Date | Requirement | Decision |
|---|---|---|
| 2026-10-25 | I-01 (07 Phase 0) | `crewbie-v2` is cut from the latest `origin/master` (fast-forwarded to f7635ef, which already contains `integration/crewbie` via PR #6). That state is what moves into `legacy/`. The owner is the only committer for now. |
| 2026-10-25 | 07 Phase 0, task 6 | The old `.env.example` is replaced. Its only still-used variable, `NEXT_PUBLIC_CREWBIE_API_URL` (read by `apps/web`), is kept as a commented line at the bottom of the new file. |
| 2026-10-25 | 09 section 5 | Dependency age rule is enforced with `exclude-newer = "2026-10-11T00:00:00Z"` in `[tool.uv]` (14 days before today). Move the date forward when new packages are needed. |
| 2026-10-25 | SRS 5.3 | "Ties go to the vibe of the earliest member" is implemented as: among the tied vibes, pick the vibe held by the earliest-joined member (ties on join time broken by alias). Otherwise a member holding a non-tied vibe would decide the result. |
| 2026-10-25 | SRS 5.3 | `RoomState.window` is `None` when members' effective windows share no time (or there are no members). Callers must not offer a join that would produce this; the matcher enforces it in Phase 3. |
| 2026-10-25 | 07 Phase 1, task 2 | In `CREWBIE_ENV=dev` with no `CREWBIE_ENVELOPE_KEY`, a key is generated once and stored at `data/dev_envelope.key` (mode 0600, git-ignored) so envelopes survive restarts. Prod requires the variable. |
| 2026-10-25 | FR-OFR-01, 5.2 | `budget_cap_usd` is stored as a float inside the encrypted envelope. Money amounts here are only compared, never summed, so float is acceptable. |
| 2026-10-25 | NFR-REL-01 | "Backoff 1, 2, 4, 8, 16 s; then marked failed" is implemented as 5 retries after the first failure (6 attempts in total). |
| 2026-10-25 | 02 section 3 | `rooms.version` starts at 1 and every `apply_state` that follows a join, leave or agreement bumps it. Offers store the version they were computed against. |
| 2026-10-25 | 09 section 1 | `api` sits above `discord_bot` and `workers` in the import-linter layers. `api/app.py` is the composition root that starts them in its lifespan (02 section 1), so it must import them. They remain independent of each other. |
| 2026-10-25 | 02 section 5 | Intent state machine gains `matching -> withdrawn` and `offered -> withdrawn`. FR-INT-06 and FR-INT-03 (replace an unjoined intent) need a student to leave before joining. |
| 2026-10-25 | 03 section 1 | New error codes outside the contract table: `FORBIDDEN` (403, seeding in prod), and bot-only `LINK_CODE_INVALID` (reason expired/used/unknown) and `LINK_CONFLICT` (reason discord_user_linked/install_linked; the bot confirms and retries with `replace=True`). |
| 2026-10-25 | NFR-SEC-04 | Admin endpoints return 404 when `CREWBIE_ADMIN_TOKEN` is unset, 401 for a missing or wrong token. |
| 2026-10-25 | 06 section 1 | `crew.py accept` prints `THREAD none` when the room has one member (no thread exists), and `THREAD pending` only for rooms of 2+. SKILL.md (Phase 6) must say so. |
| 2026-10-25 | 06 section 1 | `crew.py` exit codes by API error: LINK_REQUIRED, OFFER_EXPIRED, OFFER_STALE, ALREADY_IN_ROOM and EVENT_STARTED give 2; VALIDATION_FAILED, NOT_FOUND and OFFER_CLOSED give 4; RATE_LIMITED, UNAUTHORIZED (after one automatic re-register) and INTERNAL give 5. |
| 2026-10-25 | FR-UPD-01 | `link_required` is reserved but not emitted: the 409 on accept already carries the code synchronously. `room_active` is emitted by the bot once the thread exists (Phase 4). |
| 2026-10-25 | FR-OFR-01 | Accepting a `new_room` offer fails with `EVENT_STARTED` once the student's own window has ended; accepting a `join` offer fails once the room window has started. |
| 2026-10-25 | FR-ROM-04 | `window_changed` fires whenever a join changes the room window, including when it narrows because the joiner's window is shorter, since the existing members' plan did move. |
| 2026-10-25 | 02 section 6 | SQLite connections use `BEGIN IMMEDIATE` so concurrent writers queue on the busy timeout instead of failing on lock upgrade. Every unit of work therefore takes the write lock; acceptable at this scale. |
| 2026-10-25 | FR-INS-04 | The per-IP registration limit uses the socket peer address. Behind a reverse proxy (Phase 5) this must be changed to trust the proxy's `X-Forwarded-For`, or all students share one bucket. |
| 2026-10-25 | 03 section 1 | Only successful responses are stored for `Idempotency-Key` replay. Reusing a key on a different path returns `VALIDATION_FAILED`. |
| 2026-10-25 | FR-INT-04 | Until Phase 3 adds the time budget, matching is synchronous and `POST /v1/intents` always returns an offer (never 202). The route already returns 202 if the matcher returns no offer. |
