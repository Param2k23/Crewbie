"""Phase 1: deterministic hard validation, fail-closed evaluation parsing, honest NO_FEASIBLE_PLAN."""
import copy
import math
import unittest

from neg_helpers import FuncEvaluator, Rig, evaluation, plan_at

from services.negotiation import GroupRules, NegotiationConfig, SessionRequest
from services.negotiation.mocks import flagstaff_request
from services.negotiation.models import CandidateStatus, SessionState
from services.negotiation.validator import parse_evaluation, validate_plan

MEMBERS = ["stu_alex", "stu_maya", "stu_jordan", "stu_taylor"]


def request(**rule_kw):
    raw = flagstaff_request(rules=rule_kw or {"min_attendees": 3})
    return SessionRequest.from_mapping(raw)


def plan(**over):
    p = plan_at("2026-11-01", 10)
    p.update(session_id="s", plan_id="p", version=1, opportunity_id=None, member_refs=list(MEMBERS),
             estimate_disclaimer="x", synthetic=True)
    p.update(over)
    return p


class PublicRuleValidation(unittest.TestCase):
    def check(self, p, req=None):
        return validate_plan(p, req or request(), MEMBERS)

    def test_valid_plan_has_no_violations(self):
        self.assertEqual(self.check(plan()), [])

    def test_missing_attendee_is_rejected(self):
        self.assertIn("ATTENDANCE_MEMBERS", self.check(plan(member_refs=MEMBERS[:3])))

    def test_unknown_or_missing_cost_line_rejected(self):
        costs = {m: 5000 for m in MEMBERS[:3]}
        self.assertIn("COST_INVALID", self.check(plan(estimated_cost_cents_by_ref=costs)))

    def test_float_dollars_and_negative_costs_rejected(self):
        for bad in (52.0, -1, True, "5200"):
            costs = {m: 5000 for m in MEMBERS}
            costs["stu_alex"] = bad
            self.assertIn("COST_INVALID", self.check(plan(estimated_cost_cents_by_ref=costs)), bad)

    def test_time_rules(self):
        self.assertIn("TIME_RANGE", self.check(plan(end_at="2026-11-01T09:00:00-07:00")))
        self.assertIn("DURATION", self.check(plan(end_at="2026-11-01T23:00:00-07:00", start_at="2026-11-01T08:00:00-07:00")))
        self.assertIn("OUT_OF_WINDOW", self.check(plan(start_at="2026-11-09T10:00:00-07:00", end_at="2026-11-09T18:00:00-07:00")))
        self.assertIn("LOCAL_HOURS", self.check(plan(start_at="2026-11-01T14:00:00-07:00", end_at="2026-11-01T23:00:00-07:00")))

    def test_unparseable_times_are_structural_failures(self):
        self.assertEqual(self.check(plan(start_at="tomorrow")), ["STRUCTURE"])
        self.assertEqual(self.check(plan(start_at="2026-11-01T10:00:00")), ["STRUCTURE"])  # no offset

    def test_public_group_cost_cap(self):
        req = request(min_attendees=3, group_max_cost_per_person_cents=5000)
        self.assertIn("GROUP_COST_CAP", self.check(plan(), req))

    def test_required_role_coverage(self):
        req = request(min_attendees=3, member_roles={"stu_maya": ["driver"]}, required_roles={"driver": 1})
        self.assertEqual(self.check(plan(), req), [])
        no_driver = request(min_attendees=3, member_roles={}, required_roles={"driver": 1})
        self.assertIn("ROLE_COVERAGE", self.check(plan(), no_driver))

    def test_opportunity_access_is_never_assumed(self):
        opp = {"opportunity_id": "opp_1", "access_status": "unknown",
               "start_at": "2026-11-01T09:00:00-07:00", "end_at": "2026-11-01T20:00:00-07:00"}
        raw = flagstaff_request(opportunity=opp, rules={"min_attendees": 3, "requires_verified_public_access": True})
        req = SessionRequest.from_mapping(raw)
        self.assertIn("ACCESS_UNVERIFIED", self.check(plan(opportunity_id="opp_1"), req))
        self.assertIn("OPPORTUNITY_MISMATCH", self.check(plan(opportunity_id="other"), req))
        opp["access_status"] = "public"
        self.assertEqual(self.check(plan(opportunity_id="opp_1"), SessionRequest.from_mapping(raw)), [])

    def test_invalid_candidate_never_reaches_private_evaluators(self):
        ev = FuncEvaluator(lambda ref, p: evaluation(p, ref))
        rig = Rig(evaluator=ev)
        bad = plan_at("2026-11-01", 10, members=MEMBERS[:3])  # one attendee has no cost line / not in plan
        sid = rig.start(seed_plans=[bad])
        self.assertEqual(ev.calls, [])
        self.assertEqual(rig.coordinator.state_of(sid), SessionState.FAILED)
        self.assertEqual(rig.snap(sid)["error_code"], "NO_FEASIBLE_PLAN")
        self.assertIn("group_rule_violation", rig.trace_text())


class EvaluationParsing(unittest.TestCase):
    P = plan()

    def parse(self, raw):
        return parse_evaluation(raw, student_ref="stu_alex", plan=self.P)

    def good(self, **kw):
        return evaluation(self.P, "stu_alex", **kw)

    def test_well_formed_feasible(self):
        e = self.parse(self.good(penalty=0.3, hints=["prefer_later_start"]))
        self.assertTrue(e.feasible)
        self.assertEqual(e.soft_penalty, 0.3)
        self.assertEqual(e.hints, ("prefer_later_start",))

    def test_malformed_responses_fail_closed(self):
        for raw in (None, "yes", [], {}, {**self.good(), "feasible": "true"}, {**self.good(), "feasible": 1},
                    {**self.good(), "soft_penalty": "0.1"}, {**self.good(), "soft_penalty": math.nan}):
            self.assertFalse(self.parse(raw).feasible, raw)

    def test_response_for_other_student_plan_or_version_fails_closed(self):
        for key, value in (("student_ref", "stu_maya"), ("plan_id", "p_old"), ("version", 0), ("session_id", "other")):
            self.assertFalse(self.parse({**self.good(), key: value}).feasible, key)

    def test_feasible_flag_cannot_contradict_a_hard_issue(self):
        raw = self.good(feasible=True, issues=["HARD_BUDGET"])
        self.assertFalse(self.parse(raw).feasible)

    def test_unknown_hints_are_dropped_and_penalty_clamped(self):
        e = self.parse(self.good(penalty=9, hints=["prefer_lower_cost", "my_cap_is_6000"]))
        self.assertEqual(e.hints, ("prefer_lower_cost",))
        self.assertEqual(e.soft_penalty, 1.0)

    def test_exception_flag_ignored_when_feasible(self):
        self.assertFalse(self.parse(self.good(feasible=True, exception=True)).requires_private_exception)


class HardConstraintGates(unittest.TestCase):
    def test_seventy_dollar_plan_fails_sixty_dollar_cap_and_search_ends_honestly(self):
        """No cheaper tier exists, so nothing can satisfy the $60 cap: NO_FEASIBLE_PLAN, never a forced plan."""
        rig = Rig(config=NegotiationConfig(cost_tiers_cents=(7000,)), exception_gateway=False)
        sid = rig.start()
        snap = rig.snap(sid)
        self.assertEqual(snap["state"], "failed")
        self.assertEqual(snap["error_code"], "NO_FEASIBLE_PLAN")
        self.assertIsNone(snap["plan"])
        self.assertNotIn("proposal_ready", rig.types())
        self.assertNotIn("approval_requested", rig.types())
        self.assertEqual(rig.types()[-1], "negotiation_failed")

    def test_first_candidate_is_rejected_for_private_reasons_and_cheaper_alternative_wins(self):
        rig = Rig()
        sid = rig.start()
        first = rig.sink.events[2]
        self.assertEqual((first["type"], first["payload"]["plan_id"]), ("proposal_rejected", "plan_flagstaff_001"))
        self.assertEqual(first["payload"]["reason_category"], "constraint_conflict")
        snap = rig.snap(sid)
        self.assertEqual(snap["state"], "approval_pending")
        self.assertGreater(snap["version"], 1)
        # whatever was chosen must satisfy the $60 cap and the Saturday work block
        winner = rig.coordinator._get(sid).current_plan
        self.assertLessEqual(max(winner["estimated_cost_cents_by_ref"].values()), 6000)
        self.assertFalse(winner["start_at"].startswith("2026-10-31"))

    def test_all_four_private_agents_are_actually_asked_about_every_candidate(self):
        rig = Rig()
        sid = rig.start()
        tried = rig.snap(sid)["candidates_evaluated"]
        for ref, agent in rig.by_ref.items():
            self.assertEqual(len(agent.evaluations), tried, ref)
        plan_ids = {pid for a in rig.agents for pid, _ in a.evaluations}
        self.assertEqual(len(plan_ids), tried)

    def test_one_hard_failure_blocks_a_candidate_even_when_three_agents_accept(self):
        ev = FuncEvaluator(lambda ref, p: evaluation(p, ref, feasible=(ref != "stu_taylor")))
        rig = Rig(evaluator=ev, exception_gateway=False)
        sid = rig.start(seed_plans=[plan_at("2026-11-01", 10)])
        self.assertEqual(rig.snap(sid)["state"], "failed")
        self.assertEqual({r for r, *_ in ev.calls}, set(MEMBERS))
        self.assertFalse([e for e in rig.sink.events if e["type"] == "proposal_ready"])

    def test_agents_never_receive_other_members_cost_lines(self):
        ev = FuncEvaluator(lambda ref, p: evaluation(p, ref))
        rig = Rig(evaluator=ev)
        rig.start(seed_plans=[plan_at("2026-11-01", 10)])
        for (ref, *_), seen in zip(ev.calls, ev.seen_plans):
            self.assertEqual(set(seen["estimated_cost_cents_by_ref"]), {ref})

    def test_counteroffer_hints_are_requested_only_for_failing_members(self):
        rig = Rig()
        rig.start()
        self.assertEqual(rig.by_ref["stu_jordan"].counteroffer_requests, 0)  # feasible for the first candidate
        self.assertGreater(rig.by_ref["stu_alex"].counteroffer_requests, 0)

    def test_saturday_work_conflict_rejected_then_resolved_by_counteroffer(self):
        def verdict(ref, p):
            clash = ref == "stu_maya" and p["start_at"].startswith("2026-10-31")
            return evaluation(p, ref, feasible=not clash, hints=["prefer_different_day"] if clash else [])

        rig = Rig(evaluator=FuncEvaluator(verdict), exception_gateway=False)
        sid = rig.start(seed_plans=[plan_at("2026-10-31", 9)])
        self.assertIn("proposal_rejected", rig.types())
        self.assertIn("counteroffer_proposed", rig.types())
        winner = rig.coordinator._get(sid).current_plan
        self.assertIsNotNone(winner)
        self.assertFalse(winner["start_at"].startswith("2026-10-31"))


if __name__ == "__main__":
    unittest.main()
