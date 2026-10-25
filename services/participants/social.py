"""Private general-social policy extensions; no shared schema is modified."""
from typing import Any, Mapping, TypedDict
from .service import PrivacyError, identifier, window


class ActivitySearch(TypedDict):
    activity_id: str
    activity_kind: str
    rough_area: str
    start_at: str
    end_at: str
    group_size: int
    estimated_travel_minutes: int
    synthetic: bool


def validate_preferences(preferences: Mapping[str, Any]) -> None:
    allowed = {"activity_interests", "rough_areas", "min_group_size", "max_group_size",
               "max_duration_minutes", "max_travel_minutes", "willingness"}
    if not isinstance(preferences, dict) or not set(preferences) <= allowed:
        raise PrivacyError("INVALID_INPUT")
    for key in ("activity_interests", "rough_areas"):
        values = preferences.get(key, [])
        if not isinstance(values, list) or not all(isinstance(v, str) and v for v in values):
            raise PrivacyError("INVALID_INPUT")
    for key in ("min_group_size", "max_group_size", "max_duration_minutes", "max_travel_minutes"):
        if key in preferences and (type(preferences[key]) is not int or preferences[key] < 0):
            raise PrivacyError("INVALID_INPUT")
    if not 2 <= preferences.get("min_group_size", 2) <= preferences.get("max_group_size", 20) <= 20:
        raise PrivacyError("INVALID_INPUT")
    if preferences.get("willingness", "unavailable") not in ("interested", "unavailable"):
        raise PrivacyError("INVALID_INPUT")


def validate_activity(activity: Mapping[str, Any]) -> None:
    required = {"activity_id", "activity_kind", "rough_area", "start_at", "end_at", "group_size",
                "estimated_travel_minutes", "synthetic"}
    if not isinstance(activity, Mapping) or set(activity) != required:
        raise PrivacyError("INVALID_INPUT")
    for field in ("activity_id", "activity_kind", "rough_area"):
        identifier(activity[field])
    if type(activity["group_size"]) is not int or not 2 <= activity["group_size"] <= 20:
        raise PrivacyError("INVALID_INPUT")
    travel = activity["estimated_travel_minutes"]
    if type(travel) is not int or travel < 0 or activity["synthetic"] is not True:
        raise PrivacyError("INVALID_INPUT")
    window(activity)


def matches(profile: Mapping[str, Any], activity: Mapping[str, Any]) -> bool:
    """Discovery is interest, never enrollment, acceptance or introduction."""
    prefs = profile.get("social_preferences", {})
    start, end = window(activity)
    duration = (end - start).total_seconds() / 60
    return (prefs.get("willingness") == "interested"
            and activity["activity_kind"] in prefs.get("activity_interests", [])
            and activity["rough_area"] in prefs.get("rough_areas", [])
            and prefs.get("min_group_size", 2) <= activity["group_size"] <= prefs.get("max_group_size", 20)
            and duration <= prefs.get("max_duration_minutes", float("inf"))
            and activity["estimated_travel_minutes"] <= prefs.get("max_travel_minutes", float("inf"))
            and any(a <= start and end <= b for a, b in map(window, profile.get("available_windows", [])))
            and not any(start < b and a < end for a, b in map(window, profile["blocked_windows"])))


def evaluate_policy(profile: Mapping[str, Any], plan: Mapping[str, Any]):
    """Return only coarse trusted-coordinator signals, never a private limit."""
    prefs = profile.get("social_preferences", {})
    if not prefs:
        return [], [], 0.0
    issues, hints = [], []
    start, end = window(plan)
    if (end - start).total_seconds() > prefs.get("max_duration_minutes", float("inf")) * 60:
        issues.append("HARD_DURATION")
        hints.append("prefer_shorter_activity")
    if not prefs.get("min_group_size", 2) <= len(plan["member_refs"]) <= prefs.get("max_group_size", 20):
        issues.append("HARD_GROUP_SIZE")
        hints.append("adjust_group_size")
    if "rough_areas" in prefs and plan.get("rough_area") not in prefs["rough_areas"]:
        issues.append("HARD_AREA")
        hints.append("try_alternate_area")
    if "max_travel_minutes" in prefs:
        travel = plan.get("estimated_travel_minutes_by_ref", {}).get(profile["student_ref"])
        if travel is None or travel > prefs["max_travel_minutes"]:
            issues.append("HARD_TRAVEL")
            hints.append("prefer_less_travel")
    penalty = 0.0
    if "activity_interests" in prefs and plan.get("activity_kind") not in prefs["activity_interests"]:
        penalty = 0.25
        hints.append("prefer_alternate_activity")
    return issues, hints, penalty
