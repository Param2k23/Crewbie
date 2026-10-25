"""Per-room locks (02-ARCHITECTURE section 6): matching and accepting a room do not interleave.

The `room.version` check at accept time stays the correctness guarantee; these locks only keep
well-behaved concurrent requests from producing stale offers.
"""

import threading
from collections.abc import Iterable, Iterator
from contextlib import contextmanager


class RoomLocks:
    def __init__(self) -> None:
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def _lock_for(self, room_id: str) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(room_id, threading.Lock())

    @contextmanager
    def hold(self, room_ids: Iterable[str]) -> Iterator[None]:
        """Hold all the given rooms, always acquired in sorted order so callers cannot deadlock."""
        ordered = [self._lock_for(room_id) for room_id in sorted(set(room_ids))]
        for lock in ordered:
            lock.acquire()
        try:
            yield
        finally:
            for lock in reversed(ordered):
                lock.release()
