"""Room derivation (SRS 5.3) and lifecycle."""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from crewbie.domain.budget import BudgetBand, most_constrained
from crewbie.domain.intent import MAX_INTERESTS
from crewbie.domain.vibe import Vibe
from crewbie.domain.windows import TimeWindow, intersect_all

CLOSE_AFTER_WINDOW_END = timedelta(hours=2)
ARCHIVE_AFTER_WINDOW_END = timedelta(hours=24)


class RoomStatus(StrEnum):
    OPEN = "open"
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class MemberState:
    """What room derivation needs to know about one current member."""

    alias: str
    effective_window: TimeWindow
    budget_band: BudgetBand
    vibe: Vibe
    interests: tuple[str, ...]
    joined_at: datetime


@dataclass(frozen=True, slots=True)
class RoomState:
    size: int
    window: TimeWindow | None
    budget_band: BudgetBand | None
    vibe: Vibe | None
    top_interests: tuple[str, ...]
    status: RoomStatus


def extend_effective_window(current: TimeWindow, accepted: TimeWindow) -> TimeWindow:
    """A member's effective window grows to include any proposal their delegate accepted."""
    return current.hull(accepted)


def _derive_vibe(members: Sequence[MemberState]) -> Vibe | None:
    if not members:
        return None
    counts = Counter(member.vibe for member in members)
    top = max(counts.values())
    tied = {vibe for vibe, count in counts.items() if count == top}
    # Ties go to the vibe held by the earliest-joined member among the tied vibes.
    return min((m for m in members if m.vibe in tied), key=lambda m: (m.joined_at, m.alias)).vibe


def _derive_interests(members: Sequence[MemberState]) -> tuple[str, ...]:
    counts = Counter(slug for member in members for slug in set(member.interests))
    ranked = sorted(counts, key=lambda slug: (-counts[slug], slug))
    return tuple(ranked[:MAX_INTERESTS])


def derive_room_state(members: Sequence[MemberState]) -> RoomState:
    """Recompute shared room fields from current members; rooms are never edited directly."""
    size = len(members)
    status = RoomStatus.CLOSED if size == 0 else RoomStatus.OPEN if size == 1 else RoomStatus.ACTIVE
    return RoomState(
        size=size,
        window=intersect_all(m.effective_window for m in members),
        budget_band=most_constrained(m.budget_band for m in members),
        vibe=_derive_vibe(members),
        top_interests=_derive_interests(members),
        status=status,
    )


def lifecycle_status(
    derived: RoomStatus, current: RoomStatus, window_end: datetime | None, now: datetime
) -> RoomStatus:
    """Combine membership-derived status with time-based closing and archiving (FR-ROM-03)."""
    if current is RoomStatus.ARCHIVED:
        return RoomStatus.ARCHIVED
    if window_end is not None and now >= window_end + ARCHIVE_AFTER_WINDOW_END:
        return RoomStatus.ARCHIVED
    if current is RoomStatus.CLOSED or derived is RoomStatus.CLOSED:
        return RoomStatus.CLOSED
    if window_end is not None and now >= window_end + CLOSE_AFTER_WINDOW_END:
        return RoomStatus.CLOSED
    return derived
