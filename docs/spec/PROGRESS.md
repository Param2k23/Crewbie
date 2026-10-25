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

## Phase 1: Domain and persistence (done, awaiting owner review)

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
