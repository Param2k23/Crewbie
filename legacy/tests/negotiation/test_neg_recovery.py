"""Phase 3: changing constraints, withdrawal, versioning, approval invalidation, private exceptions."""
import json
import unittest

from neg_helpers import FuncEvaluator, Rig, evaluation, plan_at

from services.negotiation import NegotiationConfig, NegotiationError, SessionState
from services.negotiation.mocks import flagstaff_request

MEMBERS = ["stu_alex", "stu_maya", "stu_jordan", "stu_taylor"]


class BudgetChange(unittest.TestCase):
    def setUp(self):
        self.rig = Rig()
        self.sid = self.rig.start()
        self.old = self.rig.snap(self.sid)
        self.rig.accept_all(self.sid)  # all four approved version N

    def test_lowered_cap_invalidates_approvals_and_produces_a_new_valid_version(self):
        r, sid, old = self.rig, self.sid, self.old
        self.assertEqual(r.gateway.get_commitment_summary(sid, old["plan"]["plan_id"], old["version"])["accepted_count"], 4)
        r.by_ref["stu_alex"].set_hard_budget_cap(4000)
        r.coordinator.revise_negotiation(sid, {"kind": "budget", "student_ref": "stu_alex"})
        new = r.snap(sid)
        # approvals for N are gone and N can never be confirmed
        self.assertEqual(r.gateway.get_commitment_summary(sid, old["plan"]["plan_id"], old["version"])["accepted_count"], 0)
        self.assertEqual(r.coordinator.confirm_if_approved(sid, old["plan"]["plan_id"], old["version"]).error_code, "PROPOSAL_STALE")
        self.assertEqual(r.gateway.invalidations[-1][:2], (sid, old["version"]))
        # new version is a different, cheaper plan that satisfies the new private limit
        self.assertGreater(new["version"], old["version"])
        self.assertGreaterEqual(new["version"], r.gateway.invalidations[-1][2])
        self.assertEqual(new["state"], "approval_pending")
        cur = r.coordinator._get(sid).current_plan
        self.assertLessEqual(max(cur["estimated_cost_cents_by_ref"].values()), 4000)

    def test_events_show_revision_then_failure_of_old_plan_then_recovery(self):
        r = self.rig
        n = len(r.sink.events)
        r.by_ref["stu_alex"].set_hard_budget_cap(4000)
        r.coordinator.revise_negotiation(self.sid, {"kind": "budget", "student_ref": "stu_alex"})
        types = r.types()[n:]
        self.assertEqual(types[0], "proposal_revised")
        self.assertIn("proposal_rejected", types)  # the previous plan fails re-validation
        self.assertEqual(types[-2:], ["proposal_ready", "approval_requested"])
        revised = r.sink.events[n]["payload"]
        self.assertEqual(revised["previous_version"], self.old["version"])
        self.assertTrue(revised["approvals_reset"])
        self.assertEqual(revised["reason_category"], "constraint_changed")
        self.assertEqual(set(revised), {"previous_plan_id", "previous_version", "version", "reason_category", "approvals_reset"})

    def test_state_path_through_renegotiation(self):
        r = self.rig
        r.by_ref["stu_alex"].set_hard_budget_cap(4000)
        r.coordinator.revise_negotiation(self.sid, {"kind": "budget"})
        self.assertEqual(r.coordinator.transitions_of(self.sid)[3:], [
            ("approval_pending", "renegotiating"), ("renegotiating", "proposed"), ("proposed", "approval_pending")])

    def test_cap_below_every_option_ends_honestly_without_forcing_a_plan(self):
        r = self.rig
        r.coordinator.exception_gateway = None  # nobody can be asked for a waiver here
        r.by_ref["stu_alex"].set_hard_budget_cap(1000)
        r.coordinator.revise_negotiation(self.sid, {"kind": "budget", "student_ref": "stu_alex"})
        snap = r.snap(self.sid)
        self.assertEqual((snap["state"], snap["error_code"]), ("failed", "NO_FEASIBLE_PLAN"))
        self.assertIsNone(snap["plan"])
        self.assertEqual(r.types()[-1], "negotiation_failed")
        self.assertEqual(r.coordinator.confirm_if_approved(self.sid).status, "not_pending")

    def test_failed_session_recovers_when_a_constraint_relaxes(self):
        r = self.rig
        r.coordinator.exception_gateway = None
        r.by_ref["stu_alex"].set_hard_budget_cap(1000)
        r.coordinator.revise_negotiation(self.sid, {"kind": "budget", "student_ref": "stu_alex"})
        self.assertEqual(r.snap(self.sid)["state"], "failed")
        r.by_ref["stu_alex"].set_hard_budget_cap(6000)
        r.coordinator.revise_negotiation(self.sid, {"kind": "budget", "student_ref": "stu_alex"})
        self.assertEqual(r.snap(self.sid)["state"], "approval_pending")
        self.assertIsNone(r.snap(self.sid)["error_code"])

    def test_revision_is_idempotent_by_request_id(self):
        r = self.rig
        ref = {"kind": "budget", "student_ref": "stu_alex", "request_id": "chg_7"}
        r.coordinator.revise_negotiation(self.sid, ref)
        n, v = len(r.sink.events), r.snap(self.sid)["version"]
        r.coordinator.revise_negotiation(self.sid, ref)
        self.assertEqual((len(r.sink.events), r.snap(self.sid)["version"]), (n, v))

    def test_revision_input_validation(self):
        r = self.rig
        for bad in ({"kind": "mystery"}, {}, {"kind": "budget", "student_ref": "stu_stranger"}):
            with self.assertRaises(NegotiationError):
                r.coordinator.revise_negotiation(self.sid, bad)

    def test_confirmed_plan_can_be_reopened_and_approval_resets(self):
        r = self.rig
        self.assertEqual(r.coordinator.confirm_if_approved(self.sid).status, "confirmed")
        r.by_ref["stu_maya"].set_blocked_windows([{"start_at": self.old["plan"]["start_at"], "end_at": self.old["plan"]["end_at"]}])
        r.coordinator.revise_negotiation(self.sid, {"kind": "availability", "student_ref": "stu_maya"})
        snap = r.snap(self.sid)
        self.assertEqual(snap["state"], "approval_pending")
        self.assertNotEqual(snap["plan"]["start_at"][:10], self.old["plan"]["start_at"][:10])
        self.assertEqual(r.coordinator.confirm_if_approved(self.sid).status, "incomplete")

    def test_itinerary_change_uses_its_own_reason_category(self):
        self.rig.coordinator.revise_negotiation(self.sid, {"kind": "itinerary"})
        revised = [e for e in self.rig.sink.events if e["type"] == "proposal_revised"][-1]
        self.assertEqual(revised["payload"]["reason_category"], "itinerary_changed")

    def test_repeated_revisions_cannot_probe_a_member_past_the_lifetime_cap(self):
        r = Rig(config=NegotiationConfig(max_evaluations_per_member_per_session=25), exception_gateway=False)
        sid = r.start()
        r.by_ref["stu_alex"].set_hard_budget_cap(1000)
        for i in range(30):
            try:
                r.coordinator.revise_negotiation(sid, {"kind": "budget", "request_id": f"c{i}"})
            except NegotiationError:
                pass
        for ref, agent in r.by_ref.items():
            self.assertLessEqual(len(agent.evaluations) + agent.counteroffer_requests, 25, ref)


class AvailabilityChange(unittest.TestCase):
    def test_new_blocked_window_moves_the_plan_to_another_day(self):
        r = Rig()
        sid = r.start()
        day = r.snap(sid)["plan"]["start_at"][:10]
        r.by_ref["stu_taylor"].set_blocked_windows([{"start_at": f"{day}T00:00:00-07:00", "end_at": f"{day}T23:59:00-07:00"}])
        r.coordinator.revise_negotiation(sid, {"kind": "availability", "student_ref": "stu_taylor"})
        snap = r.snap(sid)
        self.assertEqual(snap["state"], "approval_pending")
        self.assertNotEqual(snap["plan"]["start_at"][:10], day)
        self.assertEqual(snap["revisions"], 1)


class Withdrawal(unittest.TestCase):
    def test_non_essential_withdrawal_replans_for_remaining_members(self):
        r = Rig()
        sid = r.start()
        r.accept_all(sid)
        old_v = r.snap(sid)["version"]
        before = {ref: len(a.evaluations) for ref, a in r.by_ref.items()}
        r.coordinator.withdraw_participant(sid, "stu_taylor")
        snap = r.snap(sid)
        self.assertEqual(snap["state"], "approval_pending")
        self.assertEqual(snap["required_count"], 3)
        self.assertNotIn("stu_taylor", snap["plan"]["member_refs"])
        self.assertGreater(snap["version"], old_v)
        self.assertEqual(len(r.by_ref["stu_taylor"].evaluations), before["stu_taylor"])  # no more probing of a leaver
        self.assertGreater(len(r.by_ref["stu_alex"].evaluations), before["stu_alex"])
        self.assertEqual(r.gateway.invalidations[-1][1], old_v)
        revised = [e for e in r.sink.events if e["type"] == "proposal_revised"][-1]
        self.assertEqual(revised["payload"]["reason_category"], "participant_change")

    def test_group_below_minimum_attendance_fails_honestly(self):
        r = Rig()
        sid = r.start(rules={"min_attendees": 4})
        r.coordinator.withdraw_participant(sid, "stu_taylor")
        snap = r.snap(sid)
        self.assertEqual((snap["state"], snap["error_code"], snap["reason_category"]),
                         ("failed", "NO_FEASIBLE_PLAN", "attendance_requirement"))
        self.assertEqual(r.gateway.get_commitment_summary(sid, "x", 0)["accepted_count"], 0)

    def test_essential_member_withdrawal_fails(self):
        r = Rig()
        sid = r.start(rules={"min_attendees": 2, "essential_member_refs": ["stu_maya"]})
        r.coordinator.withdraw_participant(sid, "stu_maya")
        self.assertEqual(r.snap(sid)["error_code"], "NO_FEASIBLE_PLAN")

    def test_required_role_leaving_fails(self):
        r = Rig()
        sid = r.start(rules={"min_attendees": 2, "member_roles": {"stu_jordan": ["driver"]}, "required_roles": {"driver": 1}})
        self.assertEqual(r.snap(sid)["state"], "approval_pending")
        r.coordinator.withdraw_participant(sid, "stu_jordan")
        self.assertEqual(r.snap(sid)["state"], "failed")

    def test_withdrawal_validation(self):
        r = Rig()
        sid = r.start()
        with self.assertRaises(NegotiationError):
            r.coordinator.withdraw_participant(sid, "stu_stranger")
        r.coordinator.withdraw_participant(sid, "stu_taylor")
        with self.assertRaises(NegotiationError):
            r.coordinator.withdraw_participant(sid, "stu_taylor")


class PrivateException(unittest.TestCase):
    def setUp(self):
        self.rig = Rig(config=NegotiationConfig(cost_tiers_cents=(5200, 7000)))
        self.rig.by_ref["stu_alex"].set_hard_budget_cap(4000)
        self.rig.by_ref["stu_alex"].set_exception_margin(1500)  # Alex would consider up to +$15, if asked
        self.sid = self.rig.start()

    def test_only_the_affected_student_is_asked_and_the_group_sees_nothing_special(self):
        r = self.rig
        self.assertEqual(r.coordinator.state_of(self.sid), SessionState.AWAITING_EXCEPTION)
        self.assertEqual([q[0] for q in r.exceptions.requests], ["stu_alex"])
        snap = r.snap(self.sid)
        self.assertEqual(snap["state"], "negotiating")
        self.assertIsNone(snap["error_code"])
        self.assertNotIn("proposal_ready", r.types())
        self.assertNotIn("stu_", json.dumps([e["payload"] for e in r.sink.events]))  # payloads name no student

    def test_approval_makes_the_plan_valid_only_via_the_students_own_evaluator(self):
        r = self.rig
        _, _, plan_id, version = r.exceptions.requests[0]
        r.coordinator.resolve_private_exception(self.sid, "stu_alex", True)
        self.assertEqual(r.snap(self.sid)["state"], "approval_pending")
        self.assertEqual((r.snap(self.sid)["plan"]["plan_id"], r.snap(self.sid)["version"]), (plan_id, version))

    def test_decline_leaves_the_plan_infeasible(self):
        r = self.rig
        r.coordinator.resolve_private_exception(self.sid, "stu_alex", False)
        snap = r.snap(self.sid)
        self.assertEqual((snap["state"], snap["error_code"], snap["reason_category"]),
                         ("failed", "NO_FEASIBLE_PLAN", "exception_declined"))
        self.assertIsNone(snap["plan"])

    def test_unaffected_student_cannot_answer_for_someone_else(self):
        with self.assertRaises(NegotiationError):
            self.rig.coordinator.resolve_private_exception(self.sid, "stu_maya", True)

    def test_without_a_private_channel_the_plan_stays_infeasible(self):
        r = Rig(config=NegotiationConfig(cost_tiers_cents=(5200, 7000)), exception_gateway=False)
        r.by_ref["stu_alex"].set_hard_budget_cap(4000)
        r.by_ref["stu_alex"].set_exception_margin(1500)
        sid = r.start()
        self.assertEqual(r.snap(sid)["error_code"], "NO_FEASIBLE_PLAN")

    def test_exception_is_never_offered_for_an_availability_conflict(self):
        r = Rig(config=NegotiationConfig(day_shift_options=(30,), cost_tiers_cents=(5200,)))
        sid = r.start(seed_plans=[plan_at("2026-10-31", 10, cost=5200)])  # Maya works Saturday
        self.assertEqual(r.snap(sid)["error_code"], "NO_FEASIBLE_PLAN")
        self.assertEqual(r.exceptions.requests, [])


class Escalations(unittest.TestCase):
    def test_exception_state_can_be_superseded_by_a_revision(self):
        r = Rig(config=NegotiationConfig(cost_tiers_cents=(5200, 7000)))
        r.by_ref["stu_alex"].set_hard_budget_cap(4000)
        r.by_ref["stu_alex"].set_exception_margin(1500)
        sid = r.start()
        r.by_ref["stu_alex"].set_hard_budget_cap(5300)
        r.coordinator.revise_negotiation(sid, {"kind": "budget", "student_ref": "stu_alex"})
        self.assertEqual(r.snap(sid)["state"], "approval_pending")


class DeclineAndExpiry(unittest.TestCase):
    def test_decline_vetoes_the_version_and_falls_back_to_a_revalidated_runner_up(self):
        r = Rig()
        sid = r.start()
        first = r.snap(sid)
        r.accept_all(sid)
        r.coordinator.record_member_decline(sid, "stu_jordan")
        second = r.snap(sid)
        self.assertEqual(second["state"], "approval_pending")
        self.assertGreater(second["version"], first["version"])
        self.assertNotEqual(second["plan"]["start_at"] + second["plan"]["end_at"], first["plan"]["start_at"] + first["plan"]["end_at"])
        self.assertEqual(r.gateway.invalidations[-1][1], first["version"])
        self.assertEqual([e for e in r.sink.events if e["type"] == "proposal_revised"][-1]["payload"]["reason_category"], "member_declined")
        self.assertEqual(r.coordinator.confirm_if_approved(sid).status, "incomplete")

    def test_runner_up_is_rechecked_against_changed_constraints(self):
        r = Rig()
        sid = r.start()
        ranked = [x.plan for x in r.coordinator._get(sid).ranked]
        r.by_ref["stu_taylor"].set_blocked_windows([{"start_at": p["start_at"], "end_at": p["end_at"]} for p in ranked[1:]])
        r.coordinator.record_member_decline(sid, "stu_jordan")
        cur = r.coordinator._get(sid).current_plan
        self.assertTrue(cur is None or all(cur["start_at"] != p["start_at"] for p in ranked[1:]))

    def test_decline_requires_a_pending_proposal(self):
        r = Rig()
        sid = r.start()
        r.coordinator.cancel_negotiation(sid)
        with self.assertRaises(NegotiationError):
            r.coordinator.record_member_decline(sid, "stu_jordan")

    def test_unanswered_exception_expires_to_no_feasible_plan(self):
        r = Rig(config=NegotiationConfig(cost_tiers_cents=(5200, 7000)))
        r.by_ref["stu_alex"].set_hard_budget_cap(4000)
        r.by_ref["stu_alex"].set_exception_margin(1500)
        sid = r.start()
        r.coordinator.expire_pending_exceptions(sid)
        snap = r.snap(sid)
        self.assertEqual((snap["state"], snap["reason_category"]), ("failed", "exception_expired"))


if __name__ == "__main__":
    unittest.main()
