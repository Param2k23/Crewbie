"""Read-only view of a room handed to the matcher. Built by services, never by the matcher."""

from dataclasses import dataclass
from datetime import datetime

from crewbie.agents.protocol import DelegateProfile
from crewbie.domain.budget import BudgetBand
from crewbie.domain.room import MemberState, RoomStatus
from crewbie.domain.vibe import Vibe
from crewbie.domain.windows import TimeWindow


@dataclass(frozen=True, slots=True)
class MemberSnapshot:
    alias: str
    state: MemberState
    profile: DelegateProfile


@dataclass(frozen=True, slots=True)
class RoomSnapshot:
    room_id: str
    event_key: str
    version: int
    created_at: datetime
    status: RoomStatus
    window: TimeWindow | None
    budget_band: BudgetBand | None
    vibe: Vibe | None
    top_interests: tuple[str, ...]
    members: tuple[MemberSnapshot, ...]
    next_alias: str

    @property
    def size(self) -> int:
        return len(self.members)
