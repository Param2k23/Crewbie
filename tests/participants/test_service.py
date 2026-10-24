from copy import deepcopy
from datetime import datetime, timezone
import json
import unittest

from services.participants.demo import load_demo
from services.participants.service import PrivacyError


class ParticipantsTests(unittest.TestCase):
    def setUp(self):
        self.s, self.trip = load_demo()
        self.alex = self.s.owner("stu_alex")
        self.maya = self.s.owner("stu_maya")
        self.e = self.s.evaluator("session_trip_001")
        self.bad, self.good = deepcopy(self.trip["candidate_plans"])
        self.scope = "trip_flagstaff_001"

    def consent(self, owner, ref, request="join"):
        owner.opt_in(ref, "campus_pulse", {"authorized": True, "matching_opt_in": True,
                     "introduction_opt_in": True, "request_id": request})

    def test_fixture_hard_conflicts_and_recovery(self):
        a = self.e.evaluate_plan_private("stu_alex", self.bad)
        m = self.e.evaluate_plan_private("stu_maya", self.bad)
        self.assertFalse(a["feasible"])
        self.assertEqual(a["internal_issue_codes"], ["HARD_BUDGET"])
        self.assertIn("HARD_AVAILABILITY", m["internal_issue_codes"])
        for ref in self.good["member_refs"]:
            self.assertTrue(self.e.evaluate_plan_private(ref, self.good)["feasible"])

    def test_no_private_values_or_untrusted_fields(self):
        self.bad["private_reason"] = "secret shift description"
        private = self.e.evaluate_plan_private("stu_alex", self.bad)
        self.assertNotIn("6000", json.dumps(private))
        safe = self.s.public_evaluation(private)
        self.assertEqual(set(safe), {"reason_category", "synthetic"})
        for forbidden in ("stu_alex", "HARD_BUDGET", "soft_penalty", "secret", "7000", "6000"):
            self.assertNotIn(forbidden, json.dumps(safe))

    def test_matching_absent_consent_and_scope_isolation(self):
        with self.assertRaisesRegex(PrivacyError, "CONSENT_REQUIRED"):
            self.alex.find_mutual_candidates("campus_pulse", "opp_demo_pizza", 5)
        self.consent(self.alex, "stu_alex")
        self.assertEqual(self.alex.find_mutual_candidates("campus_pulse", "opp_demo_pizza", 5), [])
        with self.assertRaisesRegex(PrivacyError, "CONSENT_REQUIRED"):
            self.alex.find_mutual_candidates("campus_pulse", "opp_demo_tacos", 5)

    def test_pair_approval_and_revocation(self):
        self.consent(self.alex, "stu_alex")
        self.consent(self.maya, "stu_maya")
        candidates = self.alex.find_mutual_candidates("campus_pulse", "opp_demo_pizza", 5)
        self.assertEqual(candidates[0]["student_ref"], "stu_maya")
        with self.assertRaisesRegex(PrivacyError, "CONSENT_REQUIRED"):
            self.alex.introduction("campus_pulse", "opp_demo_pizza", "stu_maya")
        self.alex.approve_introduction("campus_pulse", "opp_demo_pizza", "stu_maya", "intro")
        self.maya.approve_introduction("campus_pulse", "opp_demo_pizza", "stu_alex", "intro")
        self.assertEqual(len(self.alex.introduction("campus_pulse", "opp_demo_pizza", "stu_maya")["member_refs"]), 2)
        self.maya.revoke("campus_pulse", "revoke")
        self.assertEqual(self.alex.find_mutual_candidates("campus_pulse", "opp_demo_pizza", 5), [])
        self.consent(self.maya, "stu_maya", "rejoin")
        with self.assertRaises(PrivacyError):
            self.alex.introduction("campus_pulse", "opp_demo_pizza", "stu_maya")

    def test_withdrawal_and_expiry_block_existing_evaluator(self):
        self.alex.withdraw(self.scope, "withdraw")
        with self.assertRaisesRegex(PrivacyError, "CONSENT_REQUIRED"):
            self.e.evaluate_plan_private("stu_alex", self.good)
        self.maya.opt_in("stu_maya", self.scope, {"expires_at": "2026-10-25T00:00:00Z", "request_id": "expiry"})
        self.s._clock = lambda: datetime(2026, 10, 26, tzinfo=timezone.utc)
        with self.assertRaisesRegex(PrivacyError, "CONSENT_REQUIRED"):
            self.e.evaluate_plan_private("stu_maya", self.good)

    def test_identity_and_session_swaps(self):
        with self.assertRaisesRegex(PrivacyError, "AUTHORIZATION_FAILED"):
            self.alex.opt_in("stu_maya", self.scope, {"authorized": True, "request_id": "swap"})
        self.good["session_id"] = "unbound"
        with self.assertRaisesRegex(PrivacyError, "AUTHORIZATION_FAILED"):
            self.e.evaluate_plan_private("stu_alex", self.good)
        with self.assertRaises(PrivacyError):
            self.s.bind_session("session_trip_001", "other_scope", ["stu_alex"])

    def test_bounded_probes_cannot_reset_through_new_sessions(self):
        for n in range(8):
            self.good["estimated_cost_cents_by_ref"]["stu_alex"] = 5000 + n
            self.e.evaluate_plan_private("stu_alex", self.good)
        self.s.bind_session("another", self.scope, self.good["member_refs"])
        self.good["session_id"] = "another"
        with self.assertRaisesRegex(PrivacyError, "EVALUATION_LIMIT_REACHED"):
            self.s.evaluator("another").propose_private_counteroffer("stu_alex", self.good)

    def test_exception_explicit_owner_bound_to_content_and_revision(self):
        with self.assertRaisesRegex(PrivacyError, "PRIVATE_EXCEPTION_PENDING"):
            self.alex.approve_private_exception(self.scope, self.bad, False, "deny")
        self.alex.approve_private_exception(self.scope, self.bad, True, "approve")
        self.assertTrue(self.e.evaluate_plan_private("stu_alex", self.bad)["feasible"])
        changed = deepcopy(self.bad)
        changed["estimated_cost_cents_by_ref"]["stu_alex"] += 1
        self.assertFalse(self.e.evaluate_plan_private("stu_alex", changed)["feasible"])
        changed = deepcopy(self.bad)
        changed["version"] += 1
        self.assertFalse(self.e.evaluate_plan_private("stu_alex", changed)["feasible"])
        self.alex.update_preferences(self.scope, {"hard_budget_cap_cents": 5900}, "lower")
        self.assertFalse(self.e.evaluate_plan_private("stu_alex", self.bad)["feasible"])

    def test_idempotency_and_replay_after_revocation(self):
        consent = {"authorized": True, "request_id": "opt"}
        self.alex.opt_in("stu_alex", self.scope, consent)
        self.alex.revoke(self.scope, "rev")
        self.alex.opt_in("stu_alex", self.scope, consent)
        with self.assertRaisesRegex(PrivacyError, "CONSENT_REQUIRED"):
            self.e.evaluate_plan_private("stu_alex", self.good)
        with self.assertRaisesRegex(PrivacyError, "REQUEST_ID_CONFLICT"):
            self.alex.opt_in("stu_alex", self.scope, {"authorized": False, "request_id": "opt"})

    def test_soft_preference_and_access(self):
        early = deepcopy(self.good)
        early["start_at"] = "2026-11-01T07:00:00-07:00"
        result = self.e.evaluate_plan_private("stu_jordan", early)
        self.assertTrue(result["feasible"])
        self.assertGreater(result["soft_penalty"], 0)
        self.alex.update_preferences(self.scope, {"required_conditions": ["accessible_transport"]}, "access")
        result = self.e.evaluate_plan_private("stu_alex", self.good)
        self.assertFalse(result["feasible"])
        self.assertEqual(result["internal_issue_codes"], ["HARD_ACCESS"])

    def test_malformed_costs_and_dates(self):
        for value in (-1, True, 1.5, "6000"):
            self.good["estimated_cost_cents_by_ref"]["stu_alex"] = value
            with self.assertRaisesRegex(PrivacyError, "INVALID_INPUT"):
                self.e.evaluate_plan_private("stu_alex", self.good)
        self.good = deepcopy(self.trip["candidate_plans"][1])
        self.good["start_at"] = "2026-11-01T10:00:00"
        with self.assertRaisesRegex(PrivacyError, "INVALID_INPUT"):
            self.e.evaluate_plan_private("stu_alex", self.good)

    def test_repository_copies_prevent_alias_mutation(self):
        profile = self.s._repo.get("stu_alex", self.scope)
        profile["hard_budget_cap_cents"] = 1000000
        self.assertFalse(self.e.evaluate_plan_private("stu_alex", self.bad)["feasible"])

    def test_conflicting_hard_constraints_both_reported(self):
        self.alex.update_preferences(self.scope, {"blocked_windows": [{"start_at": self.bad["start_at"],
                                      "end_at": self.bad["end_at"]}]}, "block")
        result = self.e.evaluate_plan_private("stu_alex", self.bad)
        self.assertEqual(result["internal_issue_codes"], ["HARD_AVAILABILITY", "HARD_BUDGET"])

    def test_purge_blocks_old_capability(self):
        self.alex.approve_private_exception(self.scope, self.bad, True, "exception")
        self.alex.purge(self.scope, "purge")
        with self.assertRaisesRegex(PrivacyError, "CONSENT_REQUIRED"):
            self.e.evaluate_plan_private("stu_alex", self.bad)
        self.assertEqual(len(self.s._exceptions), 0)

    def test_profile_validation_is_atomic(self):
        with self.assertRaisesRegex(PrivacyError, "INVALID_INPUT"):
            self.alex.update_preferences(self.scope, {"soft_preferences": {"avoid_before_local_hour": "secret"}}, "bad")
        self.assertTrue(self.e.evaluate_plan_private("stu_alex", self.good)["feasible"])

    def test_canonical_evaluation_required_keys(self):
        from pathlib import Path
        schema = json.loads((Path(__file__).resolve().parents[2] /
                             "docs/implementation/contracts/crewbie.schema.json").read_text())
        result = self.e.evaluate_plan_private("stu_alex", self.good)
        self.assertEqual(set(result), set(schema["$defs"]["PrivateEvaluation"]["required"]))


if __name__ == "__main__":
    unittest.main()
