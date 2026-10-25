import unittest
from unittest.mock import patch

from integrations.cubbie.core import PulseError, parse_student_intent
from integrations.cubbie.unlocks import assess_window, checkin_draft, personality, solo_fallback, unlock_card


NOW = "2026-10-26T16:00:00Z"


class UnlockTests(unittest.TestCase):
    def setUp(self):
        self.context = dict(authorized=True, student_ref="demo", synthetic=True, campus="Tempe",
                            availability_start="2026-10-26T12:00:00-07:00",
                            availability_end="2026-10-26T14:00:00-07:00", window_confirmed=True,
                            calendar_authorized=True, calendar_status="available", calendar_busy=[],
                            canvas_authorized=True, canvas_status="available", canvas_obligations=[])
        self.item = dict(title="Fictional student equipment loan", category="benefit", synthetic=True,
                         source_url="https://example.org/demo-benefit", checked_at="2026-10-26T15:00:00Z",
                         eligibility="eligible", restrictions=["Student ID required", "Reservation not checked"],
                         cost_cents=0, cost_verified=True, duration_minutes=45, travel_minutes_each_way=10,
                         next_step="Check eligibility and choose a solo time; no reservation made.")

    def test_empty_calendar_never_means_available(self):
        self.assertEqual(assess_window(dict(self.context, window_confirmed=False))["status"], "needs_confirmation")

    def test_calendar_conflict_is_protected(self):
        c = dict(self.context, calendar_busy=[dict(start_at="2026-10-26T12:30:00-07:00", end_at="2026-10-26T13:00:00-07:00", title="SECRET")])
        result = assess_window(c)
        self.assertEqual(result["status"], "conflict")
        self.assertNotIn("SECRET", str(result))
        with self.assertRaises(PulseError):
            unlock_card(self.item, c, now=NOW)

    def test_rest_work_and_support_blocks_never_waived(self):
        for reason in ("rest", "caregiving", "work", "support appointment"):
            with self.subTest(reason=reason):
                block = dict(start_at=self.context["availability_start"], end_at=self.context["availability_end"], reason=reason)
                result = assess_window(dict(self.context, protected_windows=[block]))
                self.assertEqual(result["status"], "conflict")
                self.assertNotIn(reason, str(result))

    def test_canvas_study_buffer_conflict(self):
        obligation = dict(due_at="2026-10-26T15:00:00-07:00", reserve_minutes=120)
        self.assertEqual(assess_window(dict(self.context, canvas_obligations=[obligation]))["status"], "conflict")

    def test_canvas_unknown_preparation_requires_question(self):
        self.assertEqual(assess_window(dict(self.context, canvas_obligations=[dict(due_at="2026-10-27T09:00:00-07:00")]))["status"], "needs_confirmation")

    def test_canvas_completed_and_explicit_zero_buffer(self):
        c = dict(self.context, canvas_obligations=[dict(due_at="2026-10-26T13:00:00-07:00", completed=True)])
        self.assertEqual(assess_window(c)["status"], "student_confirmed")
        c["canvas_obligations"] = [dict(due_at="2026-10-26T13:00:00-07:00", reserve_minutes=0)]
        self.assertEqual(assess_window(c)["status"], "conflict")

    def test_unauthorized_accounts_not_consumed(self):
        c = dict(self.context, calendar_authorized=False, calendar_busy=[{"invalid": "private"}], canvas_authorized=False,
                 canvas_obligations=[{"invalid": "private"}])
        self.assertEqual(assess_window(c)["account_checks"], "partial")
        self.assertEqual(assess_window(dict(c, window_confirmed=False))["status"], "needs_confirmation")

    def test_disconnected_manual_availability(self):
        self.assertEqual(assess_window(dict(self.context, calendar_status="disconnected", canvas_status="unavailable"))["status"], "student_confirmed")

    def test_varying_windows_and_travel(self):
        short = dict(self.context, availability_end="2026-10-26T12:30:00-07:00")
        with self.assertRaises(PulseError):
            unlock_card(self.item, short, now=NOW)
        long = dict(self.context, availability_end="2026-10-28T14:00:00-07:00")
        self.assertEqual(unlock_card(self.item, long, now=NOW)["status"], "candidate")
        no_travel = dict(self.item)
        del no_travel["travel_minutes_each_way"]
        self.assertEqual(unlock_card(no_travel, self.context, now=NOW)["status"], "tentative")

    def test_half_open_commitment_boundary(self):
        c = dict(self.context, protected_windows=[dict(start_at="2026-10-26T11:00:00-07:00", end_at=self.context["availability_start"])])
        self.assertEqual(assess_window(c)["status"], "student_confirmed")

    def test_roast_opt_in_and_revocation(self):
        c = dict(self.context, personality="Roast Me")
        self.assertEqual(personality(c), "Chill")
        self.assertEqual(personality(dict(c, roast_opt_in=True)), "Roast Me")
        self.assertEqual(personality(dict(c, roast_opt_in=False)), "Chill")
        with self.assertRaises(PulseError):
            personality(dict(c, personality="Cruel"))

    def test_style_does_not_change_facts(self):
        cards = [unlock_card(self.item, dict(self.context, personality=p, roast_opt_in=True), now=NOW) for p in ("Chill", "Playful", "Roast Me")]
        self.assertEqual(len({c["text"].split("\n", 1)[1] for c in cards}), 1)
        self.assertIn("hide-and-seek", cards[2]["text"])

    def test_card_has_required_fields_and_restrictions(self):
        text = unlock_card(self.item, self.context, now=NOW)["text"]
        for marker in ("FICTIONAL DEMO", "Why:", "Eligibility:", "Cost:", "Restrictions:", "Next:", "Checked:", self.item["source_url"], "Student ID required"):
            self.assertIn(marker, text)

    def test_ineligible_or_expired_benefit_excluded(self):
        for changes in ({"eligibility": "ineligible"}, {"expires_at": NOW}):
            with self.subTest(changes=changes), self.assertRaises(PulseError):
                unlock_card(dict(self.item, **changes), self.context, now=NOW)

    def test_unknown_eligibility_price_restrictions(self):
        result = unlock_card(dict(self.item, eligibility="unknown", cost_verified=False, restrictions=[]), self.context, now=NOW)
        self.assertEqual(result["status"], "tentative")
        for phrase in ("Eligibility not verified", "Cost not verified", "Restrictions: Not verified"):
            self.assertIn(phrase, result["text"])

    def test_stale_future_missing_and_unsafe_sources(self):
        for changes in ({"checked_at": "2026-10-24T16:00:00Z"}, {"checked_at": "2026-10-27T16:00:00Z"},
                        {"source_url": ""}, {"source_url": "javascript:alert(1)"}, {"synthetic": False}):
            with self.subTest(changes=changes), self.assertRaises(PulseError):
                unlock_card(dict(self.item, **changes), self.context, now=NOW)

    def test_known_price_respects_budget(self):
        with self.assertRaises(PulseError):
            unlock_card(dict(self.item, cost_cents=3000), dict(self.context, budget_cents=1000), now=NOW)

    def test_event_clock_fit_not_just_duration(self):
        with self.assertRaises(PulseError):
            unlock_card(dict(self.item, start_at="2026-10-26T18:00:00-07:00", end_at="2026-10-26T19:00:00-07:00"), self.context, now=NOW)

    def test_proactive_requires_exact_opt_in(self):
        settings = dict(cadence="daily", local_time="09:00", timezone="America/Phoenix", notification="text", empty="brief")
        with self.assertRaises(PulseError):
            checkin_draft(self.context, **settings)
        c = dict(self.context, alerts_opt_in=True, approved_checkin=settings)
        result = checkin_draft(c, **settings)
        self.assertFalse(result["scheduled"])
        self.assertIn("Canvas", result["instructions"])
        with self.assertRaises(PulseError):
            checkin_draft(c, **dict(settings, cadence="weekly"))
        with self.assertRaises(PulseError):
            checkin_draft(dict(c, alerts_opt_in=False), **settings)

    def test_notification_preferences(self):
        settings = dict(cadence="weekdays", local_time="18:30", timezone="America/Phoenix", notification="silent", empty="silent")
        result = checkin_draft(dict(self.context, alerts_opt_in=True, approved_checkin=settings), **settings)
        self.assertEqual(result["settings"], settings)
        self.assertFalse(result["scheduled"])

    def test_weekly_requires_confirmed_day(self):
        settings = dict(cadence="weekly", local_time="09:00", timezone="America/Phoenix", notification="text", empty="brief")
        c = dict(self.context, alerts_opt_in=True, approved_checkin=dict(settings, weekday=2))
        with self.assertRaises(PulseError):
            checkin_draft(c, **settings)
        self.assertEqual(checkin_draft(c, **dict(settings, weekday=2))["settings"]["weekday"], 2)

    def test_invalid_time_and_timezone_rejected(self):
        for clock, zone in (("25:00", "UTC"), ("09:00", "Not/AZone")):
            with self.subTest(clock=clock, zone=zone), self.assertRaises(PulseError):
                checkin_draft(dict(self.context, alerts_opt_in=True), cadence="daily", local_time=clock, timezone=zone)

    def test_solo_fallback_without_backend_or_network(self):
        with patch("socket.socket", side_effect=AssertionError("No network")):
            result = solo_fallback()
        self.assertEqual(result["mode"], "solo_available")
        self.assertFalse(result["sent"])
        self.assertFalse(result["scheduled"])
        self.assertIn("invitation_draft", result)

    def test_unlocks_and_start_crew_preserve_canonical_intents(self):
        self.assertEqual(parse_student_intent("Show student benefits", self.context)["intent"], "plan_group_activity")
        brief = parse_student_intent("Start a crew", self.context)
        self.assertEqual(brief["intent"], "find_companion")
        self.assertIn("matching_consent", brief["requirements_to_verify"])


if __name__ == "__main__":
    unittest.main()
