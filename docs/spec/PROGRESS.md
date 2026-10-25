# Progress

## Phase 0: Repository restructure and tooling (done, awaiting owner review)

Done:
- `crewbie-v2` cut from latest `origin/master`; legacy code moved to `legacy/` with `git mv` (history kept).
- `pyproject.toml` (uv, Python 3.12), ruff, mypy (strict for domain/agents/matching), pytest markers,
  import-linter contracts, `uv.lock`.
- `src/crewbie/` skeleton per 02-ARCHITECTURE.md; `tests/` skeleton.
- `config.py` with `python -m crewbie.config check`.
- `.env.example` replaced; CI workflow `.github/workflows/ci.yml`.

Left: nothing for Phase 0. Not yet committed or pushed (owner commits).

Open questions: none.
