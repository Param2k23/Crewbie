from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from crewbie.domain.budget import BudgetBand
from crewbie.domain.room import MemberState, RoomState, RoomStatus
from crewbie.domain.vibe import Vibe
from crewbie.domain.windows import TimeWindow
from crewbie.persistence.tables import InstallRow, IntentRow, MembershipRow, RoomRow


@dataclass(frozen=True)
class MemberRef:
    """A current member with the ids services need to notify them."""

    intent_id: str
    install_id: str
    alias: str
    is_synthetic: bool
    effective_window: TimeWindow


class RoomRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, room_id: str, event_key: str) -> RoomRow:
        row = RoomRow(id=room_id, event_key=event_key, status=RoomStatus.OPEN.value, version=1)
        self._session.add(row)
        self._session.flush()
        return row

    def get(self, room_id: str) -> RoomRow | None:
        return self._session.get(RoomRow, room_id)

    def list_for_event(
        self,
        event_key: str,
        statuses: tuple[RoomStatus, ...] = (RoomStatus.OPEN, RoomStatus.ACTIVE),
    ) -> list[RoomRow]:
        return list(
            self._session.scalars(
                select(RoomRow)
                .where(
                    RoomRow.event_key == event_key, RoomRow.status.in_([s.value for s in statuses])
                )
                .order_by(RoomRow.created_at, RoomRow.id)
            )
        )

    def add_member(
        self,
        membership_id: str,
        room_id: str,
        intent_id: str,
        effective_window: TimeWindow,
        joined_at: datetime,
    ) -> MembershipRow:
        row = MembershipRow(
            id=membership_id,
            room_id=room_id,
            intent_id=intent_id,
            alias=self._next_alias(room_id),
            effective_start=effective_window.start,
            effective_end=effective_window.end,
            joined_at=joined_at,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def _next_alias(self, room_id: str) -> str:
        """Aliases are never reused in a room, so `member-2` always means the same person."""
        count = self._session.scalar(
            select(func.count()).select_from(MembershipRow).where(MembershipRow.room_id == room_id)
        )
        return f"member-{(count or 0) + 1}"

    def set_effective_window(self, intent_id: str, window: TimeWindow) -> None:
        row = self._session.scalar(
            select(MembershipRow).where(MembershipRow.intent_id == intent_id)
        )
        if row is not None:
            row.effective_start, row.effective_end = window.start, window.end
            self._session.flush()

    def mark_left(self, intent_id: str, left_at: datetime) -> None:
        row = self._session.scalar(
            select(MembershipRow).where(MembershipRow.intent_id == intent_id)
        )
        if row is not None and row.left_at is None:
            row.left_at = left_at
            self._session.flush()

    def member_states(self, room_id: str) -> list[MemberState]:
        """Current members as domain objects, ready for `derive_room_state`."""
        rows = self._session.execute(
            select(MembershipRow, IntentRow)
            .join(IntentRow, IntentRow.id == MembershipRow.intent_id)
            .where(MembershipRow.room_id == room_id, MembershipRow.left_at.is_(None))
            .order_by(MembershipRow.joined_at, MembershipRow.alias)
        )
        return [
            MemberState(
                alias=membership.alias,
                effective_window=TimeWindow(membership.effective_start, membership.effective_end),
                budget_band=BudgetBand.parse(intent.budget_band),
                vibe=Vibe(intent.vibe),
                interests=tuple(intent.interests),
                joined_at=membership.joined_at,
            )
            for membership, intent in rows
        ]

    def apply_state(self, room_id: str, state: RoomState, *, bump_version: bool = True) -> RoomRow:
        """Persist derived fields (FR-ROM-01). Every join, leave or agreement bumps `version`."""
        row = self._session.get(RoomRow, room_id)
        if row is None:
            raise LookupError(room_id)
        row.status = state.status.value
        row.size = state.size
        row.window_start = state.window.start if state.window else None
        row.window_end = state.window.end if state.window else None
        row.budget_band = state.budget_band.label if state.budget_band is not None else None
        row.vibe = state.vibe.value if state.vibe else None
        row.top_interests = list(state.top_interests)
        if bump_version:
            row.version += 1
        self._session.flush()
        return row

    def members(self, room_id: str) -> list[MemberRef]:
        rows = self._session.execute(
            select(MembershipRow, IntentRow.install_id, InstallRow.is_synthetic)
            .join(IntentRow, IntentRow.id == MembershipRow.intent_id)
            .join(InstallRow, InstallRow.id == IntentRow.install_id)
            .where(MembershipRow.room_id == room_id, MembershipRow.left_at.is_(None))
            .order_by(MembershipRow.joined_at, MembershipRow.alias)
        )
        return [
            MemberRef(
                intent_id=m.intent_id,
                install_id=install_id,
                alias=m.alias,
                is_synthetic=synthetic,
                effective_window=TimeWindow(m.effective_start, m.effective_end),
            )
            for m, install_id, synthetic in rows
        ]

    def current_room_id(self, intent_id: str) -> str | None:
        """The room the intent currently belongs to, if it has not left."""
        return self._session.scalar(
            select(MembershipRow.room_id).where(
                MembershipRow.intent_id == intent_id, MembershipRow.left_at.is_(None)
            )
        )

    def list_all(self) -> list[RoomRow]:
        return list(self._session.scalars(select(RoomRow).order_by(RoomRow.created_at, RoomRow.id)))

    def set_thread(self, room_id: str, thread_id: str) -> None:
        row = self._session.get(RoomRow, room_id)
        if row is not None:
            row.discord_thread_id = thread_id
            self._session.flush()
