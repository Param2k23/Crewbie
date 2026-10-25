"""Messages exchanged by agents (04-AGENT-PROTOCOL section 2). There is no reason field."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from crewbie.domain.budget import BudgetBand
from crewbie.domain.intent import SharedIntent
from crewbie.domain.windows import TimeWindow


class Verdict(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    COUNTER = "counter"


@dataclass(frozen=True, slots=True)
class Proposal:
    room_id: str
    window: TimeWindow
    round: int
    from_kind: Literal["delegate", "host"]


@dataclass(frozen=True, slots=True)
class Reply:
    """A reply reveals only accept, reject, or a counter window."""

    verdict: Verdict
    counter: TimeWindow | None = None


@dataclass(frozen=True, slots=True)
class Step:
    """One recorded evaluation. `proposal` is the window that was evaluated, never a flex bound."""

    round: int
    actor_kind: Literal["delegate", "host", "matcher"]
    actor_ref: str
    proposal: TimeWindow | None
    verdict: Verdict


@dataclass(frozen=True, slots=True, repr=False)
class DelegateProfile:
    """What one delegate knows about its student. `flex` is private: never log or return it."""

    shared: SharedIntent
    flex: TimeWindow

    def __repr__(self) -> str:
        return "DelegateProfile(<redacted>)"

    @property
    def minimum_minutes(self) -> int:
        return self.shared.activity_min_minutes

    @property
    def budget_band(self) -> BudgetBand:
        return self.shared.budget_band
