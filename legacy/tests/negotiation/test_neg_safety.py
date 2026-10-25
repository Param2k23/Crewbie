"""Event integrity, privacy, provider failures, determinism and the runnable demo."""
import argparse
import io
import json
import time
import unittest
from pathlib import Path

from neg_helpers import PRIVATE_TOKENS, FuncEvaluator, Rig, evaluation, plan_at

from services.negotiation import NegotiationConfig, SessionState
from services.negotiation.demo import build_parser, run
from services.negotiation.events import PAYLOAD_KEYS, build_event
from services.negotiation.models import ConsentRequired

ALLOWED_TYPES = {
    "opportunity_discovered", "match_requested", "match_suggested", "consent_requested", "consent_granted",
    "negotiation_started", "candidate_proposed", "proposal_rejected", "counteroffer_proposed", "fairness_evaluated",
    "proposal_ready", "approval_requested", "member_response_received", "proposal_confirmed", "proposal_revised",
    "negotiation_failed", "session_completed",
}
TRACE = Path(__file__).resolve().parents[2] / "docs" / "negotiation" / "trace_flagstaff_budget_change.jsonl"


def full_story(rig):
    """Negotiate, partially approve, lower a cap, recover, confirm."""
    sid = rig.start()
    rig.accept_all(sid)
    rig.by_ref["stu_alex"].set_hard_budget_cap(4000)
    rig.coordinator.revise_negotiation(sid, {"kind": "budget", "student_ref": "stu_alex"})
    rig.open(sid)
    rig.accept_all(sid)
    rig.coordinator.confirm_if_approved(sid)
    return sid


class EventStream(unittest.TestCase):
    def setUp(self):
        self.rig = Rig()
        self.sid = full_story(self.rig)

    def test_only_whitelisted_public_types_and_contract_envelope(self):
        for e in self.rig.sink.events:
            self.assertIn(e["type"], ALLOWED_TYPES)
            self.assertIn(e["type"], PAYLOAD_KEYS)
            self.assertEqual(e["visibility"], "group_safe")
            self.assertIs(e["synthetic"], True)
            self.assertEqual(e["session_id"], self.sid)
            self.assertEqual(set(e), {"event_id", "session_id", "timestamp", "type", "actor_ref", "visibility", "payload", "synthetic"})
            self.assertTrue(e["timestamp"].endswith("Z"))
            self.assertLessEqual(set(e["payload"]), PAYLOAD_KEYS[e["type"]])

    def test_ids_are_unique_ordered_and_timestamps_monotonic(self):
        ids = [e["event_id"] for e in self.rig.sink.events]
        self.assertEqual(ids, [f"ev_{i:04d}" for i in range(1, len(ids) + 1)])
        stamps = [e["timestamp"] for e in self.rig.sink.events]
        self.assertEqual(stamps, sorted(stamps))

    def test_no_private_values_or_reasons_anywhere_in_the_trace(self):
        text = self.rig.trace_text()
        for token in PRIVATE_TOKENS:
            self.assertNotIn(token, text, token)

    def test_snapshot_hides_per_member_costs_until_everyone_consents(self):
        snap = self.rig.snap(self.sid)
        text = json.dumps(snap).lower()
        self.assertNotIn("estimated_cost_cents_by_ref", text)
        for token in PRIVATE_TOKENS:
            self.assertNotIn(token, text.replace("estimated_total_cents", ""), token)
        self.assertIn("estimated_total_cents", snap["plan"])
        members = snap["plan"]["member_refs"]
        for m in members[:-1]:
            self.rig.coordinator.authorize_cost_disclosure(self.sid, m)
        self.assertNotIn("estimated_cost_cents_by_ref", self.rig.snap(self.sid)["plan"])
        self.rig.coordinator.authorize_cost_disclosure(self.sid, members[-1])
        self.assertIn("estimated_cost_cents_by_ref", self.rig.snap(self.sid)["plan"])

    def test_cost_disclosure_resets_with_a_new_version(self):
        for m in self.rig.snap(self.sid)["plan"]["member_refs"]:
            self.rig.coordinator.authorize_cost_disclosure(self.sid, m)
        self.rig.coordinator.revise_negotiation(self.sid, {"kind": "itinerary"})
        self.assertNotIn("estimated_cost_cents_by_ref", self.rig.snap(self.sid)["plan"])

    def test_builder_rejects_unknown_types_keys_and_unsafe_values(self):
        base = dict(session_id="s", seq=1, timestamp="2026-10-24T18:00:00Z")
        with self.assertRaises(ValueError):
            build_event(**base, type_="budget_leaked", payload={})
        with self.assertRaises(ValueError):
            build_event(**base, type_="proposal_rejected", payload={"plan_id": "p", "version": 1, "hard_budget_cap_cents": 6000})
        with self.assertRaises(ValueError):
            build_event(**base, type_="proposal_rejected", payload={"plan_id": "p", "version": 1, "reason_category": "cap is $60 <b>"})
        with self.assertRaises(ValueError):
            build_event(**base, type_="proposal_rejected", payload={"plan_id": ["p"], "version": 1})

    def test_broken_sink_does_not_corrupt_negotiation(self):
        class Bad:
            def emit(self, e):
                raise IOError("socket closed")

        rig = Rig()
        rig.coordinator.sink = Bad()
        sid = rig.start()
        self.assertEqual(rig.snap(sid)["state"], "approval_pending")
        self.assertGreater(rig.coordinator.sink_errors, 0)

    def test_identical_inputs_produce_identical_traces(self):
        a, b = Rig(), Rig()
        full_story(a)
        full_story(b)
        self.assertEqual(a.sink.events, b.sink.events)


class ProviderFailures(unittest.TestCase):
    def test_evaluator_exception_is_provider_unavailable_not_a_negative_verdict(self):
        def boom(ref, p):
            raise RuntimeError("A3 down")

        rig = Rig(evaluator=FuncEvaluator(boom))
        sid = rig.start()
        snap = rig.snap(sid)
        self.assertEqual((snap["state"], snap["error_code"]), ("failed", "PROVIDER_UNAVAILABLE"))
        self.assertNotIn("proposal_ready", rig.types())

    def test_evaluator_timeout_fails_closed(self):
        def slow(ref, p):
            time.sleep(0.4)
            return evaluation(p, ref)

        rig = Rig(evaluator=FuncEvaluator(slow), config=NegotiationConfig(evaluator_timeout_s=0.05))
        sid = rig.start()
        self.assertEqual(rig.snap(sid)["error_code"], "PROVIDER_UNAVAILABLE")

    def test_missing_consent_is_surfaced_not_bypassed(self):
        def deny(ref, p):
            raise ConsentRequired(ref)

        rig = Rig(evaluator=FuncEvaluator(deny))
        sid = rig.start()
        self.assertEqual(rig.snap(sid)["error_code"], "CONSENT_REQUIRED")

    def test_garbage_verdicts_never_become_a_plan(self):
        rig = Rig(evaluator=FuncEvaluator(lambda ref, p: {"feasible": True}), exception_gateway=False)
        sid = rig.start()
        self.assertEqual(rig.snap(sid)["state"], "failed")

    def test_per_member_probe_cap_stops_the_search(self):
        rig = Rig(config=NegotiationConfig(max_evaluations_per_member_per_session=3), exception_gateway=False)
        sid = rig.start()
        for agent in rig.by_ref.values():
            self.assertLessEqual(len(agent.evaluations) + agent.counteroffer_requests, 3)
        self.assertEqual(rig.snap(sid)["reason_category"], "search_bounds_reached")

    def test_wall_clock_budget_with_a_verified_plan_still_publishes_it(self):
        def verdict(ref, p):
            rig.clock.advance(100)
            return evaluation(p, ref)

        rig = Rig(evaluator=FuncEvaluator(verdict), config=NegotiationConfig(session_timeout_s=10))
        sid = rig.start(seed_plans=[plan_at("2026-11-01", 10), plan_at("2026-11-02", 10)])
        s = rig.coordinator._get(sid)
        self.assertEqual(rig.snap(sid)["state"], "approval_pending")
        self.assertEqual(len(s.records), 1)  # second candidate never started

    def test_wall_clock_budget_without_a_plan_is_bounded_failure(self):
        def verdict(ref, p):
            rig.clock.advance(100)
            return evaluation(p, ref, feasible=False, hints=["prefer_lower_cost"])

        rig = Rig(evaluator=FuncEvaluator(verdict), config=NegotiationConfig(session_timeout_s=10), exception_gateway=False)
        sid = rig.start(seed_plans=[plan_at("2026-11-01", 10, cost=7000)])
        snap = rig.snap(sid)
        self.assertEqual((snap["error_code"], snap["reason_category"]), ("NO_FEASIBLE_PLAN", "search_bounds_reached"))


class Demo(unittest.TestCase):
    def go(self, *argv):
        buf = io.StringIO()
        result = run(build_parser().parse_args(list(argv)), buf)
        return result, buf.getvalue()

    def test_default_run_proposes_and_leaves_maybe_pending(self):
        result, text = self.go()
        self.assertEqual(result["state"], "approval_pending")
        self.assertIn("incomplete (2/4)", text)
        self.assertNotIn("proposal_confirmed", [e["type"] for e in result["events"]])

    def test_budget_change_recovers_with_new_version(self):
        result, text = self.go("--change-budget")
        self.assertEqual(result["state"], "confirmed")
        self.assertIn("proposal_revised", [e["type"] for e in result["events"]])
        self.assertIn("Old approvals invalidated", text)

    def test_budget_below_floor_goes_private_then_fails_when_declined(self):
        result, text = self.go("--change-budget", "3000", "--exception", "no")
        self.assertEqual((result["state"], result["snapshot"]["error_code"]), ("failed", "NO_FEASIBLE_PLAN"))
        self.assertIn("ONE student only", text)

    def test_budget_below_floor_recovers_when_exception_is_approved(self):
        result, _ = self.go("--change-budget", "3000", "--exception", "yes")
        self.assertEqual(result["state"], "confirmed")

    def test_availability_and_withdrawal_variants(self):
        self.assertEqual(self.go("--change-availability")[0]["state"], "confirmed")
        result, _ = self.go("--withdraw", "stu_taylor")
        self.assertEqual(result["snapshot"]["plan"]["member_refs"].__len__(), 3)

    def test_demo_output_never_prints_private_values(self):
        for argv in ([], ["--change-budget"], ["--change-budget", "3000"], ["--withdraw", "stu_maya"]):
            _, text = self.go(*argv)
            low = text.lower()
            for token in ("6000", "7500", "9000", "10000", "hard_", "penalty", "blocked", "saturday"):
                self.assertNotIn(token, low, f"{argv}: {token}")

    def test_jsonl_mode_emits_one_valid_event_per_line(self):
        _, text = self.go("--change-budget", "--jsonl")
        events = [json.loads(line) for line in text.strip().splitlines()]
        self.assertTrue(events)
        self.assertTrue(all(e["type"] in ALLOWED_TYPES and e["visibility"] == "group_safe" for e in events))

    def test_published_replay_fixture_matches_the_live_engine(self):
        """docs/negotiation/trace_flagstaff_budget_change.jsonl is regenerated from the engine, never hand-written."""
        _, text = self.go("--change-budget", "--jsonl")
        self.assertEqual(TRACE.read_text(encoding="utf-8").strip().splitlines(), text.strip().splitlines())


if __name__ == "__main__":
    unittest.main()
