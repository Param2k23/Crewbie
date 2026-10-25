"""Matcher interface. Phase 2 ships only the stub; Phase 3 adds candidate search and negotiation."""

from dataclasses import dataclass
from typing import Protocol

from crewbie.domain.intent import SharedIntent
from crewbie.domain.offer import OfferType
from crewbie.domain.windows import TimeWindow


@dataclass(frozen=True, slots=True)
class MatchRequest:
    intent_id: str
    shared: SharedIntent


@dataclass(frozen=True, slots=True)
class MatchResult:
    offer_type: OfferType
    proposal: TimeWindow
    room_id: str | None = None
    room_version: int | None = None
    window_changed_for_room: bool = False


class Matcher(Protocol):
    def match(self, request: MatchRequest) -> MatchResult: ...


class NewRoomMatcher:
    """Always proposes a new room with the student's own window (FR-MAT-07 fallback)."""

    def match(self, request: MatchRequest) -> MatchResult:
        return MatchResult(OfferType.NEW_ROOM, request.shared.window)
