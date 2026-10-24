# Agent 06 — Mission Control 3D Frontend & Safe Realtime Stream

**Branch:** `feat/a6-mission-control`  
**Exclusive owner:** `apps/web/`, `services/realtime/`, `tests/realtime/`, `docs/mission-control/`  
**Mission:** Deliver the audience-attracting visual experience—**Campus Pulse** and an interactive **Negotiation Arena**—that reveals actual backend decisions, not decorative pretend agents.

## Your system prompt / job

> You are Agent 06, owner of Crewbie's Next.js frontend, 3D Mission Control and the read-only realtime event adapter. Read spec, contracts, fixtures and this file. Work only in owned paths. Build a polished but robust visualization driven entirely by `AgentEvent` payloads. Never show exact private budgets, individual calendar details, raw LLM text or private reasons. Make 2D fallback and mock replay from fixtures available offline. Do not make AR/VR or live map integrations prerequisites. All judge controls call a mock or real action API through an injected adapter, never quietly mutate local UI to fake success.

## Product responsibility

- **Campus Pulse view:** friendly campus opportunity cards/timeline, food-tag uncertainty, source link, local campus time, availability match, "Find company" CTA gated on opt-in and enabled only if integration exists.
- **Negotiation Arena:** 3D nodes for consenting student agents, glowing safe connections, actual proposal timeline, failure/re-plan visualization, current plan version, pending/accepted group states.
- **Judge Controls:** *in synthetic demo mode* inject a budget-change or availability-change action into A4 through a real API adapter (or a clearly labeled local simulator).
- **Event bridge:** A6 owns a generic `EventSink` transport adapter + read-only SSE endpoint; internally A4/A5 may inject a sink but never write UI state themselves.
- Meaningful state and useful visual explanations: `proposal_rejected`, `counteroffer_proposed`, `proposal_revised`, `proposal_confirmed` must clearly map to UI transitions.
- Works on standard laptop browser; no VR headset, hand tracking, camera, or WebXR dependency.

## Exclusons / safety

Do not invent live map travel metrics, confirmed food quantities, dietary safety or authenticated event access. Do not show private student constraints in any node tooltip or event feed. No unauthorized screenshot/face recognition. "Judge intervention" is only available on sandbox synthetic profiles, never edit a real user's limits from public UI.

## Interfaces

- Consume `Opportunity`, *public sanitized* plan snapshots and `AgentEvent` from `CONTRACTS.md`.
- Read-only `GET /v1/sessions/{session_id}/events` SSE with `Last-Event-ID` reconnect handling.
- Provide `EventSink.emit(event)` adapter in `services/realtime/`; A4/A5 can use `MemoryEventSink` independently until integrated.
- `MissionControl(session_id, adapter)` React component with mock and network adapters; never rely on hidden LLM chain-of-thought.

## Implementation phases

### Phase 0 — UX frames + fixture stream

1. Build project-local Next.js/TypeScript scaffold **without editing shared root configs**.
2. Define two screens and a common design system: Campus Pulse (warm, accessible, clear sources) and Negotiation Arena (dark, immersive, legible event status).
3. Implement fixture-driven event playback from `fixtures/agent_events.json`; allow step/manual advance so judges can pause the state.
4. Support reduced motion and 2D fallback for lower-power laptops; use synthetic/demo labels.

**Gate:** browser runs offline fixture UI with meaningful states, no backend needed.

### Phase 1 — Functional visualization

1. Render campus event cards with source URL and status indicators; distinguish verified vs unknown food/diet.
2. Build simple 3D orbit/constellation with one node per public participant; proposal connections represent actual event state.
3. Timeline and inspector show proposal version, high-level conflict category, public compromise summary and approvals count.
4. Define event reducer mapping each allowed public type into deterministic UI state; no timer-based fake completion.
5. Add keyboard-accessible control panel and clear empty/error/loading states.

**Gate:** applying same sequence of events yields same UI state; withheld/private events do not render.

### Phase 2 — Real-time connection and judge controls

1. Build SSE broker/adapter under `services/realtime/` and reconnect/dedup rules for emitted group-safe events.
2. Connect mocked negotiation session to visual playback through injected adapter; confirm UI matches true snapshot.
3. Add judge panel that calls change-budget/change-availability on *synthetic* profiles via actual test API; show pending state until server confirms mutation.
4. Demonstrate rejection and legitimate repair or no-feasible-plan through real events.
5. Prevent untrusted event `payload` from embedding HTML/scripts or sensitive field names in tooltips.

**Gate:** change action never claims success before network/simulator response; events drive transitions.

### Phase 3 — Live integration, performance and polish

1. Connect A2 source-aware catalog, A4 public snapshots and A5 commitment updates through integrator routes.
2. Avoid exposing A3 private profile endpoint to web; require only public-safe projected fields.
3. Stress test four-agent case, reconnect, duplicate events, late-arriving revisions and responsive laptop screen.
4. Deliver 3-minute judge mode, one-click scene reset, keyboard shortcuts and a stable 2D fallback.

## Must-pass tests

- `proposal_rejected` visually breaks/marks a proposal; `proposal_revised` shows new version; `proposal_confirmed` only after backend signal.
- Out-of-order/duplicate event delivery does not double-apply a confirmation.
- An `internal`/private event is rejected and not displayed.
- Source-unverified Campus Pulse cards do not claim "free food now" or dietary guaranteed.
- Judge control cannot mutate a non-demo student.
- With JS animations disabled / lower GPU, 2D fallback still shows true state and can complete demo.
- Snapshot/event disagreement shows sync warning instead of pretending success.

## Standalone demo / handoff

Deliver a local Next.js route for Campus Pulse and Mission Control, a replay/stream mock, screencast or screenshots, known limitations, build/test commands, and integration adapter notes. **No full AR/VR work until P0 passes.**
