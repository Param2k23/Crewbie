"""Sanitising of untrusted display text (FR-EVT-03)."""

import unicodedata

from crewbie.domain.errors import ValidationFailed

TITLE_MAX = 120
LOCATION_MAX = 120


def sanitize_text(value: str, max_length: int) -> str:
    """Strip control and format characters (including newlines) and trim to `max_length`."""
    cleaned = "".join(
        " " if ch.isspace() else ch
        for ch in value
        if not unicodedata.category(ch).startswith("C") or ch.isspace()
    )
    return " ".join(cleaned.split())[:max_length].strip()


def sanitize_required_text(field: str, value: str, max_length: int) -> str:
    cleaned = sanitize_text(value, max_length)
    if not cleaned:
        raise ValidationFailed({field: "must not be empty"})
    return cleaned
