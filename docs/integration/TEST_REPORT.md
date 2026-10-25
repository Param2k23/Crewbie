# Integration verification report

Status: **PARTIAL release readiness; integrated synthetic core verified**. All component histories and tests are preserved. No live Cubbie account run, live Discord delivery, real student profile, booking or enrollment was exercised.

## Final automated results

From Windows PowerShell at `D:\VS\crewbie-integration`:

```powershell
.\scripts\test.ps1
```

| Exact suite command (run by script) | Passed | Failed |
|---|---:|---:|
| `python -B -m unittest discover -s tests/participants -v` | 61 | 0 |
| `python -B -m unittest discover -s tests/opportunities -v` | 38 | 0 |
| `python -B -m unittest discover -s tests/negotiation -v` | 153 | 0 |
| `python -B -m unittest discover -s tests/commitments -v` | 71 | 0 |
| `python -B -m unittest discover -s tests/realtime -v` | 17 | 0 |
| `python -B -m unittest discover -s tests/cubbie -v` | 64 | 0 |
| `python -B -m unittest discover -s tests/integration -v` | 29 | 0 |
| **Python total** | **433** | **0** |

Original realtime HTTP tests emit socket ResourceWarnings and occasional disconnect tracebacks on Python 3.9; unittest still exits zero. New API tests close clients/server resources explicitly. The final local transcript is retained in ignored `.integration-audit/final-python-tests.txt`.

From `D:\VS\crewbie-integration\apps\web`:

```powershell
npm ci
npm test
npm run typecheck
npm run build
npm audit
```

Frontend: **100 tests passed, 0 failed, 10 files** (96 original + 4 actual-backend trace contract tests). Typecheck and optimized Next.js production build exit zero. `npm audit` reports **0 vulnerabilities** after the scoped PostCSS 8.5.31 override; original baseline had two affected packages. Next.js 15 and the existing frontend framework are retained.

## Cross-module scenarios

```powershell
Set-Location D:\VS\crewbie-integration
python -B -m services.api.demo
python -B scripts/export_traces.py
```

| Scenario | Actual service calls and observed result | External/synthetic boundary |
|---|---|---|
| A — Unlocks to Social Plan | A1 canonical intent and consented handoff -> A2 sourced resource normalization/discovery -> A3 opt-in matching and mutual introduction checks -> four private evaluations -> A4 proposal -> A5 same-version approvals -> A6 events. Confirmed v1, not booked. | Native Cubbie handoff is mocked. Public ASU Library resource description is real; proposed schedule, inventory, identities and consent are synthetic. |
| B — Evening | Initial candidate fails private availability; A3 coarse hints drive actual A4 counteroffers; selected v2 is below another evaluated v3. `maybe`/conditional replies remain unconfirmed; four exact-version approvals confirm. | Synthetic private profiles, candidate estimates and mock message provider only. |
| C — Weekend/replanning | 30-hour plan initially fails budget/schedule; generated day/cost counteroffers yield v3. Four explicit approvals confirm; lowering a hard cap invalidates approvals and produces v6 with zero approvals. Zero cap terminates honestly with NO_FEASIBLE_PLAN. | Synthetic prices, travel/lodging assumptions, profiles and chat delivery; no live availability/booking. |

Saved CLI result: `demo-results.json`. Saved frontend input traces: `apps/web/tests/data/integrated-traces.json`, reproducible from the export command. These are real module-generated synthetic traces, not A6's independent local simulator.

## Privacy, security and failure tests

Component and integration tests cover separate matching/sharing/introduction consent; owner/session capabilities; rejection of cross-profile access and malformed costs; protected time/budget checks; no implicit exception approval; private-field rejection; no maybe/silence/conditional confirmation; exact-version approvals; material revision invalidation; stale and duplicate messages; duplicate change/event handling; withdrawal stopping future matching/evaluation; declined proposal versus activity withdrawal; explicit cancellation; provider failure before acknowledgment; no private profile route; cross-origin/DNS-rebinding rejection; synthetic-only judge mutation; Last-Event-ID resume; public event redaction and safe group copy. External chat sends and booking/enrollment calls are not part of the mock demo.

Discord adapter tests fake the external channel/receipt only, exercising the real adapter's acknowledgment, idempotency, disabled mentions and failure behavior. SDK `discord.py==2.6.4` was installed and these tests ran without skips. No bot connected to Discord.

## Real browser / HTTP / SSE smoke

Against the production build, using three terminals:

```powershell
# terminal 1, repository root
python -B -m services.api.main --port 8788 --seed weekend
# terminal 2
Set-Location D:\VS\crewbie-integration\apps\web
npm run start
# terminal 3
Set-Location D:\VS\crewbie-integration\apps\web
node scripts/integration-smoke.mjs
```

**Passed:** actual Next.js UI creates a backend session, receives SSE, fetches the real sanitized itinerary, displays 4/4 confirmation, submits a synthetic judge budget change through HTTP, observes correlated backend events and displays a new pending version with 0 approvals. Browser page errors: **0**. Result: `browser-smoke.json`; screenshots: `screenshots/01-backend-weekend-pending.png`, `02-backend-confirmed.png`, `03-backend-replanned.png`. The smoke uses the accessible 2D mode. 3D work is preserved and builds; this smoke does not establish real-GPU performance.

Two initial smoke attempts used selectors that did not match the existing UI labels; corrected selectors then passed. No application success was inferred from those failed attempts.

## Track 1 validation

```powershell
Set-Location D:\VS\crewbie-integration
python -B -m integrations.cubbie.validate_skill skills/crewbie-unlocks
python .integration-audit\cubbie-kit\skills\cubbie-skill-creator\scripts\validate_cubbie_skill.py skills/crewbie-unlocks
```

Both pass. The official creator kit revision is `bc505e9c41ea91de77f7a8b57214fd10901a100f`; its validator requires PyYAML, installed as 6.0.2 for this run. Real Cubbie testing remains unexecuted; see CUBBIE_LIVE_TEST.md. Older strict file/manifest assumptions in A1's historical notes are superseded by the current official kit; the package contains only SKILL.md and no manifest.

## Release limitations

Windows Python 3.9.5 / Node 22.23.2 / npm 10.9.8 were used; Python 3.12 was not available. Synthetic loopback behavior is verified; production authentication, storage, session authorization, live sources, Cubbie transport and real-account provider behavior remain explicit blockers in BLOCKERS.md. The branch has local integration commits only.
