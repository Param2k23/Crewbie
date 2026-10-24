import json
import unittest
from copy import deepcopy
from pathlib import Path

from integrations.cubbie import parse_student_intent, preview_cubbie_alert, select_opportunities
from integrations.cubbie.core import PulseError, parse_preferences
from integrations.cubbie.adapters import FixtureOpportunityCatalog, MockCubbieProvider, UnavailableCubbieProvider

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "docs/implementation/fixtures"
NOW = "2026-10-26T16:00:00Z"


class CampusPulseTests(unittest.TestCase):
    def setUp(self):
        self.events = json.loads((FIXTURES / "opportunities.json").read_text(encoding="utf-8"))["opportunities"]
        self.context = dict(student_ref="stu_alex", authorized=True, synthetic=True, campus="Tempe",
                            availability_start="2026-10-26T12:00:00-07:00",
                            availability_end="2026-10-26T13:30:00-07:00")
        self.brief = parse_student_intent("free pizza vegetarian", self.context)

    def selected(self, events=None, **kwargs):
        return select_opportunities(self.brief, self.events if events is None else events, now=NOW, **kwargs)

    def preview(self, events=None):
        return preview_cubbie_alert("stu_alex", self.events if events is None else events, brief=self.brief, now=NOW)

    def test_fixture_scenario_and_contract_fields(self):
        expected = json.loads((FIXTURES / "scenarios.json").read_text(encoding="utf-8"))["scenarios"][0]["student_brief"]
        self.assertEqual(set(expected), set(self.brief))
        self.assertEqual(self.brief["intent"], "find_campus_food")
        self.assertIn("vegetarian_options", self.brief["requirements_to_verify"])
        self.assertEqual(self.preview()["opportunity_ids"], [expected["opportunity_id"]])

    def test_uncertainty_and_source(self):
        preview = self.preview()
        for text in ("Diet not verified", "not guaranteed", "Public access unknown", "RSVP requirements unknown",
                     "DEMO FIXTURE", "https://example.org/crewbie-demo/pizza", "Checked:", "-07:00"):
            self.assertIn(text, preview["text"])
        self.assertFalse(preview["sent"])

    def test_missing_source_and_invalid_urls(self):
        for url in (None, "", "javascript:alert(1)", "https://user:pass@example.com/e"):
            with self.subTest(url=url):
                event = dict(self.events[0], source_url=url)
                self.assertEqual(self.selected([event]), [])
        self.assertEqual(self.selected([dict(self.events[0], synthetic=False)]), [])

    def test_missing_data_and_bad_enums(self):
        for field in ("start_at", "end_at", "checked_at", "title", "campus", "synthetic", "dietary_suitability", "food_status", "access_status"):
            with self.subTest(field=field):
                event = deepcopy(self.events[0])
                del event[field]
                self.assertEqual(self.selected([event]), [])

    def test_campus_time_and_food_filters(self):
        self.assertEqual(len(self.selected()), 1)
        self.assertEqual(self.selected([dict(self.events[0], campus="Polytechnic")]), [])
        for food in ("none", "unknown"):
            self.assertEqual(self.selected([dict(self.events[0], food_status=food)]), [])
        self.assertEqual(len(self.selected([dict(self.events[0], food_status="unknown")], food_only=False)), 1)

    def test_expiry_freshness_and_invalid_time(self):
        for changes in ({"end_at": "2026-10-25T13:00:00-07:00"},
                        {"checked_at": "2026-10-01T00:00:00Z"},
                        {"checked_at": "2026-10-27T00:00:00Z"},
                        {"start_at": "2026-10-26T12:00:00"},
                        {"end_at": "bad"}):
            with self.subTest(changes=changes):
                self.assertEqual(self.selected([dict(self.events[0], **changes)]), [])

    def test_half_open_and_overlap_threshold(self):
        self.assertEqual(self.selected([dict(self.events[0], start_at=self.brief["availability_end"], end_at="2026-10-26T14:00:00-07:00")]), [])
        self.assertEqual(self.selected([dict(self.events[0], start_at="2026-10-26T13:15:00-07:00", end_at="2026-10-26T14:00:00-07:00")]), [])

    def test_duplicates_and_conflicting_claims(self):
        self.assertEqual(len(self.selected([self.events[0], self.events[0]])), 1)
        self.assertEqual(self.selected([self.events[0], dict(self.events[0], title="Different claim")]), [])

    def test_ranking_by_evidence_and_freshness(self):
        newer = dict(self.events[0], opportunity_id="new", checked_at="2026-10-26T15:00:00Z")
        confirmed = dict(self.events[0], opportunity_id="confirmed", food_status="confirmed_by_organizer")
        self.assertEqual([e["opportunity_id"] for e in self.selected([self.events[0], newer, confirmed])],
                         ["confirmed", "new", "opp_demo_pizza"])

    def test_diet_unsuitable_and_restricted_unknown_location(self):
        self.assertEqual(self.selected([dict(self.events[0], dietary_suitability="known_unsuitable")]), [])
        text = self.preview([dict(self.events[0], access_status="restricted", location_label=None, rsvp_required=True)])["text"]
        for phrase in ("Restricted access", "Unknown; confirm", "RSVP required"):
            self.assertIn(phrase, text)

    def test_consent_request_only(self):
        brief = parse_student_intent("Find a friend", self.context)
        self.assertTrue(brief["wants_companion"])
        self.assertIn("matching_consent", brief["requirements_to_verify"])
        with self.assertRaises(PulseError):
            parse_student_intent("pizza", dict(self.context, authorized=False))
        with self.assertRaises(PulseError):
            preview_cubbie_alert("other", self.events, brief=self.brief, now=NOW)

    def test_ambiguous_and_conflicting_time(self):
        for context, message in ((dict(self.context, availability_start=None), "lunch"),
                                 (self.context, "pizza at 1pm"),
                                 (dict(self.context, now=NOW), "pizza tomorrow"),
                                 (dict(self.context, availability_end=self.context["availability_start"]), "pizza")):
            with self.subTest(message=message), self.assertRaises(PulseError):
                parse_student_intent(message, context)
        self.assertEqual(parse_student_intent("pizza today", dict(self.context, now=NOW))["campus"], "Tempe")

    def test_preferences_and_unsupported_intent(self):
        self.assertEqual(parse_preferences("Tempe vegan weekly", self.context),
                         dict(campus="Tempe", dietary_preferences=["vegan"], cadence="weekly"))
        self.assertEqual(parse_preferences("stop alerts", dict(self.context, cadence="daily"))["cadence"], "off")
        for message in ("do my homework", "pizza Tempe Polytechnic"):
            with self.assertRaises(PulseError):
                parse_student_intent(message, self.context)

    def test_catalog_adapter(self):
        catalog = FixtureOpportunityCatalog(FIXTURES / "opportunities.json")
        results = catalog.list_opportunities("Tempe", self.brief["availability_start"], self.brief["availability_end"], True)
        self.assertEqual(len(results), 1)
        results[0]["title"] = "mutated"
        self.assertNotEqual(catalog.get_opportunity("opp_demo_pizza")["title"], "mutated")
        self.assertIsNone(catalog.get_opportunity("missing"))

    def test_provider_fails_truthfully(self):
        with self.assertRaises(PulseError) as error:
            UnavailableCubbieProvider().register_alert()
        self.assertEqual(error.exception.code, "PROVIDER_UNAVAILABLE")

    def register(self, provider, consent=None, **kwargs):
        return provider.register_alert("req", "stu_alex", self.preview(), NOW, kwargs.get("cadence", "daily"),
                                       consent if consent is not None else dict(self.context, alerts_opt_in=True))

    def test_mock_idempotency_and_cancel(self):
        provider = MockCubbieProvider()
        self.assertEqual(self.register(provider), self.register(provider))
        with self.assertRaises(PulseError):
            self.register(provider, cadence="weekly")
        provider.cancel("req", "stu_alex")
        self.assertEqual(provider.dispatch_due(NOW, dict(self.context, alerts_opt_in=True), self.events), [])

    def test_mock_timing_dispatch_once_and_revocation(self):
        provider = MockCubbieProvider()
        self.register(provider)
        consent = dict(self.context, alerts_opt_in=True)
        self.assertEqual(provider.dispatch_due("2026-10-26T15:59:59Z", consent, self.events), [])
        due = provider.dispatch_due(NOW, consent, self.events)
        self.assertEqual(len(due), 1)
        self.assertFalse(due[0]["sent"])
        self.assertEqual(provider.dispatch_due(NOW, consent, self.events), [])
        provider = MockCubbieProvider()
        self.register(provider)
        self.assertEqual(provider.dispatch_due(NOW, dict(consent, alerts_opt_in=False), self.events), [])
        self.assertEqual(provider.dispatch_due(NOW, consent, self.events), [])

    def test_mock_permissions_and_expired_event(self):
        provider = MockCubbieProvider()
        with self.assertRaises(PulseError):
            self.register(provider, self.context)
        self.register(provider)
        self.assertEqual(provider.dispatch_due("2026-10-27T00:00:00Z", dict(self.context, alerts_opt_in=True), self.events), [])


if __name__ == "__main__":
    unittest.main()
