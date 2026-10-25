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
