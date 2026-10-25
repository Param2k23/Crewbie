"""Submitting, reading and withdrawing intents (FR-INT-*)."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from crewbie.domain.budget import BudgetBand
from crewbie.domain.errors import AlreadyInRoom, NotFound, RateLimited
from crewbie.domain.event_key import event_key
from crewbie.domain.intent import (
    IntentState,
    PrivateEnvelope,
    SharedIntent,
    ensure_transition,
    validate_intent,
)
from crewbie.domain.offer import OfferState, OfferType, offer_expiry
from crewbie.domain.text import LOCATION_MAX, TITLE_MAX, sanitize_required_text, sanitize_text
from crewbie.domain.vibe import Vibe
from crewbie.domain.windows import TimeWindow
from crewbie.matching.matcher import MatchRequest
from crewbie.persistence.tables import IntentRow
from crewbie.persistence.unit_of_work import UnitOfWork
from crewbie.services import rooms
from crewbie.services._common import (
    add_update,
    shared_from_row,
    summarize_room,
    thread_url,
)
from crewbie.services.context import ServiceContext
from crewbie.services.views import IntentView, OfferView, SubmitResult

MAX_SUBMISSIONS_PER_EVENT_PER_DAY = 5  # FR-INT-05


@dataclass(frozen=True)
class EventInput:
    source_url: str
    title: str
    date: str
    start_time: str | None = None
    end_time: str | None = None
    location_label: str | None = None


@dataclass(frozen=True)
class SubmitIntent:
    event: EventInput
    window: TimeWindow
    activity_min_minutes: int
    budget_band: BudgetBand
    vibe: Vibe
    interests: tuple[str, ...]
    flex_earliest: datetime
    flex_latest: datetime
    budget_cap_usd: float | None = None


def submit(ctx: ServiceContext, install_id: str, request: SubmitIntent) -> SubmitResult:
    """Validate, store and match an intent; returns the offer made within the time budget."""
    now = ctx.clock()
    event = request.event
    key = event_key(event.source_url, event.date, event.start_time)
    shared = SharedIntent(
        key, request.window, request.activity_min_minutes, request.budget_band, request.vibe,
        request.interests,
    )  # fmt: skip
    envelope = PrivateEnvelope(request.flex_earliest, request.flex_latest, request.budget_cap_usd)
    validate_intent(shared, envelope, now)
    title = sanitize_required_text("event.title", event.title, TITLE_MAX)
    location = sanitize_text(event.location_label or "", LOCATION_MAX) or None

    with ctx.uow_factory() as uow:
        recent = uow.intents.count_since(install_id, key, now - timedelta(hours=24))
        if recent >= MAX_SUBMISSIONS_PER_EVENT_PER_DAY:
            raise RateLimited("Too many submissions for this event today.", {"retry_after": 3600})
        _supersede_live_intent(uow, install_id, key)
        uow.events.ensure(
            key,
            source_url=event.source_url,
            title=title,
            location_label=location,
            date=event.date,
            start_time=event.start_time,
            end_time=event.end_time,
        )
        intent_id = ctx.new_id("i")
        row = uow.intents.add(intent_id, install_id, shared, envelope, created_at=now)
        offer = make_offer(ctx, uow, row)
        uow.commit()
        return SubmitResult(intent_id, IntentState.OFFERED.value, offer)


def _supersede_live_intent(uow: UnitOfWork, install_id: str, key: str) -> None:
    """FR-INT-03: a resubmission replaces an unjoined intent; a joined one blocks it."""
    existing = uow.intents.get_live(install_id, key)
    if existing is None:
        return
    if existing.state == IntentState.JOINED.value:
        raise AlreadyInRoom("You are already in a crew for this event.")
    ensure_transition(IntentState(existing.state), IntentState.WITHDRAWN)
    uow.intents.set_state(existing.id, IntentState.WITHDRAWN)
    uow.offers.close_open_for_intent(existing.id, OfferState.STALE)


def make_offer(ctx: ServiceContext, uow: UnitOfWork, intent: IntentRow) -> OfferView:
    """Run the matcher for an intent in `matching` state and store the resulting offer."""
    result = ctx.matcher.match(MatchRequest(intent.id, shared_from_row(intent)))
    now = ctx.clock()
    expires_at = offer_expiry(now, ctx.config.offer_ttl_minutes)
    offer = uow.offers.add(
        ctx.new_id("o"),
        intent.id,
        result.offer_type,
        expires_at,
        room_id=result.room_id,
        room_version=result.room_version,
        proposal=result.proposal,
    )
    ensure_transition(IntentState(intent.state), IntentState.OFFERED)
    uow.intents.set_state(intent.id, IntentState.OFFERED)
    add_update(
        uow, intent.install_id, "offer_ready", intent, offer_id=offer.id, offer_type=offer.type
    )
    room = uow.rooms.get(result.room_id) if result.room_id else None
    return OfferView(
        offer_id=offer.id,
        type=result.offer_type.value,
        expires_at=expires_at,
        room=summarize_room(room) if room and result.offer_type is OfferType.JOIN else None,
        proposal=result.proposal,
        window_changed_for_room=result.window_changed_for_room,
    )


def _owned_intent(uow: UnitOfWork, install_id: str, intent_id: str) -> IntentRow:
    row = uow.intents.get(intent_id)
    if row is None or row.install_id != install_id:
        raise NotFound("Intent not found.")
    return row


def get(ctx: ServiceContext, install_id: str, intent_id: str) -> IntentView:
    with ctx.uow_factory() as uow:
        row = _owned_intent(uow, install_id, intent_id)
        room_id = uow.rooms.current_room_id(row.id)
        room = uow.rooms.get(room_id) if room_id else None
        return IntentView(row.id, row.state, room_id, thread_url(ctx, room) if room else None)


def withdraw(ctx: ServiceContext, install_id: str, intent_id: str) -> IntentView:
    """Leave the room (if any) and stop matching. Repeating the call is harmless."""
    with ctx.uow_factory() as uow:
        row = _owned_intent(uow, install_id, intent_id)
        state = IntentState(row.state)
        if state is IntentState.JOINED:
            rooms.leave(ctx, uow, row)
        elif state in (IntentState.MATCHING, IntentState.OFFERED):
            ensure_transition(state, IntentState.WITHDRAWN)
            uow.intents.set_state(row.id, IntentState.WITHDRAWN)
            uow.offers.close_open_for_intent(row.id, OfferState.DECLINED)
        uow.commit()
        return IntentView(row.id, uow.intents.get(row.id).state, None, None)  # type: ignore[union-attr]
