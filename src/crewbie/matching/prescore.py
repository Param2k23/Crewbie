"""Deterministic candidate filtering and scoring (FR-MAT-01..03, FR-MAT-08)."""

from collections.abc import Iterable
from datetime import datetime

from crewbie.domain.budget import bands_compatible
from crewbie.domain.intent import SharedIntent
from crewbie.domain.room import RoomStatus
from crewbie.domain.windows import TimeWindow
from crewbie.matching.snapshot import RoomSnapshot


def is_candidate(joiner: SharedIntent, room: RoomSnapshot, now: datetime) -> bool:
    """FR-MAT-01 and FR-MAT-02: same event, open or active, not started, compatible budget."""
    return (
        room.event_key == joiner.event_key
        and room.status in (RoomStatus.OPEN, RoomStatus.ACTIVE)
        and room.size >= 1
        and room.window is not None
        and room.window.start > now
        and room.budget_band is not None
        and bands_compatible(joiner.budget_band, room.budget_band)
    )


def overlap_ratio(joiner_window: TimeWindow, room_window: TimeWindow) -> float:
    overlap = joiner_window.intersect(room_window)
    if overlap is None:
        return 0.0
    return overlap.duration / joiner_window.duration


def prescore(joiner: SharedIntent, room: RoomSnapshot) -> float:
    """Overlap ratio plus a vibe bonus. Higher is better."""
    assert room.window is not None
    return overlap_ratio(joiner.window, room.window) + 0.5 * (joiner.vibe == room.vibe)


def rank_candidates(
    joiner: SharedIntent, rooms: Iterable[RoomSnapshot], now: datetime, limit: int
) -> list[RoomSnapshot]:
    """Best pre-score first; ties go to the larger room, then the older one (FR-MAT-03)."""
    eligible = [room for room in rooms if is_candidate(joiner, room, now)]
    eligible.sort(key=lambda r: (-prescore(joiner, r), -r.size, r.created_at, r.room_id))
    return eligible[:limit]


def post_score(joiner: SharedIntent, room: RoomSnapshot, agreed: TimeWindow) -> float:
    """Protocol section 4: agreed share of the joiner window, vibe match, shared interests."""
    shared = len(set(joiner.interests) & set(room.top_interests))
    return (
        agreed.duration / joiner.window.duration + 0.5 * (joiner.vibe == room.vibe) + 0.1 * shared
    )
