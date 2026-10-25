import copy
import unittest

from services.opportunities import (ActivityFixtureProvider, DiscoveryService, FixtureProvider,
                                   MockProvider, OpportunityCatalog, OpportunityError, normalize)
from services.opportunities.demo import scenario
from services.opportunities.models import timestamp


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.rows = ActivityFixtureProvider().load()
        self.start = "2026-10-26T12:00:00-07:00"
        self.end = "2026-10-26T14:00:00-07:00"
        self.now = lambda: timestamp("2026-10-24T19:00:00Z")

    def service(self, rows=None):
        return DiscoveryService(OpportunityCatalog(MockProvider(self.rows if rows is None else rows), now=self.now))

    def results(self, **kw):
        return self.service().recommend(self.start, self.end, **kw)["recommendations"]

    def real_venue(self):
        row = copy.deepcopy(self.rows[0])
        row.update(synthetic=False, source_url="https://asu.edu/verified-test-venue")
        row["activity"].update(source_verified=True, source_claims={"description": "Coffee conversation venue",
                                      "opening_windows": "Monday noon to two", "price": "Price $5"}, price_cents=500)
        return row

    def test_scenario_a_two_hours_nearby(self):
        result = scenario("A")
        self.assertEqual(result["query_mode"], "time_first")
        self.assertEqual({r["candidate_id"] for r in result["recommendations"]}, {"demo_games", "demo_coffee"})
        self.assertTrue(all(r["record_type"] == "synthetic_fixture" for r in result["recommendations"]))
        self.assertTrue(all(r["opportunity"]["distance_m"] <= 500 for r in result["recommendations"]))

    def test_scenario_b_two_day_fixture_and_idea(self):
        result = scenario("B")
        self.assertEqual(result["window_horizon"], "weekend")
        self.assertEqual(result["query_mode"], "intent_first")
        self.assertEqual({r["record_type"] for r in result["recommendations"]}, {"synthetic_fixture", "planning_idea"})
        idea = next(r for r in result["recommendations"] if r["record_type"] == "planning_idea")
        self.assertIsNone(idea["source_url"])
        self.assertIsNone(idea["fit"]["proposed_slot"])
        self.assertFalse(idea["fit"]["availability_confirmed"])

    def test_short_window_rejects_trip(self):
        self.assertEqual(self.results(intent="trip"), [])

    def test_evening_intent(self):
        results = self.service().recommend("2026-10-26T18:00:00-07:00", "2026-10-26T21:00:00-07:00", intent="bowling")["recommendations"]
        self.assertEqual(results[0]["candidate_id"], "demo_bowling")
        self.assertEqual(results[0]["horizon"], "evening")

    def test_half_day_and_long_break(self):
        result = self.service().recommend("2026-10-31T08:00:00-07:00", "2026-10-31T16:00:00-07:00", intent="hike")
        self.assertEqual(result["recommendations"][0]["candidate_id"], "demo_hike")
        result = self.service([]).recommend("2026-10-31T08:00:00-07:00", "2026-11-07T08:00:00-07:00", intent="trip")
        self.assertEqual(result["window_horizon"], "long_break")
        self.assertEqual(result["recommendations"][0]["candidate_id"], "idea_break")

    def test_timezone_equivalence(self):
        a = self.service().recommend(self.start, self.end)
        b = self.service().recommend("2026-10-26T19:00:00Z", "2026-10-26T21:00:00Z")
        self.assertEqual(a, b)

    def test_dst_elapsed_time(self):
        result = self.service([]).recommend("2026-11-01T01:00:00-07:00", "2026-11-01T02:00:00-08:00")
        self.assertEqual(result["window_horizon"], "short_break")
        self.assertIn("idea_coffee", [r["candidate_id"] for r in result["recommendations"]])

    def test_naive_timezone_and_invalid_window(self):
        with self.assertRaises(OpportunityError):
            self.service().recommend("2026-10-26T12:00:00", self.end)
        with self.assertRaises(ValueError):
            self.service().recommend(self.end, self.start)

    def test_event_partial_overlap_excluded(self):
        result = self.service().recommend("2026-10-26T13:00:00-07:00", self.end, include_ideas=False)
        self.assertEqual(result["recommendations"], [])

    def test_incompatible_and_unknown_opening_hours(self):
        for windows in ([], [{"start_at": "2026-10-26T15:00:00-07:00", "end_at": "2026-10-26T17:00:00-07:00"}]):
            row = copy.deepcopy(self.rows[0])
            row["activity"]["opening_windows"] = windows
            result = self.service([row]).recommend(self.start, self.end, include_ideas=False)
            self.assertEqual(result["recommendations"], [])

    def test_real_source_and_hours_require_evidence(self):
        row = self.real_venue()
        row["activity"]["source_claims"].pop("opening_windows")
        result = self.service([row]).recommend(self.start, self.end, include_ideas=False)
        self.assertEqual(result["recommendations"], [])
        row = self.real_venue()
        row["activity"]["source_claims"].pop("description")
        result = self.service([row]).recommend(self.start, self.end, include_ideas=False)
        self.assertEqual(result["recommendations"], [])
        self.assertEqual(result["diagnostics"][0]["code"], "EVENT_UNVERIFIED")

    def test_verified_real_is_not_confirmed_inventory(self):
        r = self.service([self.real_venue()]).recommend(self.start, self.end, include_ideas=False)["recommendations"][0]
        self.assertEqual(r["record_type"], "verified_real")
        self.assertEqual(r["known"]["price_cents"], 500)
        self.assertFalse(r["fit"]["availability_confirmed"])
        self.assertEqual(r["fit"]["basis"], "estimated_visit_within_listed_opening_window")

    def test_unknown_prices_and_budget_preference(self):
        r = self.results(budget_preference_cents=1000, allow_unknown_price=False)
        self.assertEqual([x["candidate_id"] for x in r], ["demo_games"])
        r = self.results(budget_preference_cents=1000)
        self.assertIn("price and total cost", next(x for x in r if x["candidate_id"] == "demo_coffee")["requires_verification"])
        row = self.real_venue()
        row["activity"]["source_claims"].pop("price")
        self.assertIsNone(normalize(row)["activity"]["price_cents"])
        self.assertEqual(self.service([self.real_venue()]).recommend(self.start, self.end, budget_preference_cents=100, include_ideas=False)["recommendations"], [])

    def test_food_filter_remains_optional(self):
        self.assertTrue(self.results(include_ideas=False))
        self.assertEqual(self.results(food_only=True), [])
        catalog = OpportunityCatalog(FixtureProvider(), now=self.now)
        r = DiscoveryService(catalog).recommend(self.start, self.end, food_only=True)["recommendations"]
        self.assertEqual([x["candidate_id"] for x in r], ["opp_demo_pizza"])
        self.assertEqual(DiscoveryService(catalog).recommend(self.start, self.end, free_food_only=True)["recommendations"], [])

    def test_duplicates_and_stable_order(self):
        a = self.service(self.rows + self.rows).recommend(self.start, self.end)
        b = self.service(list(reversed(self.rows))).recommend(self.start, self.end)
        self.assertEqual(a, b)

    def test_expired_and_stale_excluded(self):
        row = copy.deepcopy(self.rows[1])
        row.update(start_at="2026-10-23T12:00:00-07:00", end_at="2026-10-23T13:00:00-07:00")
        self.assertEqual(self.service([row]).recommend(self.start, self.end, include_ideas=False)["recommendations"], [])
        row = dict(self.rows[1], checked_at="2026-10-20T18:00:00Z")
        self.assertEqual(self.service([row]).recommend(self.start, self.end, include_ideas=False)["recommendations"], [])

    def test_empty_results_and_source_failure(self):
        self.assertEqual(self.results(intent="unrecognized activity"), [])
        with self.assertRaises(OpportunityError) as error:
            OpportunityCatalog(MockProvider(unavailable=True), now=self.now)
        self.assertEqual(error.exception.code, "SOURCE_UNAVAILABLE")
        catalog = OpportunityCatalog(MockProvider(unavailable=True), fallback=ActivityFixtureProvider(), now=self.now)
        result = DiscoveryService(catalog).recommend(self.start, self.end)
        self.assertEqual(result["diagnostics"][0]["code"], "SOURCE_UNAVAILABLE")
        self.assertTrue(result["recommendations"])

    def test_interest_ranking_and_location_context(self):
        games = self.results(interests=["games"])[0]
        self.assertEqual(games["candidate_id"], "demo_games")
        r = self.service([]).recommend(self.start, self.end, location_context="regional")
        self.assertEqual(r["recommendations"], [])

    def test_malformed_activity_rejected(self):
        for change in ({"duration_minutes": [90, 60]}, {"price_cents": -1}, {"kind": "hotel_booking"},
                       {"opening_windows": [{"start_at": self.end, "end_at": self.start}]}):
            row = copy.deepcopy(self.rows[0])
            row["activity"].update(change)
            with self.subTest(change=change), self.assertRaises(OpportunityError):
                normalize(row)


if __name__ == "__main__":
    unittest.main()
