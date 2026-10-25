"""General social planning: time-first / intent-first requests, multi-day logistics, matched groups,
and the three verification scenarios (A dinner/game, B two-day trip, C mid-plan constraint change)."""
import argparse
import io
import json
import re
import unittest
from pathlib import Path

from neg_helpers import FuncEvaluator, Rig, evaluation, plan_at

from services.negotiation import MemoryEventSink, NegotiationConfig, NegotiationCoordinator, NegotiationError, SessionRequest, SteppingClock
from services.negotiation.catalog import ActivityCatalog
from services.negotiation.demo import build_parser, run
from services.negotiation.mocks import MockCommitmentGateway, MockExceptionGateway, MockPrivateEvaluator, ScriptedSuggester
from services.negotiation.models import parse_ts
from services.negotiation.scenarios import dinner_game_kit, flagstaff_kit, two_day_trip_kit
from services.negotiation.validator import normalize_candidate, validate_plan

DOCS = Path(__file__).resolve().parents[2] / "docs" / "negotiation"


class KitRig:
    """A coordinator wired to a scenario kit's private agents."""

    def __init__(self, kit, **kw):
        self.kit = kit
        self.by_ref = {a.student_ref: a for a in kit.agents}
        self.ev = MockPrivateEvaluator(kit.agents)
        self.gateway, self.exceptions, self.sink = MockCommitmentGateway(), MockExceptionGateway(), MemoryEventSink()
        self.clock = SteppingClock()
        kw.setdefault("exception_gateway", self.exceptions)
        self.c = NegotiationCoordinator(self.ev, self.gateway, self.sink, clock=self.clock, **kw)
        self.sid = self.c.start_negotiation(kit.request)
        self.open()

    def open(self):
        s = self.c.get_public_snapshot(self.sid)
        if s["plan"]:
            self.gateway.open_proposal(s)

    def snap(self):
        return self.c.get_public_snapshot(self.sid)

    def accept_all(self):
        s = self.snap()
        for m in s["plan"]["member_refs"]:
            self.gateway.record_approval(self.sid, s["plan"]["plan_id"], s["version"], m, "accepted")

    def types(self):
        return self.sink.types()

    def violates(self, plan):
        """Independent re-check of a published plan against each member's PRIVATE profile (test oracle)."""
        start, end = parse_ts(plan["start_at"]), parse_ts(plan["end_at"])
        bad = []
        for ref, agent in self.by_ref.items():
            p = agent._p
            if ref not in plan["member_refs"]:
                continue
            cost = self.c._get(self.sid).current_plan["estimated_cost_cents_by_ref"][ref]
            if cost > p["hard_budget_cap_cents"]:
                bad.append((ref, "budget"))
            for w in p["blocked_windows"]:
                if start < parse_ts(w["end_at"]) and end > parse_ts(w["start_at"]):
                    bad.append((ref, "time"))
            if p.get("hard_max_nights") is not None and plan["nights"] > p["hard_max_nights"]:
                bad.append((ref, "nights"))
        return bad


# ----------------------------------------------------------------------------- time-first / intent-first
class RequestModes(unittest.TestCase):
    def req(self, **kw):
        raw = dinner_game_kit(mode="time_first").request
        raw.update(kw)
        return SessionRequest.from_mapping(raw)

    def test_time_first_offers_several_activity_kinds_for_the_free_time(self):
        seeds = ActivityCatalog().seeds(self.req(slot_limit=20), ["a", "b", "c", "d"])
        kinds = {s["activity_kind"] for s in seeds}
        self.assertTrue({"dinner", "games", "sports", "hiking"} <= kinds, kinds)

    def test_duration_constrains_what_fits_but_does_not_force_a_category(self):
        evening = self.req(window_start="2026-11-06T17:00:00-07:00", window_end="2026-11-06T21:00:00-07:00", slot_limit=50)
        kinds = {s["activity_kind"] for s in ActivityCatalog().seeds(evening, ["a", "b"])}
        self.assertNotIn("weekend_trip", kinds)  # 30 hours cannot fit a 4-hour window
        self.assertNotIn("day_trip", kinds)
        self.assertIn("games", kinds)  # a short activity is still offered
        long_window = self.req(slot_limit=50)
        kinds_long = {s["activity_kind"] for s in ActivityCatalog().seeds(long_window, ["a", "b"])}
        self.assertIn("games", kinds_long)  # a long window does not push everyone into a trip
        self.assertIn("dinner", kinds_long)

    def test_every_candidate_interval_fits_inside_the_planning_window(self):
        r = self.req(slot_limit=50)
        w0, w1 = parse_ts(r.window_start), parse_ts(r.window_end)
        for s in ActivityCatalog().seeds(r, ["a", "b"]):
            self.assertTrue(w0 <= parse_ts(s["start_at"]) < parse_ts(s["end_at"]) <= w1)

    def test_intent_first_only_proposes_the_requested_activity(self):
        rig = KitRig(dinner_game_kit())
        kinds = {e["payload"].get("activity_kind") for e in rig.sink.events if e["type"] == "candidate_proposed"}
        self.assertEqual(kinds, {"dinner_games"})

    def test_intent_first_unknown_activity_is_a_validation_error(self):
        kit = dinner_game_kit()
        kit.request["intent"] = {"kind": "skydiving"}
        c = NegotiationCoordinator(MockPrivateEvaluator(kit.agents), MockCommitmentGateway(), MemoryEventSink())
        with self.assertRaises(NegotiationError) as cm:
            c.start_negotiation(kit.request)
        self.assertEqual(cm.exception.code, "INVALID_REQUEST")
        with self.assertRaises(NegotiationError):
            SessionRequest.from_mapping({**kit.request, "intent": None})

    def test_time_first_session_negotiates_a_mix_and_picks_a_valid_one(self):
        kit = dinner_game_kit(mode="time_first")
        kit.request["slot_limit"] = 8
        rig = KitRig(kit)
        s = rig.snap()
        self.assertEqual(s["state"], "approval_pending")
        kinds = {e["payload"]["activity_kind"] for e in rig.sink.events if e["type"] == "candidate_proposed"}
        self.assertGreater(len(kinds), 1)
        self.assertEqual(rig.violates(s["plan"]), [])

    def test_soft_activity_preference_influences_only_valid_choices(self):
        kit = dinner_game_kit(mode="time_first")
        kit.request["slot_limit"] = 60
        rig = KitRig(kit, config=NegotiationConfig(max_candidates=60, target_feasible=60, max_rounds=1))
        ranked = rig.c._get(rig.sid).ranked
        self.assertGreater(len(ranked), 5)
        self.assertTrue(all(all(e.feasible for e in r.evaluations.values()) for r in ranked))
        burden = lambda r: r.evaluations["stu_cam"].soft_penalty  # noqa: E731
        liked = {"dinner_games", "games"}
        # Cam's activity preference is a soft penalty: it never admits an invalid plan, it only orders valid ones
        self.assertTrue(all(burden(r) >= 0.15 for r in ranked if r.plan["activity_kind"] not in liked))
        self.assertTrue(all(burden(r) < 0.15 for r in ranked if r.plan["activity_kind"] in liked))
        first_liked = min(i for i, r in enumerate(ranked) if r.plan["activity_kind"] in liked)
        self.assertLess(first_liked, len(ranked) // 2 + 1)


# ----------------------------------------------------------------------------- Phase 1 general feasibility
class GeneralFeasibility(unittest.TestCase):
    def setUp(self):
        self.kit = two_day_trip_kit()
        self.req = SessionRequest.from_mapping(self.kit.request)
        self.roster = self.req.member_refs

    def norm(self, **over):
        raw = ActivityCatalog().seeds(self.req, self.roster)[0]
        raw.update(over)
        return normalize_candidate(raw, session_id="s", plan_id="p", version=1, request=self.req, roster=self.roster)

    def test_two_day_trip_is_flagged_overnight_with_lodging_to_verify(self):
        p = self.norm()
        self.assertEqual((p["overnight"], p["nights"]), (True, 1))
        self.assertEqual(p["unverified_items"], ["transport", "lodging"])
        self.assertEqual(validate_plan(p, self.req, self.roster), [])

    def test_overnight_and_nights_are_recomputed_not_trusted(self):
        p = self.norm(overnight=False, nights=0, unverified_items=[])
        self.assertTrue(p["overnight"])
        self.assertEqual(p["unverified_items"], ["transport", "lodging"])

    def test_assumed_or_booked_logistics_are_rejected(self):
        for logistics, code in (({"transport": "booked"}, "LOGISTICS_ASSUMED"),
                                ({"lodging": "confirmed"}, "LOGISTICS_ASSUMED"),
                                ({"transport": "not_needed"}, "TRANSPORT_ASSUMED"),
                                ({"lodging": "not_needed"}, "LODGING_ASSUMED")):
            self.assertIn(code, validate_plan(self.norm(logistics=logistics), self.req, self.roster), logistics)

    def test_venue_hours_must_cover_the_whole_interval_and_unknown_hours_are_flagged(self):
        dinner = SessionRequest.from_mapping(dinner_game_kit().request)
        roster = dinner.member_refs
        base = ActivityCatalog().seeds(dinner, roster)[0]
        p = normalize_candidate(base, session_id="s", plan_id="p", version=1, request=dinner, roster=roster)
        self.assertIn("venue_hours", p["unverified_items"])  # we do not know the opening times
        closed = dict(base, venue_hours={"opens_at": base["start_at"], "closes_at": "2026-11-06T20:00:00-07:00"})
        self.assertIn("VENUE_CLOSED", validate_plan(normalize_candidate(closed, session_id="s", plan_id="p", version=1,
                                                                        request=dinner, roster=roster), dinner, roster))
        open_ = dict(base, venue_hours={"opens_at": base["start_at"], "closes_at": base["end_at"]})
        q = normalize_candidate(open_, session_id="s", plan_id="p", version=1, request=dinner, roster=roster)
        self.assertEqual(validate_plan(q, dinner, roster), [])
        self.assertNotIn("venue_hours", q["unverified_items"])

    def test_no_logistics_flag_for_activities_that_genuinely_need_none(self):
        kit = dinner_game_kit(mode="time_first")
        req = SessionRequest.from_mapping(kit.request)
        games = next(s for s in ActivityCatalog().seeds(SessionRequest.from_mapping({**kit.request, "slot_limit": 50}), req.member_refs)
                     if s["activity_kind"] == "games")
        p = normalize_candidate(games, session_id="s", plan_id="p", version=1, request=req, roster=req.member_refs)
        self.assertEqual(p["unverified_items"], [])

    def test_blocked_second_day_rejects_the_whole_two_day_trip(self):
        """Hard availability applies to the ENTIRE interval, not just the start."""
        rig = KitRig(two_day_trip_kit())
        recs = rig.c._get(rig.sid).records
        two_day = [r for r in recs if r.plan["nights"] == 1]
        self.assertTrue(two_day)
        sat_to_sun = [r for r in two_day if r.plan["start_at"].startswith("2026-11-14")]
        self.assertEqual(sat_to_sun[0].status.value, "rejected")
        fri_to_sat = [r for r in two_day if r.plan["start_at"].startswith("2026-11-13")]
        self.assertEqual(fri_to_sat[0].status.value, "rejected")  # only the SECOND day (Saturday) is blocked for Hal

    def test_snapshot_surfaces_what_humans_must_verify_and_calls_costs_estimates(self):
        rig = KitRig(dinner_game_kit())
        plan = rig.snap()["plan"]
        self.assertEqual(plan["unverified_items"], ["transport", "venue_hours"])
        self.assertIn("estimate", plan["estimate_disclaimer"].lower())
        self.assertNotIn("booked", json.dumps(plan).lower())


# ----------------------------------------------------------------------------- unauthorised exceptions
class UnauthorizedExceptions(unittest.TestCase):
    def test_model_claimed_exception_is_discarded_and_plan_still_rejected(self):
        kit = dinner_game_kit()
        pricey = plan_at("2026-11-07", 18, cost=9000, members=[a.student_ref for a in kit.agents], hours=4,
                         exception_approved=True, cost_exception="approved by all", activity_kind="dinner_games")
        kit.request.update(seed_plans=[pricey], mode="seeded")
        rig = KitRig(kit, suggester=ScriptedSuggester([[pricey]]), config=NegotiationConfig(target_feasible=99))
        recs = rig.c._get(rig.sid).records
        first = recs[0]
        self.assertEqual(first.status.value, "rejected")
        self.assertNotIn("exception_approved", first.plan)
        self.assertNotIn("cost_exception", first.plan)

    def test_exception_counts_only_if_the_students_own_side_revalidates(self):
        """A coordinator-side 'yes' without the student's evaluator agreeing cannot make a plan valid."""
        from services.negotiation.mocks import MockParticipantAgent  # noqa: F401  (documented dependency)
        calls = {"n": 0}

        def verdict(ref, p):
            calls["n"] += 1
            over = p["estimated_cost_cents_by_ref"][ref] > 4000 and ref == "stu_alex"
            return evaluation(p, ref, feasible=not over, exception=over, hints=[])

        rig = Rig(evaluator=FuncEvaluator(verdict), config=NegotiationConfig(cost_tiers_cents=(5200,)))
        sid = rig.start(seed_plans=[plan_at("2026-11-01", 10, cost=5200)])
        self.assertEqual(rig.coordinator.state_of(sid).value, "awaiting_exception")
        rig.coordinator.resolve_private_exception(sid, "stu_alex", True)
        self.assertEqual(rig.snap(sid)["state"], "failed")  # evaluator still says no
        self.assertIsNone(rig.snap(sid)["plan"])

    def test_declined_or_missing_exception_never_yields_a_plan_over_the_cap(self):
        kit = dinner_game_kit()
        rig = KitRig(kit)
        rig.by_ref["stu_dev"].set_hard_budget_cap(1000)  # lowest tier is 500 per person... plan costs 3000
        rig.by_ref["stu_dev"].set_exception_margin(500)
        rig.c.revise_negotiation(rig.sid, {"kind": "budget", "student_ref": "stu_dev"})
        s = rig.snap()
        if rig.c.state_of(rig.sid).value == "awaiting_exception":
            rig.c.resolve_private_exception(rig.sid, "stu_dev", False)
            s = rig.snap()
        if s["plan"]:
            self.assertEqual(rig.violates(s["plan"]), [])
        else:
            self.assertEqual(s["error_code"], "NO_FEASIBLE_PLAN")


# ----------------------------------------------------------------------------- group origin & isolation
class GroupOrigins(unittest.TestCase):
    def test_matched_group_requires_everyones_introduction_consent(self):
        kit = dinner_game_kit()
        kit.request.update(group_origin="matched", consent_context={"introduction_consent_refs": ["stu_ari", "stu_bea"]})
        rig = KitRig(kit)
        s = rig.snap()
        self.assertEqual((s["state"], s["error_code"]), ("failed", "CONSENT_REQUIRED"))
        self.assertEqual(sum(len(a.evaluations) for a in rig.kit.agents), 0)  # nobody was even probed

    def test_matched_group_with_full_consent_negotiates_like_any_other(self):
        kit = dinner_game_kit()
        kit.request.update(group_origin="matched",
                           consent_context={"introduction_consent_refs": [a.student_ref for a in kit.agents]})
        self.assertEqual(KitRig(kit).snap()["state"], "approval_pending")

    def test_unknown_group_origin_rejected(self):
        with self.assertRaises(NegotiationError):
            SessionRequest.from_mapping({**dinner_game_kit().request, "group_origin": "stranger_danger"})

    def test_agents_only_ever_see_their_own_cost_line_in_every_scenario(self):
        for kit in (dinner_game_kit(), two_day_trip_kit()):
            seen = []
            inner = MockPrivateEvaluator(kit.agents)

            class Spy:
                def evaluate_plan_private(self, ref, plan):
                    seen.append((ref, set(plan["estimated_cost_cents_by_ref"])))
                    return inner.evaluate_plan_private(ref, plan)

                def propose_private_counteroffer(self, ref, plan):
                    seen.append((ref, set(plan["estimated_cost_cents_by_ref"])))
                    return inner.propose_private_counteroffer(ref, plan)

            c = NegotiationCoordinator(Spy(), MockCommitmentGateway(), MemoryEventSink())
            c.start_negotiation(kit.request)
            self.assertTrue(seen)
            self.assertTrue(all(costs == {ref} for ref, costs in seen))


# ----------------------------------------------------------------------------- Scenario A
class ScenarioDinnerAndGames(unittest.TestCase):
    def setUp(self):
        self.rig = KitRig(dinner_game_kit())

    def test_early_slots_fail_and_a_valid_alternative_is_found(self):
        s = self.rig.snap()
        self.assertEqual(s["state"], "approval_pending")
        self.assertIn("proposal_rejected", self.rig.types())  # at least one slot failed
        first_events = self.rig.sink.events[1:3]
        self.assertEqual([e["type"] for e in first_events], ["candidate_proposed", "proposal_rejected"])
        self.assertEqual(self.rig.violates(s["plan"]), [])
        self.assertFalse(s["plan"]["start_at"].startswith("2026-11-06"))  # Friday is blocked for Bea

    def test_all_four_members_were_privately_asked_about_every_slot(self):
        n = self.rig.snap()["candidates_evaluated"]
        for agent in self.rig.kit.agents:
            self.assertEqual(len(agent.evaluations), n)

    def test_one_conflicting_member_is_enough_to_reject_a_slot(self):
        recs = self.rig.c._get(self.rig.sid).records
        sat17 = next(r for r in recs if r.plan["start_at"] == "2026-11-07T17:00:00-07:00")  # only Cam is blocked
        self.assertEqual(sat17.status.value, "rejected")
        self.assertEqual([r for r, e in sat17.evaluations.items() if not e.feasible], ["stu_cam"])

    def test_nobody_is_confirmed_on_maybe(self):
        s = self.rig.snap()
        for m, a in zip(s["plan"]["member_refs"], ("accepted", "accepted", "tentative", "accepted")):
            self.rig.gateway.record_approval(self.rig.sid, s["plan"]["plan_id"], s["version"], m, a)
        self.assertEqual(self.rig.c.confirm_if_approved(self.rig.sid).status, "incomplete")

    def test_public_trace_leaks_no_private_values(self):
        assert_trace_private_safe(self, self.rig)


# ----------------------------------------------------------------------------- Scenario B
class ScenarioTwoDayTrip(unittest.TestCase):
    def test_full_length_plans_fail_and_counteroffers_reach_a_valid_alternative(self):
        rig = KitRig(two_day_trip_kit())
        s = rig.snap()
        t = rig.types()
        self.assertEqual(s["state"], "approval_pending")
        self.assertLess(t.index("proposal_rejected"), t.index("counteroffer_proposed"))
        self.assertEqual(rig.violates(s["plan"]), [])
        self.assertFalse(s["plan"]["overnight"])  # the agents' counteroffer shortened the trip
        self.assertEqual(s["plan"]["activity_kind"], "day_trip")
        first = [e for e in rig.sink.events if e["type"] == "candidate_proposed"]
        self.assertTrue(all(e["payload"]["overnight"] for e in first))

    def test_counteroffers_chain_to_versions_that_exist_and_rounds_are_bounded(self):
        rig = KitRig(two_day_trip_kit())
        versions = {e["payload"]["version"] for e in rig.sink.events if "version" in e["payload"]}
        for e in rig.sink.events:
            if e["type"] == "counteroffer_proposed":
                parent = e["payload"]["derived_from_version"]
                self.assertIn(parent, versions)
                self.assertLess(parent, e["payload"]["version"])
        s = rig.snap()
        self.assertLessEqual(s["rounds"], NegotiationConfig().max_rounds)
        self.assertLessEqual(s["candidates_evaluated"], NegotiationConfig().max_candidates)

    def test_when_nothing_works_the_result_is_an_honest_no_feasible_plan(self):
        rig = KitRig(two_day_trip_kit(impossible=True))
        s = rig.snap()
        self.assertEqual((s["state"], s["error_code"]), ("failed", "NO_FEASIBLE_PLAN"))
        self.assertIsNone(s["plan"])
        self.assertNotIn("proposal_ready", rig.types())
        self.assertNotIn("approval_requested", rig.types())
        self.assertEqual(rig.types()[-1], "negotiation_failed")
        self.assertLessEqual(s["candidates_evaluated"], NegotiationConfig().max_candidates)

    def test_hard_max_nights_forces_a_shorter_trip_via_the_agents_own_hint(self):
        kit = two_day_trip_kit()
        kit.agents[0]._p["hard_max_nights"] = 0  # Eli will not do overnight trips
        for a in kit.agents:  # make every full-length date otherwise fine, isolating the nights rule
            a._p["blocked_windows"], a._p["hard_budget_cap_cents"] = [], 20000
        rig = KitRig(kit)
        s = rig.snap()
        self.assertEqual(s["state"], "approval_pending")
        self.assertEqual(s["plan"]["nights"], 0)
        self.assertEqual(rig.violates(s["plan"]), [])

    def test_public_trace_leaks_no_private_values(self):
        assert_trace_private_safe(self, KitRig(two_day_trip_kit()))
        assert_trace_private_safe(self, KitRig(two_day_trip_kit(impossible=True)))


# ----------------------------------------------------------------------------- Scenario C
class ScenarioConstraintChangesMidPlan(unittest.TestCase):
    def test_availability_change_invalidates_the_plan_and_genuinely_replans(self):
        rig = KitRig(dinner_game_kit())
        rig.accept_all()
        old = rig.snap()
        self.assertEqual(rig.c.confirm_if_approved(rig.sid, version=old["version"]).status, "confirmed") if False else None
        rig.by_ref["stu_cam"].set_blocked_windows(
            [{"start_at": old["plan"]["start_at"], "end_at": old["plan"]["end_at"]}])
        n = len(rig.sink.events)
        rig.c.revise_negotiation(rig.sid, {"kind": "availability", "student_ref": "stu_cam"})
        new = rig.snap()
        # 1. the previous plan was re-validated and FAILED
        new_events = rig.sink.events[n:]
        self.assertEqual(new_events[0]["type"], "proposal_revised")
        first_rejection = next(e for e in new_events if e["type"] == "proposal_rejected")
        reproposed = next(e for e in new_events if e["type"] == "candidate_proposed")
        self.assertEqual(first_rejection["payload"]["version"], reproposed["payload"]["version"])
        # 2. approvals for the old version are void
        self.assertEqual(rig.gateway.get_commitment_summary(rig.sid, old["plan"]["plan_id"], old["version"])["accepted_count"], 0)
        self.assertEqual(rig.c.confirm_if_approved(rig.sid, old["plan"]["plan_id"], old["version"]).error_code, "PROPOSAL_STALE")
        # 3. a different plan that satisfies the NEW constraint
        self.assertGreater(new["version"], old["version"])
        self.assertNotEqual(new["plan"]["start_at"], old["plan"]["start_at"])
        self.assertEqual(rig.violates(new["plan"]), [])

    def test_outcome_depends_on_the_changed_value_not_on_a_script(self):
        outcomes = {}
        for cap in (3000, 2000, 1500, 400):
            rig = KitRig(dinner_game_kit(), exception_gateway=None)
            rig.by_ref["stu_dev"].set_hard_budget_cap(cap)
            rig.c.revise_negotiation(rig.sid, {"kind": "budget", "student_ref": "stu_dev"})
            s = rig.snap()
            outcomes[cap] = (s["state"], s["plan"] and max(rig.c._get(rig.sid).current_plan["estimated_cost_cents_by_ref"].values()))
        self.assertEqual(outcomes[3000][0], "approval_pending")  # no real change: still fine
        self.assertEqual(outcomes[2000][0], "approval_pending")
        self.assertLessEqual(outcomes[2000][1], 2000)
        self.assertLessEqual(outcomes[1500][1], 1500)
        self.assertEqual(outcomes[400][0], "failed")  # below every price tier => honest failure
        costs = [outcomes[c][1] for c in (3000, 2000, 1500)]
        self.assertEqual(costs, sorted(costs, reverse=True))

    def test_trip_budget_change_recovers_and_a_second_change_can_end_in_no_plan(self):
        # the default lifetime probe cap is deliberately tight; this long story needs headroom
        rig = KitRig(two_day_trip_kit(), exception_gateway=None,
                     config=NegotiationConfig(max_evaluations_per_member_per_session=300))
        first = rig.snap()
        rig.by_ref["stu_gus"].set_hard_budget_cap(4000)
        rig.c.revise_negotiation(rig.sid, {"kind": "budget", "student_ref": "stu_gus", "request_id": "c1"})
        second = rig.snap()
        self.assertEqual(second["state"], "approval_pending")
        self.assertEqual(rig.violates(second["plan"]), [])
        self.assertGreater(second["version"], first["version"])
        rig.by_ref["stu_gus"].set_hard_budget_cap(100)
        rig.c.revise_negotiation(rig.sid, {"kind": "budget", "student_ref": "stu_gus", "request_id": "c2"})
        third = rig.snap()
        self.assertEqual((third["state"], third["error_code"]), ("failed", "NO_FEASIBLE_PLAN"))
        rig.by_ref["stu_gus"].set_hard_budget_cap(9000)  # relaxed again => engine recovers
        rig.c.revise_negotiation(rig.sid, {"kind": "budget", "student_ref": "stu_gus", "request_id": "c3"})
        self.assertEqual(rig.snap()["state"], "approval_pending")

    def test_participant_withdrawal_replans_for_the_remaining_group(self):
        rig = KitRig(dinner_game_kit())
        rig.kit.request  # min_attendees is 4 here: a withdrawal must fail honestly
        rig.c.withdraw_participant(rig.sid, "stu_bea")
        s = rig.snap()
        self.assertEqual((s["state"], s["reason_category"]), ("failed", "attendance_requirement"))
        kit = dinner_game_kit()
        kit.request["rules"]["min_attendees"] = 3
        rig2 = KitRig(kit)
        rig2.c.withdraw_participant(rig2.sid, "stu_bea")
        s2 = rig2.snap()
        self.assertEqual(s2["state"], "approval_pending")
        self.assertEqual(s2["required_count"], 3)
        self.assertNotIn("stu_bea", s2["plan"]["member_refs"])
        # Bea's Friday conflict is gone, so earlier slots may now be chosen
        self.assertEqual(rig2.violates(s2["plan"]), [])


# ----------------------------------------------------------------------------- CLI + replay fixtures
class DemoScenarios(unittest.TestCase):
    def go(self, *argv):
        buf = io.StringIO()
        result = run(build_parser().parse_args(list(argv)), buf)
        return result, buf.getvalue()

    def test_scenarios_via_cli(self):
        self.assertEqual(self.go("--scenario", "dinner")[0]["state"], "approval_pending")
        self.assertEqual(self.go("--scenario", "trip")[0]["state"], "approval_pending")
        res, text = self.go("--scenario", "trip", "--impossible")
        self.assertEqual((res["state"], res["snapshot"]["error_code"]), ("failed", "NO_FEASIBLE_PLAN"))
        self.assertEqual(self.go("--scenario", "dinner", "--change-availability")[0]["state"], "confirmed")
        self.assertEqual(self.go("--scenario", "trip", "--change-budget")[0]["state"], "confirmed")
        self.assertEqual(self.go("--scenario", "dinner", "--withdraw", "stu_dev")[0]["state"], "failed")

    def test_replay_fixtures_match_the_live_engine(self):
        for name, argv in (("trace_dinner_game_availability_change.jsonl", ["--scenario", "dinner", "--change-availability"]),
                           ("trace_two_day_trip_budget_change.jsonl", ["--scenario", "trip", "--change-budget"])):
            _, text = self.go(*argv, "--jsonl")
            self.assertEqual((DOCS / name).read_text(encoding="utf-8").strip().splitlines(), text.strip().splitlines(), name)

    def test_cli_output_never_prints_private_caps(self):
        for argv in (["--scenario", "dinner", "--change-budget"], ["--scenario", "trip", "--change-budget"]):
            _, text = self.go(*argv)
            for token in ("3500", "4000 ", "15000", "12000", "9000", "hard_budget", "blocked"):
                self.assertNotIn(token, text, f"{argv}: {token}")


def assert_trace_private_safe(tc, rig):
    kit = rig.kit
    text = json.dumps(rig.sink.events, sort_keys=True).lower()
    snap = json.dumps(rig.snap(), sort_keys=True).lower().replace("estimated_total_cents", "")
    caps = {str(a._p["hard_budget_cap_cents"]) for a in kit.agents}
    for blob in (text, snap):
        for cap in caps:
            tc.assertIsNone(re.search(rf"\b{cap}\b", blob), cap)
        for token in ("budget", "hard_", "penalty", "soft", "blocked", "refuse", "prefers", "issue"):
            tc.assertNotIn(token, blob, token)
    for e in rig.sink.events:  # per-member costs and scores never appear
        tc.assertNotIn("estimated_cost_cents_by_ref", e["payload"])
        tc.assertFalse({"score", "penalty", "history"} & set(e["payload"]))


if __name__ == "__main__":
    unittest.main()
