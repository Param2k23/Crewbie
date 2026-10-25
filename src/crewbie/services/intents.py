"""Submitting, reading and withdrawing intents (FR-INT-*)."""

import logging
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
from crewbie.domain.offer import OfferState
from crewbie.domain.text import LOCATION_MAX, TITLE_MAX, sanitize_required_text, sanitize_text
from crewbie.domain.vibe import Vibe
from crewbie.domain.windows import TimeWindow
from crewbie.persistence.tables import IntentRow
from crewbie.persistence.unit_of_work import UnitOfWork
from crewbie.services import matchmaking, rooms
from crewbie.services._common import (
    thread_url,
)
from crewbie.services.context import ServiceContext
from crewbie.services.views import IntentView, SubmitResult

logger = logging.getLogger("crewbie.intents")
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


def submit(
    ctx: ServiceContext,
    install_id: str,
    request: SubmitIntent,
    only_room_id: str | None = None,
) -> SubmitResult:
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
        uow.intents.add(intent_id, install_id, shared, envelope, created_at=now)
        uow.commit()

    # Matching runs after the intent is safely stored. If it fails the intent stays in
    # `matching` and the background sweep retries it (FR-INT-04).
    try:
        offer = matchmaking.run(ctx, intent_id, only_room_id)
    except Exception:
        logger.exception("matching failed", extra={"intent_id": intent_id})
        offer = None
    state = IntentState.OFFERED if offer else IntentState.MATCHING
    return SubmitResult(intent_id, state.value, offer)


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
