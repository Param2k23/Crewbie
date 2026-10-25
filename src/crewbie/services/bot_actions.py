"""Use cases only the Discord bot calls. Signatures stay transport-neutral so the bot could move
to HTTP later (03-API-CONTRACT section 3)."""

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from crewbie.domain.budget import BudgetBand
from crewbie.domain.errors import EventStarted, NotFound, ValidationFailed
from crewbie.domain.intent import IntentState
from crewbie.domain.room import RoomStatus
from crewbie.domain.vibe import Vibe
from crewbie.domain.windows import TimeWindow
from crewbie.services import installs, intents, room_view
from crewbie.services._common import thread_url
from crewbie.services.context import ServiceContext
from crewbie.services.views import OfferView


@dataclass(frozen=True)
class CrewStatus:
    room_id: str
    event_title: str
    window: TimeWindow | None
    size: int
    status: str
    thread_url: str | None


@dataclass(frozen=True)
class ThreadMember:
    install_id: str
    intent_id: str
    room_id: str


@dataclass(frozen=True)
class JoinForm:
    """The Join modal, already parsed (FR-BOT-06)."""

    earliest: time
    latest: time
    minimum_minutes: int
    budget_band: BudgetBand
    vibe: Vibe


@dataclass(frozen=True)
class BoardJoinResult:
    install_id: str
    intent_id: str
    offer: OfferView


def crews_for_user(ctx: ServiceContext, discord_user_id: str) -> list[CrewStatus]:
    """The caller's current crews (`/crew status`)."""
    with ctx.uow_factory() as uow:
        link = uow.links.get_by_discord_user(discord_user_id)
        if link is None:
            return []
        crews: list[CrewStatus] = []
        for intent in uow.intents.list_for_install(
            link.install_id, frozenset({IntentState.JOINED})
        ):
            room_id = uow.rooms.current_room_id(intent.id)
            room = uow.rooms.get(room_id) if room_id else None
            event = uow.events.get(intent.event_key)
            if room is None or event is None:
                continue
            window = (
                TimeWindow(room.window_start, room.window_end)
                if room.window_start and room.window_end
                else None
            )
            crews.append(
                CrewStatus(
                    room.id, event.title, window, room.size, room.status, thread_url(ctx, room)
                )
            )
        return crews


def member_in_thread(
    ctx: ServiceContext, thread_id: str, discord_user_id: str
) -> ThreadMember | None:
    with ctx.uow_factory() as uow:
        room = uow.rooms.get_by_thread(thread_id)
        link = uow.links.get_by_discord_user(discord_user_id)
        if room is None or link is None:
            return None
        for member in uow.rooms.members(room.id):
            if member.install_id == link.install_id:
                return ThreadMember(link.install_id, member.intent_id, room.id)
    return None


def leave_thread(ctx: ServiceContext, thread_id: str, discord_user_id: str) -> bool:
    """`/crew leave` inside a room thread (FR-BOT-10). False if the caller is not a member."""
    found = member_in_thread(ctx, thread_id, discord_user_id)
    if found is None:
        return False
    intents.withdraw(ctx, found.install_id, found.intent_id)
    return True


def request_board_join(
    ctx: ServiceContext, discord_user_id: str, username: str, room_id: str, form: JoinForm
) -> BoardJoinResult:
    """Submit an intent for one board room and negotiate with that room only (FR-BOT-06)."""
    content = room_view.load_room(ctx, room_id)
    if content is None or content.window is None:
        raise NotFound("That crew is no longer open.")
    if content.status not in (RoomStatus.OPEN.value, RoomStatus.ACTIVE.value):
        raise NotFound("That crew is no longer open.")
    if ctx.clock() >= content.window.start:
        raise EventStarted("That crew's plan has already started.")

    zone = ZoneInfo(ctx.config.timezone)
    day = content.window.start.astimezone(zone).date()
    earliest = datetime.combine(day, form.earliest, tzinfo=zone)
    latest = datetime.combine(day, form.latest, tzinfo=zone)
    if latest <= earliest:
        raise ValidationFailed({"latest": "must be after the earliest start"})
    clipped = content.window.intersect(TimeWindow(earliest, latest))
    if clipped is None:
        raise ValidationFailed({"time": "your times do not overlap this crew's plan"})

    install = installs.ensure_discord_install(ctx, discord_user_id, username)
    with ctx.uow_factory() as uow:
        event = uow.events.get(content.event_key)
        if event is None:
            raise NotFound("That crew is no longer open.")
        event_input = intents.EventInput(
            source_url=event.source_url,
            title=event.title,
            date=event.date,
            start_time=event.start_time,
            end_time=event.end_time,
            location_label=event.location_label,
        )
    request = intents.SubmitIntent(
        event=event_input,
        window=clipped,
        activity_min_minutes=form.minimum_minutes,
        budget_band=form.budget_band,
        vibe=form.vibe,
        interests=(),
        flex_earliest=earliest,
        flex_latest=latest,
    )
    result = intents.submit(ctx, install.install_id, request, only_room_id=room_id)
    if result.offer is None:
        raise NotFound("Matching is taking longer than usual. Try again in a minute.")
    return BoardJoinResult(install.install_id, result.intent_id, result.offer)
