"""Server-Sent Events framing and the generator shared by every HTTP front end."""
from __future__ import annotations

import json
import threading
from typing import Any, Iterator, Mapping

from .sink import MemoryEventSink

RETRY_MS = 2000
KEEPALIVE_SECONDS = 15.0


def format_sse(event: Mapping[str, Any]) -> bytes:
    data = json.dumps(event, separators=(",", ":"), ensure_ascii=True)
    return f"id: {event['event_id']}\nevent: agent_event\ndata: {data}\n\n".encode()


def stream_session(
    sink: MemoryEventSink,
    session_id: str,
    last_event_id: str | None = None,
    stop: threading.Event | None = None,
    keepalive: float = KEEPALIVE_SECONDS,
) -> Iterator[bytes]:
    """Yield SSE frames forever (until ``stop``). Read-only: nothing here can write to the sink."""
    yield f"retry: {RETRY_MS}\n\n".encode()
    cursor = last_event_id
    while not (stop and stop.is_set()):
        batch = sink.read_after(session_id, cursor, timeout=keepalive)
        if not batch:
            yield b": keep-alive\n\n"
            continue
        for e in batch:
            yield format_sse(e)
        cursor = batch[-1]["event_id"]
