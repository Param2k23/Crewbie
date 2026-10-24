# Copy-Paste Launch Instructions for Six Coding Agents

## One-time instruction for the project lead

Create an initial repository commit including the full `crewbie_agent_specs` package. Lock shared contracts until the first integration milestone. Start six agents on separate worktrees/branches with the same root commit. Do not ask each agent to "build the entire app".

## Common instructions (prepend to *every* agent prompt)

> This is the Crewbie DevHacks ASU monorepo. You are one of six parallel coding agents. Read `docs/implementation/PROJECT_SPEC.md`, `docs/implementation/CONTRACTS.md`, `docs/implementation/COORDINATION.md` and fixture JSON before writing code. Only edit files in the ownership directory listed in your own agent task. You must implement a runnable mock/demo mode with automated unit tests and a README inside your owned directory. Do not edit shared contracts, fixtures, root configs, or someone else's work. When an external SDK/source is unavailable, report a blocker and continue with a truthful stub—do not invent methods. Never expose private budgets/availability. Finish by reporting branch/commit, files, commands, tests, blockers, exact integration points and demo evidence.

## Agent-specific assignments

1. **Agent 01 / `feat/a1-cubbie-skill`:** Read `docs/implementation/agents/AGENT_01_CUBBIE_SKILL.md`. Mandatory sponsor Skill first. Implement parser, alert preview, demo adapter and genuine provider hook if documented. Produce `VERIFICATION.md`.
2. **Agent 02 / `feat/a2-campus-events`:** Read `docs/implementation/agents/AGENT_02_CAMPUS_OPPORTUNITIES.md`. Verify Sun Devil Central source access immediately. Implement evidence-aware Opportunity catalog and synthetic fallback. Produce `SOURCE_AUDIT.md`.
3. **Agent 03 / `feat/a3-profiles-consent`:** Read `docs/implementation/agents/AGENT_03_PRIVATE_AGENTS.md`. Implement consent, private profiles, opt-in candidate matching, per-student private feasibility checks and coarse counteroffers with tests.
4. **Agent 04 / `feat/a4-negotiation`:** Read `docs/implementation/agents/AGENT_04_NEGOTIATION_FAIRNESS.md`. Implement deterministic candidate validation, coordinator state machine, private evaluator adapters, fairness ranking, revision and redacted event emission.
5. **Agent 05 / `feat/a5-group-host`:** Read `docs/implementation/agents/AGENT_05_GROUP_CHAT.md`. Implement one visible group bot, mock provider, proposal-version approvals and safe intro/icebreakers. Test ambiguous and conditional replies.
6. **Agent 06 / `feat/a6-mission-control`:** Read `docs/implementation/agents/AGENT_06_MISSION_CONTROL.md`. Implement Next.js UI, real event reducer, 3D network, SSE read-only bridge, demo replay and 2D fallback. No fake approvals or VR dependency.

## Deliverable policy

An agent is *done* only when it supplies a reproducible standalone demo, tests of the assigned failure case, safe typed contracts, and no unauthorized shared-file edits. The lead merges in the order in `COORDINATION.md` and runs the end-to-end test before announcing progress.
