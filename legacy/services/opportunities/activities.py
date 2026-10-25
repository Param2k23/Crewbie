"""Additive activity metadata; canonical event fields remain unchanged."""
from copy import deepcopy

from .models import OpportunityError, timestamp


def activity_metadata(value, *, synthetic):
    if not isinstance(value, dict):
        raise OpportunityError("EVENT_UNVERIFIED", "Activity metadata must be an object")
    kind = value.get("kind", "event")
    if kind not in ("event", "venue"):
        raise OpportunityError("EVENT_UNVERIFIED", "Unsupported activity kind")
    result = {"kind": kind}
    context = value.get("location_context", "unknown")
    if context not in ("local", "regional", "unknown"):
        raise OpportunityError("EVENT_UNVERIFIED", "Invalid activity location context")
    result["location_context"] = context
    for key in ("categories", "interests"):
        items = value.get(key, [])
        if not isinstance(items, list) or any(not isinstance(x, str) or not x.strip() for x in items):
            raise OpportunityError("EVENT_UNVERIFIED", f"Invalid activity {key}")
        result[key] = sorted({x.casefold().strip() for x in items})
    quotes = value.get("source_claims", {})
    if not isinstance(quotes, dict) or any(not isinstance(v, str) for v in quotes.values()):
        raise OpportunityError("EVENT_UNVERIFIED", "Activity source claims must be quotations")
    result["source_claims"] = {k: v for k, v in quotes.items()
                               if k in ("description", "opening_windows", "price", "location") and v.strip()}
    result["source_verified"] = value.get("source_verified") is True and bool(result["source_claims"].get("description"))
    duration = value.get("duration_minutes")
    if duration is not None and (not isinstance(duration, list) or len(duration) != 2
                                or any(type(x) is not int or x <= 0 for x in duration) or duration[1] < duration[0]):
        raise OpportunityError("EVENT_UNVERIFIED", "Duration needs positive ordered minute range")
    result["duration_minutes"] = deepcopy(duration)
    result["duration_basis"] = "planning_estimate" if duration else "unknown"
    price = value.get("price_cents")
    if price is not None and (type(price) is not int or price < 0):
        raise OpportunityError("EVENT_UNVERIFIED", "Price must be nonnegative integer cents")
    result["price_cents"] = price if synthetic or result["source_claims"].get("price") else None
    windows = value.get("opening_windows", [])
    if not isinstance(windows, list):
        raise OpportunityError("EVENT_UNVERIFIED", "Opening windows must be a list")
    clean = []
    for w in windows:
        if not isinstance(w, dict) or timestamp(w.get("end_at")) <= timestamp(w.get("start_at")):
            raise OpportunityError("EVENT_UNVERIFIED", "Invalid opening interval")
        clean.append({"start_at": w["start_at"], "end_at": w["end_at"]})
    result["opening_windows"] = clean if synthetic or result["source_claims"].get("opening_windows") else []
    return result
