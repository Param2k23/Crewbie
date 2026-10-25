"""Recognise planning requests in group chat (new plan, change, cancel).

Only coarse labels are extracted (activity type, timeframe words, change
aspects). Raw message text is never forwarded, so private details a student
mentions in passing cannot reach the negotiation service.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

_ACTIVITY_TYPES = (
    ("trip", r"road ?trip|trip|getaway|camping|hike|hiking|go somewhere|weekend away|fall break|spring break|winter break|over break|flagstaff"),
    ("meal", r"dinner|lunch|breakfast|brunch|coffee|boba|pizza|eat|food|meal|drinks"),
    ("game", r"badminton|tennis|basketball|soccer|volleyball|pickleball|bowling|climbing|board games?|games?|play|sports?|frisbee|golf"),
    ("event", r"concert|movie|film|show|festival|workshop|hackathon|club|museum|party"),
)
_TIMEFRAME = re.compile(
    r"\b(tonight|tomorrow|today|this weekend|next weekend|the weekend|this week|next week|this (?:mon|tues|wednes|thurs|fri|satur|sun)day"
    r"|(?:mon|tues|wednes|thurs|fri|satur|sun)day|fall break|spring break|winter break|over break)\b"
)
_NEW_CUE = re.compile(
    r"\b(anyone|anybody|who'?s|who is|we should|let'?s|should we|can we|shall we|wanna|want to|down to|are we|any plans|are you free|is anyone)\b"
)
_CHANGE_VERB = re.compile(r"\b(move|change|reschedule|postpone|push|shift|switch|swap|make it|do it)\b")
_CHANGE_TARGET = re.compile(r"\b(plan|trip|dinner|lunch|game|meetup|it|this|that|to|the|a bit|an hour)\b")
_CANCEL_GROUP = re.compile(r"\b(let'?s|should we|can we|we should|why don'?t we)\s+(cancel|call off|scrap)\b|\b(cancel|call off|scrap)\s+(the|this|our|that)\b")
_ASPECTS = (
    ("cost", r"cheap(?:er)?|cost|price|expensive|afford|less money|budget"),
    ("time", r"earlier|later|start|an hour|a bit|o'?clock|\d{1,2}\s?(?:am|pm)|morning|evening|afternoon"),
    ("date", r"(?:mon|tues|wednes|thurs|fri|satur|sun)day|weekend|tomorrow|next week|date|day"),
    ("location", r"somewhere else|different place|location|closer|farther|venue|place"),
    ("people", r"invite|bring|add|plus one|extra"),
)


@dataclass(frozen=True)
class PlanningIntent:
    kind: str  # new_plan | change_request | cancel_request | none
    activity_type: Optional[str] = None
    activity_label: Optional[str] = None
    timeframe: Optional[str] = None
    aspects: tuple = ()


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower().replace("’", "'")).strip()


def detect_activity(t: str) -> tuple[Optional[str], Optional[str]]:
    for kind, pat in _ACTIVITY_TYPES:
        m = re.search(rf"\b({pat})\b", t)
        if m:
            return kind, m.group(1)
    return None, None


def classify_planning(text: str, *, has_open_proposal: bool) -> PlanningIntent:
    """With an open proposal only change/cancel are recognised, so approvals are never mistaken for new plans."""
    t = _norm(text)
    if not t:
        return PlanningIntent("none")
    tf = _TIMEFRAME.search(t)
    timeframe = tf.group(1) if tf else None
    if has_open_proposal:
        if re.search(r"\bi\s+(?:have|need|want|got)\s+to\s+cancel\b|\bi'?m\s+cancel", t):
            return PlanningIntent("none")  # personal withdrawal, handled by the reply parser
        if _CANCEL_GROUP.search(t):
            return PlanningIntent("cancel_request")
        if _CHANGE_VERB.search(t) and _CHANGE_TARGET.search(t) and (timeframe or "?" in t or re.search(r"\b(can|could|should|what about|how about)\b", t)):
            aspects = tuple(a for a, pat in _ASPECTS if re.search(rf"\b(?:{pat})\b", t))
            return PlanningIntent("change_request", timeframe=timeframe, aspects=aspects or ("details",))
        return PlanningIntent("none")
    kind, label = detect_activity(t)
    if _NEW_CUE.search(t) and (kind or timeframe or "do something" in t or "plan" in t):
        return PlanningIntent("new_plan", kind or "other", label or "something", timeframe)
    return PlanningIntent("none")
