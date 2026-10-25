"""Deterministic discovery service implementing the frozen A2 callables."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

from .models import OpportunityError, normalize, source_key, timestamp
from .providers import FixtureProvider


class OpportunityCatalog:
    def __init__(self, provider=None, *, fallback=None, now=None, max_age=timedelta(hours=24)):
        self.provider = provider if provider is not None else FixtureProvider()
        self.fallback = fallback
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.max_age = max_age
        self.diagnostics = []
        self._records = []
        self.refresh()

    def refresh(self):
        self.diagnostics = []
        provider = self.provider
        try:
            records = provider.load()
        except OpportunityError as exc:
            if exc.code != "SOURCE_UNAVAILABLE" or self.fallback is None:
                raise
            self.diagnostics.append({"code": exc.code, "fallback": "demo_fixture"})
            provider = self.fallback
            records = provider.load()
            if any(r.get("synthetic") is not True for r in records):
                raise OpportunityError("EVENT_UNVERIFIED", "Fallback must be synthetic")
        normalized = []
        for raw in records:
            try:
                normalized.append(normalize(raw, provider.name))
            except OpportunityError as exc:
                self.diagnostics.append({"code": exc.code, "reason": str(exc)})
        # Most recently checked wins as a complete record. Never merge certainty.
        normalized.sort(key=lambda r: (-timestamp(r["checked_at"]).timestamp(), json.dumps(r, sort_keys=True)))
        keys, ids, unique = set(), set(), []
        for r in normalized:
            key = (r["synthetic"], source_key(r["source_url"]), timestamp(r["start_at"]))
            if key in keys or r["opportunity_id"] in ids:
                continue
            keys.add(key)
            ids.add(r["opportunity_id"])
            unique.append(r)
        self._records = unique

    def _view(self, record, dietary_preference=None):
        r = deepcopy(record)
        now = self.now()
        age = now - timestamp(r["checked_at"])
        r["stale"] = age > self.max_age or age < timedelta(0)
        r["expired"] = timestamp(r["end_at"]) <= now
        r["warnings"] = ["Food remaining and dietary safety are not guaranteed."]
        if r["synthetic"]:
            r["warnings"].append("DEMO ONLY: fictional listing; no actual event or inventory.")
        if r["stale"]:
            r["warnings"].append("Source check is stale or future-dated; recheck before attending.")
        if r["expired"]:
            r["warnings"].append("Event has ended.")
        if not r["location_label"]:
            r["warnings"].append("Location unverified.")
        if r["rsvp_required"] is None or r["access_status"] != "public":
            r["warnings"].append("Verify RSVP and entry requirements with organizer.")
        if dietary_preference:
            r["dietary_suitability"] = r["evidence"].get("dietary", {}).get(dietary_preference.casefold(), {}).get("status", "unknown")
        return r

    def get_opportunity(self, opportunity_id):
        return next((self._view(r) for r in self._records if r["opportunity_id"] == opportunity_id), None)

    def list_opportunities(self, campus=None, starts_after=None, ends_before=None, food_only=False, *,
                           time_mode="contained", free_food_only=False, dietary_preference=None,
                           allow_unknown_diet=True, allow_restricted=False, rsvp_policy="any",
                           include_stale=False, include_past=False, distances=None, max_distance_m=None,
                           limit=None, offset=0):
        """Return JSON-ready records. distances is a caller-grounded ID -> metres map.

        No routing, coordinate inference, enrollment, RSVP action or user data storage.
        Unknown distance is excluded when a distance cap is supplied.
        """
        lower = timestamp(starts_after) if starts_after else None
        upper = timestamp(ends_before) if ends_before else None
        if lower and upper and lower >= upper:
            raise ValueError("Invalid query window")
        if time_mode not in ("contained", "overlap") or rsvp_policy not in ("any", "not_required", "required"):
            raise ValueError("Invalid time mode or RSVP policy")
        if offset < 0 or (limit is not None and limit < 0):
            raise ValueError("Invalid pagination")
        distances = distances or {}
        if any(type(d) not in (int, float) or not 0 <= d < float("inf") for d in distances.values()):
            raise ValueError("Distances must be finite nonnegative metres")
        if max_distance_m is not None and (type(max_distance_m) not in (int, float) or not 0 <= max_distance_m < float("inf")):
            raise ValueError("Invalid distance cap")
        result = []
        for raw in self._records:
            r = self._view(raw, dietary_preference)
            start, end = timestamp(r["start_at"]), timestamp(r["end_at"])
            if campus and r["campus"].casefold() != campus.casefold():
                continue
            if (r["stale"] and not include_stale) or (r["expired"] and not include_past):
                continue
            if time_mode == "contained" and ((lower and start < lower) or (upper and end > upper)):
                continue
            if time_mode == "overlap" and ((lower and end <= lower) or (upper and start >= upper)):
                continue
            if food_only and r["food_status"] not in ("listed", "confirmed_by_organizer"):
                continue
            if free_food_only and (not r["free_food_evidence"] or r["food_status"] not in ("listed", "confirmed_by_organizer")):
                continue
            if not allow_restricted and r["access_status"] == "restricted":
                continue
            if dietary_preference and (r["dietary_suitability"] == "known_unsuitable" or
                                      (not allow_unknown_diet and r["dietary_suitability"] == "unknown")):
                continue
            if rsvp_policy == "not_required" and r["rsvp_required"] is not False:
                continue
            if rsvp_policy == "required" and r["rsvp_required"] is not True:
                continue
            distance = distances.get(r["opportunity_id"])
            if max_distance_m is not None and (distance is None or distance > max_distance_m):
                continue
            r["distance_m"] = distance
            if distance is not None:
                r["distance_basis"] = "caller_supplied_grounded_metres"
            result.append(r)
        # Lexicographic, documented priorities; stable ID resolves all ties.
        food_rank = {"confirmed_by_organizer": 0, "listed": 1, "unknown": 2, "none": 3}
        result.sort(key=lambda r: (r["stale"], r["dietary_suitability"] != "known_suitable",
                                  not r["free_food_evidence"], food_rank[r["food_status"]],
                                  r["access_status"] != "public", r["rsvp_required"] is not False,
                                  r["distance_m"] if r["distance_m"] is not None else float("inf"),
                                  timestamp(r["start_at"]), r["opportunity_id"]))
        return result[offset:None if limit is None else offset + limit]


def list_opportunities(campus=None, starts_after=None, ends_before=None, food_only=False, **kwargs):
    return OpportunityCatalog().list_opportunities(campus, starts_after, ends_before, food_only, **kwargs)


def get_opportunity(opportunity_id):
    return OpportunityCatalog().get_opportunity(opportunity_id)
