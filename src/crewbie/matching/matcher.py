"""The matcher: candidate selection, bounded negotiation and offer choice (FR-MAT-*).

Pure with respect to storage. Services hand it a snapshot and persist what it returns.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from crewbie.agents.delegate import Chooser, DelegatePolicy
from crewbie.agents.host import HostPolicy
from crewbie.agents.protocol import DelegateProfile
from crewbie.domain.offer import OfferType
from crewbie.domain.room import MemberState, state_after_join
from crewbie.domain.windows import TimeWindow
from crewbie.matching.negotiation import NegotiationResult, run_negotiation
from crewbie.matching.prescore import post_score, rank_candidates
from crewbie.matching.snapshot import RoomSnapshot


@dataclass(frozen=True, slots=True)
class MatchRequest:
    intent_id: str
    event_key: str
    joiner: DelegateProfile
    rooms: tuple[RoomSnapshot, ...]
    now: datetime


@dataclass(frozen=True, slots=True)
class MatchResult:
    offer_type: OfferType
    proposal: TimeWindow
    room_id: str | None = None
    room_version: int | None = None
    window_changed_for_room: bool = False
    negotiations: tuple[NegotiationResult, ...] = ()


class Matcher(Protocol):
    def match(self, request: MatchRequest) -> MatchResult: ...


class DeterministicMatcher:
    """FR-MAT-03: at most `max_candidates` rooms, `max_rounds` rounds each, within a time budget."""

    def __init__(
        self,
        *,
        max_candidates: int = 3,
        max_rounds: int = 3,
        time_budget_seconds: float = 10.0,
        chooser: Chooser | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_candidates = max_candidates
        self._max_rounds = max_rounds
        self._budget = time_budget_seconds
        self._chooser = chooser
        self._monotonic = monotonic

    def match(self, request: MatchRequest) -> MatchResult:
        started = self._monotonic()
        shared = request.joiner.shared
        candidates = rank_candidates(shared, request.rooms, request.now, self._max_candidates)
        negotiations: list[NegotiationResult] = []
        agreements: list[tuple[RoomSnapshot, NegotiationResult, TimeWindow]] = []
        for room in candidates:
            if self._monotonic() - started > self._budget:
                break  # stop starting new negotiations; keep what we have
            result = self._negotiate(request, room)
            negotiations.append(result)
            if result.outcome == "agreed" and result.agreed is not None:
                agreements.append((room, result, result.agreed))
        if not agreements:
            return MatchResult(OfferType.NEW_ROOM, shared.window, negotiations=tuple(negotiations))
        # FR-MAT-08: best post-negotiation score, then larger room, then older room.
        room, _, agreed = min(
            agreements,
            key=lambda a: (
                -post_score(shared, a[0], a[2]),
                -a[0].size,
                a[0].created_at,
                a[0].room_id,
            ),
        )
        return MatchResult(
            OfferType.JOIN,
            agreed,
            room.room_id,
            room.version,
            self._window_changes(request, room, agreed),
            tuple(negotiations),
        )

    def _negotiate(self, request: MatchRequest, room: RoomSnapshot) -> NegotiationResult:
        assert room.window is not None and room.budget_band is not None
        joiner = DelegatePolicy(request.joiner, self._chooser)
        host = HostPolicy(
            [(m.alias, DelegatePolicy(m.profile, self._chooser)) for m in room.members],
            room.budget_band,
        )
        opening = joiner.initial_proposal(
            room.room_id, room.window, host.required_minutes, room.budget_band
        )
        result = run_negotiation(
            room_id=room.room_id,
            room_band=room.budget_band,
            joiner=joiner,
            joiner_ref=room.next_alias,
            host=host,
            opening=opening,
            max_rounds=self._max_rounds,
        )
        if result.agreed is not None and self._window_after(request, room, result.agreed) is None:
            return NegotiationResult(
                room.room_id, "failed", None, result.rounds, result.opening, result.joiner_ref,
                result.steps, "no_common_window",
            )  # fmt: skip
        return result

    def _window_after(
        self, request: MatchRequest, room: RoomSnapshot, agreed: TimeWindow
    ) -> TimeWindow | None:
        joiner = MemberState(
            room.next_alias,
            request.joiner.shared.window,
            request.joiner.shared.budget_band,
            request.joiner.shared.vibe,
            request.joiner.shared.interests,
            request.now,
        )
        return state_after_join([m.state for m in room.members], joiner, agreed).window

    def _window_changes(
        self, request: MatchRequest, room: RoomSnapshot, agreed: TimeWindow
    ) -> bool:
        return self._window_after(request, room, agreed) != room.window
