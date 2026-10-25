"""General social matching, independent negotiation consent and multi-day safety."""
from copy import deepcopy
import json
import unittest

from services.participants.service import PrivacyError
from services.participants.social_demo import load_social_demo, run_scenarios


class SocialTests(unittest.TestCase):
    def setUp(self):
        self.s, self.data = load_social_demo()
        self.scope = self.data["discovery_scope"]
        self.trip_scope = self.data["trip_scope"]
        self.alex = self.s.owner("stu_alex")
        self.maya = self.s.owner("stu_maya")
        self.bad, self.good = deepcopy(self.data["trip_plans"])
        self.e = self.s.evaluator(self.good["session_id"])

    def discover(self):
        for ref in self.good["member_refs"]:
            self.s.owner(ref).opt_in(ref, self.scope, {"matching_opt_in": True, "request_id": "find-crew"})

    def negotiate(self):
        for ref in self.good["member_refs"]:
            self.s.owner(ref).opt_in(ref, self.trip_scope, {"negotiation_opt_in": True, "request_id": "friends"})

    def game_plan(self):
        self.discover()
        for owner in (self.alex, self.maya):
            owner.join_activity(self.scope, "evening_games", "game_participation", "join")
        plan = deepcopy(self.good)
        activity = self.data["activities"][0]
        plan.update(session_id="session_games", plan_id="game_plan", member_refs=["stu_alex", "stu_maya"],
                    activity_id="evening_games", activity_kind="games", rough_area="Tempe",
                    start_at=activity["start_at"], end_at=activity["end_at"],
                    estimated_cost_cents_by_ref={"stu_alex": 1500, "stu_maya": 1500},
                    estimated_travel_minutes_by_ref={"stu_alex": 20, "stu_maya": 20})
        self.s.bind_session("session_games", "game_participation", plan["member_refs"], activity_id="evening_games")
        return plan, self.s.evaluator("session_games")

    def test_general_interest_without_optin_does_not_match(self):
        with self.assertRaisesRegex(PrivacyError, "CONSENT_REQUIRED"):
            self.alex.find_mutual_candidates(self.scope, "evening_games", 5)

    def test_games_and_dinner_have_different_candidates(self):
        self.discover()
        games = self.alex.find_mutual_candidates(self.scope, "evening_games", 5)
        dinner = self.alex.find_mutual_candidates(self.scope, "evening_dinner", 5)
        self.assertEqual([p["student_ref"] for p in games], ["stu_maya"])
        self.assertEqual([p["student_ref"] for p in dinner], ["stu_jordan", "stu_maya"])
        self.assertEqual(games[0]["shared_interests"], ["games"])
        self.assertEqual(dinner[0]["shared_interests"], [])

    def test_interest_does_not_authorize_negotiation(self):
        self.discover()
        with self.assertRaisesRegex(PrivacyError, "CONSENT_REQUIRED"):
            self.e.evaluate_plan_private("stu_alex", self.good)
        self.s.bind_session("discovery_misuse", self.scope, self.good["member_refs"])
        plan = dict(self.good, session_id="discovery_misuse")
        with self.assertRaisesRegex(PrivacyError, "CONSENT_REQUIRED"):
            self.s.evaluator("discovery_misuse").evaluate_plan_private("stu_alex", plan)

    def test_duration_area_group_and_willingness_filter(self):
        self.discover()
        base = self.data["discovery_preferences"]["stu_maya"]
        for index, change in enumerate(({"max_duration_minutes": 89}, {"rough_areas": ["Phoenix"]},
                                          {"min_group_size": 3}, {"willingness": "unavailable"})):
            prefs = dict(base, **change)
            self.maya.update_preferences(self.scope, {"social_preferences": prefs}, "filter-" + str(index))
            self.assertEqual(self.alex.find_mutual_candidates(self.scope, "evening_games", 5), [])

    def test_discovery_queries_are_bounded(self):
        self.discover()
        for _ in range(8):
            self.alex.find_mutual_candidates(self.scope, "evening_games", 1)
        with self.assertRaisesRegex(PrivacyError, "EVALUATION_LIMIT_REACHED"):
            self.alex.find_mutual_candidates(self.scope, "evening_dinner", 1)

    def test_join_authorizes_only_the_specific_activity(self):
        plan, evaluator = self.game_plan()
        self.assertTrue(evaluator.evaluate_plan_private("stu_alex", plan)["feasible"])
        self.assertTrue(evaluator.evaluate_plan_private("stu_maya", plan)["feasible"])
        plan["activity_id"] = "evening_dinner"
        with self.assertRaisesRegex(PrivacyError, "AUTHORIZATION_FAILED"):
            evaluator.evaluate_plan_private("stu_alex", plan)

    def test_join_cannot_overwrite_existing_authorization(self):
        self.discover()
        with self.assertRaisesRegex(PrivacyError, "AUTHORIZATION_FAILED"):
            self.alex.join_activity(self.scope, "evening_games", self.trip_scope, "overwrite")

    def test_join_changed_times_are_stale_authorization(self):
        plan, evaluator = self.game_plan()
        plan["end_at"] = "2026-10-30T20:00:00-07:00"
        with self.assertRaisesRegex(PrivacyError, "AUTHORIZATION_FAILED"):
            evaluator.evaluate_plan_private("stu_alex", plan)

    def test_declined_activity_stays_rejected_after_optin(self):
        self.discover()
        self.alex.decline_activity(self.scope, "evening_games", "decline")
        self.alex.opt_in("stu_alex", self.scope, {"matching_opt_in": True, "request_id": "again"})
        self.assertEqual(self.alex.find_mutual_candidates(self.scope, "evening_games", 5), [])
        with self.assertRaisesRegex(PrivacyError, "CONSENT_REQUIRED"):
            self.alex.join_activity(self.scope, "evening_games", "joined", "join-after-no")
        self.assertTrue(self.alex.find_mutual_candidates(self.scope, "evening_dinner", 5))

    def test_decline_blocks_existing_join_and_cannot_be_waived(self):
        plan, evaluator = self.game_plan()
        self.alex.decline_activity(self.scope, "evening_games", "decline")
        with self.assertRaisesRegex(PrivacyError, "CONSENT_REQUIRED"):
            evaluator.evaluate_plan_private("stu_alex", plan)
        with self.assertRaisesRegex(PrivacyError, "CONSENT_REQUIRED"):
            self.alex.approve_private_exception("game_participation", plan, True, "override-no")

    def test_no_stranger_introduction_without_separate_consent(self):
        self.discover()
        with self.assertRaisesRegex(PrivacyError, "CONSENT_REQUIRED"):
            self.alex.introduction(self.scope, "evening_games", "stu_maya")

    def test_revocation_blocks_future_matching_and_introduction(self):
        self.discover()
        for owner, ref, other in ((self.alex, "stu_alex", "stu_maya"), (self.maya, "stu_maya", "stu_alex")):
            owner.opt_in(ref, self.scope, {"introduction_opt_in": True, "request_id": "intro"})
            owner.approve_introduction(self.scope, "evening_games", other, "pair")
        self.assertTrue(self.alex.introduction(self.scope, "evening_games", "stu_maya"))
        self.maya.revoke(self.scope, "stop")
        self.assertEqual(self.alex.find_mutual_candidates(self.scope, "evening_games", 5), [])
        with self.assertRaisesRegex(PrivacyError, "CONSENT_REQUIRED"):
            self.alex.introduction(self.scope, "evening_games", "stu_maya")

    def test_existing_group_needs_no_public_matching(self):
        self.negotiate()
        for ref in self.good["member_refs"]:
            p = self.s._repo.get(ref, self.trip_scope)
            self.assertFalse(p["matching_opt_in"])
            self.assertFalse(p["introduction_opt_in"])
            self.assertTrue(self.e.evaluate_plan_private(ref, self.good)["feasible"])

    def test_multiday_checks_the_middle_of_the_interval(self):
        self.negotiate()
        # Neither endpoint is inside Maya's work interval; the middle conflicts.
        result = self.e.evaluate_plan_private("stu_maya", self.bad)
        self.assertFalse(result["feasible"])
        self.assertIn("HARD_AVAILABILITY", result["internal_issue_codes"])
        self.assertNotIn("6000", json.dumps(result))

    def test_multiday_requires_full_available_interval(self):
        self.negotiate()
        self.alex.update_preferences(self.trip_scope, {"available_windows": [
            {"start_at": self.good["start_at"], "end_at": "2026-11-01T23:00:00-07:00"},
            {"start_at": "2026-11-03T00:00:00-07:00", "end_at": self.good["end_at"]}]}, "calendar-gap")
        result = self.e.evaluate_plan_private("stu_alex", self.good)
        self.assertIn("HARD_AVAILABILITY", result["internal_issue_codes"])

    def test_travel_duration_and_preferences_return_coarse_feedback(self):
        self.negotiate()
        self.alex.update_preferences(self.trip_scope, {"social_preferences": {
            "max_duration_minutes": 90, "max_travel_minutes": 30}}, "limits")
        result = self.e.evaluate_plan_private("stu_alex", self.good)
        self.assertEqual(result["internal_issue_codes"], ["HARD_DURATION", "HARD_TRAVEL"])
        self.assertEqual(result["counteroffer_hints"], ["prefer_less_travel", "prefer_shorter_activity"])
        jordan = self.e.evaluate_plan_private("stu_jordan", self.good)
        self.assertTrue(jordan["feasible"])
        self.assertGreater(jordan["soft_penalty"], 0)
        self.assertIn("prefer_alternate_activity", jordan["counteroffer_hints"])

    def test_missing_travel_evidence_fails_closed(self):
        self.negotiate()
        self.good.pop("estimated_travel_minutes_by_ref")
        result = self.e.evaluate_plan_private("stu_alex", self.good)
        self.assertIn("HARD_TRAVEL", result["internal_issue_codes"])

    def test_private_request_never_changes_limits_or_approves(self):
        self.negotiate()
        before = self.s._repo.get("stu_alex", self.trip_scope)
        status = self.e.request_private_exception("stu_alex", self.bad, "private-request")
        self.assertEqual(status, {"status": "pending", "synthetic": True})
        self.assertFalse(self.e.evaluate_plan_private("stu_alex", self.bad)["feasible"])
        self.assertEqual(before, self.s._repo.get("stu_alex", self.trip_scope))
        inbox = self.alex.pending_private_exceptions(self.trip_scope)
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0]["proposed_cost_cents"], self.bad["estimated_cost_cents_by_ref"]["stu_alex"])
        self.assertEqual(self.maya.pending_private_exceptions(self.trip_scope), [])

    def test_owner_can_approve_pending_exception_only_for_exact_version(self):
        self.negotiate()
        self.e.request_private_exception("stu_alex", self.bad, "pending")
        self.alex.respond_private_exception(self.trip_scope, "pending", True, "yes")
        self.assertTrue(self.e.evaluate_plan_private("stu_alex", self.bad)["feasible"])
        revised = dict(self.bad, version=3)
        self.assertFalse(self.e.evaluate_plan_private("stu_alex", revised)["feasible"])

    def test_private_denial_is_not_reprompted_by_new_request_id(self):
        self.negotiate()
        self.e.request_private_exception("stu_alex", self.bad, "pending")
        self.alex.respond_private_exception(self.trip_scope, "pending", False, "no")
        self.assertEqual(self.e.request_private_exception("stu_alex", self.bad, "retry")["status"], "declined")
        self.assertEqual(self.alex.pending_private_exceptions(self.trip_scope), [])
        self.assertFalse(self.e.evaluate_plan_private("stu_alex", self.bad)["feasible"])

    def test_changed_profile_invalidates_private_request(self):
        self.negotiate()
        self.e.request_private_exception("stu_alex", self.bad, "pending")
        self.alex.update_preferences(self.trip_scope, {"hard_budget_cap_cents": 5900}, "change")
        self.assertEqual(self.alex.pending_private_exceptions(self.trip_scope), [])
        with self.assertRaisesRegex(PrivacyError, "PROPOSAL_STALE"):
            self.alex.respond_private_exception(self.trip_scope, "pending", True, "stale-yes")

    def test_withdrawal_blocks_private_requests_and_owner_inbox(self):
        self.negotiate()
        self.e.request_private_exception("stu_alex", self.bad, "pending")
        self.alex.withdraw(self.trip_scope, "leave")
        with self.assertRaisesRegex(PrivacyError, "CONSENT_REQUIRED"):
            self.alex.pending_private_exceptions(self.trip_scope)
        with self.assertRaisesRegex(PrivacyError, "CONSENT_REQUIRED"):
            self.e.request_private_exception("stu_alex", self.bad, "retry")

    def test_existing_group_decline_cannot_be_bypassed_by_removing_id(self):
        self.negotiate()
        self.alex.decline_activity(self.trip_scope, "weekend_trip", "decline")
        with self.assertRaisesRegex(PrivacyError, "CONSENT_REQUIRED"):
            self.e.evaluate_plan_private("stu_alex", self.good)
        self.good.pop("activity_id")
        with self.assertRaisesRegex(PrivacyError, "AUTHORIZATION_FAILED"):
            self.e.evaluate_plan_private("stu_alex", self.good)

    def test_full_social_demo_has_no_private_disclosures(self):
        output = run_scenarios()
        self.assertFalse(output["scenario_b"]["plans"][0]["all_feasible"])
        self.assertTrue(output["scenario_b"]["plans"][1]["all_feasible"])
        for forbidden in ("6000", "7000", "blocked_windows", "work", "HARD_", "soft_penalty",
                          "proposed_cost_cents", "max_duration", "max_travel", "negotiation_opt_in"):
            self.assertNotIn(forbidden, json.dumps(output))

    def test_repeated_exception_requests_make_only_one_private_prompt(self):
        self.negotiate()
        self.e.request_private_exception("stu_alex", self.bad, "first")
        self.e.request_private_exception("stu_alex", self.bad, "second")
        self.assertEqual(len(self.alex.pending_private_exceptions(self.trip_scope)), 1)
        self.alex.respond_private_exception(self.trip_scope, "first", False, "no")
        self.assertEqual(self.alex.pending_private_exceptions(self.trip_scope), [])
        self.assertEqual(self.e.request_private_exception("stu_alex", self.bad, "second")["status"], "declined")

    def test_revoked_exception_never_reports_cached_approval(self):
        self.negotiate()
        self.e.request_private_exception("stu_alex", self.bad, "pending")
        self.alex.respond_private_exception(self.trip_scope, "pending", True, "yes")
        self.alex.revoke_private_exception(self.trip_scope, self.bad, "revoke")
        self.assertEqual(self.e.request_private_exception("stu_alex", self.bad, "pending")["status"], "declined")
        self.assertFalse(self.e.evaluate_plan_private("stu_alex", self.bad)["feasible"])

    def test_social_negotiation_requires_immutable_activity_binding(self):
        self.negotiate()
        self.s.bind_session("unbound_activity", self.trip_scope, self.good["member_refs"])
        with self.assertRaisesRegex(PrivacyError, "AUTHORIZATION_FAILED"):
            self.s.evaluator("unbound_activity").evaluate_plan_private("stu_alex", dict(self.good, session_id="unbound_activity"))
        with self.assertRaisesRegex(PrivacyError, "AUTHORIZATION_FAILED"):
            self.s.bind_session(self.good["session_id"], self.trip_scope, self.good["member_refs"], activity_id="other")

    def test_purge_removes_private_exception_plan_snapshots(self):
        self.negotiate()
        self.e.request_private_exception("stu_alex", self.bad, "pending")
        self.alex.purge(self.trip_scope, "purge")
        self.assertFalse(any(k[:2] == ("stu_alex", self.trip_scope) for k in self.s._pending_exceptions))

    def test_malformed_social_metadata_fails_atomically(self):
        for i, prefs in enumerate(({"max_duration_minutes": True}, {"min_group_size": 5, "max_group_size": 3},
                                   {"rough_areas": "Tempe"}, {"willingness": "maybe"}, {"unknown": True})):
            with self.assertRaisesRegex(PrivacyError, "INVALID_INPUT"):
                self.alex.update_preferences(self.scope, {"social_preferences": prefs}, "bad-social-" + str(i))
        self.assertEqual(self.s._repo.get("stu_alex", self.scope)["social_preferences"],
                         self.data["discovery_preferences"]["stu_alex"])

    def test_new_social_profile_defaults_to_no_negotiation(self):
        profile = self.s._repo.get("stu_alex", self.trip_scope)
        profile.pop("negotiation_opt_in")
        self.s.seed_profile(profile)
        with self.assertRaisesRegex(PrivacyError, "CONSENT_REQUIRED"):
            self.e.evaluate_plan_private("stu_alex", self.good)

    def test_join_does_not_inherit_history_or_sharing_consent(self):
        self.discover()
        self.alex.opt_in("stu_alex", self.scope, {"history_opt_in": True, "introduction_opt_in": True,
                                                "request_id": "extra-consent"})
        self.alex.join_activity(self.scope, "evening_games", "isolated_game", "join")
        joined = self.s._repo.get("stu_alex", "isolated_game")
        self.assertTrue(joined["negotiation_opt_in"])
        for permission in ("matching_opt_in", "introduction_opt_in", "history_opt_in"):
            self.assertFalse(joined[permission])


if __name__ == "__main__":
    unittest.main()
