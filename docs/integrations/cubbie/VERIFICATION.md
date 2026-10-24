# Campus Pulse provider verification

Updated: 2026-10-24 against the supplied **Build a Cubbie Skill — Hackathon Guide**, October 19, 2026, @ziyou ([local PDF](HACKATHON_GUIDE.pdf)). **Actual Cubbie Skill execution: UNVERIFIED. Track 1 is incomplete until public GitHub installation and the main flow succeed on a real account.** An instruction-only Skill now exists at `skills/campus-pulse/SKILL.md`; the preserved Python simulator is a separate local test component.

## Evidence and discovery

Read PROJECT_SPEC.md, CONTRACTS.md, COORDINATION.md, AGENT_01_CUBBIE_SKILL.md, fixture data and existing Python implementation. The newly supplied local PDF supersedes earlier assumptions that a custom Skill SDK, outbound scheduling API, or backend was necessary. Read all seven PDF pages by decoding its text streams and Unicode font maps. External PDF/YAML package installation was blocked by sandbox networking; no repository dependency or configuration was changed.

Historical discovery before receiving the guide: public searches used `Cubbie DevHacks ASU skills developer documentation API`, `"Cubbie" "DevHacks"`, and `"Cubbie" "skills" assistant developer`. These did not establish a sponsor-linked Skill specification. Search results were not proof that documentation did not exist.

The earlier [Cubbie API developer page](https://www.cubbie.com/developers) described procurement/catalog workflows and was not established as sponsor documentation. It is not used as evidence for this Skill. No authentication attempts, outbound messages or private listing access occurred.

## Guide-confirmed architecture

- Pages 1–2: Cubbie supplies web/browser abilities, memory, connected accounts, reminders and scheduled check-ins. Instructions name abilities in plain words; scripts cannot call those abilities directly.
- Pages 2–3: Agent Skills folder with YAML `name` and `description` in SKILL.md. Scripts and cubbie.yaml are optional. Native-only Skill needs no manifest, packages, keys or login setup.
- Pages 3–4, 6–7: Optional scripts run on Linux, Python 3.12 / Node 22; 2-minute default (up to 10), 1 CPU, 2 GB; first 8,000 output characters. Scripts use declared HTTPS hosts, exact dependency versions and per-student secure inputs. No background servers, MCP servers, script calls to Cubbie abilities, or team-secret hosting. None of these script facilities are needed or requested by Campus Pulse.
- Pages 5–6: Text a public GitHub repository, folder or SKILL.md link; review summary and exact commit; reply yes to install. Installs are per student and commit-pinned. Updates require a new summary and confirmation. Cubbie texts only its own student.
- Page 6: At most 5 MiB and 300 files per Skill, 1 MiB per file, 10 hosts and 5 keys; up to 20 installed Skills per student. Track 1 requires real install and main-flow execution within the first ten hours; exact cutoff and submission form need organizer confirmation.

## Capability table

| Capability | Status | Evidence / limitation |
|---|---|---|
| Frozen OpportunityBrief parser | VERIFIED locally | Fixture scenario and parser tests; not sponsor execution |
| Campus/time/food/freshness selection | VERIFIED locally | Automated tests against shared fictional opportunities |
| Private source-linked preview and uncertainty copy | VERIFIED locally | Runnable demo, source/diet/access tests |
| User-authorized campus, dietary and cadence parsing | VERIFIED locally | Context and message parser; no persistent sponsor memory |
| Scheduling, duplicate requests, cancellation, revocation | VERIFIED mock only | In-memory, explicitly invoked, one-occurrence due simulation; never sends |
| Agent Skills format and optional manifest | VERIFIED in guide, pp. 2–3, 6 | Native SKILL.md added; local strict-subset YAML/package validation passes; installer acceptance UNVERIFIED |
| Natural-language invocation and native abilities | VERIFIED in guide, pp. 1–3, 5 | Workflow names abilities in plain words; no tool schema invented; actual invocation UNVERIFIED |
| Memory and connected-account abilities | VERIFIED in guide, pp. 1–2 | Use permissioned native memory; accounts optional; per-account permission/revocation behavior UNVERIFIED |
| Scheduled check-ins and proactive messages | VERIFIED in guide, pp. 1, 3 | Consent-based native scheduling instructions provided; actual creation, delivery, duplicate handling and cancellation UNVERIFIED |
| Optional script sandbox / external calls | VERIFIED in guide, pp. 3–4, 6–7 | Exact versions, HTTPS host declarations, secure per-student inputs; no scripts or manifest shipped |
| GitHub installation, updates and limits | VERIFIED in guide, pp. 5–7 | Public link, summary, yes, commit pin; publication and install UNVERIFIED |
| Actual Track 1 runtime invocation | UNVERIFIED / BLOCKED | No real run, screenshot, receipt or provider log exists |

## Remaining real-account requirements

No backend API, SDK or credential is required for basic Track 1. Obtain an authorized Cubbie test account, approval to publish the Skill folder to a public GitHub branch, then text the folder link to Cubbie and confirm the installation summary. Verify discovery, dietary uncertainty, no-results behavior and consented native scheduling using the checklist in [NATIVE_SKILL.md](NATIVE_SKILL.md). Capture the installed commit and redacted actual results. Native ability internals, delivery guarantees and schedule-management behavior remain unobserved.

For future A2/A3 integration only: obtain integrator-approved HTTPS deployment hosts, authenticated identity/consent mapping, allowed service transport and error behavior. These services are not needed for native discovery or check-ins. A3 matching remains unavailable until configured, authorized and mutually consented; direct texting to others remains unsupported.

Run the real-account checklist and update statuses only from observed evidence. Local package checks and the Python simulator cannot establish actual Cubbie behavior. The preserved UnavailableCubbieProvider describes the local Python bridge's lack of a direct scheduling integration; it does not mean Cubbie's native scheduling is undocumented or unavailable.
