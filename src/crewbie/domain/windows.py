"""TimeWindow value object: overlap, intersect, hull, duration."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from crewbie.domain.errors import ValidationFailed


@dataclass(frozen=True, slots=True)
class TimeWindow:
    """Half-open interval [start, end). Windows that only touch do not overlap."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValidationFailed({"window": "datetimes must include a UTC offset"})
        if self.start >= self.end:
            raise ValidationFailed({"window": "start must be before end"})

    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    def overlaps(self, other: "TimeWindow") -> bool:
        return self.start < other.end and other.start < self.end

    def intersect(self, other: "TimeWindow") -> "TimeWindow | None":
        if not self.overlaps(other):
            return None
        return TimeWindow(max(self.start, other.start), min(self.end, other.end))

    def hull(self, other: "TimeWindow") -> "TimeWindow":
        """Smallest window containing both."""
        return TimeWindow(min(self.start, other.start), max(self.end, other.end))

    def contains(self, other: "TimeWindow") -> bool:
        return self.start <= other.start and other.end <= self.end


def intersect_all(windows: Iterable[TimeWindow]) -> TimeWindow | None:
    """Intersection of every window; None when there are none or they share no time."""
    result: TimeWindow | None = None
    for index, window in enumerate(windows):
        if index == 0:
            result = window
            continue
        assert result is not None
        result = result.intersect(window)
        if result is None:
            return None
    return result


GRID_MINUTES = 15
_GRID_SECONDS = GRID_MINUTES * 60


def floor_to_grid(moment: datetime) -> datetime:
    """Round down to a 15-minute boundary (UTC-aligned, which matches every common offset)."""
    seconds = int(moment.timestamp())
    return datetime.fromtimestamp(seconds - seconds % _GRID_SECONDS, tz=moment.tzinfo)


def ceil_to_grid(moment: datetime) -> datetime:
    """Round up to a 15-minute boundary."""
    floored = floor_to_grid(moment)
    return floored if floored == moment else floored + timedelta(minutes=GRID_MINUTES)
