# Legacy prototype

The multi-agent prototype that preceded Crewbie v2: negotiation, commitments, participants, opportunities and
realtime services, the Cubbie integration helpers, and the first Discord chat bot.

It is kept as read-only reference for ideas (see `docs/spec/02-ARCHITECTURE.md` section 7). Nothing under
`src/` may import from it, and `tests/unit/test_layering.py` fails if anything does. It is not run by CI and
its tests are not collected by the root `pytest` configuration.

| Directory | Was |
|---|---|
| `services/` | Python services (api, commitments, negotiation, opportunities, participants, realtime) |
| `integrations/` | Cubbie integration helpers, including `cubbie/validate_skill.py` |
| `apps_chat_bot/` | Discord/group chat bot (formerly `apps/chat_bot`) |
| `tests/` | Tests for the above |
| `scripts/` | Trace export and Windows test runner |
| `requirements-discord.txt` | Discord dependency of the old bot |

History and verification notes for the prototype are in `docs/integration/`.
