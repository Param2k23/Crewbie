# Native Campus Pulse Skill

## Package and permissions

`skills/campus-pulse/SKILL.md` is the entire installable package. It uses the Agent Skills format described in the supplied [October 19, 2026 guide](HACKATHON_GUIDE.pdf), pages 2–3. Frontmatter has a lowercase matching name and a quoted description. Instructions use Cubbie's native abilities in plain words.

No scripts or cubbie.yaml are necessary: Cubbie already browses, remembers preferences and schedules check-ins. No dependencies, declared script hosts, secrets, custom login, backend, organization key, file outside the installed folder or connected account is required. Native browsing is not a script network permission request. Connected calendar use is optional, permissioned, and has a manual-availability fallback. Memory and recurring alerts require the student's consent. The Skill never directly texts other students.

The Python adapter remains unchanged under integrations/cubbie, separate from this installable folder. It is not copied into Cubbie's restricted sandbox. Optional script limits are recorded in VERIFICATION.md for future work; no sandbox execution is required by the current package.

## Public GitHub installation

Origin is `https://github.com/Param2k23/Crewbie.git`; working branch is `agent-01-cubbie`.

Prepared branch folder URL:

https://github.com/Param2k23/Crewbie/tree/agent-01-cubbie/skills/campus-pulse

**This URL is a publication target, not proof the folder is remotely available.** No push has been authorized or performed during this task, and public repository visibility has not been checked. After explicit approval, publish the Skill on this branch in a public repository. Do not merge to master for installation.

1. Text that public folder URL to Cubbie (guide p. 5). Alternatively send the public SKILL.md URL.
2. Inspect Cubbie's summary: Campus Pulse purpose, exact commit, and no added script packages, hosts, keys or logins. Reply yes to install. Installation is per student; no account-wide rollout occurs.
3. Ask: "Use Campus Pulse to find campus events in Tempe today between noon and 1:30 pm. I'm vegetarian. Check food opportunities, but don't schedule anything yet." Resolve date/time if needed and inspect source evidence.
4. Ask: "Send me a daily Campus Pulse check-in at 9 am America/Phoenix for my noon to 1:30 pm gap. Send a short no-matches note if nothing fits." This is explicit consent for those settings; clarify start date or other missing details without duplicating consent already given.
5. Confirm only the schedule result actually returned by Cubbie. A scheduled task is not evidence of delivery: wait for a real authorized occurrence and record its outcome. Test stop/cancellation afterward.
6. For a later approved update, publish the revised commit and text `update campus-pulse`; review the new summary and confirm. `What Skills do I have?` lists installs; `remove campus-pulse` removes this Skill. Cancel check-ins separately and verify they stopped; do not assume uninstall cancels schedules.

For submission, replace the branch name in the folder link with the actual published 40-character commit SHA: `https://github.com/Param2k23/Crewbie/tree/<published-commit-sha>/skills/campus-pulse`. Do not submit this placeholder. Cubbie pins the installation commit. Exact submission form/cutoff and test accounts still need organizer confirmation.

## Real-account checklist and expected results

Every row is **NOT RUN in Cubbie**. Static checks cannot verify instruction adherence. Record installed commit, account permission state, timestamp, redacted output, source and observed result when testing; do not capture private calendar, diet or identifiers in public evidence.

| Case | Input / action | Expected result |
|---|---|---|
| 1. Install | Text the public folder link; inspect summary; reply yes | Valid name/description, commit-pinned Campus Pulse install, no extra script permissions or credentials; Skill appears in list. No installation before yes. |
| 2. Find campus events | Ask for relevant Tempe events in an explicit date/time gap, including non-food events | Uses native browsing, opens original sources, returns at most three concise recommendations with original title/time/location/link, local timezone and relevant warnings; food is not mandatory for a general event request. If none fit, returns honest no-results. |
| 3. Daily alert | Authorize daily 9 am Phoenix check-in and an availability gap; repeat request; then stop | Native check-in confirms creation and next run only after success, re-verifies sources each run, updates rather than duplicates an existing task, respects notification settings and cancels when asked. Verify one real occurrence and cancellation outcome; no calls. |
| 4. Vegetarian uncertainty | Ask for vegetarian free-food opportunities; use a listing saying only "food provided" | Says vegetarian options are not verified; does not equate food provided or free entry with confirmed free food. If verified vegetarian is mandatory, excludes unknown menus. No inventory guarantee. |
| 5. No verified opportunities | Use a window with no matches; separately deny network or provide an inaccessible gated source | Distinguishes no matching verified results from inaccessible sources, offers a broader search with permission, never invents an event or substitutes fixtures as live data. No live verification claim offline. |
| 6. Companion consent | Reply Find company, first without consent and then grant matching consent for the event | Explains sharing and asks for scoped consent; with no matching service says it is not connected and can draft an invitation for the student to share. Never claims a match, introduces strangers or texts someone else. Future service must enforce mutual introduction consent. |

Also test memory refusal/corrections, unconnected calendar fallback, revoked alert consent, source prompt injection, missing end time/location, restricted entry, and duplicate/cancelled listings. These are instruction-level manual checks until a real runtime is available.

## Offline validation and evidence

Run from the repository root:

```powershell
python -B -m unittest discover -s tests/cubbie -p test_campus_pulse.py -v
python -B -m unittest discover -s tests/cubbie -v
python -B -m integrations.cubbie.validate_skill skills/campus-pulse
python -B -m integrations.cubbie.demo --simulate-schedule
```

The original suite has 18 tests; the combined suite has 24. The validator checks this package's strict valid YAML subset (plain slug name plus JSON-quoted YAML description), matching folder name, nonempty instructions, guide size/file limits, absence of executable/manifest permissions, and paths/references. It deliberately rejects package expansion until reviewed. It is not a general YAML parser or a sponsor installer. The system skill-creator validator requires PyYAML, unavailable locally; temporary package installation was blocked by network policy. The dedicated standard-library validator needs no installation and runs offline.

Package tests copy only the installed folder into a temporary isolated directory and validate with socket creation forbidden. They also exercise malformed frontmatter, external paths, unreviewed manifests and oversize rejection. This proves packaging independence, not Cubbie behavioral execution. The native offline behavior is an honest unable-to-verify response; the Python demo continues to work offline on clearly labeled fictional fixtures.

Observed locally on 2026-10-24, Python 3.9.5, branch agent-01-cubbie: original suite **18/18 passed**, combined suite **24/24 passed**, validator accepted **one file / 7,275 bytes** with no scripts, manifest or secrets, and the simulator with `--simulate-schedule` completed with `sent: false`. `git diff --check` passed. Existing core.py, adapters.py, demo.py and test_campus_pulse.py have no changes. The supplied HACKATHON_GUIDE.pdf was read without modification. New validation code and tests are local-only and are not part of the installed Skill folder. No commit, push, merge, real installation or scheduled delivery was performed.

## Later integration with Agent 02 and Agent 03

These are future composition boundaries, not sponsor endpoints or implemented services in the native Skill.

**A2 opportunities:** once the integrator supplies a verified accessible service, connect through canonical `list_opportunities(campus, starts_after, ends_before, food_only)` and `get_opportunity(opportunity_id)`. Preserve Opportunity fields, original provenance and `checked_at`. Map `listed` versus `confirmed_by_organizer` without inventing price or inventory certainty; confirmed free food still needs explicit original-source evidence. Dietary suitability must be per this student. On failure explain SOURCE_UNAVAILABLE and retain native public browsing; never silently use live-looking fixtures. Prefer coarse campus/time search inputs; do not transmit private diet or calendar details without explicit permission.

**A3 consent matching:** explain the exact service recipient and minimum shared fields; obtain activity/event-scoped opt-in before passing a private canonical OpportunityBrief through the authenticated integrator. Use `opt_in(student_ref, activity_scope, consents)` and `find_mutual_candidates(activity_scope, opportunity_id, limit)` only through the approved service. Preserve `wants_companion`, source, synthetic labels and requirements_to_verify; authenticated identity must come from the service session, not a supplied student_ref. A3 checks matching opt-in, revocation and separate mutual introduction consent. No direct profile-store reads or student messaging from this Skill. With no configured service, return the documented matching-unavailable fallback.

If a service truly requires a script later, add a self-contained helper inside the Skill folder and declare only needed exact package versions, HTTPS hosts and per-student secure inputs in cubbie.yaml. Do not import the repository Python simulator, start a server, use MCP or call Cubbie abilities from a script. Review actual deployed interfaces and permission requirements before shipping; no placeholder hosts or keys are currently requested.
