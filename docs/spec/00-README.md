# Crewbie v2 specification

| File | Purpose |
|---|---|
| `01-SRS.md` | Software requirements: scope, actors, functional and non-functional requirements |
| `02-ARCHITECTURE.md` | Components, directory layout, data model, data flows, state machines |
| `03-API-CONTRACT.md` | HTTP API used by the Cubbie Skill script, the Discord bot and Mission Control |
| `04-AGENT-PROTOCOL.md` | Delegate, room host and matcher: messages, rules, LLM boundary |
| `05-DISCORD-BOT.md` | Linking, threads, board, icebreaker, facilitation |
| `06-CUBBIE-SKILL.md` | Changes to `skills/crewbie-unlocks`: `crew.py` CLI and SKILL.md section |
| `07-IMPLEMENTATION-PLAN.md` | Phases, tasks, acceptance criteria |
| `08-INPUTS-FROM-OWNER.md` | Accounts, keys and decisions needed from the owner, with instructions |
| `09-ENGINEERING-STANDARDS.md` | Code style, layering, testing, logging, security rules |
| `10-AWS-DEPLOYMENT.md` | EC2 deployment with on/off scripts; first-time AWS setup steps for the owner |

Hackathon context: https://hackathon.cubbie.ai. Track 1 (Cubbie Skill) is submitted. This spec targets one
submission covering Track 2 (agent-to-agent coordination) and Track 3 (group chat assistant), while keeping the
Track 1 Skill useful on its own.

Conventions: requirement keywords MUST, SHOULD, MAY follow RFC 2119. Priority P0 = demo cannot happen without it,
P1 = expected in the submission, P2 = only if time remains.
