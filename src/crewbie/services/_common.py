"""Helpers shared by several use cases. Not part of the public service surface."""

from dataclasses import dataclass, replace
from typing import Any

from crewbie.domain.budget import BudgetBand
from crewbie.domain.intent import SharedIntent
from crewbie.domain.room import RoomState, RoomStatus, derive_room_state, lifecycle_status
from crewbie.domain.vibe import Vibe
from crewbie.domain.windows import TimeWindow
from crewbie.persistence.tables import IntentRow, RoomRow
from crewbie.persistence.unit_of_work import UnitOfWork
from crewbie.services.context import ServiceContext
from crewbie.services.views import RoomSummary


def room_window(room: RoomRow) -> TimeWindow | None:
    if room.window_start is None or room.window_end is None:
        return None
    return TimeWindow(room.window_start, room.window_end)


def summarize_room(room: RoomRow) -> RoomSummary:
    return RoomSummary(
        room_id=room.id,
        size=room.size,
        status=room.status,
        window=room_window(room),
        vibe=room.vibe,
        budget_band=room.budget_band,
        top_interests=list(room.top_interests),
    )


def thread_url(ctx: ServiceContext, room: RoomRow) -> str | None:
    if not room.discord_thread_id or not ctx.config.guild_id:
        return None
    return f"https://discord.com/channels/{ctx.config.guild_id}/{room.discord_thread_id}"


@dataclass(frozen=True)
class RoomChange:
    room: RoomRow
    state: RoomState
    old_window: TimeWindow | None

    @property
    def window_changed(self) -> bool:
        return (
            self.old_window is not None
            and self.state.window is not None
            and self.old_window != self.state.window
        )


def recompute_room(ctx: ServiceContext, uow: UnitOfWork, room_id: str) -> RoomChange:
    """Re-derive shared room fields from current members and bump the version (FR-ROM-01)."""
    room = uow.rooms.get(room_id)
    if room is None:
        raise LookupError(room_id)
    old_window = room_window(room)
    derived = derive_room_state(uow.rooms.member_states(room_id))
    end = derived.window.end if derived.window else room.window_end
    status = lifecycle_status(derived.status, RoomStatus(room.status), end, ctx.clock())
    state = replace(derived, status=status)
    return RoomChange(uow.rooms.apply_state(room_id, state), state, old_window)


def window_payload(window: TimeWindow | None) -> dict[str, str] | None:
    if window is None:
        return None
    return {"start": window.start.isoformat(), "end": window.end.isoformat()}


def add_update(
    uow: UnitOfWork, install_id: str, kind: str, intent: IntentRow, **extra: Any
) -> None:
    """Write a public-safe update (FR-UPD-01) in the caller's transaction."""
    event = uow.events.get(intent.event_key)
    payload: dict[str, Any] = {
        "intent_id": intent.id,
        "event_title": event.title if event else "",
    }
    payload.update({key: value for key, value in extra.items() if value is not None})
    uow.updates.append(install_id, kind, payload)


def enqueue(
    ctx: ServiceContext, uow: UnitOfWork, kind: str, payload: dict[str, Any], dedupe_key: str
) -> None:
    uow.outbox.enqueue(ctx.new_id("job"), kind, payload, dedupe_key, ctx.clock())


def discord_user_id_of(uow: UnitOfWork, install_id: str) -> str | None:
    link = uow.links.get_by_install(install_id)
    return link.discord_user_id if link else None


def shared_from_row(intent: IntentRow) -> SharedIntent:
    return SharedIntent(
        event_key=intent.event_key,
        window=TimeWindow(intent.window_start, intent.window_end),
        activity_min_minutes=intent.activity_min_minutes,
        budget_band=BudgetBand.parse(intent.budget_band),
        vibe=Vibe(intent.vibe),
        interests=tuple(intent.interests),
    )
