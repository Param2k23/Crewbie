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

## Phase 3: Agents and matcher, deterministic (done, committed 3992834)

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

## Phase 4: Discord bot (done, committed 2f881b5; live checks passed by the owner)

Done:
- `discord_bot/`: client with guild-synced `/crew link|status|leave|help|meetpoint`, persistent Join button on
  board cards, Join modal, outbox worker for all seven job kinds, live gateway, runtime started from the API
  lifespan (`CREWBIE_DISCORD_ENABLED=true`), `/healthz` reports `discord`.
- Services for the bot: room view (public fields only), outbox job results, bot actions (status, leave, board
  join), room lifecycle worker.
- All user-facing strings in `messages.py`; untrusted event text is neutralised; no mentions unless asked.
- Tests with a fake gateway that implements the production protocol: AS-2, AS-3, AS-7, AS-8, AS-11, retry and
  backoff, idempotency, closed DMs, board card lifecycle, thread archive, synthetic members skipped, handlers
  and modal, messages, runtime wiring; privacy scan extended to everything the bot says and logs.
- A real connection check passed: the bot logged in, synced commands to the guild and `/healthz` showed
  `discord: connected`.

Pending (needs the owner and test accounts):
- Set `CREWBIE_DISCORD_ENABLED=true` in `.env`, run `uv run python -m crewbie`, and walk the live checklist in
  the Phase 4 summary (AS-2, AS-7, AS-8 with two Discord accounts).
- Optional: `CREWBIE_DISCORD_TEST_CHANNEL_ID`, then `uv run pytest -m discord_live`.

Open questions: none.

## Phase 5: Deployment on AWS EC2 (done, committed 7e817e9)

Done:
- Part A with the owner (A2 skipped, region Ohio `us-east-2`; see DECISIONS.md). `crewbie-ops` profile works.
- Part B files, with CI green: shellcheck, PowerShell parse, and a Compose job that builds the image, serves
  HTTPS through Caddy, runs non-root and keeps data across down/up.
- Part C: server bootstrapped, `.env.prod` pushed (mode 600), first deploy healthy. Public URL
  `https://18-220-104-252.sslip.io`: Let's Encrypt certificate, HTTP redirects to HTTPS, HSTS on,
  `/healthz` returns `ok` with `discord: connected`.
- `DEFAULT_API_URL` in `crew.py` points at the public URL (local development uses `CREWBIE_API_URL`).
- AS-1 and AS-2 pass against the public URL, run by the owner with two Discord accounts.
- `/healthz` also answers HEAD for uptime monitors (needs one `deploy.sh` run).

- Task 7 verified: one full `down` then `up` took 189 s from stop to a healthy `discord: connected`. Row counts
  in every table were identical before and after (2 installs, 1 active room with thread and card, 8 done outbox
  jobs). Same URL, same certificate serial and fingerprint, and Caddy's issuance count stayed at 1, so no new
  certificate was requested.
- The `crew.py` URL change and the HEAD fix are committed, pushed and deployed.

Pending: Part F teardown after the hackathon (release the Elastic IP, terminate the instance, delete the
`crewbie-ops` keys). The instance is left running.

Open questions: none.

## Phase 6: Skill update and live Cubbie test (done; merged to master)

Done:
- `SKILL.md` updated in exactly three places: the header sentence, one optional "Going" line on the Unlock
  Card, and the "Find a crew" section (disclosure, steps, check-in, leave, failure handling). The tone setup
  (Chill, Playful, Roast Me), the personality rules and all student-exclusive-first sections are untouched.
- Tests pin what must never be lost: tone options and consent, the student-exclusive ranking and the
  "Student unlock if you're flexible" rule, the consent disclosure against what `crew.py` sends, and every
  `crew.py` command in the Skill against the real CLI.
- Official Cubbie kit validator (`validate_cubbie_skill.py`) passes with no warnings. The old
  `legacy/integrations/cubbie/validate_skill.py` no longer applies: it rejects any bundled script.
- `docs/spec/LIVE_TEST.md` is the checklist and results sheet.

Pending: the live checklist with two Cubbie students (needs I-06), then the owner's approval to merge
`crewbie-v2` into `master`.

Live test (owner, two real Cubbie students): install, tone question first, Roast Me consent, student-price
ranking, disclosure, crew start with Discord linking, look-alike event search, B joining and the private
thread all worked. Findings fixed along the way: precise private-data wording, Replace-link hint, check-in
rhythm, `crew.py`-only rule, and Cubbie-assisted event matching. Steps 9 to 13 of `LIVE_TEST.md`
(check-in delivery, leave, solo plan with the service down, tone check, privacy check) were not individually
reported; the owner to confirm. Merge of `crewbie-v2` into `master` still needs the owner's explicit approval.

Update 2026-10-25: step 9 confirmed (A's Cubbie reported two students going) and the owner reported the other
steps as working. Deferred to the end by the owner: step 11 (solo plan with the service offline) and a Join from
the Discord board card with a fresh account. The owner approved merging `crewbie-v2` into `master`.

## Website (landing page)
`apps/web` now serves the "Cubbie x Crewbie" landing page at `/unlocks` (`/` redirects there; the Mission Control
demo is at `/demo` and `/arena`). Content is written around Cubbie as the base, tests guard the claims, and a
`web` CI job runs typecheck, tests and build. Deployed to Vercel production at https://crewbie-sepia.vercel.app
(see `apps/web/README.md` to redeploy). `crewbie-v2` is merged into `master`.

Deferred to the end by the owner: live test step 11 (service offline) and a Join from the Discord board card.
Next: Phase 7 (LLM agents, facilitation, Mission Control), most of it optional.
