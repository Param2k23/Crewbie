"""EventSink protocol and the in-memory implementation A4/A5 can use before integration."""
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any, Mapping, Protocol

from .schema import EventRejected, validate_public_event


class EventSink(Protocol):
    def emit(self, event: Mapping[str, Any]) -> None: ...


class MemoryEventSink:
    """Validated, de-duplicated, per-session ordered event log with blocking readers.

    * ``emit`` raises :class:`EventRejected` for private/malformed events (loud producer failure);
      the rejection is also counted in ``rejected`` (codes only, never contents).
    * Duplicate ``event_id`` within a session is ignored (idempotent emit).
    * Order is arrival order per session, matching CONTRACTS.md section 4.
    """

    def __init__(self, max_events_per_session: int = 5000):
        self._cond = threading.Condition()
        self._events: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._ids: dict[str, set[str]] = defaultdict(set)
        self._max = max_events_per_session
        self.rejected: list[str] = []

    def emit(self, event: Mapping[str, Any]) -> None:
        try:
            clean = validate_public_event(event)
        except EventRejected as e:
            with self._cond:
                self.rejected.append(e.code)
            raise
        sid = clean["session_id"]
        with self._cond:
            if clean["event_id"] in self._ids[sid]:
                return
            if len(self._events[sid]) >= self._max:
                raise EventRejected("SESSION_FULL", "per-session event cap reached")
            self._ids[sid].add(clean["event_id"])
            self._events[sid].append(clean)
            self._cond.notify_all()

    def events(self, session_id: str) -> list[dict[str, Any]]:
        with self._cond:
            return list(self._events.get(session_id, ()))

    def read_after(self, session_id: str, last_event_id: str | None, timeout: float | None = None) -> list[dict[str, Any]]:
        """Events after ``last_event_id`` (all events if it is unknown). Blocks up to ``timeout`` when none."""
        with self._cond:
            def pending() -> list[dict[str, Any]]:
                evs = self._events.get(session_id, [])
                if last_event_id is None:
                    return list(evs)
                for i, e in enumerate(evs):
                    if e["event_id"] == last_event_id:
                        return list(evs[i + 1:])
                # Unknown id (e.g. server restarted): resend everything; clients de-dup by event_id.
                return list(evs)

            out = pending()
            if out or not timeout:
                return out
            self._cond.wait(timeout)
            return pending()
