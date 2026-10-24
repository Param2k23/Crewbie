"""Deterministic private intent parsing and source-grounded previews.

Context must be constructed by a trusted identity adapter, never from a raw
client user_id. These functions do not send, persist preferences or match people.
"""
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from uuid import uuid4

PHOENIX = timezone(timedelta(hours=-7), "America/Phoenix")
CAMPUSES = ("Tempe", "West Valley", "Downtown Phoenix", "Polytechnic")


class PulseError(ValueError):
    def __init__(self, code, detail):
        self.code = code
        super().__init__(detail)


def instant(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
        if not isinstance(result, datetime) or result.utcoffset() is None:
            raise ValueError()
        return result
    except (ValueError, TypeError, AttributeError):
        raise PulseError("VALIDATION_ERROR", "An explicit timezone-aware timestamp is required")


def parse_preferences(message, context):
    """Private preferences; deliberately kept out of public telemetry."""
    text = message.lower()
    campuses = [c for c in CAMPUSES if c.lower() in text]
    if len(campuses) > 1:
        raise PulseError("VALIDATION_ERROR", "Choose one campus")
    campus = campuses[0] if campuses else context.get("campus")
    if campus not in CAMPUSES:
        raise PulseError("VALIDATION_ERROR", "Specify a supported campus")
    diet = context.get("dietary_preferences", [])
    if not isinstance(diet, (list, tuple)) or any(not isinstance(x, str) for x in diet):
        raise PulseError("VALIDATION_ERROR", "Dietary preferences must be a list of strings")
    diet = sorted(set(diet) | {d for d in ("vegetarian", "vegan", "halal", "gluten-free") if d in text})
    cadence = context.get("cadence", "off")
    if re.search(r"\b(daily|weekly)\b", text):
        cadence = re.search(r"\b(daily|weekly)\b", text).group()
    if re.search(r"\b(stop alerts|no alerts|cancel alerts)\b", text):
        cadence = "off"
    if cadence not in ("off", "daily", "weekly"):
        raise PulseError("VALIDATION_ERROR", "Cadence must be off, daily or weekly")
    return {"campus": campus, "dietary_preferences": diet, "cadence": cadence}


def parse_student_intent(message, consent_context):
    """Return the frozen OpportunityBrief; raise rather than guess a time gap."""
    c = consent_context
    if c.get("authorized") is not True or not c.get("student_ref"):
        raise PulseError("CONSENT_REQUIRED", "Trusted authenticated context is required")
    if not isinstance(message, str) or not message.strip():
        raise PulseError("VALIDATION_ERROR", "A request is required")
    text = message.lower()
    companion = bool(re.search(r"\b(company|companion|friend|someone to go)\b", text))
    if companion:
        intent = "find_companion"
    elif re.search(r"\b(food|pizza|tacos|lunch)\b", text):
        intent = "find_campus_food"
    elif re.search(r"\b(trip|group activity)\b", text):
        intent = "plan_group_activity"
    else:
        raise PulseError("VALIDATION_ERROR", "Unrecognized Campus Pulse intent")
    prefs = parse_preferences(message, c)
    start, end = instant(c.get("availability_start")), instant(c.get("availability_end"))
    if end <= start:
        raise PulseError("VALIDATION_ERROR", "Availability end must follow start")
    # Relative dates require an injected clock and must agree with the explicit gap.
    if "tomorrow" in text or re.search(r"\btoday\b", text):
        now = instant(c.get("now")).astimezone(PHOENIX)
        expected = now.date() + timedelta(days=1 if "tomorrow" in text else 0)
        if start.astimezone(PHOENIX).date() != expected:
            raise PulseError("VALIDATION_ERROR", "Requested date conflicts with availability")
    # Unsupported free-form clock times must be clarified rather than ignored.
    if re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b|\bat\s+\d|\bfrom\s+\d", text):
        raise PulseError("VALIDATION_ERROR", "Confirm clock times as structured availability")
    requirements = ["event_entry_policy"]
    requirements += [d + "_options" for d in prefs["dietary_preferences"]]
    if companion and not (c.get("matching_opt_in") is True and c.get("activity_scope")):
        requirements.append("matching_consent")
    return {"brief_id": "brief_" + uuid4().hex, "student_ref": c["student_ref"],
            "intent": intent, "campus": prefs["campus"],
            "availability_start": start.isoformat(), "availability_end": end.isoformat(),
            "opportunity_id": c.get("opportunity_id"), "wants_companion": companion,
            "requirements_to_verify": requirements, "source": "cubbie_skill",
            "synthetic": c.get("synthetic") is True}


def _source_ok(event):
    try:
        u = urlsplit(event.get("source_url", ""))
        return (u.scheme in ("https", "http") and bool(u.hostname) and not u.username
                and not u.password and (event.get("synthetic") is True or
                not (u.hostname == "example.org" or u.hostname.endswith(".example.org"))))
    except (ValueError, TypeError):
        return False


def select_opportunities(brief, opportunities, *, now=None, food_only=True,
                         max_age=timedelta(days=3), minimum_overlap=timedelta(minutes=20),
                         transit_buffer=timedelta(0)):
    """Filter half-open windows; rank food evidence, freshness, overlap, then ID.

    Three-day freshness is a local demo policy, not a sponsor guarantee.
    Contradictory duplicate IDs are excluded rather than silently choosing a claim.
    A2 dietary suitability must already be evaluated for the requesting student.
    """
    now = instant(now or datetime.now(timezone.utc))
    start, end = instant(brief["availability_start"]), instant(brief["availability_end"])
    if end <= start or minimum_overlap <= timedelta(0) or transit_buffer < timedelta(0) or max_age < timedelta(0):
        raise PulseError("VALIDATION_ERROR", "Invalid selection timing policy")
    by_id, conflicts = {}, set()
    for event in opportunities:
        if not isinstance(event, dict) or not isinstance(event.get("opportunity_id"), str) or not event["opportunity_id"]:
            continue
        key = event["opportunity_id"]
        if key in by_id and by_id[key] != event:
            conflicts.add(key)
        by_id[key] = event
    ranked = []
    for key, e in by_id.items():
        if key in conflicts or e.get("campus") != brief["campus"] or not _source_ok(e):
            continue
        if not isinstance(e.get("synthetic"), bool) or not isinstance(e.get("title"), str) or not e["title"].strip():
            continue
        if e.get("food_status") not in ("none", "listed", "confirmed_by_organizer", "unknown"):
            continue
        if e.get("dietary_suitability") not in ("unknown", "known_suitable", "known_unsuitable"):
            continue
        if e.get("access_status") not in ("unknown", "public", "restricted"):
            continue
        if e["dietary_suitability"] == "known_unsuitable":
            continue
        if food_only and e["food_status"] not in ("listed", "confirmed_by_organizer"):
            continue
        try:
            es, ee, checked = instant(e.get("start_at")), instant(e.get("end_at")), instant(e.get("checked_at"))
        except PulseError:
            continue
        if ee <= es or ee <= now or not timedelta(0) <= now - checked <= max_age:
            continue
        overlap = min(end - transit_buffer, ee) - max(start + transit_buffer, es, now)
        if overlap < minimum_overlap:
            continue
        ranked.append(((e["food_status"] == "confirmed_by_organizer", checked, overlap.total_seconds()), key, dict(e)))
    ranked.sort(key=lambda x: x[1])
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [row[2] for row in ranked]


def preview_cubbie_alert(student_ref, opportunities, *, brief=None, now=None, food_only=True):
    """Private preview only. Never pass this output to group chat or SSE."""
    if brief is None or brief.get("student_ref") != student_ref:
        raise PulseError("CONSENT_REQUIRED", "A private student brief is required")
    events = select_opportunities(brief, opportunities, now=now, food_only=food_only)
    messages = []
    for e in events[:3]:
        label = "[DEMO FIXTURE - fictional event] " if e["synthetic"] else ""
        times = " to ".join(instant(e[k]).astimezone(PHOENIX).isoformat(timespec="minutes") for k in ("start_at", "end_at"))
        food = {"listed": "Food mentioned in listing.", "confirmed_by_organizer": "Organizer confirmed food provision.",
                "unknown": "Food provision unknown.", "none": "No food listed."}[e["food_status"]]
        diet = "Diet not verified; ask the organizer about ingredients and dietary suitability."
        if e["dietary_suitability"] == "known_suitable":
            diet = "Catalog reports suitability for your preferences; confirm ingredients with the organizer."
        access = {"public": "Listed as public access.", "restricted": "Restricted access; verify eligibility before going.",
                  "unknown": "Public access unknown; verify entry policy."}[e["access_status"]]
        rsvp = "RSVP required." if e.get("rsvp_required") is True else "RSVP not listed as required." if e.get("rsvp_required") is False else "RSVP requirements unknown."
        messages.append(f"{label}{e['title']}\n{times} (America/Phoenix)\n"
                        f"Venue: {e.get('location_label') or 'Unknown; confirm with organizer'}.\n"
                        f"{food} Free meal and remaining availability are not guaranteed. {diet}\n"
                        f"{access} {rsvp}\nSource: {e['source_url']}\nChecked: {e['checked_at']}\n"
                        "Check the source before attending. Reply 'Find company' to request consent-based matching.")
    return {"student_ref": student_ref, "visibility": "private", "mode": "preview_only", "sent": False,
            "opportunity_ids": [e["opportunity_id"] for e in events[:3]],
            "synthetic": any(e["synthetic"] for e in events[:3]),
            "text": "\n\n".join(messages) if messages else "No verified candidate fits this window. Try a different campus or time; no alert sent."}
