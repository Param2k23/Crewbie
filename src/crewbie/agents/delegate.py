"""Delegate agent: the deterministic guard plus a pluggable chooser (protocol sections 3 and 4).

The guard is the only thing that can turn a decision into an `accept`, so no chooser, including a
future LLM, can accept a proposal outside the student's private limits (P-1).
"""

from datetime import timedelta
from typing import Protocol

from crewbie.agents.protocol import DelegateProfile, Proposal, Reply, Verdict
from crewbie.domain.budget import BudgetBand, bands_compatible
from crewbie.domain.windows import TimeWindow, ceil_to_grid, floor_to_grid


def allowed(profile: DelegateProfile, window: TimeWindow, room_band: BudgetBand) -> bool:
    """The guard: inside flex, long enough, and a compatible budget band."""
    return (
        profile.flex.contains(window)
        and window.duration >= timedelta(minutes=profile.minimum_minutes)
        and bands_compatible(profile.budget_band, room_band)
    )


def closest_allowed(
    profile: DelegateProfile,
    target: TimeWindow,
    room_band: BudgetBand,
    at_least_minutes: int | None = None,
) -> TimeWindow | None:
    """The allowed window nearest to `target`, or None when no allowed window exists.

    Bounds are snapped inward to a 15-minute grid, so a counter never states the student's exact
    flex limit (replies are shared with the other side and with Mission Control).
    """
    if not bands_compatible(profile.budget_band, room_band):
        return None
    minimum = timedelta(minutes=max(profile.minimum_minutes, at_least_minutes or 0))
    low, high = ceil_to_grid(profile.flex.start), floor_to_grid(profile.flex.end)
    if high - low < minimum:
        return None
    clipped = target.intersect(TimeWindow(low, high))
    if clipped is not None and clipped.duration >= minimum:
        return clipped
    midpoint = target.start + target.duration / 2
    start = min(max(midpoint - minimum / 2, low), high - minimum)
    start = max(floor_to_grid(start), low)
    return TimeWindow(start, start + minimum)


class Chooser(Protocol):
    """Picks a verdict for a proposal. The guard checks whatever it returns."""

    def choose(
        self, profile: DelegateProfile, proposal: Proposal, room_band: BudgetBand
    ) -> Reply: ...


class DeterministicChooser:
    def choose(self, profile: DelegateProfile, proposal: Proposal, room_band: BudgetBand) -> Reply:
        if allowed(profile, proposal.window, room_band):
            return Reply(Verdict.ACCEPT)
        counter = closest_allowed(profile, proposal.window, room_band)
        if counter is None:
            return Reply(Verdict.REJECT)
        return Reply(Verdict.COUNTER, counter)


class DelegatePolicy:
    def __init__(self, profile: DelegateProfile, chooser: Chooser | None = None) -> None:
        self._profile = profile
        self._chooser = chooser or DeterministicChooser()
        self._fallback = DeterministicChooser()

    @property
    def minimum_minutes(self) -> int:
        return self._profile.minimum_minutes

    def evaluate(self, proposal: Proposal, room_band: BudgetBand) -> Reply:
        """Decide on a proposal; the result is safe for this student whatever the chooser said."""
        reply = self._chooser.choose(self._profile, proposal, room_band)
        if reply.verdict is Verdict.ACCEPT and allowed(self._profile, proposal.window, room_band):
            return reply
        if (
            reply.verdict is Verdict.COUNTER
            and reply.counter is not None
            and allowed(self._profile, reply.counter, room_band)
        ):
            return reply
        if reply.verdict is Verdict.REJECT:
            return reply
        # An unsafe accept or counter is replaced by the deterministic decision.
        return self._fallback.choose(self._profile, proposal, room_band)

    def initial_proposal(
        self, room_id: str, room_window: TimeWindow, required_minutes: int, room_band: BudgetBand
    ) -> Proposal | None:
        """The joiner opening offer (protocol section 4); None when no allowed window exists."""
        profile = self._profile
        overlap = profile.shared.window.intersect(room_window)
        if overlap is not None and overlap.duration >= timedelta(minutes=profile.minimum_minutes):
            window = overlap if allowed(profile, overlap, room_band) else None
            window = window or closest_allowed(profile, overlap, room_band)
        else:
            # Too little overlap: ask for a window near the room's, long enough for everyone.
            length = timedelta(minutes=max(profile.minimum_minutes, required_minutes))
            middle = room_window.start + room_window.duration / 2
            wanted = TimeWindow(middle - length / 2, middle + length / 2)
            window = closest_allowed(
                profile, wanted, room_band, at_least_minutes=required_minutes
            ) or closest_allowed(profile, wanted, room_band)
        if window is None or not allowed(profile, window, room_band):
            return None
        return Proposal(room_id, window, 1, "delegate")
