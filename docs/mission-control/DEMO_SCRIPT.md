# Three-minute judge flow

Prep: `cd apps/web && npm run build && npx next start` (or `npm run dev`), open `/arena`. Screenshots of every step are in `screenshots/`.

| Time | Action | What to say / what judges see |
|---|---|---|
| 0:00 | Open **Discover** (`/`) | "Crewbie finds options and labels what's unknown: food is *mentioned*, not guaranteed; diet unverified; sources and freshness shown." |
| 0:20 | **Quick Plan** tab → press **Step** 3× | Planning-intent panel (tonight, ~6h). Four agents, plan v1 **rejected**: a red fracture, reason generic ("availability conflict, details private"). |
| 0:50 | **Step** 7× | Counteroffer v2, fairness check, approvals requested. 2 ✓, 1 conditional (?, *not* an acceptance), 1 silent. Banner: nothing is confirmed. |
| 1:15 | **Judge**: hard budget → `12` → acknowledge → Send | Panel shows "Request sent, nothing changed yet" → "Server: accepted" → events arrive: v2 rejected, **v3 revised**, approvals reset to 0/4, itinerary preview changes. State: SIMULATOR badge. |
| 1:50 | Reset (R). Judge: budget `4` | Honest outcome: **No plan** (NO_FEASIBLE_PLAN), nothing confirmed. |
| 2:10 | **Weekend Plan** → Step to hold (12) | Two failed proposals (budget, departure), v3 itinerary on a two-day horizon, redacted constraints. |
| 2:30 | Judge: **Withdraw** `stu_taylor` | v4 for a group of three: withdrawn node stays ✕, approvals 0/3. Then **Let remaining members accept** → confirmed only after the confirmation event. |
| 2:50 | Press **V** | Same state in the accessible 2D view. Mention Live tab: same UI over the read-only SSE bridge; the dev server answers 501 to judge requests and the UI reports it honestly. |

Everything labelled SYNTHETIC / NOT THE REAL ENGINE is scripted by A6; success states only follow emitted events.
