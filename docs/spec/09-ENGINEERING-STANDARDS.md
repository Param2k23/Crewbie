# Engineering standards

## 1. Layering

```
api, discord_bot, workers  ──▶  services  ──▶  matching, agents  ──▶  domain
                                   │
                                   └──▶  persistence  ──▶  domain
```

- `domain`: pure functions and frozen dataclasses. No IO, no clock reads (pass `now`), no randomness (pass ids).
- `agents` and `matching`: depend on `domain` and on small protocols (`DelegateView`, `RoomSnapshot`), never on
  SQLAlchemy models or discord.py types. `agents/llm` is the only place that imports the Anthropic SDK.
- `services`: the only layer that opens a unit of work, writes outbox/updates rows, and calls the matcher.
- `api` and `discord_bot`: translate transport to service calls and back. No business rules.
- Enforce with import-linter contracts (or an equivalent test) in CI.

## 2. Code style

- Python 3.12, type hints everywhere, `from __future__ import annotations` not needed.
- ruff (lint + format), line length 100. mypy strict for `domain`, `agents`, `matching`; standard elsewhere.
- Names say what things are: `derive_room_state`, not `process`. No abbreviations beyond common ones (`id`, `url`).
- Functions do one thing; prefer under 40 lines. Modules under 300 lines; split by responsibility, not by type.
- No module-level mutable state except the logger and the settings object.
- Dependency injection through constructors and FastAPI dependencies; no service locators.
- Errors: raise `DomainError` subclasses with a stable `code`; map once in `api/errors.py` and once in
  `discord_bot/messages.py`. Never return `None` to mean failure.
- Time: all datetimes timezone-aware. Store UTC; convert at the edges with `CREWBIE_TIMEZONE`.
- No print statements in `src/`; use the logger.
- Comments explain why, not what. Docstrings on public functions in `domain`, `agents`, `services`.

## 3. Testing

- Test names include requirement IDs where they verify one: `test_fr_ofr_02_stale_offer_triggers_rematch`.
- Unit tests for `domain`, `agents`, `matching` use no database and no network.
- Integration tests use a temporary SQLite file and the FastAPI test client; Discord via a fake adapter that
  implements the same protocol as the production adapter.
- Property-based tests (Hypothesis) for window math and the delegate guard.
- Privacy tests (`tests/privacy/`) use sentinel values and scan logs (captured), responses, DB tables other than
  `envelopes`, outbox payloads, updates and public events.
- `e2e` and `discord_live` markers are opt-in.

## 4. Logging and observability

- JSON logs: `ts`, `level`, `msg`, `request_id`, `install_ref` (first 8 hex of sha256(install_id)), `room_id`,
  `job_id`, `event_type`.
- Redaction filter drops keys named `token`, `authorization`, `flex`, `budget_cap_usd`, `envelope`, `ciphertext`.
- Log one line per request, per negotiation (outcome, rounds, duration), per outbox job attempt.

## 5. Security

- Treat every external string (event fields, Discord messages, modal input, LLM output) as untrusted.
- LLM output: strict JSON schema, length limits, then the deterministic guard.
- Secrets only from environment; `config check` reports presence and format, never values.
- Dependencies pinned exactly in `uv.lock`; choose versions released at least 14 days ago.
- No team secret in `skills/`.

## 6. Git

- Branch `crewbie-v2`; small commits; message format `<area>: <change> (FR-XXX-NN)`.
- Do not rewrite `master` history. Merge `crewbie-v2` into `master` only after Phase 6 approval.
