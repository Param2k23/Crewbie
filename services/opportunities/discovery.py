"""Activity-agnostic recommendations. Ideas never masquerade as Opportunities."""
from copy import deepcopy
from datetime import timedelta, timezone

from .models import OpportunityError, timestamp


class IdeaProvider:
    """General possibilities, not named businesses, offers or live availability."""
    def load(self):
        return [
            {"idea_id": "idea_coffee", "title": "Coffee and conversation", "categories": ["coffee"],
             "interests": ["social"], "duration_minutes": [60, 90], "location_context": "local"},
            {"idea_id": "idea_games", "title": "Casual games with friends", "categories": ["games"],
             "interests": ["social", "games"], "duration_minutes": [60, 90], "location_context": "local"},
            {"idea_id": "idea_evening", "title": "Dinner and an evening activity", "categories": ["dinner", "movies", "bowling"],
             "interests": ["social"], "duration_minutes": [180, 240], "location_context": "local"},
            {"idea_id": "idea_outdoors", "title": "Half-day outdoor experience", "categories": ["outdoors", "hike", "day_out"],
             "interests": ["nature"], "duration_minutes": [240, 480], "location_context": "regional"},
            {"idea_id": "idea_weekend", "title": "Two-day getaway planning idea", "categories": ["trip", "getaway"],
             "interests": ["nature", "travel"], "duration_minutes": [2880, 4320], "location_context": "regional"},
            {"idea_id": "idea_break", "title": "Long-break exploration planning idea", "categories": ["trip", "getaway"],
             "interests": ["travel"], "duration_minutes": [7200, 10080], "location_context": "regional"},
        ]


def horizon(minutes):
    if minutes <= 120:
        return "short_break"
    if minutes <= 240:
        return "evening"
    if minutes <= 720:
        return "half_day"
    if minutes <= 4320:
        return "weekend"
    return "long_break"


class DiscoveryService:
    def __init__(self, catalog, *, ideas=None):
        self.catalog = catalog
        self.ideas = ideas if ideas is not None else IdeaProvider()

    def recommend(self, starts_after, ends_before, *, intent=None, categories=None, campus=None,
                  interests=(), budget_preference_cents=None, allow_unknown_price=True,
                  food_only=False, free_food_only=False, include_ideas=True,
                  distances=None, max_distance_m=None, location_context=None, limit=10):
        """Time-first if intent is absent; intent/category-first otherwise.

        Budget is a discovery preference, never negotiation hard-limit approval.
        All dates require offsets; durations are elapsed time, not local wall time.
        """
        start, end = timestamp(starts_after), timestamp(ends_before)
        if end <= start or type(limit) is not int or limit < 0:
            raise ValueError("Invalid window or result limit")
        if budget_preference_cents is not None and (type(budget_preference_cents) is not int or budget_preference_cents < 0):
            raise ValueError("Budget preference must be nonnegative integer cents")
        requested = {x.casefold().strip() for x in (categories or [])}
        if intent:
            # Explicit vocabulary, no inferred provider inventory or natural language claims.
            aliases = {"weekend trip": "trip", "day out": "day_out", "hiking": "hike", "free food": "food"}
            requested.add(aliases.get(intent.casefold().strip(), intent.casefold().strip()))
        interest_set = {x.casefold().strip() for x in interests}
        minutes = (end - start).total_seconds() / 60
        rows = self.catalog.list_opportunities(campus=campus, food_only=food_only,
                                              free_food_only=free_food_only, distances=distances,
                                              max_distance_m=max_distance_m)
        diagnostics = deepcopy(self.catalog.diagnostics)
        candidates = []
        for row in rows:
            activity = row.get("activity", {})
            cats = set(activity.get("categories", ["event"]))
            if row["food_status"] in ("listed", "confirmed_by_organizer"):
                cats.add("food")
            if requested and not requested.intersection(cats):
                continue
            if location_context and activity.get("location_context", "unknown") != location_context:
                continue
            if not row["synthetic"] and not activity.get("source_verified"):
                diagnostics.append({"code": "EVENT_UNVERIFIED", "opportunity_id": row["opportunity_id"]})
                continue
            if activity.get("kind", "event") == "event":
                s, e = timestamp(row["start_at"]), timestamp(row["end_at"])
                if s < start or e > end or s < self.catalog.now():
                    continue
                duration = (e - s).total_seconds() / 60
                slot = {"start_at": row["start_at"], "end_at": row["end_at"]}
                basis = "listed_event_times"
            else:
                duration_range = activity.get("duration_minutes")
                if not duration_range:
                    continue  # no guessed visit length
                duration = duration_range[0]
                slots = []
                for window in activity.get("opening_windows", []):
                    s = max(start, timestamp(window["start_at"]), timestamp(row["start_at"]), self.catalog.now())
                    e = min(end, timestamp(window["end_at"]), timestamp(row["end_at"]))
                    if (e - s).total_seconds() >= duration * 60:
                        slots.append(s)
                if not slots:
                    continue  # unknown opening hours cannot establish a suitable time
                s = min(slots).astimezone(timezone.utc)
                slot = {"start_at": s.isoformat(), "end_at": (s + timedelta(minutes=duration)).isoformat()}
                basis = "estimated_visit_within_listed_opening_window"
            price = activity.get("price_cents")
            if price is None and not allow_unknown_price:
                continue
            if price is not None and budget_preference_cents is not None and price > budget_preference_cents:
                continue
            checks = ["current availability", "transport and travel time", "entry and RSVP requirements"]
            if price is None:
                checks.append("price and total cost")
            candidate = {
                "candidate_id": row["opportunity_id"],
                "record_type": "synthetic_fixture" if row["synthetic"] else "verified_real",
                "title": row["title"], "synthetic": row["synthetic"], "source_url": row["source_url"],
                "categories": sorted(cats), "horizon": horizon(duration), "opportunity": row,
                "known": {"location": row["location_label"], "campus": row["campus"], "price_cents": price,
                          "source_claims": activity.get("source_claims", {})},
                "fit": {"proposed_slot": slot, "duration_minutes": duration, "basis": basis,
                        "availability_confirmed": False},
                "requires_verification": checks,
            }
            candidates.append((candidate, set(activity.get("interests", [])), price))
        if include_ideas and not food_only and not free_food_only and max_distance_m is None:
            for raw in self.ideas.load():
                cats = set(raw["categories"])
                if requested and not requested.intersection(cats):
                    continue
                if location_context and raw["location_context"] != location_context:
                    continue
                duration = raw["duration_minutes"][0]
                if duration > minutes or start < self.catalog.now() or not allow_unknown_price:
                    continue
                candidate = {
                    "candidate_id": raw["idea_id"], "record_type": "planning_idea", "title": raw["title"],
                    "synthetic": False, "source_url": None, "categories": sorted(cats), "horizon": horizon(duration),
                    "known": {"location_context": raw["location_context"], "price_cents": None},
                    "fit": {"duration_minutes": deepcopy(raw["duration_minutes"]), "basis": "planning_estimate",
                            "availability_confirmed": False, "proposed_slot": None},
                    "requires_verification": ["venue or destination", "opening hours and schedule", "price and total cost",
                                              "transport and travel time", "admission and availability",
                                              "lodging if overnight", "weather and accessibility"],
                }
                candidates.append((candidate, set(raw["interests"]), None))
        # Ideas are deduped by ID; Opportunities already deduped by the catalog.
        candidates.sort(key=lambda item: (
            {"verified_real": 0, "synthetic_fixture": 1, "planning_idea": 2}[item[0]["record_type"]],
            -len(interest_set.intersection(item[1])),
            item[2] is None if budget_preference_cents is not None else False,
            item[2] if budget_preference_cents is not None and item[2] is not None else 0,
            abs(minutes - (item[0]["fit"]["duration_minutes"][0] if isinstance(item[0]["fit"]["duration_minutes"], list)
                           else item[0]["fit"]["duration_minutes"])), item[0]["candidate_id"]))
        seen, results = set(), []
        for candidate, _, _ in candidates:
            key = (candidate["record_type"], candidate["candidate_id"])
            if key not in seen:
                seen.add(key)
                results.append(candidate)
        return {"query_mode": "intent_first" if requested else "time_first", "window_horizon": horizon(minutes),
                "recommendations": results[:limit], "diagnostics": diagnostics,
                "notice": "Suggestions require verification; no booking, inventory or transport availability is confirmed."}
