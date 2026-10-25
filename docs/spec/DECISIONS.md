# Decisions

| Date | Requirement | Decision |
|---|---|---|
| 2026-10-25 | I-01 (07 Phase 0) | `crewbie-v2` is cut from the latest `origin/master` (fast-forwarded to f7635ef, which already contains `integration/crewbie` via PR #6). That state is what moves into `legacy/`. The owner is the only committer for now. |
| 2026-10-25 | 07 Phase 0, task 6 | The old `.env.example` is replaced. Its only still-used variable, `NEXT_PUBLIC_CREWBIE_API_URL` (read by `apps/web`), is kept as a commented line at the bottom of the new file. |
| 2026-10-25 | 09 section 5 | Dependency age rule is enforced with `exclude-newer = "2026-10-11T00:00:00Z"` in `[tool.uv]` (14 days before today). Move the date forward when new packages are needed. |
