"""Regenerate frontend contract evidence from the actual Python modules."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.api.runtime import Runtime, MEMBERS

traces = {}
for scenario in ("unlocks", "evening", "weekend"):
    runtime = Runtime()
    snap = runtime.seed(scenario, matching=True, sharing=True, introduction=True)
    sid = snap["session_id"]
    pending = runtime.events.sink.events(sid)
    for i, ref in enumerate(MEMBERS):
        runtime.message(sid, ref, f"I accept version {snap['version']}", f"approve_{i}")
    traces[scenario] = {"pending": pending, "confirmed": runtime.events.sink.events(sid), "snapshot": runtime.snapshot(sid)}
    if scenario == "weekend":
        runtime.change(sid, {"request_id": "constraint_change", "synthetic_confirmed": True,
            "changed_constraint_ref": {"member_ref": MEMBERS[2], "kind": "hard_budget", "value": 2000}})
        traces[scenario].update(replanned=runtime.events.sink.events(sid), replanned_snapshot=runtime.snapshot(sid))
target = ROOT / "apps/web/tests/data/integrated-traces.json"
target.parent.mkdir(exist_ok=True)
target.write_text(json.dumps(traces, indent=2) + "\n", encoding="utf-8")
print("Exported real-module synthetic traces:", target)
