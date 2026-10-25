"""Adversarial and integration-boundary tests; all providers are offline fakes."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import unittest

from services.participants.demo import load_demo
from services.participants.identity import DemoIdentityProvider, OwnerGateway
from services.participants.service import ParticipantService, PrivacyError


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.s, self.trip = load_demo()
        self.plan = deepcopy(self.trip["candidate_plans"][1])
        self.owner = self.s.owner("stu_alex")
        self.scope = "trip_flagstaff_001"
        self.evaluator = self.s.evaluator("session_trip_001")

    def test_demo_auth_rejects_ids_and_swapped_student(self):
        gateway = OwnerGateway(self.s, DemoIdentityProvider({"demo-secret": "stu_alex"}))
        for token in ("stu_alex", "unknown", None, {}):
            with self.assertRaisesRegex(PrivacyError, "AUTHORIZATION_FAILED"):
                gateway.authenticate(token)
        owner = gateway.authenticate("demo-secret")
        with self.assertRaisesRegex(PrivacyError, "AUTHORIZATION_FAILED"):
            owner.opt_in("stu_maya", self.scope, {"authorized": True, "request_id": "swap"})

    def test_empty_availability_is_a_hard_limit(self):
        self.owner.update_preferences(self.scope, {"available_windows": []}, "empty-calendar")
        result = self.evaluator.evaluate_plan_private("stu_alex", self.plan)
        self.assertFalse(result["feasible"])
        self.assertEqual(result["internal_issue_codes"], ["HARD_AVAILABILITY"])

    def test_consent_expiry_cannot_be_removed_by_falsey_input(self):
        self.owner.opt_in("stu_alex", self.scope, {"expires_at": "2026-10-25T00:00:00Z", "request_id": "expire"})
        for index, value in enumerate((None, "", False, 0)):
            with self.assertRaisesRegex(PrivacyError, "INVALID_INPUT"):
                self.owner.opt_in("stu_alex", self.scope, {"expires_at": value, "request_id": "bad-" + str(index)})
        self.s._clock = lambda: datetime(2026, 10, 26, tzinfo=timezone.utc)
        with self.assertRaisesRegex(PrivacyError, "CONSENT_REQUIRED"):
            self.evaluator.evaluate_plan_private("stu_alex", self.plan)

    def test_malformed_profile_updates_do_not_commit(self):
        changes = [{"blocked_windows": None}, {"available_windows": [None]},
                   {"blocked_windows": [{"start_at": "secret"}]}, {"shareable_interests": "secret"}]
        for i, change in enumerate(changes):
            with self.assertRaisesRegex(PrivacyError, "INVALID_INPUT"):
                self.owner.update_preferences(self.scope, change, "invalid-" + str(i))
        self.assertTrue(self.evaluator.evaluate_plan_private("stu_alex", self.plan)["feasible"])

    def test_invalid_canonical_envelopes_fail_safely(self):
        plans = [None, [], {}, dict(self.plan, activities="private"), dict(self.plan, synthetic=False),
                 dict(self.plan, member_refs=["stu_alex", "stu_alex"]),
                 dict(self.plan, estimated_cost_cents_by_ref={"stu_alex": 5200}),
                 dict(self.plan, verified_conditions={"access": "yes"})]
        for plan in plans:
            with self.assertRaisesRegex(PrivacyError, "INVALID_INPUT"):
                self.evaluator.evaluate_plan_private("stu_alex", plan)

    def test_stranger_scope_cannot_gain_second_opportunity(self):
        opportunity = deepcopy(self.s._opportunities["campus_pulse", "opp_demo_pizza"])
        opportunity["opportunity_id"] = "opp_other"
        with self.assertRaisesRegex(PrivacyError, "AUTHORIZATION_FAILED"):
            self.s.register_opportunity("campus_pulse", opportunity)
        self.plan["opportunity_id"] = "opp_demo_pizza"
        with self.assertRaisesRegex(PrivacyError, "AUTHORIZATION_FAILED"):
            self.evaluator.evaluate_plan_private("stu_alex", self.plan)

    def test_changed_opportunity_requires_fresh_scope(self):
        opportunity = deepcopy(self.s._opportunities["campus_pulse", "opp_demo_pizza"])
        opportunity["start_at"] = "2026-10-27T12:00:00-07:00"
        opportunity["end_at"] = "2026-10-27T13:00:00-07:00"
        with self.assertRaisesRegex(PrivacyError, "PROPOSAL_STALE"):
            self.s.register_opportunity("campus_pulse", opportunity)

    def test_exception_revocation_and_replay(self):
        bad = self.trip["candidate_plans"][0]
        self.owner.approve_private_exception(self.scope, bad, True, "approve")
        self.assertTrue(self.evaluator.evaluate_plan_private("stu_alex", bad)["feasible"])
        self.owner.revoke_private_exception(self.scope, bad, "revoke")
        self.owner.approve_private_exception(self.scope, bad, True, "approve")
        self.assertFalse(self.evaluator.evaluate_plan_private("stu_alex", bad)["feasible"])

    def test_parallel_probes_share_one_atomic_allowance(self):
        def probe(index):
            plan = deepcopy(self.plan)
            plan["estimated_cost_cents_by_ref"]["stu_alex"] += index
            try:
                self.evaluator.evaluate_plan_private("stu_alex", plan)
                return "evaluated"
            except PrivacyError as error:
                return str(error)
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(probe, range(24)))
        self.assertEqual(outcomes.count("evaluated"), 8)
        self.assertEqual(outcomes.count("EVALUATION_LIMIT_REACHED"), 16)

    def test_counteroffer_protocol_works_without_profile_access(self):
        class FakeCoordinator:
            def __init__(self, evaluator):
                self.evaluator = evaluator

            def assess(self, refs, plan):
                return all(self.evaluator.evaluate_plan_private(ref, plan)["feasible"] for ref in refs)

        coordinator = FakeCoordinator(self.evaluator)
        self.assertFalse(coordinator.assess(self.plan["member_refs"], self.trip["candidate_plans"][0]))
        hints = self.evaluator.propose_private_counteroffer("stu_alex", self.trip["candidate_plans"][0])
        self.assertEqual(hints, {"counteroffer_hints": ["prefer_lower_cost"], "synthetic": True})
        self.assertTrue(coordinator.assess(self.plan["member_refs"], self.plan))

    def test_query_limit_cannot_be_disabled(self):
        for limit in (0, -1, 9, True, None):
            with self.assertRaisesRegex(PrivacyError, "INVALID_INPUT"):
                ParticipantService(probe_limit=limit)

    def test_public_serializer_rejects_uncertain_feasibility(self):
        for result in ({}, None, {"feasible": "false"}, {"feasible": 1}):
            with self.assertRaisesRegex(PrivacyError, "INVALID_INPUT"):
                self.s.public_evaluation(result)

    def test_demo_output_does_not_disclose_private_records(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from services.participants.demo import main
        output = StringIO()
        with redirect_stdout(output):
            main()
        text = output.getvalue()
        for forbidden in ("6000", "10000", "hard_budget", "blocked_windows", "soft_penalty",
                          "HARD_BUDGET", "demo-token", "internal_issue_codes", "estimated_cost_cents"):
            self.assertNotIn(forbidden, text)

    def test_matching_calendar_and_campus_are_required(self):
        for ref in ("stu_alex", "stu_maya"):
            self.s.owner(ref).opt_in(ref, "campus_pulse", {"authorized": True, "matching_opt_in": True,
                                                         "request_id": "join"})
        alex, maya = self.s.owner("stu_alex"), self.s.owner("stu_maya")
        maya.update_preferences("campus_pulse", {"campus": "West Valley"}, "campus")
        self.assertEqual(alex.find_mutual_candidates("campus_pulse", "opp_demo_pizza", 5), [])
        maya.update_preferences("campus_pulse", {"campus": "Tempe", "blocked_windows": [{
            "start_at": "2026-10-26T12:30:00-07:00", "end_at": "2026-10-26T13:30:00-07:00"}]}, "block")
        self.assertEqual(alex.find_mutual_candidates("campus_pulse", "opp_demo_pizza", 5), [])


if __name__ == "__main__":
    unittest.main()
