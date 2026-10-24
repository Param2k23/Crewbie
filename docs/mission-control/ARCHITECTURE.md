# Architecture

## Data flow

```
 source (Adapter)                       pure core                        views
 ───────────────                        ─────────                        ─────
 FixtureAdapter  ─┐                   sanitizeEvent (allowlist,          StatusPanel / VersionsPanel
 DemoAdapter     ─┼─ raw events ───▶  visibility gate, leak scan)  ──▶   Event timeline / Inspector
 NetworkAdapter  ─┘  (SSE / replay)   missionReducer                     ArenaScene (R3F) ─┐ both read
        ▲                            log = unique events sorted by       ArenaFallback (SVG)┘ buildSceneModel()
        │                            (timestamp,event_id); view =
  JudgeAdapter ◀── request only ──   deriveView(log) (pure fold)
  (never writes state)
```

* **`lib/events/sanitize.ts`** – every event passes through it, even from our own fixtures. `visibility` must equal
  `group_safe`; payload keys are an allowlist with typed validators; any key matching budget/cost/calendar/prompt/
  reasoning/token/diet/private/internal… (at any depth) rejects the **whole** event (a producer leak is a bug, not
  something to scrub quietly). Free text drops `<>`/control chars, is length-capped, and is only ever rendered as React
  text. Rejections are counted by code; contents are never displayed.
* **`lib/events/reducer.ts`** – state is `log` + derived `view`. The view is a **pure fold of the sorted, de-duplicated
  log**, so duplicates, reordering and late arrivals cannot double-apply anything (tested at every prefix of the fixture).
  Rules worth knowing:
  * `proposal_confirmed` is shown as confirmed only if it targets the current version **and** the stream contains at
    least `required_count` `accepted` responses for that version **and** any reported `accepted_count` matches.
    Otherwise it is recorded as *not applied*, a `CONFIRM_MISMATCH` sync warning is raised, and the UI stays "pending".
  * Responses for a non-live version are ignored (`STALE_VERSION`). A new version starts with zero approvals;
    older approvals stay in `commitmentsByVersion` as history only.
  * `conditional`, `interested`, `tentative`, `pending` never count as acceptance.
  * `negotiation_failed` is a valid terminal state (`NO_FEASIBLE_PLAN`), shown without alarm wording.
  * `compareSnapshot()` + the `snapshot` action surface disagreement between a public snapshot and the stream.
* **`lib/replay/controller.ts`** – step/play/pause/reset/speed. Timers only pace *when a recorded event is revealed*;
  tests prove that with no ticks nothing is confirmed. Hold points pause before a given index (used by the demo).
* **`lib/adapters`** – `MissionAdapter { connect, replay, judge, actions }`.
  `FixtureAdapter` (canonical file), `DemoAdapter` (scripted + `LocalSimulator`), `NetworkAdapter` (SSE, browser
  `EventSource` handles `Last-Event-ID`). `HttpJudgeAdapter` maps 404/501/network errors to "unavailable" and other
  failures to "rejected"; only a 2xx is "accepted", and even that only means *the request was received*.
* **`lib/scene/model.ts`** – the single `MissionView → SceneModel` mapping used by both the 3D scene and the SVG
  fallback, so they cannot disagree. Lines appear only after `approval_requested`; the approval arc is
  `accepted/required` from backend counts; the red fracture means `reason_category`/`failure_code` and names no one.

## Components

`app/page.tsx` → `CampusPulse` · `app/arena/page.tsx` → `MissionControlApp` (mode tabs + live form) →
`MissionControl({ adapter })` (controls, stage, inspector) → `ArenaScene` (dynamic, no SSR) | `ArenaFallback`,
`StatusPanel`, `VersionsPanel`, `JudgePanel`, timeline, `Legend`.

3D falls back to 2D automatically when WebGL is missing or the scene throws; the user can force 2D (button, `V`,
`?view=2d`, remembered in `localStorage` with try/catch). `prefers-reduced-motion` stops animation and uses
`frameloop="demand"`.

## Honesty rules (what the UI will not do)

1. No success state without the matching backend event; no timer or button creates one.
2. Judge UI = request lifecycle only (`pending → server answer → "reflected in stream"` when an event echoes the
   `request_id`). It never edits plan state.
3. Demo mode is a separate, always-labelled adapter (`NOT THE REAL ENGINE`, actor refs `demo_script`/`local_simulator`).
   Its simulator thresholds are internal and not rendered.
4. Judge controls are disabled unless every received event is `synthetic: true`, and demo profiles are whitelisted.
   (UI gating is not authorization; see INTEGRATION.md.)
5. Campus Pulse never says "free food now"; `listed` ⇒ "mentioned in listing; availability unknown", dietary fit is
   "unverified" unless the data has `known_*`. The private profiles in `scenarios.json` are never imported.
