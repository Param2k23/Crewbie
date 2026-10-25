"""Room discovery for Cubbie recommendations (FR-DSC-*)."""

from crewbie.domain.errors import ValidationFailed
from crewbie.domain.event_key import event_key
from crewbie.domain.room import RoomStatus
from crewbie.services._common import summarize_room
from crewbie.services.context import ServiceContext
from crewbie.services.views import RoomSummary


def resolve_event_key(
    key: str | None, source_url: str | None, date: str | None, start_time: str | None
) -> str:
    """Accept either a known `event_key` or the fields it is computed from (FR-EVT-01)."""
    if key:
        return key
    if not source_url or not date:
        raise ValidationFailed({"event": "give event_key, or source_url and date"})
    return event_key(source_url, date, start_time)


def list_rooms(ctx: ServiceContext, key: str) -> list[RoomSummary]:
    """Open and active rooms that have not ended. Summaries carry aggregates only (FR-DSC-02)."""
    now = ctx.clock()
    with ctx.uow_factory() as uow:
        rooms = uow.rooms.list_for_event(key, (RoomStatus.OPEN, RoomStatus.ACTIVE))
        return [
            summarize_room(room)
            for room in rooms
            if room.window_end is None or room.window_end > now
        ]
