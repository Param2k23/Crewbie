import json
import unittest
from pathlib import Path
from unittest.mock import patch

from integrations.cubbie.core import PulseError, parse_student_intent
from integrations.cubbie.handoff import MockPlanningGateway, request_handoff
from integrations.cubbie.planner import plan_request


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.context = dict(authorized=True, student_ref="synthetic_student", synthetic=True, campus="Tempe",
                            location="Tempe", availability_start="2026-10-26T12:00:00-07:00",
                            availability_end="2026-10-26T14:00:00-07:00", budget_cents=2000,
                            travel_tolerance_minutes=15, group_size=1, interests=["outdoors"])

    def test_short_window_standalone_offline(self):
        with patch("socket.socket", side_effect=AssertionError("Network forbidden")):
            result = plan_request("I have two free hours", self.context)
        self.assertEqual(result["brief"]["intent"], "plan_group_activity")
        self.assertEqual(result["details"]["requested_duration_minutes"], 120)
        self.assertIn("nearby", result["tentative_ideas"][0])
        self.assertFalse(result["booked"])
        self.assertEqual(result["backend"], "not_required")

    def test_multiday_window_and_duration(self):
        context = dict(self.context, availability_start="2026-10-30T10:00:00-07:00",
                       availability_end="2026-11-01T10:00:00-07:00")
        result = plan_request("Plan a two-day trip", context)
        self.assertEqual(result["details"]["requested_duration_minutes"], 2880)
        self.assertEqual(result["brief"]["availability_end"], context["availability_end"])
        self.assertTrue(any("overnight" in q for q in result["questions"]))

    def test_trip_missing_preferences_is_conversation(self):
        result = plan_request("Plan a two-day trip", dict(authorized=True, student_ref="demo"))
        self.assertIsNone(result["brief"])
        self.assertEqual(result["status"], "clarification_needed")
        self.assertTrue(any("dates/times" in q for q in result["questions"]))
        self.assertTrue(any("spending limit" in q for q in result["questions"]))

    def test_requested_duration_conflict(self):
        result = plan_request("Plan a two-day trip", self.context)
        self.assertTrue(any("exceeds" in q for q in result["questions"]))
        self.assertEqual(result["candidates"], [])

    def test_explicit_requests_and_legacy_intents(self):
        for message, expected in (("Plan dinner", "plan_group_activity"), ("Play badminton", "plan_group_activity"),
                                  ("Help organize a weekend trip", "plan_group_activity"),
                                  ("Find people to play badminton", "find_companion"),
                                  ("Find a crew", "find_companion"), ("Find people to join", "find_companion"),
                                  ("free pizza", "find_campus_food")):
            with self.subTest(message=message):
                self.assertEqual(parse_student_intent(message, self.context)["intent"], expected)

    def test_weekday_and_relative_date_conflicts(self):
        with self.assertRaises(PulseError):
            parse_student_intent("Plan dinner Friday", self.context)
        friday = dict(self.context, availability_start="2026-10-30T17:00:00-07:00", availability_end="2026-10-30T19:00:00-07:00")
        self.assertEqual(parse_student_intent("Plan dinner Friday", friday)["intent"], "plan_group_activity")
        self.assertIsNotNone(plan_request("I have two hours free tomorrow", self.context, now="2026-10-25T18:00:00Z")["brief"])

    def test_invalid_planning_preferences(self):
        for key, value in (("budget_cents", -1), ("budget_cents", True), ("travel_tolerance_minutes", -1),
                           ("group_size", 0), ("interests", "sport"), ("location", "")):
            with self.subTest(key=key), self.assertRaises(PulseError):
                plan_request("Plan dinner", dict(self.context, **{key: value}))

    def test_timezone_required(self):
        with self.assertRaises(PulseError):
            plan_request("Plan dinner", dict(self.context, availability_start="2026-10-26T12:00:00"))

    def test_budget_is_private_sidecar_not_shared_schema(self):
        result = plan_request("Plan dinner", self.context)
        self.assertEqual(result["details"]["budget_cents"], 2000)
        self.assertNotIn("budget_cents", result["brief"])
        self.assertNotIn("details", result["brief"])

    def test_candidate_uncertainty_and_no_results(self):
        root = Path(__file__).resolve().parents[2]
        events = json.loads((root / "docs/implementation/fixtures/opportunities.json").read_text(encoding="utf-8"))["opportunities"]
        result = plan_request("Find events", self.context, events, now="2026-10-26T16:00:00Z")
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["candidates"][0]["status"], "demo_fixture")
        self.assertIn("require verification", result["candidates"][0]["caveat"])
        result = plan_request("Plan dinner", self.context, events, now="2026-10-26T16:00:00Z")
        self.assertEqual(result["candidates"], [])
        self.assertIn("dinner", result["tentative_ideas"][0])

    def handoff_context(self, brief, **changes):
        return dict(self.context, activity_scope="demo_activity", consent_scope="demo_activity",
                    consent_brief_id=brief["brief_id"], **changes)

    def test_matching_rejection_never_calls_gateway(self):
        brief = parse_student_intent("Find a crew", self.context)
        mock = MockPlanningGateway()
        for changes in ({}, {"sharing_opt_in": True}, {"sharing_opt_in": True, "matching_opt_in": False}):
            with self.subTest(changes=changes), self.assertRaises(PulseError):
                request_handoff(brief, self.handoff_context(brief, **changes), "r1", gateway=mock)
        self.assertEqual(mock.requests, {})

    def test_matching_scope_and_revocation(self):
        brief = parse_student_intent("Find a crew", self.context)
        context = self.handoff_context(brief, sharing_opt_in=True, matching_opt_in=True)
        mock = MockPlanningGateway()
        self.assertFalse(request_handoff(brief, context, "r1", gateway=mock)["matched"])
        for change in ({"consent_scope": "other"}, {"consent_brief_id": "other"}, {"sharing_opt_in": False}, {"student_ref": "other"}):
            with self.subTest(change=change), self.assertRaises(PulseError):
                request_handoff(brief, dict(context, **change), "r1", gateway=mock)

    def test_mock_idempotency_and_private_redaction(self):
        brief = parse_student_intent("Find a crew vegetarian", self.context)
        brief["budget_cents"] = 1234
        context = self.handoff_context(brief, sharing_opt_in=True, matching_opt_in=True)
        mock = MockPlanningGateway()
        first = request_handoff(brief, context, "r1", gateway=mock)
        self.assertEqual(first, request_handoff(brief, context, "r1", gateway=mock))
        serialized = json.dumps(list(mock.requests.values()))
        self.assertNotIn("budget_cents", serialized)
        self.assertNotIn("vegetarian", serialized)
        self.assertEqual(len(mock.requests), 1)
        with self.assertRaises(PulseError):
            request_handoff(dict(brief, opportunity_id="changed"), context, "r1", gateway=mock)

    def test_coordination_requires_separate_opt_in(self):
        brief = parse_student_intent("Plan dinner", self.context)
        context = self.handoff_context(brief, sharing_opt_in=True, matching_opt_in=True)
        with self.assertRaises(PulseError):
            request_handoff(brief, context, "r1", action="coordination", gateway=MockPlanningGateway())
        result = request_handoff(brief, dict(context, coordination_opt_in=True), "r1", action="coordination", gateway=MockPlanningGateway())
        self.assertEqual(result["status"], "mock_received")
        self.assertFalse(result["confirmed"])

    def test_missing_backend_keeps_plan_available(self):
        brief = parse_student_intent("Find a crew", self.context)
        with self.assertRaises(PulseError) as error:
            request_handoff(brief, self.handoff_context(brief, sharing_opt_in=True, matching_opt_in=True), "r1")
        self.assertEqual(error.exception.code, "PROVIDER_UNAVAILABLE")
        self.assertTrue(plan_request("I have two free hours", self.context)["tentative_ideas"])

    def test_no_implicit_reminder(self):
        result = plan_request("Plan dinner", self.context)
        self.assertFalse(result["scheduled"])


if __name__ == "__main__":
    unittest.main()
