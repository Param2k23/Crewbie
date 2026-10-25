"""Recognising that two students mean the same event even when their searches found different pages.

The event key stays exact (FR-EVT-01). This module only ranks *candidates* for a person to confirm:
it never merges anything by itself.
"""

import re
from dataclasses import dataclass
from datetime import time

_STOP_TITLE = frozenset(
    {"the", "a", "an", "at", "in", "on", "of", "and", "for", "to", "with", "by", "tonight", "today",
     "showing", "screening", "imax", "3d", "2d", "pg", "pg13", "nr", "r"}
)  # fmt: skip
_CITIES = frozenset(
    {"tempe", "phoenix", "mesa", "chandler", "scottsdale", "glendale", "az", "arizona"}
)
# Generic words that describe any venue and say nothing about which one it is.
_STOP_PLACE = frozenset(
    {"the", "a", "an", "at", "of", "and", "campus", "st", "street", "ave", "avenue", "rd", "road",
     "blvd", "dr", "drive", "e", "w", "n", "s", "library", "theater", "theatre", "cinema",
     "cinemas", "movie", "movies", "center", "centre", "hall", "building", "room"}
)  # fmt: skip
_YEAR = re.compile(r"^(19|20)\d\d$")
_WORDS = re.compile(r"[a-z0-9]+")

MAX_START_GAP_MINUTES = 30
MIN_TITLE_SCORE = 0.6
MIN_TOTAL_SCORE = 0.65
MIN_PLACE_OVERLAP = 0.5


@dataclass(frozen=True, slots=True)
class EventDescriptor:
    title: str
    date: str
    start_time: str | None = None
    location_label: str | None = None


def _tokens(text: str, stop: frozenset[str], drop_years: bool) -> frozenset[str]:
    words = _WORDS.findall(text.lower())
    kept = {
        w for w in words
        if w not in stop and (len(w) > 1 or w.isdigit()) and not (drop_years and _YEAR.match(w))
    }  # fmt: skip
    return frozenset(kept)


def _overlap(a: frozenset[str], b: frozenset[str]) -> tuple[float, float]:
    """(Jaccard, containment of the smaller set) of two token sets."""
    if not a or not b:
        return 0.0, 0.0
    shared = len(a & b)
    return shared / len(a | b), shared / min(len(a), len(b))


def title_score(a: str, b: str) -> float:
    """1.0 for the same words; a title that contains the other's words scores 0.9."""
    jaccard, containment = _overlap(_tokens(a, _STOP_TITLE, True), _tokens(b, _STOP_TITLE, True))
    return max(jaccard, 0.9 * containment)


def _minutes(value: str) -> int | None:
    try:
        parsed = time.fromisoformat(value)
    except ValueError:
        return None
    return parsed.hour * 60 + parsed.minute


def match_score(query: EventDescriptor, candidate: EventDescriptor) -> float | None:
    """How likely two descriptions are the same event, or None if they cannot be.

    Hard rules: the same date; start times within 30 minutes when both are known; places that
    share a distinctive word and half of the smaller place's words when both are known; and a
    clear title match.
    """
    if query.date != candidate.date:
        return None
    title = title_score(query.title, candidate.title)
    if title < MIN_TITLE_SCORE:
        return None

    time_part = 0.5  # unknown start time on either side
    if query.start_time and candidate.start_time:
        a, b = _minutes(query.start_time), _minutes(candidate.start_time)
        if a is not None and b is not None:
            gap = abs(a - b)
            if gap > MAX_START_GAP_MINUTES:
                return None
            time_part = 1 - gap / (2 * MAX_START_GAP_MINUTES)

    place_part = 0.5  # unknown place on either side
    if query.location_label and candidate.location_label:
        a_tokens = _tokens(query.location_label, _STOP_PLACE, False)
        b_tokens = _tokens(candidate.location_label, _STOP_PLACE, False)
        if a_tokens and b_tokens:
            _, containment = _overlap(a_tokens, b_tokens)
            # Sharing only a city name ("Tempe") does not make two venues the same place.
            if containment < MIN_PLACE_OVERLAP or not (a_tokens & b_tokens) - _CITIES:
                return None
            place_part = containment

    total = 0.6 * title + 0.25 * place_part + 0.15 * time_part
    return total if total >= MIN_TOTAL_SCORE else None
