# Crewbie — Six-Agent Parallel Build Pack

This directory is a **specification and delegation package**, not implemented source code. It converts the approved Crewbie product concept into six non-overlapping workstreams that can be started in parallel.

## Start here

1. Read [`PROJECT_SPEC.md`](PROJECT_SPEC.md) — what the unified product does and its P0 demo.
2. Read [`CONTRACTS.md`](CONTRACTS.md) — fixed data model, interfaces, event names and privacy rules.
3. Read [`COORDINATION.md`](COORDINATION.md) — branch/worktree ownership, mocks, merge protocol and test gates.
4. Give each coding agent **its one assignment file** plus the three docs above and `fixtures/`. See [`START_PROMPTS.md`](START_PROMPTS.md) for ready-to-send prompts.
5. Have your project lead (human) create an initial repository commit with these files, then spawn six independent worktrees/branches.

## Agent assignments

| Agent | Mission | File |
|---|---|---|
| 01 | Mandatory Cubbie Skill and Campus Pulse messaging | [`agents/AGENT_01_CUBBIE_SKILL.md`](agents/AGENT_01_CUBBIE_SKILL.md) |
| 02 | Authorized ASU event discovery and source credibility | [`agents/AGENT_02_CAMPUS_OPPORTUNITIES.md`](agents/AGENT_02_CAMPUS_OPPORTUNITIES.md) |
| 03 | Private student profiles, consent and companion matching | [`agents/AGENT_03_PRIVATE_AGENTS.md`](agents/AGENT_03_PRIVATE_AGENTS.md) |
| 04 | Multi-agent negotiation, hard constraints and fairness | [`agents/AGENT_04_NEGOTIATION_FAIRNESS.md`](agents/AGENT_04_NEGOTIATION_FAIRNESS.md) |
| 05 | Group chat host and versioned commitments | [`agents/AGENT_05_GROUP_CHAT.md`](agents/AGENT_05_GROUP_CHAT.md) |
| 06 | Campus Pulse visual UI, 3D Mission Control and safe event stream | [`agents/AGENT_06_MISSION_CONTROL.md`](agents/AGENT_06_MISSION_CONTROL.md) |

## Bundled fixtures / contracts

- `fixtures/opportunities.json`: **synthetic**, source-labeled campus event examples; **not current real ASU events**.
- `fixtures/scenarios.json`: four-person trip constraints and expected decision behavior; all participants fictitious.
- `fixtures/chat_transcript.json`: canned but representative incoming participant replies for unit testing, not a fake production conversation.
- `fixtures/agent_events.json`: redacted event transitions for Mission Control mock replay.
- `contracts/crewbie.schema.json`: JSON Schema `$defs` for the shared event, opportunity, candidate plan and commitment record shapes.

## Suggested repository placement

If you plan to commit this package to `Param2k23/Devhacks-ASU` branch `ideas`, place its contents under `docs/implementation/` **before coding**. After the contract baseline commit, give each coding agent its own branch. No GitHub push is performed by this package. Use one independent branch or worktree per agent.

## 4 non-negotiables

- **Mandatory Skill first:** Track 1 is not satisfied by a simulated Cubbie Skill alone. Actual provider testing is needed.
- **Private-by-default:** No sensitive budgets or schedules in group chat or public UI.
- **Real decisions:** Visuals reflect actual recorded state changes, not scripted success animations.
- **One product:** food alerts, companion introductions and trip planning are examples of the same consent -> negotiation -> commitment engine.
