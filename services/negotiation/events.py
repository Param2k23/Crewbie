"""Privacy-safe AgentEvent construction.

Every event type has an explicit payload key whitelist and values are limited to short
scalars. Building an event outside the whitelist raises: it is a programming error, not
something to emit "just in case".
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional

from .protocols import EventSink

ACTOR = "coordination_engine"

PAYLOAD_KEYS: Mapping[str, frozenset] = {
    "negotiation_started": frozenset({"group_size"}),
    "candidate_proposed": frozenset({"plan_id", "version"}),
    "proposal_rejected": frozenset({"plan_id", "version", "reason_category"}),
    "counteroffer_proposed": frozenset({"plan_id", "version", "derived_from_version", "summary"}),
    "fairness_evaluated": frozenset({"plan_id", "version", "rank", "feasible_count", "balance"}),
    "proposal_ready": frozenset({"plan_id", "version", "approval_state"}),
    "approval_requested": frozenset({"plan_id", "version", "required_count"}),
    "proposal_confirmed": frozenset({"plan_id", "version", "accepted_count", "required_count"}),
    "proposal_revised": frozenset(
        {"previous_plan_id", "previous_version", "version", "reason_category", "approvals_reset"}
    ),
    "negotiation_failed": frozenset({"error_code", "reason_category", "candidates_evaluated", "rounds"}),
    "session_completed": frozenset({"outcome"}),
}
_SAFE_STR = re.compile(r"^[A-Za-z0-9_ .,:\-()']{0,120}$")


class SystemClock:
    def now_iso(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def monotonic(self) -> float:
        return time.monotonic()


class SteppingClock:
    """Deterministic clock: each ``now_iso`` call advances ``step_s`` seconds (repeatable demo traces)."""

    def __init__(self, start: str = "2026-10-24T18:01:00Z", step_s: int = 1) -> None:
        self._t = datetime.fromisoformat(start.replace("Z", "+00:00"))
        self._step = timedelta(seconds=step_s)
        self._mono = 0.0

    def now_iso(self) -> str:
        t = self._t
        self._t += self._step
        return t.strftime("%Y-%m-%dT%H:%M:%SZ")

    def monotonic(self) -> float:
        return self._mono

    def advance(self, seconds: float) -> None:  # test hook for timeout behaviour
        self._mono += seconds


class MemoryEventSink:
    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []

    def emit(self, event: Mapping[str, Any]) -> None:
        self.events.append(dict(event))

    def types(self) -> List[str]:
        return [e["type"] for e in self.events]


def build_event(*, session_id: str, seq: int, timestamp: str, type_: str, payload: Mapping[str, Any],
                synthetic: bool = True) -> Dict[str, Any]:
    allowed = PAYLOAD_KEYS.get(type_)
    if allowed is None:
        raise ValueError(f"event type {type_!r} is not an allowed public type")
    extra = set(payload) - allowed
    if extra:
        raise ValueError(f"payload keys {sorted(extra)} not whitelisted for {type_}")
    for key, value in payload.items():
        if value is not None and not isinstance(value, (str, int, bool)):
            raise ValueError(f"payload value for {key} must be a scalar")
        if isinstance(value, str) and not _SAFE_STR.match(value):
            raise ValueError(f"payload string for {key} contains disallowed characters")
    return {
        "event_id": f"ev_{seq:04d}",
        "session_id": session_id,
        "timestamp": timestamp,
        "type": type_,
        "actor_ref": ACTOR,
        "visibility": "group_safe",
        "payload": dict(payload),
        "synthetic": synthetic,
    }
