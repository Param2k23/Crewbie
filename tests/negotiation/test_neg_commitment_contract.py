"""Executable form of docs/negotiation/COMMITMENT_SUMMARY_PROPOSAL.md (A5 may reuse check_commitment_summary)."""
import unittest

from neg_helpers import Rig

REQUIRED = {"session_id": str, "plan_id": str, "version": int, "required_count": int, "accepted_count": int}
OPTIONAL_COUNTS = ("declined_count", "withdrawn_count")


def check_commitment_summary(summary, session_id, plan_id, version):
    """Return a list of contract violations (empty = conforms)."""
    bad = []
    for key, typ in REQUIRED.items():
        v = summary.get(key)
        if isinstance(v, bool) or not isinstance(v, typ):
            bad.append(f"{key} must be {typ.__name__}")
    for key in OPTIONAL_COUNTS:
        v = summary.get(key, 0)
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            bad.append(f"{key} must be a non-negative integer")
    if "confirmed" in summary and not isinstance(summary["confirmed"], bool):
        bad.append("confirmed must be boolean")
    if (summary.get("session_id"), summary.get("plan_id"), summary.get("version")) != (session_id, plan_id, version):
        bad.append("echo fields must match the request")
    if isinstance(summary.get("required_count"), int) and summary["required_count"] < 1:
        bad.append("required_count must be >= 1")
    extra = set(summary) - set(REQUIRED) - set(OPTIONAL_COUNTS) - {"confirmed"}
    if extra:
        bad.append(f"unexpected fields {sorted(extra)}")  # nothing member-specific may ride along
    return bad


class MockGatewayConforms(unittest.TestCase):
    def test_summary_shape(self):
        rig = Rig()
        sid = rig.start()
        s = rig.snap(sid)
        rig.gateway.record_approval(sid, s["plan"]["plan_id"], s["version"], "stu_alex", "accepted")
        summary = rig.gateway.get_commitment_summary(sid, s["plan"]["plan_id"], s["version"])
        self.assertEqual(check_commitment_summary(summary, sid, s["plan"]["plan_id"], s["version"]), [])

    def test_checker_catches_bad_shapes(self):
        base = {"session_id": "s", "plan_id": "p", "version": 1, "required_count": 4, "accepted_count": 4}
        self.assertEqual(check_commitment_summary(base, "s", "p", 1), [])
        for bad in ({**base, "accepted_count": True}, {**base, "version": 2}, {**base, "member_states": {"a": "x"}},
                    {**base, "confirmed": "yes"}, {**base, "declined_count": -1}, {**base, "required_count": 0}):
            self.assertTrue(check_commitment_summary(bad, "s", "p", 1), bad)


class CoordinatorFollowsTheDecisionTable(unittest.TestCase):
    CASES = [
        ({}, "confirmed", None),
        ({"accepted_count": 3}, "incomplete", "APPROVAL_INCOMPLETE"),
        ({"required_count": 3}, "incomplete", "APPROVAL_INCOMPLETE"),
        ({"declined_count": 1}, "incomplete", "APPROVAL_INCOMPLETE"),
        ({"withdrawn_count": 1}, "incomplete", "APPROVAL_INCOMPLETE"),
        ({"confirmed": False}, "incomplete", "APPROVAL_INCOMPLETE"),
        ({"version": 999}, "stale", "PROPOSAL_STALE"),
        ({"plan_id": "other"}, "stale", "PROPOSAL_STALE"),
    ]

    def test_table(self):
        for patch, status, code in self.CASES:
            rig = Rig()
            sid = rig.start()
            s = rig.snap(sid)
            full = {"session_id": sid, "plan_id": s["plan"]["plan_id"], "version": s["version"],
                    "required_count": 4, "accepted_count": 4}
            rig.gateway.get_commitment_summary = lambda a, b, c, d={**full, **patch}: d
            res = rig.coordinator.confirm_if_approved(sid)
            self.assertEqual((res.status, res.error_code), (status, code), patch)

    def test_nothing_older_than_the_new_floor_survives_invalidation(self):
        rig = Rig()
        sid = rig.start()
        rig.accept_all(sid)
        old = rig.snap(sid)
        rig.by_ref["stu_alex"].set_hard_budget_cap(4000)
        rig.coordinator.revise_negotiation(sid, {"kind": "budget"})
        _, old_v, floor = rig.gateway.invalidations[-1]
        self.assertEqual(old_v, old["version"])
        self.assertEqual(rig.gateway.get_commitment_summary(sid, old["plan"]["plan_id"], old["version"])["accepted_count"], 0)
        self.assertGreaterEqual(rig.snap(sid)["version"], floor)


if __name__ == "__main__":
    unittest.main()
