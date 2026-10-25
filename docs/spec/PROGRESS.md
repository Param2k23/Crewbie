# Progress

## Phase 0: Repository restructure and tooling (done, committed 792b265)

Done:
- `crewbie-v2` cut from latest `origin/master`; legacy code moved to `legacy/` with `git mv` (history kept).
- `pyproject.toml` (uv, Python 3.12), ruff, mypy (strict for domain/agents/matching), pytest markers,
  import-linter contracts, `uv.lock`.
- `src/crewbie/` skeleton per 02-ARCHITECTURE.md; `tests/` skeleton.
- `config.py` with `python -m crewbie.config check`.
- `.env.example` replaced; CI workflow `.github/workflows/ci.yml`.

Left: nothing.

## Phase 1: Domain and persistence (done, committed 9b7462e)

Done:
- Domain: `event_key`, `TimeWindow`, `BudgetBand`, `Vibe`, `SharedIntent`, `PrivateEnvelope` (redacted repr),
  intent lifecycle, `derive_room_state`, room lifecycle, offer rules, text sanitising, errors with stable codes.
- Persistence: 14 tables, Alembic migration `0001` (checked against the models by a test), SQLite WAL and
  foreign keys, Fernet envelope encryption, repositories, outbox with backoff, unit of work.
- Tests: Hypothesis property tests for windows and room derivation; envelope round trip; plaintext scan of
  every non-envelope table; outbox retry schedule. Domain coverage 100% (gate 85% in CI).

Left for later phases: `logging.py` redaction filter (Phase 2), link code and idempotency-key storage
(Phase 2), services that call these repositories (Phase 2 and 3).

Open questions: none.

## Phase 2: API, auth, installs, discovery, intents (done, committed b70c7be)

Done:
- FastAPI app factory, error mapping (one place), request IDs, JSON logging with redaction filter.
- Install auth (SHA-256 token hash, constant-time compare), in-memory rate limiting, `Idempotency-Key` replay.
- Routers: health, installs, link-codes, rooms, rooms/lookup, intents (submit, get, withdraw), offers
  (accept, decline), updates, admin (rooms, close, outbox, seed). `python -m crewbie` runs the server.
- Services per use case. The matcher is a stub that always offers a new room (Phase 3 replaces it). Join
  accept, stale rematch, leave, install deletion and the offer sweeper are implemented and tested with a
  scripted matcher, so Phase 3 only has to supply real `MatchResult`s.
- `skills/crewbie-unlocks/scripts/crew.py` complete (stdlib only); `scripts/dev/seed.py`.
- Tests: API (installs, linking, intents, offers, room flows, discovery, admin), `tests/skill/` (crew.py as a
  subprocess against a live server), `tests/privacy/` (sentinel envelope values scanned across responses,
  logs and every table except `envelopes`; mutation-checked to fail on a planted leak).
- AS-1 and AS-7 pass end to end through `crew.py`; AS-2, AS-3, AS-6, AS-8 pass at API level via scripted offers.

Left for later phases: real matching (Phase 3); Discord worker that consumes the outbox and writes
`discord_thread_id`/`room_active` (Phase 4); `DEFAULT_API_URL` in crew.py (Phase 5); SKILL.md rewrite (Phase 6);
`/v1/stream` (Phase 7).

Open questions: none.

## Phase 3: Agents and matcher, deterministic (done, awaiting owner review)

Done:
- `agents/`: protocol messages, delegate (deterministic guard plus pluggable chooser), host (fan-out and
  merge), aliases. The guard is the only path to `accept`, so no chooser can accept outside the private limits.
- `matching/`: room snapshot, filters and pre-score, bounded negotiation, matcher (max 3 rooms, 3 rounds,
  time budget, best-of-agreements by post-score with the FR-MAT-08 tie-breaks).
- `services/matchmaking.py`: snapshot, negotiate outside any transaction, persist the offer with
  `room_version`, negotiations, steps and public events in one transaction. Per-room locks. Stale offers
  trigger a fresh matching run. Stranded intents are retried by the sweeper.
- `telemetry/public_events.py`: allowlist serializer. `scripts/dev/simulate.py`: 50 intents over 3 events.
- Tests: guard, host, negotiation, prescore and matcher units with Hypothesis (P-1, P-2, P-4); API-level
  AS-2, AS-3, AS-4, AS-5, AS-6; FR-MAT-09 events; privacy harness extended to real negotiations (P-2),
  mutation-checked; simulation run as a test. Coverage of domain, agents and matching: 99.8%.

Left for later phases: Discord worker that consumes the outbox (Phase 4); LLM chooser, captions and prompt
injection tests P-3/AS-10 (Phase 7); `/v1/stream` over `public_events` (Phase 7).

Open questions: none.
