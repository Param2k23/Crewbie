"""Room discovery for Cubbie recommendations (FR-DSC-*)."""

from crewbie.domain.errors import ValidationFailed
from crewbie.domain.event_key import event_key
from crewbie.domain.event_match import EventDescriptor, match_score
from crewbie.domain.room import RoomStatus
from crewbie.domain.text import LOCATION_MAX, TITLE_MAX, sanitize_text
from crewbie.services._common import summarize_room
from crewbie.services.context import ServiceContext
from crewbie.services.views import EventCandidate, RoomSummary


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


MAX_CANDIDATES = 3


def search_events(
    ctx: ServiceContext,
    title: str,
    date: str,
    start_time: str | None = None,
    location_label: str | None = None,
    source_url: str | None = None,
) -> list[EventCandidate]:
    """Events that look like the one described and already have an open or active crew.

    Students' searches rarely land on the same web page, so the exact event key is not enough to
    find each other. This only suggests candidates; the student confirms, and the confirmed
    event's own link is then used so the keys match exactly.
    """
    query = EventDescriptor(
        sanitize_text(title, TITLE_MAX),
        date,
        start_time,
        sanitize_text(location_label or "", LOCATION_MAX) or None,
    )
    exact_key = event_key(source_url, date, start_time) if source_url else None
    now = ctx.clock()
    found: list[EventCandidate] = []
    with ctx.uow_factory() as uow:
        for event in uow.events.list_for_date(date):
            score: float | None = (
                1.0
                if event.event_key == exact_key
                else match_score(
                    query,
                    EventDescriptor(
                        event.title, event.date, event.start_time, event.location_label
                    ),
                )
            )
            if score is None:
                continue
            rooms = [
                summarize_room(room)
                for room in uow.rooms.list_for_event(
                    event.event_key, (RoomStatus.OPEN, RoomStatus.ACTIVE)
                )
                if room.window_end is None or room.window_end > now
            ]
            if rooms:
                found.append(
                    EventCandidate(
                        event.event_key, event.title, event.location_label, event.date,
                        event.start_time, event.source_url, rooms, round(score, 2),
                    )
                )  # fmt: skip
    found.sort(key=lambda c: (-c.score, -c.going, c.event_key))
    return found[:MAX_CANDIDATES]
