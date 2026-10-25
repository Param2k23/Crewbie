"""Public-safe description of a room for Discord rendering. Never includes envelope fields."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from crewbie.domain.windows import TimeWindow
from crewbie.services._common import room_window
from crewbie.services.context import ServiceContext


@dataclass(frozen=True)
class MemberContent:
    alias: str
    install_id: str
    discord_user_id: str | None
    username: str | None
    is_synthetic: bool


@dataclass(frozen=True)
class RoomContent:
    room_id: str
    event_key: str
    status: str
    size: int
    version: int
    thread_id: str | None
    board_message_id: str | None
    event_title: str
    event_date: str
    location_label: str | None
    window: TimeWindow | None
    vibe: str | None
    budget_band: str | None
    top_interests: tuple[str, ...]
    interest_counts: dict[str, int] = field(default_factory=dict)
    members: tuple[MemberContent, ...] = ()
    created_at: datetime | None = None

    @property
    def real_members(self) -> tuple[MemberContent, ...]:
        return tuple(m for m in self.members if not m.is_synthetic)


def load_room(ctx: ServiceContext, room_id: str) -> RoomContent | None:
    with ctx.uow_factory() as uow:
        room = uow.rooms.get(room_id)
        if room is None:
            return None
        event = uow.events.get(room.event_key)
        counts: Counter[str] = Counter()
        members: list[MemberContent] = []
        for ref in uow.rooms.members(room_id):
            intent = uow.intents.get(ref.intent_id)
            if intent is not None:
                counts.update(set(intent.interests))
            link = uow.links.get_by_install(ref.install_id)
            members.append(
                MemberContent(
                    ref.alias,
                    ref.install_id,
                    link.discord_user_id if link else None,
                    link.discord_username if link else None,
                    ref.is_synthetic,
                )
            )
        return RoomContent(
            room_id=room.id,
            event_key=room.event_key,
            status=room.status,
            size=room.size,
            version=room.version,
            thread_id=room.discord_thread_id,
            board_message_id=room.board_message_id,
            event_title=event.title if event else "",
            event_date=event.date if event else "",
            location_label=event.location_label if event else None,
            window=room_window(room),
            vibe=room.vibe,
            budget_band=room.budget_band,
            top_interests=tuple(room.top_interests),
            interest_counts=dict(counts),
            members=tuple(members),
            created_at=room.created_at,
        )
