# Live test with Cubbie (Phase 6)

Run by the owner with two real Cubbie students against the deployed server
`https://18-220-104-252.sslip.io`. Record the result of each step below and attach redacted screenshots
(cover phone numbers, names, Discord user names and links you do not want to publish).

Before you start: `bash scripts/ops/status.sh` shows `running` and `discord: connected`. Your local `.env`
has `CREWBIE_DISCORD_ENABLED=false`.

## Setup

Student A and Student B each text their Cubbie:

```
Install https://github.com/Param2k23/Crewbie/tree/crewbie-v2/skills/crewbie-unlocks
```

Cubbie should name the repository and folder and ask before fetching it. Reply `yes`. Texting the same link
again later updates the Skill to the newest commit (use this after any fix). Each student also needs a
Discord account in the Crewbie server (the invite link is in `CREWBIE_DISCORD_INVITE_URL`).

Use two **real** event listings that both Cubbies can open at the same original link, with a date and start
time. Matching is by link, date and start time, so both students must use the same listing.

## Checklist

| # | Step | Expected | Result | Notes |
|---|---|---|---|---|
| 1 | Install A and B from the branch link | Cubbie asks before fetching, then installs `crewbie-unlocks` | PASS (A, B) | Both installed from the branch link; A's Cubbie backed up the previous version. |
| 2 | First message to Cubbie about planning something | The **first** question is the tone: "What vibe would you like: Chill, Playful, or Roast Me (lighthearted teasing only)?" | PASS (A, B) | Tone question came first on both. |
| 3 | Skip the tone question once (A) and pick Roast Me (B) | A: Chill, no nagging. B: asked permission before remembering the choice | PASS | A skipped: Chill, not blocked, not repeated. B chose Roast Me, was asked before it was remembered. One mild finance joke (accepted as model variance). |
| 4 | Ask for an activity that has a student discount | Student-exclusive options are searched and ranked **first**; public options only after; a near-match is offered as "Student unlock if you're flexible" | PASS (A) | Student price $10.81 (ID) vs $14.59 public, sourced, conditions stated. B did not say it had checked student perks (variance, watch). |
| 5 | Confirm an activity (A), say yes to "find other students" | Before the first send, Cubbie lists exactly what is shared and what stays private, and waits for a yes | PASS (A) | First wording said the limits stay with the agent, then Cubbie corrected itself. Fixed: SKILL.md now says they reach the server encrypted and are never shown. |
| 6 | A: submit, then accept | `new_room` offer, then accept asks A to link Discord with a code; after `/crew link` accept says joined, a card appears on `#crew-board`, no chat yet ("opens when someone joins") | PASS (A) | Link needed two tries: the owner's Discord account was already linked and the Replace button was missed. Hint added to SKILL.md. Card appeared on the board; check-in set at 15 minutes (Cubbie's limit). |
| 7 | B asks about the **same** event | The Unlock Card says "1 student going" (the count) | | |
| 8 | B: submit, accept, link | A `join` offer is described in plain words; after the yes and the link, B is in a private thread with the icebreaker; both get a DM | | |
| 9 | A accepts a scheduled check-in, then B joins | A's check-in texts a plain-words update ("someone joined", then the chat link), and nothing when there is nothing new | | |
| 10 | B leaves (Cubbie or `/crew leave`) | Thread notice "member-2 left"; A is told in the next check-in | | |
| 11 | Solo plan with the service down: `bash scripts/ops/down.sh --yes`, then ask Cubbie for a plan | Cubbie says crew matching is unavailable and still gives the full solo plan. Then `bash scripts/ops/up.sh` | | |
| 12 | Tone check after all this | Roast Me still teases only hidden perks or optional adventures, never about being alone, other students or someone leaving | | |
| 13 | Nothing private leaked | Discord thread and DMs show no flex times and no budget cap; Cubbie sent no dietary, calendar or course details | | |

Step 11 takes the bot offline for about three minutes; do it last.

## Evidence

Put redacted screenshots in `docs/spec/live-test/` (create the folder) named by step number, for example
`06-link-required.png`. Do not commit anything that shows a token, a link code you have not used yet, or a
person's phone number.

## Findings

List anything that did not match "Expected", with the step number and what Cubbie actually said. Claude Code
turns each finding into a fix, pushes it, and the students text the install link again to update.

| Step | What happened | Fix |
|---|---|---|
| | | |

## Sign-off

- [ ] The owner confirms the checklist above.
- [ ] The Track 1 Skill still produces solo plans (steps 4 and 11).
- [ ] The owner approves merging `crewbie-v2` into `master`. The merge makes this the Track 1 entry, because
      the Skill installs from `master`.
