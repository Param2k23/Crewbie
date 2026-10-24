"""Fairness ranks FEASIBLE plans only, spreads soft compromises, and never overrides a hard limit."""
import unittest

from neg_helpers import FuncEvaluator, Rig, evaluation, plan_at

from services.negotiation import InMemoryFairnessHistory, NegotiationConfig
from services.negotiation.mocks import flagstaff_request
from services.negotiation.fairness import rank_feasible, score_record
from services.negotiation.models import CandidateRecord, CandidateStatus, Evaluation

MEMBERS = ["stu_alex", "stu_maya", "stu_jordan", "stu_taylor"]
CFG = NegotiationConfig()


def record(penalties, *, cost=5000, start="2026-11-01T10:00:00-07:00", feasible=True):
    evs = {m: Evaluation(m, feasible, False, (), p, ()) for m, p in zip(MEMBERS, penalties)}
    plan = {"start_at": start, "estimated_cost_cents_by_ref": {m: cost for m in MEMBERS}, "member_refs": MEMBERS,
            "end_at": start, "activities": [], "opportunity_id": None}
    return CandidateRecord(plan, CandidateStatus.FEASIBLE if feasible else CandidateStatus.REJECTED, "seed", None, evs)


class Formula(unittest.TestCase):
    def test_even_spread_beats_concentrated_burden_at_equal_total(self):
        even, lumpy = record([0.2, 0.2, 0.2, 0.2]), record([0.8, 0.0, 0.0, 0.0])
        ranked = rank_feasible([lumpy, even], {}, CFG)
        self.assertIs(ranked[0].record, even)
        self.assertLess(ranked[0].score, ranked[1].score)

    def test_lower_total_compromise_wins_when_spread_is_equal(self):
        a, b = record([0.1] * 4), record([0.3] * 4)
        self.assertIs(rank_feasible([b, a], {}, CFG)[0].record, a)

    def test_history_penalises_burdening_the_already_burdened(self):
        a, b = record([0.4, 0, 0, 0]), record([0, 0.4, 0, 0])
        hist = {"stu_alex": 1.0, "stu_maya": 0.0}
        self.assertIs(rank_feasible([a, b], hist, CFG)[0].record, b)
        self.assertIs(rank_feasible([a, b], {}, CFG)[0].record, a)  # no history: tie-break only

    def test_ties_break_deterministically_regardless_of_input_order(self):
        a = record([0.1] * 4, start="2026-11-01T10:00:00-07:00")
        b = record([0.1] * 4, start="2026-11-02T10:00:00-07:00")
        for order in ([a, b], [b, a]):
            self.assertIs(rank_feasible(order, {}, CFG)[0].record, a)

    def test_cost_breaks_ties_before_time(self):
        cheap, dear = record([0.1] * 4, cost=4000, start="2026-11-02T10:00:00-07:00"), record([0.1] * 4, cost=5000)
        self.assertIs(rank_feasible([dear, cheap], {}, CFG)[0].record, cheap)

    def test_ranking_refuses_infeasible_candidates_outright(self):
        """Fairness can never turn invalid into valid: it does not even accept such input."""
        with self.assertRaises(ValueError):
            rank_feasible([record([0.0] * 4, feasible=False), record([0.5] * 4)], {}, CFG)

    def test_score_is_documented_formula(self):
        r = record([0.2, 0.0, 0.0, 0.0])
        mean, var = 0.05, ((0.15 ** 2) + 3 * (0.05 ** 2)) / 4
        hist = {"stu_alex": 0.5}
        expected = mean + 2 * var + (0.5 * 0.2) / 4
        self.assertAlmostEqual(score_record(r, hist, CFG).score, expected, places=7)


class SoftPreferencesOnlyAmongValidPlans(unittest.TestCase):
    def test_early_start_dislike_orders_valid_plans_but_never_admits_an_invalid_one(self):
        early_ok = plan_at("2026-11-01", 7, cost=5200)  # valid but early (Alex/Jordan/Taylor dislike it)
        late_ok = plan_at("2026-11-01", 10, cost=5200)  # valid, no early penalty
        late_too_dear = plan_at("2026-11-01", 11, cost=9000)  # zero soft penalty on time, but breaks Alex's cap
        rig = Rig(config=NegotiationConfig(target_feasible=99, max_candidates=3))
        sid = rig.start(seed_plans=[early_ok, late_ok, late_too_dear])
        s = rig.coordinator._get(sid)
        self.assertEqual(s.current_plan["start_at"][11:13], "10")
        self.assertLessEqual(max(s.current_plan["estimated_cost_cents_by_ref"].values()), 6000)
        ranked_starts = [r.plan["start_at"][11:13] for r in s.ranked]
        self.assertEqual(ranked_starts, ["10", "07"])
        self.assertTrue(all(all(e.feasible for e in r.evaluations.values()) for r in s.ranked))
        rejected = [r for r in s.records if r.status is CandidateStatus.REJECTED]
        self.assertTrue(any(r.plan["start_at"][11:13] == "11" for r in rejected))

    def test_public_events_do_not_reveal_who_carries_the_compromise(self):
        rig = Rig()
        rig.start()
        for e in rig.sink.events:
            if e["type"] == "fairness_evaluated":
                self.assertEqual(set(e["payload"]), {"plan_id", "version", "rank", "feasible_count", "balance"})
                self.assertIn(e["payload"]["balance"], ("balanced", "uneven"))


class TwoSessionHistory(unittest.TestCase):
    """Penalty depends on the day only: day A burdens Alex, day B burdens Maya; both are fully valid."""

    @staticmethod
    def verdict(ref, p):
        day = p["start_at"][:10]
        if day == "2026-11-01":
            return evaluation(p, ref, penalty=0.4 if ref == "stu_alex" else 0.0)
        return evaluation(p, ref, penalty=0.4 if ref == "stu_maya" else 0.0)

    def run_session(self, rig, n):
        seeds = [plan_at("2026-11-01", 10), plan_at("2026-11-02", 10)]
        sid = rig.coordinator.start_negotiation(flagstaff_request(
            request_id=f"req_{n}", session_id=f"session_{n}", seed_plans=seeds))
        rig.open(sid)
        rig.accept_all(sid)
        self.assertEqual(rig.coordinator.confirm_if_approved(sid).status, "confirmed")
        return rig.coordinator._get(sid).current_plan["start_at"][:10]

    def test_burden_rotates_to_the_member_who_did_not_carry_it_last_time(self):
        hist = InMemoryFairnessHistory(opted_in=set(MEMBERS))
        rig = Rig(evaluator=FuncEvaluator(self.verdict), fairness_history=hist)
        first = self.run_session(rig, 1)
        second = self.run_session(rig, 2)
        self.assertEqual(first, "2026-11-01")  # tie: earliest wins; Alex carried it
        self.assertEqual(second, "2026-11-02")  # history now spares Alex
        for e in rig.sink.events:  # nothing about history leaked
            self.assertNotIn("history", str(e).lower())

    def test_without_opt_in_no_history_is_used_or_recorded(self):
        hist = InMemoryFairnessHistory(opted_in=set())
        rig = Rig(evaluator=FuncEvaluator(self.verdict), fairness_history=hist)
        self.assertEqual(self.run_session(rig, 1), "2026-11-01")
        self.assertEqual(self.run_session(rig, 2), "2026-11-01")  # no memory => same tie-break
        self.assertEqual(hist.burden_shares(MEMBERS), {})

    def test_partial_opt_in_only_counts_those_who_consented(self):
        hist = InMemoryFairnessHistory(opted_in={"stu_maya"})
        hist.record_outcome("s0", {"stu_alex": 0.9, "stu_maya": 0.2})
        self.assertEqual(hist.burden_shares(MEMBERS), {"stu_maya": 1.0})

    def test_history_cannot_override_a_hard_constraint(self):
        """Only the day that burdens Alex is valid; Alex's history must not bring back the invalid day."""
        def verdict(ref, p):
            if p["start_at"][:10] == "2026-11-02":
                return evaluation(p, ref, feasible=(ref != "stu_taylor"))  # Taylor cannot do day B
            return evaluation(p, ref, penalty=0.9 if ref == "stu_alex" else 0.0)

        hist = InMemoryFairnessHistory(opted_in=set(MEMBERS))
        hist.record_outcome("old", {"stu_alex": 5.0})
        rig = Rig(evaluator=FuncEvaluator(verdict), fairness_history=hist, exception_gateway=False)
        sid = rig.coordinator.start_negotiation(flagstaff_request(
            seed_plans=[plan_at("2026-11-01", 10), plan_at("2026-11-02", 10)]))
        s = rig.coordinator._get(sid)
        self.assertEqual(s.current_plan["start_at"][:10], "2026-11-01")
        self.assertEqual(len(s.ranked), 1)

    def test_history_recorded_once_per_confirmed_session(self):
        hist = InMemoryFairnessHistory(opted_in=set(MEMBERS))
        rig = Rig(evaluator=FuncEvaluator(self.verdict), fairness_history=hist)
        sid = rig.coordinator.start_negotiation(flagstaff_request(
            seed_plans=[plan_at("2026-11-01", 10)]))
        rig.open(sid)
        rig.accept_all(sid)
        rig.coordinator.confirm_if_approved(sid)
        rig.coordinator.confirm_if_approved(sid)
        self.assertEqual(hist.burden_shares(MEMBERS)["stu_alex"], 1.0)
        self.assertEqual(hist._totals["stu_alex"], 0.4)


if __name__ == "__main__":
    unittest.main()
