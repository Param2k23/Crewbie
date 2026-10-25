"""Three cross-module scenarios, synthetic external boundaries only."""
import json
from .runtime import Runtime, MEMBERS


def main():
    result = []
    for scenario in ("unlocks", "evening", "weekend"):
        runtime = Runtime()
        snap = runtime.seed(scenario, matching=True, sharing=True, introduction=True)
        sid = snap["session_id"]
        runtime.message(sid, MEMBERS[0], "maybe", "maybe")
        assert not runtime.snapshot(sid)["commitments"]["confirmed"]
        for i, ref in enumerate(MEMBERS):
            runtime.message(sid, ref, f"I accept version {snap['version']}", f"accept_{i}", version=snap["version"])
        final = runtime.snapshot(sid)
        assert final["state"] == "confirmed"
        report = {"scenario": scenario, "mode": "DEMO/SYNTHETIC", "state": final["state"],
                  "private_agent_calls": len(runtime.evaluator.calls), "version": final["version"],
                  "event_types": [e["type"] for e in runtime.events.sink.events(sid)], "booking_confirmed": False}
        if scenario == "weekend":
            revised = runtime.change(sid, {"request_id": "change_demo", "synthetic_confirmed": True,
                "changed_constraint_ref": {"member_ref": MEMBERS[2], "kind": "hard_budget", "value": 2000}})
            assert revised["state"] != "confirmed"
            report["after_change"] = revised["state"]
            report["after_change_version"] = revised["version"]
        result.append(report)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
