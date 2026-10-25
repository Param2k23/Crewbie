"""In-memory token buckets (FR-INS-04). Fine for one process; swap for Redis if we scale out."""

import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from crewbie.domain.errors import RateLimited


@dataclass(frozen=True)
class RateLimits:
    requests_per_minute: int = 30
    registrations_per_hour: int = 10


class TokenBucketLimiter:
    def __init__(
        self, capacity: int, per_seconds: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._capacity = capacity
        self._refill_per_second = capacity / per_seconds
        self._clock = clock
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        """Spend one token for `key` or raise `RateLimited` with a Retry-After hint."""
        now = self._clock()
        with self._lock:
            tokens, last = self._buckets.get(key, (float(self._capacity), now))
            tokens = min(self._capacity, tokens + (now - last) * self._refill_per_second)
            if tokens < 1:
                self._buckets[key] = (tokens, now)
                wait = math.ceil((1 - tokens) / self._refill_per_second)
                raise RateLimited("Too many requests.", {"retry_after": wait})
            self._buckets[key] = (tokens - 1, now)
