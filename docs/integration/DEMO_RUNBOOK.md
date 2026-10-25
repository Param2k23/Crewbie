# Three-minute judge demo

Start backend and frontend using SETUP_WINDOWS.md. Open `http://localhost:3000/arena?mode=live&view=2d`. Clearly say: **actual Crewbie service calls, synthetic students/constraints/prices, mock local chat delivery**. Quick/Weekend standalone tabs are a separate simulator; use **Live stream** for the integrated demo.

1. **0:00–0:40 — Discover:** Show the standalone `skills/crewbie-unlocks/SKILL.md`, source-backed card/privacy instructions and manual Cubbie test status. Click **Start unlocks**. Explain that the ASU Library resource description is real while the proposed slot and participants are synthetic; the native-to-backend handoff is mocked. Show actual discovery/matching events and pending approvals.
2. **0:40–1:25 — Negotiate:** Click **Start evening**. Observe real rejected candidate and counteroffers, followed by the selected feasible version. The selected version may be lower than another evaluated candidate. Show private details absent from the event inspector; show the itinerary and outstanding logistics checks.
3. **1:25–2:05 — Commit:** Copy the connected session ID into the PowerShell approval commands in SETUP_WINDOWS.md. Send `maybe` first; it must remain unconfirmed. Then issue each synthetic student's explicit acceptance of the displayed version. Only after all four approvals does the real A5 service emit confirmation. Explain that group confirmation is not a booking.
4. **2:05–2:50 — Replan:** Click **Start weekend**. Show the 30-hour proposal after real budget/schedule rejections. In Judge intervention choose `stu_jordan`, change hard budget to `$20`, check the synthetic acknowledgment and submit. Wait for backend events: old proposal invalidation, rejection and counteroffer/new version with zero approvals. A lower `$0` budget via API may legitimately end in `NO_FEASIBLE_PLAN`. No frontend action fabricates success.
5. **2:50–3:00 — Show robustness:** Switch 2D/3D and identify the synthetic badge. Describe the optional Discord adapter and native Cubbie manual checklist as awaiting real-account verification.

If backend/network is unavailable, state it and show labeled replay only. Do not present replay as live integration. The CLI is a deterministic full-loop backup:

```powershell
Set-Location D:\VS\crewbie-integration
python -B -m services.api.demo
```

This runs A/B/C across actual modules and prints confirmations plus weekend replan; it does not send external messages. Saved evidence is `docs/integration/demo-results.json`; frontend contract traces can be regenerated with `python -B scripts/export_traces.py`.

For a real Discord rehearsal, start `python -B -m apps.chat_bot.discord_live` with the authorized setup, send `!crewbie evening` or `!crewbie weekend`, then have each mapped tester send `I accept version N`. Connect Mission Control to the printed session ID. Do not call this live until provider receipts and observed channel behavior have been recorded.
