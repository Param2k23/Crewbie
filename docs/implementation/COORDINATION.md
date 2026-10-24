# CREWBIE — Parallel Agent Coordination & Integration Runbook

## Bootstrap (project lead, before spawning agents)

1. Create the monorepo and commit `PROJECT_SPEC.md`, `CONTRACTS.md`, fixtures and these six agent files as the **contracts baseline**.
2. Agree on Python 3.12, FastAPI for backend adapters, Next.js/TypeScript for UI, and in-memory/mock adapters as the default. Real provider integrations are conditional on actual docs and keys. Do not let six agents concurrently edit the same root config.
3. Give every coding agent **this master spec, the contracts, the fixtures and ONLY its assigned agent file**. Each gets an isolated branch or worktree from that commit.
4. Recommended branches: `feat/a1-cubbie-skill`, `feat/a2-campus-events`, `feat/a3-profiles-consent`, `feat/a4-negotiation`, `feat/a5-group-host`, `feat/a6-mission-control`.
5. Decide who is integrator. The integrator exclusively owns `services/api/main.py`, root dependency setup, API route registration, root `.env.example`, and final combined tests.

## Exclusive file ownership

| Agent | Can change | Must not change |
|---|---|---|
| A1 | `integrations/cubbie/`, `tests/cubbie/`, `docs/integrations/cubbie/` | all other component directories |
| A2 | `services/opportunities/`, `tests/opportunities/`, `docs/opportunities/` | integrations, profiles, negotiation |
| A3 | `services/participants/`, `tests/participants/`, `docs/participants/` | negotiation, chat |
| A4 | `services/negotiation/`, `tests/negotiation/`, `docs/negotiation/` | participant private store, chat, UI |
| A5 | `services/commitments/`, `apps/chat_bot/`, `tests/commitments/`, `docs/commitments/` | core negotiation, UI |
| A6 | `apps/web/`, `services/realtime/`, `tests/realtime/`, `docs/mission-control/` | negotiation, user profiles, source adapters |
| Integrator | root configs, `services/api/`, shared `contracts/`, root `docs/` | should not rewrite component internals without owner review |

Agents must not edit canonical `PROJECT_SPEC.md`, `CONTRACTS.md`, fixtures, or other agent task files mid-sprint. Raise changes in a separate note to integrator.

## Dependency / mock approach

- **A1** mocks A2 events and scheduled sends until Cubbie capabilities are proven. Must demonstrate an actual sponsor Skill early if supported.
- **A2** uses fixture events and interface-only A1 preferences; no need to wait for Skill.
- **A3** uses synthetic participant IDs and fixture plans; exposes private feasibility interface to A4.
- **A4** uses fake `PrivateEvaluator`, `CommitmentGateway` and `MemoryEventSink` until other services exist.
- **A5** uses synthetic incoming group messages, a fake public plan snapshot, and a fake consent gateway; never requires real Discord to test logic.
- **A6** replays a shared safe event fixture into a stream and renders it; doesn't wait for A4/A5.

## Milestones & integration order

| Checkpoint | Expected outcome |
|---|---|
| **M0: Contract freeze** | All agents have same schema, event names, fixtures, owners and mocks |
| **M1: Isolated slice** | Each owner shows standalone happy path, 1 failure path, tests, local run instructions |
| **M2: First integrated loop** | A1/A2 opportunity -> A3 consent/match -> A4 proposal -> A5 group approval -> A6 event visualization |
| **M3: Judge intervention** | Change hard budget; proposal rejected, re-negotiated or fails honestly; old approvals invalidated |
| **M4: Track evidence** | Track 1 sponsor demo, Track 2 agents/validator proof, Track 3 chat transcript/state proof |
| **M5: Rehearsal** | Three-minute coherent demo; no reliance on unstable third-party source or live model availability |

**Merge order:** contracts+fixtures baseline -> A3 and A4 interface test -> A5 -> A6 -> A2 -> A1 actual sponsor hook. This is an **integration sequence**, not a reason to delay independent parallel coding.

## Handoff report required from each agent

Submit: (1) commit hash/branch, (2) file list, (3) commands to run, (4) known limitations, (5) API contract changes requested, (6) automated test results, (7) screenshots/logs of standalone demo, (8) privacy checks and unresolved external dependencies.

## Sample project-lead integration smoke tests

1. Load synthetic events and students; perform `find_campus_food`; assert source URL + uncertainty wording.
2. Mark two students matching- and intro-consented; obtain candidate; refuse stranger introduction without consent.
3. Start four-agent Flagstaff negotiation; reject $70 for $60 hard cap; generate viable option or `NO_FEASIBLE_PLAN`.
4. Submit chat responses `yes`, `maybe`, `yes if...`, `no`; assert no confirmed plan.
5. Replan a validated candidate by changing availability; assert version increments, relevant approvals reset, stream shows rejection and revision.
6. Confirm all four on current version; assert backend state `confirmed` and visualization uses `proposal_confirmed` event.

## Communication / escalation policy

Blockers affecting shared contracts are reported immediately with a tiny reproducible JSON example. Integrator resolves cross-team ambiguity. Avoid speculative edits to another workstream. If external integrations are blocked, **ship a truthful mock/demo path and mark the real connector incomplete**.

## What is NOT an agent's job

Changing the concept, building unrelated features, making unapproved third-party purchases, scraping behind auth screens, publishing other students' private information, or committing secrets. Each agent optimizes for its own bounded acceptance tests and the unified demo.
