"""Allowlisted serializer for public-safe events (SRS 5.4). Anything else is dropped."""

from datetime import datetime
from enum import Enum
from typing import Any

from crewbie.domain.windows import TimeWindow

# Mission Control vocabulary (FR-MC-02).
EVENT_TYPES = frozenset(
    {
        "match_requested",
        "negotiation_started",
        "candidate_proposed",
        "counteroffer_proposed",
        "proposal_rejected",
        "proposal_confirmed",
        "negotiation_failed",
    }
)

ALLOWED_FIELDS = frozenset(
    {
        "room_id",
        "event_key",
        "size",
        "round",
        "proposal_window",
        "verdict",
        "actor_kind",
        "actor_ref",
        "failure_code",
    }
)


def _plain(value: Any) -> Any:
    if isinstance(value, TimeWindow):
        return {"start": value.start.isoformat(), "end": value.end.isoformat()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def public_event(event_type: str, **fields: Any) -> tuple[str, dict[str, Any]]:
    """Build (type, payload) keeping only allowlisted, non-empty fields."""
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown public event type: {event_type}")
    payload = {
        name: _plain(value)
        for name, value in fields.items()
        if name in ALLOWED_FIELDS and value is not None
    }
    return event_type, payload
