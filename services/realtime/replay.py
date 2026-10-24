"""Deterministic fixture replay into an EventSink (for the standalone demo and tests)."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Callable

from .sink import EventSink

DEFAULT_FIXTURE = Path(__file__).resolve().parents[2] / "docs" / "implementation" / "fixtures" / "agent_events.json"


def load_fixture_events(path: Path = DEFAULT_FIXTURE) -> list[dict]:
    return json.loads(path.read_text())["events"]


def replay(
    sink: EventSink,
    events: list[dict],
    interval: float = 1.5,
    stop: threading.Event | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Emit recorded events in order; pacing only. Returns how many were emitted."""
    n = 0
    for e in events:
        if stop and stop.is_set():
            break
        sink.emit(e)
        n += 1
        if interval:
            sleep(interval)
    return n
