"""Contract-compatible normalization. No inference of food inventory or user diet."""
from copy import deepcopy
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit


class OpportunityError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def timestamp(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.utcoffset() is None:
            raise ValueError("timezone required")
        return result
    except (AttributeError, TypeError, ValueError) as exc:
        raise OpportunityError("EVENT_UNVERIFIED", "Invalid offset-aware timestamp") from exc


def source_key(url):
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), parsed.query, ""))


def normalize(raw, provider="structured_import"):
    """Accept canonical records plus optional evidence metadata; return a JSON mapping.

    Importing parties are responsible for source authorization and exact quotations.
    Extra input keys are deliberately not forwarded (they may contain private data).
    """
    if not isinstance(raw, dict):
        raise OpportunityError("EVENT_UNVERIFIED", "Event must be an object")
    for key in ("opportunity_id", "title", "campus", "source_url"):
        if not isinstance(raw.get(key), str) or not raw[key].strip():
            raise OpportunityError("EVENT_UNVERIFIED", f"Missing {key}")
    start, end, checked = (timestamp(raw.get(k)) for k in ("start_at", "end_at", "checked_at"))
    if end <= start:
        raise OpportunityError("EVENT_UNVERIFIED", "End must follow start")
    if type(raw.get("synthetic")) is not bool:
        raise OpportunityError("EVENT_UNVERIFIED", "Explicit synthetic boolean required")
    synthetic = raw["synthetic"]
    try:
        url = urlsplit(raw["source_url"])
    except ValueError as exc:
        raise OpportunityError("EVENT_UNVERIFIED", "Invalid evidence URL") from exc
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
        raise OpportunityError("EVENT_UNVERIFIED", "Public evidence URL required")
    if not synthetic and (url.hostname == "example.org" or url.hostname.endswith(".example.org")):
        raise OpportunityError("EVENT_UNVERIFIED", "Demo URL on real event")
    if synthetic and "DEMO" not in raw["title"].upper():
        raise OpportunityError("EVENT_UNVERIFIED", "Synthetic title needs DEMO label")
    enums = {
        "food_status": {"none", "listed", "confirmed_by_organizer", "unknown"},
        "access_status": {"public", "restricted", "unknown"},
        "dietary_suitability": {"known_suitable", "known_unsuitable", "unknown"},
    }
    out = {k: raw[k] for k in ("opportunity_id", "title", "campus", "start_at", "end_at", "source_url", "checked_at", "synthetic")}
    for key, allowed in enums.items():
        value = raw.get(key, "unknown")
        if not isinstance(value, str) or value not in allowed:
            raise OpportunityError("EVENT_UNVERIFIED", f"Invalid {key}")
        out[key] = value
    for key in ("location_label", "organizer", "access_restrictions"):
        value = raw.get(key)
        if value is not None and not isinstance(value, str):
            raise OpportunityError("EVENT_UNVERIFIED", f"Invalid {key}")
        out[key] = value
    if raw.get("location_private") is True:
        out["location_label"] = None
    if raw.get("rsvp_required") is not None and type(raw["rsvp_required"]) is not bool:
        raise OpportunityError("EVENT_UNVERIFIED", "Invalid RSVP requirement")
    out["rsvp_required"] = raw.get("rsvp_required")
    detail = raw.get("food_detail", "Food not verified")
    if not isinstance(detail, str):
        raise OpportunityError("EVENT_UNVERIFIED", "Invalid food detail")
    evidence = raw.get("evidence", {})
    if not isinstance(evidence, dict):
        raise OpportunityError("EVENT_UNVERIFIED", "Evidence must be an object")
    evidence = {k: deepcopy(v) for k, v in evidence.items()
                if k in {"food_quote", "free_food_quote", "dietary", "organizer_confirmation", "attendance_quote"}}
    for key in ("food_quote", "free_food_quote", "attendance_quote"):
        if key in evidence and not isinstance(evidence[key], str):
            raise OpportunityError("EVENT_UNVERIFIED", "Evidence quotes must be strings")
    if not synthetic:
        if out["food_status"] in {"listed", "confirmed_by_organizer"} and not evidence.get("food_quote"):
            out["food_status"] = "unknown"
        if out["food_status"] == "confirmed_by_organizer" and evidence.get("organizer_confirmation") is not True:
            out["food_status"] = "listed"
    # Dietary assessments are always scoped to an explicitly queried preference.
    out["dietary_suitability"] = "unknown"
    diet = evidence.get("dietary", {})
    if not isinstance(diet, dict) or any(
        not isinstance(k, str) or not isinstance(v, dict)
        or v.get("status") not in ("known_suitable", "known_unsuitable")
        or not isinstance(v.get("quote"), str) or not v["quote"].strip()
        for k, v in diet.items()
    ):
        raise OpportunityError("EVENT_UNVERIFIED", "Dietary claims need specific evidence")
    out.update(food_detail=detail, evidence=evidence,
               free_food_evidence=bool(evidence.get("free_food_quote", "").strip()),
               food_availability="unknown",
               provenance={"provider": provider, "source_url": raw["source_url"],
                           "checked_at": raw["checked_at"], "access": "fixture" if synthetic else "public_or_authorized_import"})
    if "activity" in raw:
        from .activities import activity_metadata
        out["activity"] = activity_metadata(raw["activity"], synthetic=synthetic)
    return out
