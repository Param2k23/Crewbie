from datetime import UTC, datetime, timedelta

from crewbie.domain.budget import BudgetBand
from crewbie.domain.room import MemberState
from crewbie.domain.vibe import Vibe
from crewbie.domain.windows import TimeWindow

BASE = datetime(2026, 11, 6, 16, 0, tzinfo=UTC)


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def window(start_min: int, end_min: int) -> TimeWindow:
    return TimeWindow(at(start_min), at(end_min))


def member(
    alias: str = "member-1",
    start: int = 0,
    end: int = 120,
    band: BudgetBand = BudgetBand.MID,
    vibe: Vibe = Vibe.CHILL,
    interests: tuple[str, ...] = (),
    joined: int = 0,
) -> MemberState:
    return MemberState(alias, window(start, end), band, vibe, interests, at(-1000 + joined))
