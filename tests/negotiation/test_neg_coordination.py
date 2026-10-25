"""Phase 2: bounded rounds, counteroffers, LLM-suggester containment, stop conditions, state machine."""
import unittest

from neg_helpers import FuncEvaluator, Rig, evaluation, plan_at

from services.negotiation import NegotiationConfig, NegotiationError, SessionState
from services.negotiation.mocks import ScriptedSuggester, flagstaff_request
from services.negotiation.models import TRANSITIONS

MEMBERS = ["stu_alex", "stu_maya", "stu_jordan", "stu_taylor"]


class CounterofferRounds(unittest.TestCase):
    def test_rejection_drives_counteroffers_derived_from_the_rejected_version(self):
        rig = Rig()
        rig.start()
        counters = [e for e in rig.sink.events if e["type"] == "counteroffer_proposed"]
        self.assertTrue(counters)
        self.assertEqual(counters[0]["payload"]["derived_from_version"], 1)
        self.assertIn("alternative day", counters[0]["payload"]["summary"].lower())
        self.assertIn("reduced estimated cost", counters[0]["payload"]["summary"].lower())

    def test_counteroffers_follow_the_hints_not_a_script(self):
        """Only a cost problem => only cost-reducing counteroffers; the day never changes."""
        def verdict(ref, p):
            over = max(p["estimated_cost_cents_by_ref"].values()) > 5000
            return evaluation(p, ref, feasible=not over, hints=["prefer_lower_cost"] if over else [])

        rig = Rig(evaluator=FuncEvaluator(verdict), exception_gateway=False)
        sid = rig.start(seed_plans=[plan_at("2026-11-01", 10, cost=7000)])
        winner = rig.coordinator._get(sid).current_plan
        self.assertLessEqual(max(winner["estimated_cost_cents_by_ref"].values()), 5000)
        self.assertTrue(winner["start_at"].startswith("2026-11-01T10"))

    def test_rounds_are_bounded(self):
        rig = Rig(config=NegotiationConfig(max_rounds=1), exception_gateway=False)
        sid = rig.start()
        snap = rig.snap(sid)
        self.assertEqual(snap["rounds"], 1)
        self.assertEqual(snap["state"], "failed")
        self.assertEqual(snap["error_code"], "NO_FEASIBLE_PLAN")
        self.assertEqual(snap["reason_category"], "search_bounds_reached")

    def test_candidates_are_bounded_per_run(self):
        rig = Rig(config=NegotiationConfig(max_candidates=3, target_feasible=99))
        sid = rig.start()
        self.assertLessEqual(rig.snap(sid)["candidates_evaluated"], 3)
        self.assertLessEqual(len(rig.by_ref["stu_alex"].evaluations), 3)

    def test_exhausted_search_without_hints_ends_with_no_feasible_plan(self):
        ev = FuncEvaluator(lambda ref, p: evaluation(p, ref, feasible=False, hints=[]))
        rig = Rig(evaluator=ev, exception_gateway=False)
        sid = rig.start()
        snap = rig.snap(sid)
        self.assertEqual((snap["state"], snap["error_code"], snap["reason_category"]),
                         ("failed", "NO_FEASIBLE_PLAN", "search_exhausted"))

    def test_search_stops_once_enough_feasible_candidates_exist(self):
        rig = Rig(config=NegotiationConfig(target_feasible=2))
        rig.start()
        fair = [e for e in rig.sink.events if e["type"] == "fairness_evaluated"]
        self.assertGreaterEqual(len(fair), 2)
        self.assertEqual([e["payload"]["rank"] for e in fair], list(range(1, len(fair) + 1)))

    def test_event_order_matches_the_contract_shape(self):
        rig = Rig()
        rig.start()
        t = rig.types()
        self.assertEqual(t[0], "negotiation_started")
        self.assertEqual(t[-2:], ["proposal_ready", "approval_requested"])
        self.assertLess(t.index("proposal_rejected"), t.index("counteroffer_proposed"))
        self.assertLess(max(i for i, x in enumerate(t) if x == "fairness_evaluated"), t.index("proposal_ready"))


class LanguageModelContainment(unittest.TestCase):
    def test_suggester_cannot_override_validators_or_private_checks(self):
        """A 'model' proposes a $0 plan that claims approval and drops a member, plus one Alex cannot afford."""
        sneaky = plan_at("2026-11-01", 10, cost=0, members=MEMBERS[:3], approved=True, feasible=True, version=99,
                         plan_id="plan_gold", member_refs=MEMBERS[:3])
        unaffordable = plan_at("2026-11-01", 11, cost=9000)
        sug = ScriptedSuggester([[sneaky, unaffordable]])
        rig = Rig(suggester=sug, config=NegotiationConfig(target_feasible=99))
        sid = rig.start()
        records = rig.coordinator._get(sid).records
        suggested = [r for r in records if r.origin == "suggestion"]
        self.assertEqual(len(suggested), 2)
        by_cost = {max(r.plan["estimated_cost_cents_by_ref"].values()): r for r in suggested}
        self.assertEqual(by_cost[0].status.value, "invalid")  # missing member: deterministic rule
        self.assertEqual(by_cost[9000].status.value, "rejected")  # Alex's private cap
        for r in suggested:
            self.assertNotIn("approved", r.plan)
            self.assertNotEqual(r.plan["plan_id"], "plan_gold")
            self.assertNotEqual(r.version, 99)
        self.assertNotIn(by_cost[0].plan["plan_id"], [r.plan["plan_id"] for r in rig.coordinator._get(sid).ranked])

    def test_good_suggestion_still_needs_all_four_private_checks(self):
        good = plan_at("2026-11-01", 11, cost=4400)
        rig = Rig(suggester=ScriptedSuggester([[good]]), config=NegotiationConfig(target_feasible=99))
        sid = rig.start()
        rec = next(r for r in rig.coordinator._get(sid).records if r.origin == "suggestion")
        self.assertEqual(set(rec.evaluations), set(MEMBERS))

    def test_suggester_sees_public_context_only(self):
        sug = ScriptedSuggester([[]])
        rig = Rig(suggester=sug)
        rig.start()
        text = str(sug.contexts).lower()
        for token in ("budget", "6000", "7500", "blocked", "soft", "penalty", "estimated_cost_cents_by_ref"):
            self.assertNotIn(token, text)

    def test_failing_suggester_is_ignored(self):
        class Boom:
            def suggest(self, ctx):
                raise RuntimeError("model down")

        rig = Rig(suggester=Boom())
        sid = rig.start()
        self.assertEqual(rig.snap(sid)["state"], "approval_pending")

    def test_suggestions_per_round_are_capped(self):
        many = [plan_at("2026-11-01", 10 + i % 3, cost=3500 + 100 * i) for i in range(8)]
        rig = Rig(suggester=ScriptedSuggester([many]), config=NegotiationConfig(max_suggestions_per_round=2, target_feasible=99))
        sid = rig.start()
        self.assertEqual(sum(r.origin == "suggestion" for r in rig.coordinator._get(sid).records), 2)


class StateMachine(unittest.TestCase):
    def test_happy_path_transitions(self):
        rig = Rig()
        sid = rig.start()
        self.assertEqual(rig.coordinator.transitions_of(sid), [
            ("created", "negotiating"), ("negotiating", "proposed"), ("proposed", "approval_pending")])

    def test_coordinator_never_confirms_without_the_commitment_gateway(self):
        rig = Rig()
        sid = rig.start()
        self.assertNotEqual(rig.coordinator.state_of(sid), SessionState.CONFIRMED)
        self.assertNotIn("proposal_confirmed", rig.types())
        res = rig.coordinator.confirm_if_approved(sid)
        self.assertEqual((res.status, res.error_code), ("incomplete", "APPROVAL_INCOMPLETE"))

    def test_maybe_conditional_and_declined_never_confirm(self):
        for answer in ("tentative", "conditional", "interested", "pending", "declined", "withdrawn"):
            rig = Rig()
            sid = rig.start()
            rig.accept_all(sid, "accepted")
            snap = rig.snap(sid)
            rig.gateway.record_approval(sid, snap["plan"]["plan_id"], snap["version"], "stu_jordan", answer)
            res = rig.coordinator.confirm_if_approved(sid)
            self.assertEqual(res.status, "incomplete", answer)
            self.assertNotIn("proposal_confirmed", rig.types(), answer)

    def test_confirmed_only_after_all_required_accept_same_version(self):
        rig = Rig()
        sid = rig.start()
        rig.accept_all(sid)
        res = rig.coordinator.confirm_if_approved(sid, version=rig.snap(sid)["version"])
        self.assertEqual((res.status, res.accepted_count, res.required_count), ("confirmed", 4, 4))
        self.assertEqual(rig.types()[-2:], ["proposal_confirmed", "session_completed"])
        self.assertEqual(rig.coordinator.state_of(sid), SessionState.CONFIRMED)
        again = rig.coordinator.confirm_if_approved(sid)  # idempotent
        self.assertEqual(again.status, "confirmed")
        self.assertEqual(rig.types().count("proposal_confirmed"), 1)

    def test_gateway_summary_for_a_different_version_is_stale(self):
        rig = Rig()
        sid = rig.start()
        rig.accept_all(sid)
        v = rig.snap(sid)["version"]
        self.assertEqual(rig.coordinator.confirm_if_approved(sid, version=v - 1).error_code, "PROPOSAL_STALE")
        rig.gateway.get_commitment_summary = lambda s, p, ver: {**{"plan_id": p, "version": ver + 1,
                                                                   "required_count": 4, "accepted_count": 4}}
        self.assertEqual(rig.coordinator.confirm_if_approved(sid).error_code, "PROPOSAL_STALE")
        self.assertNotIn("proposal_confirmed", rig.types())

    def test_untrustworthy_summaries_do_not_confirm(self):
        for bad in ({"accepted_count": 4, "required_count": 3}, {"accepted_count": 3, "required_count": 4},
                    {"accepted_count": True, "required_count": 1}, {"accepted_count": 4, "required_count": 4, "confirmed": False},
                    {"accepted_count": 4, "required_count": 4, "declined_count": 1}):
            rig = Rig()
            sid = rig.start()
            rig.gateway.get_commitment_summary = lambda s, p, v, bad=bad: {"plan_id": p, "version": v, **bad}
            self.assertEqual(rig.coordinator.confirm_if_approved(sid).status, "incomplete", bad)

    def test_gateway_outage_is_provider_unavailable_not_confirmation(self):
        rig = Rig()
        sid = rig.start()

        def boom(*a):
            raise RuntimeError("down")

        rig.gateway.get_commitment_summary = boom
        res = rig.coordinator.confirm_if_approved(sid)
        self.assertEqual((res.status, res.error_code), ("incomplete", "PROVIDER_UNAVAILABLE"))

    def test_start_is_idempotent_per_request_id(self):
        rig = Rig()
        a = rig.start()
        n = len(rig.sink.events)
        b = rig.coordinator.start_negotiation(flagstaff_request())
        self.assertEqual(a, b)
        self.assertEqual(len(rig.sink.events), n)

    def test_unknown_session_and_illegal_calls(self):
        rig = Rig()
        with self.assertRaises(NegotiationError) as cm:
            rig.coordinator.get_public_snapshot("nope")
        self.assertEqual(cm.exception.code, "UNKNOWN_SESSION")
        sid = rig.start()
        with self.assertRaises(NegotiationError):
            rig.coordinator.resolve_private_exception(sid, "stu_alex", True)  # none pending
        with self.assertRaises(NegotiationError):
            rig.coordinator._transition(rig.coordinator._get(sid), SessionState.NEGOTIATING)

    def test_cancelled_is_terminal_and_invalidates_the_proposal(self):
        rig = Rig()
        sid = rig.start()
        v = rig.snap(sid)["version"]
        rig.coordinator.cancel_negotiation(sid)
        self.assertEqual(rig.coordinator.state_of(sid), SessionState.CANCELLED)
        self.assertEqual(rig.gateway.invalidations[-1][1], v)
        self.assertEqual(rig.types()[-1], "session_completed")
        with self.assertRaises(NegotiationError):
            rig.coordinator.revise_negotiation(sid, {"kind": "budget"})
        self.assertEqual(rig.coordinator.confirm_if_approved(sid, version=v).status, "stale")

    def test_cancellation_during_search_stops_further_probing(self):
        rig = Rig()
        holder = {}

        class CancelOnFirstRejection:
            def __init__(self, inner):
                self.inner = inner

            def emit(self, event):
                self.inner.emit(event)
                if event["type"] == "proposal_rejected" and "sid" in holder:
                    rig.coordinator.cancel_negotiation(holder["sid"])

        rig.coordinator.sink = CancelOnFirstRejection(rig.sink)
        holder["sid"] = "session_trip_001"
        rig.coordinator.start_negotiation(flagstaff_request())
        self.assertEqual(rig.coordinator.state_of("session_trip_001"), SessionState.CANCELLED)
        self.assertEqual(len(rig.by_ref["stu_alex"].evaluations), 1)
        self.assertNotIn("proposal_ready", rig.types())

    def test_transition_table_has_no_exit_from_cancelled(self):
        self.assertEqual(TRANSITIONS[SessionState.CANCELLED], set())
        self.assertNotIn(SessionState.CONFIRMED, TRANSITIONS[SessionState.NEGOTIATING])  # cannot skip approvals


if __name__ == "__main__":
    unittest.main()
