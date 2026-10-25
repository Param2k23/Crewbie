import copy
import json
from pathlib import Path
import unittest

from services.opportunities import (AuthorizedImportProvider, FixtureProvider, MockProvider,
                                   OpportunityCatalog, OpportunityError, normalize)
from services.opportunities.models import timestamp


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.rows = FixtureProvider().load()
        self.clock = timestamp("2026-10-24T19:00:00Z")

    def catalog(self, rows=None, **kw):
        return OpportunityCatalog(MockProvider(self.rows if rows is None else rows), now=lambda: self.clock, **kw)

    def real(self, **kw):
        r = dict(self.rows[0], synthetic=False, source_url="https://asuevents.asu.edu/event/test")
        r.update(kw)
        return r

    def test_contract_fields_preserved_and_missing_unknown(self):
        r = self.catalog().get_opportunity("opp_demo_workshop")
        self.assertIsNone(r["location_label"])
        self.assertEqual(r["food_status"], "unknown")
        self.assertEqual(r["dietary_suitability"], "unknown")
        for k, v in self.rows[0].items():
            self.assertEqual(self.catalog().get_opportunity("opp_demo_pizza")[k], v)

    def test_food_provided_is_only_listed(self):
        r = normalize(self.real(evidence={"food_quote": "Food Provided"}))
        self.assertEqual(r["food_status"], "listed")
        self.assertFalse(r["free_food_evidence"])
        self.assertEqual(r["food_availability"], "unknown")

    def test_free_rsvp_and_missing_food_do_not_imply_food(self):
        r = normalize(self.real(food_detail="Free RSVP"))
        self.assertEqual(r["food_status"], "unknown")
        self.assertFalse(r["free_food_evidence"])
        self.assertEqual(self.catalog([self.real()]).list_opportunities(food_only=True), [])

    def test_confirmation_requires_evidence(self):
        r = self.real(food_status="confirmed_by_organizer", evidence={"food_quote": "Food Provided"})
        self.assertEqual(normalize(r)["food_status"], "listed")
        r["evidence"]["organizer_confirmation"] = True
        self.assertEqual(normalize(r)["food_status"], "confirmed_by_organizer")

    def test_reject_bad_provenance_times_and_enums(self):
        for changes in ({"source_url": "https://example.org/demo"}, {"source_url": "file:///etc/passwd"},
                        {"start_at": "2026-10-26T12:00:00"}, {"end_at": self.rows[0]["start_at"]},
                        {"checked_at": None}, {"food_status": "guaranteed"}, {"synthetic": "false"},
                        {"rsvp_required": "yes"}, {"title": ""}, {"campus": None}):
            with self.subTest(changes=changes), self.assertRaises(OpportunityError):
                normalize(self.real(**changes))

    def test_diet_scoped_to_preference(self):
        r = self.real(evidence={"food_quote": "Food Provided", "dietary": {
            "vegetarian": {"status": "known_suitable", "quote": "Vegetarian options offered"},
            "vegan": {"status": "known_unsuitable", "quote": "No vegan options"}}})
        c = self.catalog([r])
        self.assertEqual(c.list_opportunities()[0]["dietary_suitability"], "unknown")
        self.assertEqual(c.list_opportunities(dietary_preference="vegetarian")[0]["dietary_suitability"], "known_suitable")
        self.assertEqual(c.list_opportunities(dietary_preference="vegan"), [])
        self.assertEqual(c.list_opportunities(dietary_preference="halal", allow_unknown_diet=False), [])
        self.assertEqual(len(c.list_opportunities(dietary_preference="halal")), 1)

    def test_diet_evidence_required(self):
        with self.assertRaises(OpportunityError):
            normalize(self.real(evidence={"dietary": {"halal": {"status": "known_suitable"}}}))

    def test_duplicates_newest_wins_order_independent(self):
        newer = dict(self.rows[0], opportunity_id="new", source_url=self.rows[0]["source_url"] + "/#details",
                     checked_at="2026-10-24T18:30:00Z", food_status="unknown")
        for rows in ([self.rows[0], newer], [newer, self.rows[0]]):
            result = self.catalog(rows).list_opportunities()
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["opportunity_id"], "new")
            self.assertEqual(result[0]["food_status"], "unknown")

    def test_same_id_deduplicated(self):
        self.assertEqual(len(self.catalog([self.rows[0], dict(self.rows[0], source_url="https://example.org/other")]).list_opportunities()), 1)

    def test_stale_future_checks_and_expired(self):
        for checked in ("2026-10-20T18:00:00Z", "2026-10-25T18:00:00Z"):
            c = self.catalog([dict(self.rows[0], checked_at=checked)])
            self.assertEqual(c.list_opportunities(), [])
            self.assertTrue(c.get_opportunity("opp_demo_pizza")["stale"])
            self.assertEqual(len(c.list_opportunities(include_stale=True)), 1)
        c = self.catalog([dict(self.rows[0], start_at="2026-10-23T12:00:00-07:00", end_at="2026-10-23T13:00:00-07:00")])
        self.assertEqual(c.list_opportunities(), [])
        self.assertTrue(c.get_opportunity("opp_demo_pizza")["expired"])

    def test_campus_containment_overlap_boundaries(self):
        c = self.catalog()
        self.assertEqual(c.list_opportunities(campus="Polytechnic"), [])
        args = dict(campus="tempe", starts_after="2026-10-26T12:30:00-07:00", ends_before="2026-10-26T13:30:00-07:00")
        self.assertEqual(c.list_opportunities(**args), [])
        self.assertEqual(len(c.list_opportunities(**args, time_mode="overlap")), 1)
        self.assertEqual(c.list_opportunities(starts_after="2026-10-26T13:00:00-07:00", ends_before="2026-10-26T14:00:00-07:00", time_mode="overlap"), [])

    def test_access_rsvp_and_free_food(self):
        self.assertEqual(len(self.catalog().list_opportunities(allow_restricted=True)), 3)
        self.assertEqual(self.catalog().list_opportunities(rsvp_policy="not_required"), [])
        self.assertEqual(len(self.catalog().list_opportunities(rsvp_policy="required", allow_restricted=True)), 1)
        self.assertEqual(self.catalog().list_opportunities(free_food_only=True), [])
        r = self.real(rsvp_required=False, evidence={"food_quote": "Free pizza", "free_food_quote": "Free pizza"})
        self.assertEqual(len(self.catalog([r]).list_opportunities(free_food_only=True, rsvp_policy="not_required")), 1)

    def test_grounded_distances_only(self):
        c = self.catalog()
        self.assertEqual(c.list_opportunities(max_distance_m=500), [])
        result = c.list_opportunities(max_distance_m=500, distances={"opp_demo_pizza": 250})
        self.assertEqual([r["opportunity_id"] for r in result], ["opp_demo_pizza"])
        with self.assertRaises(ValueError):
            c.list_opportunities(distances={"opp_demo_pizza": float("nan")})

    def test_source_denied_and_explicit_fallback(self):
        for fields in ({"login_redirect": True}, {"captcha": True}, {"http_status": 403}, {"redirect_url": "/login"}):
            p = AuthorizedImportProvider(dict(access="public_or_authorized", opportunities=self.rows, **fields), permitted=True)
            with self.assertRaises(OpportunityError) as error:
                p.load()
            self.assertEqual(error.exception.code, "SOURCE_UNAVAILABLE")
        with self.assertRaises(OpportunityError):
            AuthorizedImportProvider({"access": "public_or_authorized", "opportunities": self.rows}).load()
        with self.assertRaises(OpportunityError):
            OpportunityCatalog(MockProvider(unavailable=True))
        c = OpportunityCatalog(MockProvider(unavailable=True), fallback=FixtureProvider(), now=lambda: self.clock)
        self.assertEqual(c.diagnostics[0]["code"], "SOURCE_UNAVAILABLE")
        self.assertTrue(all(r["synthetic"] for r in c.list_opportunities()))

    def test_authorized_import(self):
        p = AuthorizedImportProvider({"access": "public_or_authorized", "opportunities": [self.real()]}, permitted=True)
        self.assertFalse(OpportunityCatalog(p, now=lambda: self.clock).list_opportunities()[0]["synthetic"])

    def test_observed_public_snapshot_keeps_restrictions(self):
        path = Path(__file__).resolve().parents[2] / "docs/opportunities/observed_public_import.json"
        p = AuthorizedImportProvider(json.loads(path.read_text()), permitted=True)
        c = OpportunityCatalog(p, now=lambda: timestamp("2026-10-24T22:30:00Z"))
        self.assertEqual(c.list_opportunities(), [])
        event = c.list_opportunities(allow_restricted=True, food_only=True)[0]
        self.assertFalse(event["synthetic"])
        self.assertIsNone(event["location_label"])
        self.assertFalse(event["free_food_evidence"])
        self.assertIsNone(event["rsvp_required"])
        self.assertEqual(event["food_status"], "listed")

    def test_private_fields_and_return_mutation(self):
        r = dict(self.rows[0], location_private=True, private_budget=6000, access_token="secret")
        c = self.catalog([r])
        view = c.get_opportunity(r["opportunity_id"])
        self.assertIsNone(view["location_label"])
        self.assertNotIn("access_token", view)
        self.assertNotIn("private_budget", view)
        view["evidence"]["food_quote"] = "changed"
        self.assertNotIn("food_quote", c.get_opportunity(r["opportunity_id"])["evidence"])

    def test_bad_records_diagnostic_and_unknown_id(self):
        c = self.catalog([{}, *self.rows])
        self.assertEqual(c.diagnostics[0]["code"], "EVENT_UNVERIFIED")
        self.assertIsNone(c.get_opportunity("missing"))

    def test_stable_rank_and_pagination(self):
        a, b = self.catalog(), self.catalog(list(reversed(self.rows)))
        self.assertEqual(a.list_opportunities(), b.list_opportunities())
        self.assertEqual(a.list_opportunities(limit=1, offset=1), a.list_opportunities()[1:2])
        with self.assertRaises(ValueError):
            a.list_opportunities(starts_after="2026-10-27T00:00:00Z", ends_before="2026-10-26T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
