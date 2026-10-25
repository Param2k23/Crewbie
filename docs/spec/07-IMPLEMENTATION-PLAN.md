# Implementation plan

Work on branch `crewbie-v2` cut from `master`. Merge to `master` only at the end of Phase 6 (the Track 1 Skill
installs from `master`, so a broken `master` breaks the Track 1 entry).

Each phase lists inputs needed from the owner (see 08-INPUTS-FROM-OWNER.md), tasks, and a definition of done (DoD).

## Phase 0: Repository restructure and tooling

Inputs: none (confirm branch strategy, I-01).

Tasks:
1. `git mv services legacy/services`, `git mv integrations legacy/integrations`,
   `git mv apps/chat_bot legacy/apps_chat_bot`, `git mv tests legacy/tests`, `git mv scripts legacy/scripts`,
   move `requirements-discord.txt` into `legacy/`. Do not touch `apps/web`, `skills/`, `docs/`.
2. Add `legacy/README.md`: what it was, that it is not imported, pointer to `docs/integration/` history.
3. Create `pyproject.toml` (uv), `src/crewbie/` skeleton per 02-ARCHITECTURE.md, `tests/` skeleton.
4. Configure ruff (lint + format), mypy (strict for `domain`, `agents`, `matching`), pytest with markers
   `e2e`, `discord_live`; import-linter (or a test) enforcing layering.
5. `config.py` with pydantic-settings and `python -m crewbie.config check`.
6. Move `docs/spec/env.example` to `.env.example` (replace the old one).
7. CI: GitHub Actions running ruff, mypy, pytest on push.

DoD: `uv run pytest` passes (placeholder tests), `ruff`/`mypy` clean, `legacy/` not importable from `src/`.

## Phase 1: Domain and persistence

Inputs: none.

Tasks:
1. Domain: `event_key`, `TimeWindow`, `BudgetBand`, `Vibe`, `SharedIntent`, `PrivateEnvelope`,
   `derive_room_state`, offer rules, errors with stable codes.
2. Persistence: tables, repositories, unit of work, Fernet envelope encryption (dev key auto-generated in
   `CREWBIE_ENV=dev`; required in prod), SQLite WAL, simple migration bootstrap (Alembic SHOULD be used).
3. Property tests (Hypothesis) for windows and room derivation.

DoD: FR-EVT-01, 5.1, 5.3 covered by tests; envelope round-trip encryption test; coverage ≥ 85% in domain.

## Phase 2: API, auth, installs, discovery, intents without matching

Inputs: none.

Tasks:
1. FastAPI app factory, error mapping, request IDs, JSON logging with redaction filter.
2. Install auth (hash, constant-time compare), rate limiting (in-memory token bucket is fine).
3. Routers: health, installs, link-codes, rooms, rooms/lookup, intents (store only; matching stub returns
   `new_room`), offers accept/decline, updates, admin.
4. `crew.py` complete against this API; `tests/skill/`.
5. Privacy test harness `tests/privacy/`: submit intents with sentinel envelope values (e.g. 17:37, cap 913) and
   assert they appear nowhere in logs, responses, updates, public events.

DoD: AS-1 passes end to end via `crew.py` against a local server; privacy tests green.

## Phase 3: Agents and matcher (deterministic)

Inputs: none.

Tasks:
1. `agents/protocol.py`, `delegate.py` (guard + deterministic chooser), `host.py`.
2. `matching/prescore.py`, `negotiation.py`, `matcher.py`; per-room locks; time budget.
3. Offer creation with `room_version`; staleness on accept; rematch on stale.
4. Public events for each step (FR-MAT-09).
5. Tests: AS-2..AS-6 at service level; safety properties P-1, P-2, P-4, P-5.

DoD: all MAT and OFR P0 requirements tested; `scripts/dev/simulate.py` runs 50 synthetic intents across 3 events
with no errors and prints a room summary.

## Phase 4: Discord bot

Inputs: I-02 (Discord application, token, guild, channel IDs, invite), I-03 (test accounts).

Tasks:
1. Client with guild-synced commands; lifespan startup; health reporting.
2. `/crew link`, `/crew status`, `/crew leave`, `/crew help`.
3. Outbox worker and all job kinds; thread creation; DMs with fallback.
4. Icebreaker (template first), welcome, window change notice.
5. Board card + Join modal (P1).
6. Tests with a fake Discord adapter (protocol class) for the worker; one opt-in `discord_live` test that posts
   to a test channel.

DoD: AS-2, AS-7, AS-8 pass with two Discord test accounts on a local server.

## Phase 5: Deployment (AWS EC2)

Inputs: I-04 (AWS account with credits), I-05 (values from `10-AWS-DEPLOYMENT.md` A11), I-13 (repo visibility
for cloning on the server), secrets filled by the owner in `.env.prod`.

Tasks:
1. Walk the owner through `10-AWS-DEPLOYMENT.md` Part A, one section at a time, waiting for confirmation.
   Part A runs in parallel with tasks 2 to 4.
2. Create Part B files: `Dockerfile`, `deploy/docker-compose.yml`, `deploy/Caddyfile`, `deploy/bootstrap.sh`,
   `scripts/ops/*` (`.sh` and `.ps1`), `scripts/ops/ops.env.example`, `docs/spec/env.prod.example`,
   `.gitignore` entries.
3. Test locally: `docker compose -f deploy/docker-compose.yml up --build` with `CREWBIE_HOSTNAME=localhost`
   (Caddy serves a local certificate), `/healthz` ok.
4. Lint shell scripts with `shellcheck`; test PowerShell scripts parse with `pwsh -NoProfile -Command` if
   available.
5. Run Part C with the owner.
6. Set `DEFAULT_API_URL` in `crew.py` to `https://<CREWBIE_HOSTNAME>`.
7. Verify `up` and `down` cycle: data survives, URL unchanged, certificate reused (no new issuance in Caddy logs).

DoD: `scripts/ops/status` shows running and healthy with `discord: connected`; AS-1 and AS-2 pass against the
public URL; a full `down` → `up` cycle preserves rooms and installs.

## Phase 6: Skill update and live Cubbie test

Inputs: I-06 (Cubbie account(s) with the Skill installed; ideally two students).

Tasks:
1. Update SKILL.md per 06-CUBBIE-SKILL.md.
2. Run the Track 1 kit validator (see `legacy/integrations/cubbie/validate_skill.py` or the official kit) on the
   Skill folder.
3. Live checklist: install from branch link, tone setup unaffected, solo plan works with API down, discovery count
   shows, submit → offer → accept → link → thread, check-in delivers updates, leave works.
4. Record outcomes and redacted screenshots in `docs/spec/LIVE_TEST.md`.
5. Merge `crewbie-v2` to `master` after the owner approves.

DoD: owner confirms the live checklist; Track 1 Skill still produces solo plans.

## Phase 7: LLM agents, facilitation, Mission Control

Inputs: I-07 (Anthropic API key), I-08 (Mission Control scope decision).

Tasks:
1. LLM client, prompts, schemas, fallbacks; P-3 injection tests (AS-10).
2. LLM icebreaker and mention Q&A; reminders; quiet nudge (P2); meetpoint poll (P2).
3. `/v1/stream` SSE; adapter in `apps/web/src/lib/adapters/` mapping new events to existing UI types; one view
   that shows a negotiation: proposals, verdicts, final offer.

DoD: with `CREWBIE_LLM_MODE=on`, AS-1..AS-11 pass; with `off`, they still pass.

## Phase 8: Demo and submission

Inputs: I-09 (demo participants and script approval), I-10 (submission owner and deadline).

Tasks:
1. `docs/DEMO.md`: a 3-minute script: student A confirms in Cubbie (new room), student B confirms (joins, thread,
   icebreaker), student C with tighter window triggers visible negotiation in Mission Control, C leaves.
2. Seed command for the demo event; reset command.
3. README rewrite: what Crewbie does, architecture diagram, how to run, how agents protect private constraints.
4. Track 2/3 submission text: what agents share, how conflicts resolve, when students confirm.

DoD: two dry runs completed within 3 minutes each.
