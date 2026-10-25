# CLAUDE.md

Instructions for Claude Code working in the Crewbie repository.

## What this project is

Crewbie lets a student confirm a campus activity in Cubbie (an iMessage assistant), then optionally get matched
with other students going to the same activity. Matching is done by server-side agents that negotiate on each
student's behalf. Matched students land in a private Discord thread where a Crewbie bot posts an icebreaker and
helps the group coordinate.

The full specification lives in `docs/spec/`. Read it before writing code:

1. `docs/spec/00-README.md` (index and reading order)
2. `docs/spec/01-SRS.md` (requirements; every requirement has an ID such as `FR-INT-03`)
3. `docs/spec/02-ARCHITECTURE.md` (components, data model, data flows, state machines)
4. `docs/spec/03-API-CONTRACT.md`
5. `docs/spec/04-AGENT-PROTOCOL.md`
6. `docs/spec/05-DISCORD-BOT.md`
7. `docs/spec/06-CUBBIE-SKILL.md`
8. `docs/spec/07-IMPLEMENTATION-PLAN.md` (phases, tasks, definition of done)
9. `docs/spec/08-INPUTS-FROM-OWNER.md` (what to ask the owner for, and when)
10. `docs/spec/09-ENGINEERING-STANDARDS.md`

If the spec and the code disagree, the spec wins. If the spec is ambiguous or contradicts itself, stop and ask
the owner one specific question instead of guessing. Record the answer in `docs/spec/DECISIONS.md`
(create it if missing) with the date and the requirement ID it affects.

## How to work

- Work phase by phase, in the order of `07-IMPLEMENTATION-PLAN.md`. Do not start a phase until the previous
  phase's definition of done passes.
- At the start of each phase, check `08-INPUTS-FROM-OWNER.md` for inputs that phase needs. If any are missing,
  ask for them before writing code that depends on them. Ask for all of a phase's missing inputs in one message.
- Never ask the owner to paste a secret (bot token, API key, admin token, encryption key) into the chat.
  Tell them which variable to set in `.env` and confirm by running `python -m crewbie.config check`, which
  reports only whether each variable is present and well formed.
- Reference requirement IDs in commit messages and test names, for example
  `test_fr_match_04_rejects_budget_two_bands_apart`.
- Keep a short progress log in `docs/spec/PROGRESS.md`: phase, what was done, what is left, open questions.

## Repository rules

- New code goes under `src/crewbie/` (server, agents, bot) and `skills/crewbie-unlocks/` (Cubbie Skill).
- The previous multi-agent prototype is moved to `legacy/` in Phase 0. Read it for ideas; do not import from it.
- `apps/web/` (Mission Control) stays where it is. It is low priority (Phase 7).
- Layering: `domain` imports nothing from `api`, `persistence`, `discord_bot` or `agents.llm`. See
  `09-ENGINEERING-STANDARDS.md` for the full dependency rules.

## Commands

```bash
uv sync                                  # install dependencies
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run pytest                            # unit + integration
uv run pytest -m e2e                     # needs a running server; see 07-IMPLEMENTATION-PLAN.md
uv run python -m crewbie.config check    # verify .env without printing secrets
uv run python -m crewbie                 # run API + Discord bot in one process
uv run python scripts/dev/seed.py        # seed demo data (requires CREWBIE_ENV=dev)
```

## Definition of done for any change

- `ruff`, `mypy` and `pytest` pass.
- New behavior has tests that name the requirement ID.
- No private envelope field (see `01-SRS.md` section 5.2) appears in logs, API responses, Discord messages,
  LLM prompts for other agents, or the Mission Control stream. `tests/privacy/` enforces this; keep it green.
