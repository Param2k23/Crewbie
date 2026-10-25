"""Event emission for the three public event types A5 owns."""
from __future__ import annotations

from typing import Any, Mapping, Protocol


class EventSink(Protocol):
    def emit(self, event: Mapping[str, Any]) -> None: ...


class MemoryEventSink:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def emit(self, event: Mapping[str, Any]) -> None:
        self.events.append(dict(event))

    def of_type(self, type_: str) -> list[dict]:
        return [e for e in self.events if e["type"] == type_]


class CommitmentListener(Protocol):
    """Structured callbacks for A4 / the integrator (no reasons, no free text)."""

    def on_commitment_event(self, event: Mapping[str, Any]) -> None: ...


class MemoryListener:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def on_commitment_event(self, event: Mapping[str, Any]) -> None:
        self.events.append(dict(event))

    def of_kind(self, kind: str) -> list[dict]:
        return [e for e in self.events if e["kind"] == kind]


PUBLIC_TYPES = {
    "approval_requested": {"plan_id", "version", "required_count"},
    "member_response_received": {"plan_id", "version", "member_ref", "state"},
    "proposal_confirmed": {"plan_id", "version", "required_count", "accepted_count"},
}


def build_event(seq: int, session_id: str, timestamp: str, type_: str, payload: dict, synthetic: bool) -> dict:
    allowed = PUBLIC_TYPES[type_]  # KeyError => not an A5 event type
    extra = set(payload) - allowed
    if extra:
        raise ValueError(f"payload keys not allowed for {type_}: {sorted(extra)}")
    return {
        "event_id": f"ev_a5_{seq:04d}",
        "session_id": session_id,
        "timestamp": timestamp,
        "type": type_,
        "actor_ref": "group_host",
        "visibility": "group_safe",
        "payload": payload,
        "synthetic": synthetic,
    }
