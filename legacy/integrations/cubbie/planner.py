"""Private local conversation model, not a new cross-agent contract or live service."""
import re
from copy import deepcopy

from .core import PulseError, classify_intent, instant, parse_student_intent, select_opportunities


def _duration(message):
    text = message.lower().replace("-", " ")
    match = re.search(r"\b(one|two|three|\d+)\s+(?:free\s+)?(hours?|days?)\b", text)
    if not match:
        return None
    amount = {"one": 1, "two": 2, "three": 3}.get(match[1])
    amount = int(match[1]) if amount is None else amount
    if amount <= 0:
        raise PulseError("VALIDATION_ERROR", "Duration must be positive")
    return amount * (1440 if match[2].startswith("day") else 60)


def planning_details(message, context):
    """Local-only sidecar. Never add these private fields to OpportunityBrief."""
    details = {k: deepcopy(context.get(k)) for k in
               ("location", "budget_cents", "interests", "activity_types", "travel_tolerance_minutes", "group_size")}
    for key in ("budget_cents", "travel_tolerance_minutes", "group_size"):
        value = details[key]
        if value is not None and (type(value) is not int or value < (1 if key == "group_size" else 0)):
            raise PulseError("VALIDATION_ERROR", "Invalid private planning preference: " + key)
    for key in ("interests", "activity_types"):
        value = details[key]
        if value is not None and (not isinstance(value, list) or any(not isinstance(x, str) for x in value)):
            raise PulseError("VALIDATION_ERROR", "Expected a list of preferences")
    if details["location"] is not None and (not isinstance(details["location"], str) or not details["location"].strip()):
        raise PulseError("VALIDATION_ERROR", "Location must be a nonempty string")
    details["requested_duration_minutes"] = _duration(message)
    details["requested_activity"] = next((a for a in ("badminton", "dinner", "coffee", "hiking", "trip", "events")
                                           if re.search(r"\b" + a + r"\b", message.lower())), None)
    return details


def plan_request(message, context, opportunities=(), *, now=None):
    """Gather constraints; provide verified candidates or clearly tentative ideas.

    Uses only caller-supplied A2-shaped data. No browsing, scheduling, bookings,
    identity disclosure or external calls occur. Native Cubbie does live research.
    """
    if context.get("authorized") is not True or not context.get("student_ref"):
        raise PulseError("CONSENT_REQUIRED", "Trusted private identity is required")
    intent = classify_intent(message)
    details = planning_details(message, context)
    questions = []
    if not context.get("campus"):
        questions.append("What is your starting campus? Other locations can be planned natively in Cubbie.")
    if not context.get("availability_start") or not context.get("availability_end"):
        questions.append("What exact start and end dates/times, including timezone, are available?")
    brief = None
    if not questions:
        brief = parse_student_intent(message, dict(context, now=now) if now is not None else context)
        minutes = (instant(brief["availability_end"]) - instant(brief["availability_start"])).total_seconds() / 60
        if details["requested_duration_minutes"] and details["requested_duration_minutes"] > minutes:
            questions.append("The requested duration exceeds your available window. Which should change?")
    else:
        minutes = None
    if details["budget_cents"] is None:
        questions.append("What spending limit should I use, or should I focus on free options?")
    if details["travel_tolerance_minutes"] is None:
        questions.append("How far are you willing to travel each way?")
    if details["group_size"] is None:
        questions.append("Is this solo, with existing friends, or would you like to find a crew?")
    if details["requested_activity"] == "trip" or (minutes and minutes >= 1440):
        questions.append("Which destination or interests, transport, and overnight accommodation constraints should I use?")
    elif not details["requested_activity"] and not details["interests"] and not details["activity_types"]:
        questions.append("Would you prefer food, sport, outdoors, or another activity?")
    candidates = []
    if brief and not any("duration exceeds" in q for q in questions):
        for e in select_opportunities(brief, opportunities, now=now, food_only=intent == "find_campus_food"):
            # A partial event overlap does not establish that a whole plan fits.
            if instant(e["start_at"]) < instant(brief["availability_start"]) or instant(e["end_at"]) > instant(brief["availability_end"]):
                continue
            activity = details["requested_activity"]
            if activity and activity != "events" and activity not in e["title"].lower():
                continue
            candidates.append({"title": e["title"], "start_at": e["start_at"], "end_at": e["end_at"],
                               "source_url": e["source_url"], "synthetic": e["synthetic"],
                               "location": e.get("location_label"), "checked_at": e["checked_at"],
                               "status": "demo_fixture" if e["synthetic"] else "catalog_candidate",
                               "caveat": "Price, opening hours, reservations, dietary suitability and travel time require verification; timing alone does not establish feasibility."})
    ideas = []
    if not candidates:
        activity = details["requested_activity"]
        if activity == "trip" or (minutes and minutes >= 1440):
            ideas = ["Draft a two-part itinerary: travel and one main activity, then an optional overnight stay and return; confirm destination, hours, transport and accommodation before choosing dates."]
        elif activity:
            ideas = [f"Research nearby {activity} options within your time and travel limits; verify hours, price and any reservation before selecting one."]
        else:
            ideas = ["Consider a nearby coffee break or a self-guided walk; reserve time for returning. Venue hours, costs, access and travel are unverified."]
    return {"visibility": "private", "mode": "local_preview", "brief": brief,
            "details": details, "questions": questions, "candidates": candidates,
            "tentative_ideas": ideas, "scheduled": False, "booked": False,
            "backend": "not_required", "status": "clarification_needed" if questions else "preview_ready",
            "next_action": "Confirm missing constraints, then verify original sources before acting. Find a crew is optional."}
