# Crewbie

Text Cubbie. Find your crew. Make plans happen.

Crewbie is a Skill built entirely on [Cubbie](https://hackathon.cubbie.ai), the iMessage assistant. A student
texts Cubbie, which finds student-only perks first and plans around their week. Only if the student says yes,
Crewbie finds other students going to the same event, lets private agents agree on a time inside each student's
hidden limits, and opens a private Discord thread with an icebreaker. Built for the Cubbie hackathon.

## How the pieces fit

| Piece | Where | What it does |
|---|---|---|
| Cubbie Skill | `skills/crewbie-unlocks/` | `SKILL.md` (tone, student-first ranking, language, consent) and `scripts/crew.py` (the only way Cubbie talks to the server) |
| Server | `src/crewbie/` | FastAPI API, SQLite, deterministic rule-based agents (delegate, host, matcher), outbox worker |
| Discord bot | `src/crewbie/discord_bot/` | Linking, `#crew-board` cards, private threads, icebreaker, plan-moved notices (English only) |
| Website | `apps/web/` | Landing page at `/unlocks` (Next.js, deployed on Vercel). Mission Control demo routes remain but are not developed |
| Ops | `deploy/`, `scripts/ops/` | Docker, Caddy (automatic HTTPS), on/off/deploy/backup scripts for one AWS EC2 instance |
| Spec | `docs/spec/` | Requirements, architecture, API, protocol, plan, decisions log, progress log |

Privacy: each student's private limits (earliest/latest time and budget cap) are stored only as encrypted
data, never logged, never sent to other students or Discord. `tests/privacy/` enforces it.

## Status (2026-10-26)

Phases 0 to 6 and the website are complete; Phase 7 was skipped by decision (Mission Control dropped, LLM agents
deferred). The agents are rule-based, not LLM. The hackathon is over and the AWS server has been torn down, so
the Skill's default server address no longer answers: Cubbie falls back to a normal solo plan. To bring the
whole system back, follow [docs/REBUILD.md](docs/REBUILD.md).

## Run it locally

```bash
uv sync
cp docs/spec/env.example .env          # fill values; set CREWBIE_DISCORD_ENABLED=false to skip Discord
uv run python -m crewbie.config check  # reports which variables are present, never their values
uv run python -m crewbie               # API + Discord bot
uv run pytest                          # 439 tests
```

Website: `cd apps/web && npm install && npm run dev`, then open `/unlocks`.

## Where to read next

- [docs/REBUILD.md](docs/REBUILD.md): bring the server back, or tear it down again
- [docs/DEMO_BRIEF.md](docs/DEMO_BRIEF.md): the pitch, what is true, what not to claim
- [docs/spec/00-README.md](docs/spec/00-README.md): the full specification
- [docs/spec/DECISIONS.md](docs/spec/DECISIONS.md) and [docs/spec/PROGRESS.md](docs/spec/PROGRESS.md): why things are the way they are
- [docs/spec/LIVE_TEST.md](docs/spec/LIVE_TEST.md): what was tested live with real Cubbie students
- Known gaps: Discord messages are English only; a non-English live Cubbie chat, a Join from the board card with
  a fresh account, and the service-offline path were covered by automated tests only.
