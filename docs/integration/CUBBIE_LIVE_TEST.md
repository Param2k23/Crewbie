# MANUAL REAL CUBBIE TEST — not executed

Track 1 local validation passes; native installation and execution remain **UNVERIFIED**. Use only the project manager's authorized Cubbie account. No backend is needed for basic Unlocks discovery.

The project manager merged A1 and renamed the package in `cccfa06c4c76734a96c52681af92594b7fe1f0ce`. The installation target is now:

https://github.com/Param2k23/Crewbie/tree/master/skills/crewbie-unlocks

This is the PM-published Skill, not the unpushed integration branch. Confirm public accessibility and inspect the installed commit. Do not assume a summary, install receipt or later native action will succeed. Record each observed outcome and a redacted screenshot/receipt, without private account data.

| Exact student message | Expected outcome / evidence to record |
|---|---|
| `Install https://github.com/Param2k23/Crewbie/tree/master/skills/crewbie-unlocks` | Review Crewbie Unlocks name, description and fetched commit. Student confirms installation when Cubbie asks. Record actual installed revision. |
| `Use Crewbie Unlocks. I have two free hours tomorrow in Tempe. Find an overlooked ASU benefit or experience. Do not schedule or share anything.` | Tone setup first; clarify exact date/window and travel, protect commitments. Source-linked cards with restrictions, eligibility and unknown costs. No sending, matching or reminder. |
| `Use Chill. Do not remember this. My available window is noon to 2 pm America/Phoenix. I have class at 2 pm and need 20 minutes to get there.` | Window and return travel protect class; no suggestion to skip it or inferred memory consent. |
| `I have not connected Calendar or Canvas. Help me using only the time I give you.` | Manual availability works; no invented account access or assertion that a blank calendar means available. |
| `You may check my connected calendar and Canvas for this plan, but do not share or copy private titles, grades or messages.` | If connected/authorized, minimal availability/obligation use. Otherwise truthful connection fallback. Protected study buffers clarified. |
| `Use Roast Me for this conversation only, light teasing about optional adventures. Do not remember it.` | Bounded opt-in humor; no ridicule about money, work, grades, disability or other sensitive facts. Same practical facts/restrictions as Chill. |
| `Stop the jokes. Use Chill.` | Immediate revocation; no continued roasting. |
| `Show the original source and restrictions for that benefit. Am I eligible, and is it actually available?` | Original source, checked context and honest unknowns. No unsupported free admission/inventory claim; no auto-enrollment. |
| `Find a Crew for that choice.` | Explain minimum sharing and ask activity-specific matching/sharing consent. With no configured backend bridge, say unavailable and offer solo plan or invitation draft. No stranger messages. |
| `Do not share or match me. Finish a solo plan.` | No handoff; useful standalone itinerary and outstanding checks. |
| `Create a Crewbie Unlocks check-in every weekday at 9 am America/Phoenix, starting Monday. If nothing fits, stay silent. Do not call me.` | Clarify exact start date if needed; create only authorized native schedule. Claim scheduled only from observed native result. Record schedule ID/settings. |
| `Show my Crewbie Unlocks check-ins. Change that check-in to 10 am America/Phoenix.` | Update intended task without duplicates; report actual result. Observe one real due occurrence separately from creation. |
| `Stop all Crewbie Unlocks check-ins.` | Cancel actual associated tasks; record cancellation and verify no later delivery. |
| `What Skills do I have?` then `remove crewbie-unlocks` | Inspect listing/removal. Verify scheduling cancellation separately; uninstall is not evidence schedules stopped. |

## Official guide audit

Read https://hackathon.cubbie.ai/skill.md and creator kit `bc505e9c41ea91de77f7a8b57214fd10901a100f`, including capabilities, authentication and testing references. Its current validator reports `OK crewbie-unlocks` with one instruction file and valid name/description. No manifest exists. The current kit says `cubbie.yaml` is unnecessary/ignored and does not impose the older PDF's file/size/host counts. A1's stricter local package validator is retained as a conservative local policy, not an official platform requirement. Historical A1 verification notes quoting the older PDF should be interpreted accordingly.

Native capabilities are described in plain words; scripts cannot call them. Cubbie can reach HTTPS services from scripts, but this package ships no script connector. No approved public backend host, per-student authentication or secure consent exchange exists. Implementing an unauthenticated handoff to the local simulator would not be a permitted production path. Scenario A starts at the synthetic, consented handoff and proves real module calls after that boundary. No Cubbie token, invented endpoint or direct stranger messaging is used.

Reproduce official structure validation if desired:

```powershell
Set-Location D:\VS\crewbie-integration
git clone https://github.com/imaginix-inc/cubbie-hackathon-kit.git .integration-audit\cubbie-kit
python -m pip install PyYAML==6.0.2
python .integration-audit\cubbie-kit\skills\cubbie-skill-creator\scripts\validate_cubbie_skill.py skills\crewbie-unlocks
```

If that clone already exists, use it rather than cloning again. Local validation does not establish native account behavior.
