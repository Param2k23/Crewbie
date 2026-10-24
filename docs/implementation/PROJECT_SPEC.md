# CREWBIE — Master Project Specification

**Tagline:** Find your people. Make a plan. Actually show up.  
**Purpose:** One shared reference for six autonomous coding agents building in parallel.  
**Status:** Build specification, not an implementation.  
**Scope:** DevHacks ASU / Cubbie hackathon; Track 1 mandatory (Cubbie Skills), Track 2 (Agent-to-Agent Coordination), Track 3 (Group Chat Assistant).  
**Last revised:** 2026-10-24.  
**Canonical companion:** [`CONTRACTS.md`](CONTRACTS.md), [`COORDINATION.md`](COORDINATION.md), agent files under [`agents/`](agents/).

> **Reality check:** The sponsor-provided Cubbie Skills API, outbound scheduling permissions, supported messaging providers, and complete ASU event access have **not** been validated. Implement adapters and explicit demo fallbacks; do not invent integrations or imply coverage.

## 1. One-sentence definition

Crewbie is a **Cubbie-powered social coordination system** that finds relevant student opportunities, helps consenting students connect, has individual agents privately negotiate feasible and fair group plans, and uses one group-chat host to obtain human commitments; an event-driven 3D Mission Control shows what actually happened.

## 2. The one product loop

1. **Discover:** Student receives a useful opportunity (e.g., club offers food during an available lunch gap) or proposes a group activity (e.g., four friends want a Flagstaff trip).
2. **Understand:** Cubbie Skill or group chat creates a structured, source-grounded intent; no inferred certainty about event food, costs, or user consent.
3. **Opt in:** Student elects to match with others or invites existing friends; personal agents only participate within authorized scope.
4. **Negotiate:** Agents propose options, privately check individual constraints, and produce a feasible candidate; fairness ranks feasible alternatives, never waives a hard limit.
5. **Agree:** One group-chat host introduces people, offers a contextual icebreaker, and records explicit agreement to an identical proposal version.
6. **Act/adapt:** With permission, Cubbie sends reminders; changes invalidate affected approvals and trigger bounded re-negotiation.

**Design constraint:** Campus Pulse and the Flagstaff trip are **two examples of the same coordination engine**, not separate apps. Food discovery is the human hook; group negotiation is the technical centerpiece.

## 3. Target users and demonstrated outcomes

- **Solo student:** Finds a credible nearby campus event that fits an authorized lunch window even without companion matching.
- **Opt-in companions:** Find a consenting person to attend an opportunity together, agree on a public meetup, and receive a mutually approved icebreaker.
- **Existing friend group:** Produces a plan without disclosing private budgets, work commitments, or reasons for discomfort; no one is marked confirmed on a 'maybe'.
- **Hackathon judge:** Changes a constraint, watches the current plan fail validation, observes legitimate re-planning, and confirms that UI state corresponds to structured backend events.

## 4. Canonical demonstration scenarios

### Scenario A — Campus Pulse: free food + someone to go with

Student opts in to a morning campus-food alert, sets campus, dietary preferences, lunch window and alert cadence. Crewbie shows an event with a **verifiable citation URL**, food-indicator evidence, time, venue if publicly available, RSVP/access requirements, and freshness. It explicitly marks dietary suitability, remaining availability and public access **unknown** when unconfirmed. Student chooses **Find company**. Consent-based discovery finds another opted-in student. Private agents establish compatible timing. With mutual approval the host introduces both students, offers one event-specific icebreaker, and proposes a safe public meetup.

**Non-negotiable:** “Food Provided” is not equal to “guaranteed free meal,” vegetarian/halal safe, unrestricted entry, or food still available. A logged-in-only directory must not be bypassed. Curated sample opportunities must be visibly marked *demo fixtures*, not presented as live ASU events.

### Scenario B — Four friends' Flagstaff plan

Four consenting synthetic participants privately specify: an **$60 hard budget cap**; one **cannot miss Saturday work**; one **strongly dislikes early departures**; and one **prefers low-cost activities**. Agents propose plans, check individual feasibility without leaking actual budget or work reasons, rank valid options for fairness, and send one proposal to group chat. If the least-cost option still exceeds a hard cap, the affected user alone receives a private exception request; without approval it stays infeasible. One chat participant responds “maybe,” remaining pending. A judge lowers a cap or changes availability; existing proposal/approvals are invalidated as needed, and a new revision or honest no-solution result appears in Mission Control.

**Non-negotiable:** estimates are clearly estimates; no fake transport inventory, paid bookings, payment collection or guaranteed travel timing.

## 5. Three independent, connected track submissions

| Track | Component | Independent value / judge proof |
|---|---|---|
| **T1 mandatory: Cubbie Skills** | Campus Pulse Skill and intent-to-action workflow | Verified Skill execution in Cubbie, source-aware food alerts, useful without another student |
| **T2: Agent-to-Agent Coordination** | Private participant agents + constraint/fairness negotiator | Real counteroffers and deterministic invalidation under private conflicting constraints |
| **T3: Group Chat Assistant** | Crewbie Host and commitment protocol | Existing four-person chat reaches a versioned agreement; conditional or silent replies remain pending |

**Never** have 4 agents chat visibly in group; there are 4 *private* agents and 1 visible shared host.

## 6. Product requirements

### P0 — Must be working

- Native Cubbie Skill **as actually allowed by sponsor docs** OR documented non-submitted local simulator while awaiting access; flag unmet sponsor eligibility separately.
- At least 3 source-attributed, clearly genuine **or clearly fixture-labeled** candidate events. Filtering by campus, time gap, food tag, dietary uncertainty; no unsupported certainty.
- Consent-based opt-in for companion matching; full private info stays on user's side.
- Four independently constrained synthetic student profiles and agent feasibility/counteroffer negotiation.
- Deterministic validator: hard availability, budget, required roles/access/approval cannot be overridden by language model.
- Group host: acceptance state machine (interested / tentative / conditional / accepted / declined / withdrawn); approvals bound to proposal version.
- Interactive Mission Control reacting to actual emitted agent events, including failure and recovery.
- End-to-end synthetic fallback demo with no third-party secrets required.

### P1 — Important if P0 solid

- Fairness history across two sessions, only opted-in; well-defined scoring and no hard-constraint override.
- Source freshness/RSVP warnings and practical campus transit buffer.
- Icebreaker with approved shared interest; one compact opt-in reminder handoff.
- Dropout recovery and reason-redacted explanation.

### P2 — Stretch, not a prerequisite

- Vision model extracts event flyer information, subject to human verification.
- AR-lite camera overlays, richer 3D visuals, wider campus sources, real optional calendar sync.

### Out of scope

A full travel-booking/payment system; generic student planner; AI course tutor; automated public profile scraping; unauthorized scraping or login bypass; detailed AR/VR world; identifying people from camera feed; claiming live food inventory.

## 7. Architecture and ownership

```text
Cubbie message / Skill           Public/authorized event sources
        |                                     |
 A1 Skill Adapter                         A2 Event Catalog
        |                                     |
        +--------------- Opportunity Brief ---+
                              |
                  A3 Consents / Profiles / Match pool
                              |
                   A4 Negotiation Engine
          proposals -> private feasibility checks -> ranking
                              |
                 A5 Commitment & Chat Host
                              |
                       human confirmations
                              |
      A6 Realtime adapter -> 3D Mission Control (event stream)
```

**A1** Cubbie Skill, scheduling adapter, student messaging preview.  
**A2** campus event ingestion, source evidence, filter/query API.  
**A3** student private profiles, consent gate, opt-in matching, private feasibility oracle.  
**A4** negotiation coordinator, deterministic validation, fairness, proposal revision and event emission.  
**A5** group-chat bot, icebreakers, commitment/version state machine.  
**A6** 3D Mission Control, read-only realtime stream bridge, design and usability.

One human project lead/integrator owns API composition, environment bootstrapping, review, merges, and secrets. **The integrator is not a seventh coding agent.** No agent edits another agent's directory. Interfaces are frozen in `CONTRACTS.md` before parallel coding.

## 8. Integration strategy

Each agent delivers a self-contained component with a runnable **mock/demo mode**, unit tests, README and a clearly bounded adapter. Parallel agents must not depend on another agent being finished.

- No agent edits the root shared config, root README, `CONTRACTS.md`, or another owner's files without an approved contract-change request.
- Cross-team communication is typed JSON, or an in-process Python interface wrapped by an HTTP router; contract remains transport-neutral where possible.
- Synthetic IDs and UTC RFC3339 timestamps for event records; use campus-local time with offset in displayed event summaries.
- A4 emits redacted domain events. A6 subscribes to them; NEVER visualize raw LLM prompts, hidden reasoning or private constraint values.
- The integrator connects adapters through one composition layer after merging feature branches.

## 9. Privacy and integrity requirements

- Opt-in matching and mutual consent before creating a stranger introduction.
- User-private fields (exact budgets, private schedule details, diet if sensitive, work reasons) cannot be included in group messages, client dashboard payloads, or logs.
- Minimize inference leakage: use a bounded number of private feasibility evaluations and coarse feedback; agents do not expose precise budget ceilings by repeated binary probing.
- A hard budget/availability limit requires private **explicit approval** for an exception; do not auto-adjust it.
- A proposal is confirmed only when *every required member* explicitly approves the **same version**.
- Changes to required participants, itinerary, estimated individual spend, key times, or hard constraints generate a new version and reset impacted approvals.
- Flag unknown food/diet/RSVP/access fields; no fictitious current free food.
- No money movement, RSVP, external invites or third-party data sharing without authorized action.
- Synthetic demo profiles must be clearly labeled; optionally purge sensitive temporary data after run.

## 10. Quality gates and acceptance tests

1. **Sponsor eligibility:** A1 has a screenshot/log/validated test in actual Cubbie, or explicitly reports *unverified* and describes remediation.
2. **Opportunity trust:** A2 event has provenance and `food_status` correctly distinguishes `listed` from `confirmed`; a blocked listing cannot be silently traversed.
3. **Match consent:** A3 rejects stranger matching and introduction unless both participants explicitly opt in.
4. **Hard rules:** A4 rejects a $70 estimated cost against a $60 hard cap, Saturday conflicting work time, and conflicting required roles.
5. **Privacy:** Neither A4 public events nor A5 outbound group messages contain an exact private cap, private calendar description, or refusal reason.
6. **Fairness:** Among feasible near-equivalent options, ranking can favor the previously burdened member; never pushes any infeasible option through.
7. **Commitments:** A5 leaves “maybe” pending, captures conditional acceptance correctly, and resets approval on material revision.
8. **UI fidelity:** A6 renders `proposal_rejected`, `proposal_revised`, and `proposal_confirmed` from the event stream, not arbitrary timers.
9. **Offline demo:** All six modules run on the shared synthetic fixtures without network, provider credentials or payments.
10. **Smoke test:** Campus Pulse -> consented match -> introduction; separate trip -> conflict -> re-plan -> explicit approve -> confirmed.

## 11. Time and prioritization

**Hour 0–1:** Integrator freezes contracts; A1 validates Cubbie sponsor APIs; A2 validates campus listings and fallback; other agents generate mock-driven modules.  
**First 10 hours:** A1 must prioritize the required working Skill and submission artifacts; integrator checks track eligibility. Other agents complete their minimal vertical slices independently.  
**Second block:** Integrate negotiation with profile evaluator, then chat commitments, then realtime Mission Control; test explicit approval and private exception path.  
**Final block:** Scripted-but-real backend test scenarios, graceful fallback, rehearsal, screenshots, and track-specific submission packages.

Work backward from actual hackathon end time; this is sequencing guidance, **not** a claim about official schedule.

## 12. Demo storyboard (3 minutes)

- **0:00–0:35** Campus Pulse Cubbie Skill: source-linked food notice aligned with lunch gap; show dietary uncertainty.
- **0:35–1:00** Student taps “Find company”; consented matched companion; group intro + event-specific icebreaker.
- **1:00–1:45** Switch to four-friend Flagstaff scenario. Live Mission Control shows alternatives rejected and counteroffers generated.
- **1:45–2:25** Judge changes private budget or availability; affected plan fails, event stream updates, agents produce a better feasible version (or honestly explain no solution).
- **2:25–3:00** Group host tracks “maybe” as pending; all four explicitly accept the same plan; Mission Control displays confirmation.

## 13. Open decisions / blockers

- Exact Cubbie Skills SDK, event triggers, data scopes, rate limits, and supported outbound reminders: **Sponsor docs required.**
- ASU public/authorized events access: **A2 must verify immediately.** Sun Devil Central replaced the retired Sun Devil Sync; do not claim broad coverage without a source.
- Messaging platform (Discord recommended for hackathon reliability, subject to permitted app/bot policies): **Integrator chooses after A5 provider spike.**
- Actual demo hardware, schedule, production domains, API keys and participants: **Team decides.**

## 14. Definition of done

A reliable P0 implementation proves one unified product, all 3 track-specific capabilities stand independently, private limits never leak, the group never confirms an unapproved plan, Mission Control displays real negotiation events, and the demo remains runnable offline using labeled synthetic data.
