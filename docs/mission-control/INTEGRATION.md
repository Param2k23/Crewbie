# Integration notes for the integrator (Agent 06)

Everything below is something A6 **assumes, needs, or could not decide alone**. Nothing here edits contracts; each
item is a proposal for the integrator to accept or reject.

## 1. Wiring (what to do at merge)

1. Create one `MemoryEventSink` (or your own `EventSink`) and hand the **same instance** to A4 and A5 as their `EventSink`:
   ```python
   from services.realtime import MemoryEventSink
   from services.realtime.fastapi_router import create_router   # needs fastapi; verified with fastapi+uvicorn
   sink = MemoryEventSink()
   app.include_router(create_router(sink))     # GET /v1/sessions/{session_id}/events  (SSE, Last-Event-ID)
   ```
   `sink.emit()` **raises `EventRejected`** for non-`group_safe`/private-looking/malformed events. Producers should
   catch it and log the code; it is a bug in the producer, never something to retry or scrub.
2. Web app: `NEXT_PUBLIC_CREWBIE_API_URL=https://api-host` (or leave unset and type it in the Live tab). The API must
   allow the web origin via CORS (`Access-Control-Allow-Origin`, headers `content-type, idempotency-key, last-event-id`)
   or be reverse-proxied same-origin. A6 did not edit root/Next rewrites to avoid cross-ownership config.
3. `services/realtime` is stdlib-only (Python ≥ 3.10). `dev_server.py` is a rehearsal tool, not for production.

## 2. API the UI needs from other agents

| Need | Owner | Status in A6 |
|---|---|---|
| `GET /v1/sessions/{id}/events` SSE of `group_safe` events | A6 (done) | implemented, tested |
| **`POST /v1/sessions/{id}/constraint-changes`** – judge intervention | **A4** (wraps `revise_negotiation(session_id, changed_constraint_ref)`) | UI client done; **route does not exist yet**. Dev bridge returns 501 and the UI reports it honestly |
| **`GET /v1/sessions/{id}/snapshot`** → public snapshot | A4 (`get_public_snapshot`) | reducer supports comparison (`PublicSnapshot` type); **no fetcher wired** because the route/shape is unspecified |
| Opportunity list `list_opportunities(...)` over HTTP | A2 | Discover reads the fixture copy only |
| **Public plan snapshot with itinerary** (title, window, activities with times, aggregate budget wording) per version | A4 | UI has `PlanPreview` and renders it from `adapter.previews()`; live streams supply none today, so the itinerary panel says "not supplied". Needs an agreed sanitized shape (aggregate/redacted costs only, per CONTRACTS §2 CandidatePlan) |
| Match/introduction request (`opt_in`, `find_mutual_candidates`) | A3 | "Find company" button is permanently disabled with an explanation |

### Judge request (proposed)

```
POST /v1/sessions/{session_id}/constraint-changes
Idempotency-Key: judge_ab12cd34
{
  "request_id": "judge_ab12cd34",
  "session_id": "session_demo_001",
  "changed_constraint_ref": {"member_ref": "stu_alex", "kind": "hard_budget", "value": 4500},
  "synthetic_confirmed": true
}
```
* `kind`: `hard_budget` (`value` = integer US cents) | `block_window` (`value` = opaque window id; the live adapter
  currently offers `blocks_current_day` | `blocks_all_days`, A4 should define the real vocabulary) | `withdraw`
  (`value` = `"withdraw"`; the server should emit `member_response_received` with `state: withdrawn`, then a revision whose
  `approval_requested.required_count` reflects the remaining participants).
* Changed (A6 v2): the previous `availability` kind was renamed `block_window`.
* Respond `202` (accepted for processing) / `4xx` rejected. **The UI treats a 2xx only as "request received"**; the
  outcome must arrive as events (`proposal_rejected` → `proposal_revised`/`negotiation_failed` …).
* **Server-side authorization is mandatory:** refuse unless the session and `member_ref` are synthetic sandbox data.
  The UI's synthetic gate is a convenience, not security.
* Please echo `request_id` in the payload of the resulting events (see §3) so the panel can show
  "Reflected in the event stream". If not echoed the panel truthfully says "Not yet reflected".

## 3. Event payload expectations / proposed optional fields

A6 renders only these payload keys (anything else is dropped; private-looking keys reject the event):
`plan_id, version, group_size, reason_category (free slug; labelled for constraint_conflict, budget_conflict, availability_conflict, departure_conflict), summary, approval_state, required_count, accepted_count, member_ref,
state, condition_category, fairness_category, failure_code, changed_constraint_kind, opportunity_id, request_id`.

The canonical fixture already covers most. **Optional additions proposed** (older clients ignore them; CONTRACTS §1 rule):

| Field | On event(s) | Why |
|---|---|---|
| `version` | every plan-related event | reducer needs it; `counteroffer_proposed` in the fixture has `version` but **no `plan_id`** (handled) |
| `required_count` | `approval_requested`, `proposal_confirmed` | approval arc + confirmation consistency check |
| `accepted_count` | `proposal_confirmed` | cross-check against responses seen in the stream |
| `condition_category` (slug, e.g. `needs_time_change`) | `member_response_received` with `state: conditional` | explain conditional approvals without free text |
| `fairness_category` (slug, e.g. `balanced`) | `fairness_evaluated` | `fairness_evaluated` has no defined payload in CONTRACTS; nothing per-member is shown |
| `failure_code` (e.g. `NO_FEASIBLE_PLAN`) | `negotiation_failed` | contract §5 error codes |
| `changed_constraint_kind` (`hard_budget`/`availability`) | `proposal_rejected`/`proposal_revised` after a judge change | generic cause only, **no member identity or value** |
| `request_id` | events caused by a judge request | correlation |

**Never** put `member_ref` on a conflict/rejection event: the arena deliberately shows the conflict without attributing it.

### Ordering

The reducer sorts by `(timestamp, event_id)`, so producers must emit **non-decreasing timestamps per session** (the
fixture does) – or tell A6 to switch to a monotonic `seq` field. Clock skew between A4 and A5 emitters would otherwise
reorder events (e.g. a response sorting before its `approval_requested` is ignored as stale).

## 4. Open questions for the integrator

1. **Judge route path/shape** (§2): accept `…/constraint-changes` or name the real one? Who validates "synthetic only"?
2. **Public snapshot route + shape** (assumed `{session_id, current_version, status, accepted_count?, required_count?}`).
3. **SSE authentication.** Browser `EventSource` cannot send an `Authorization` header. Options: same-site cookie,
   short-lived signed `?token=` issued by the API, or switch A6 to `fetch()`-based streaming. A6 currently sends
   no credentials (demo only). Production authZ for "who may watch session X" is unresolved.
4. **Member display.** The UI shows `member_ref` verbatim (`stu_alex`). Is showing opaque refs to all viewers acceptable,
   or should A3/A4 publish consented display labels (e.g., first names) in a public event field?
5. **Group size before refs are known.** Refs appear only when members respond; until then the arena shows
   "Agent 1…n" slots from `negotiation_started.group_size`. A `members_listed`-style public field would remove the placeholder
   but is a contract change (not proposed unless wanted).
6. **Real Campus Pulse feed** (A2) and the **Find company** flow (A3 consents) – routes and response shapes.
7. Should `fairness_evaluated` carry anything beyond a category? (Currently not rendered numerically on purpose.)

## 5. Known blockers / non-blockers

* **No blockers** for standalone use. Real end-to-end behaviour (a judge change driving A4) is blocked on §2 routes.
* `npm audit` reports advisories on the pinned `next@15.x` (transitive `postcss`). Root dependency policy is the
  integrator's call; upgrading Next within the 15 line should be tried at merge. Production `npm run build` passes.
* Screenshots were produced in headless Chromium with software WebGL; real GPUs will look smoother.
* A6 added `apps/web/node_modules` handling via `apps/web/.gitignore`; there is **no root workspace config**.
  If the integrator creates a root `package.json` workspace, `apps/web/package.json` name is `crewbie-mission-control`.
* Python tests run with `unittest` (pytest is not installed in the sandbox); they are pytest-compatible.
* The demo adapter's events are authored by A6 and are **not** negotiation-engine output. Replace with live events at merge;
  nothing else depends on them.
