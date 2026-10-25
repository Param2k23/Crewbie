"""Accepting, declining and expiring offers (FR-OFR-*, FR-LNK-04)."""

from crewbie.domain.errors import (
    EventStarted,
    LinkRequired,
    NotFound,
    OfferClosed,
    OfferExpired,
    OfferStale,
)
from crewbie.domain.intent import IntentState, ensure_transition
from crewbie.domain.offer import (
    OfferState,
    OfferType,
    ensure_acceptable,
    ensure_not_started,
    is_expired,
)
from crewbie.domain.room import extend_effective_window
from crewbie.domain.windows import TimeWindow
from crewbie.persistence.tables import IntentRow, OfferRow
from crewbie.persistence.unit_of_work import UnitOfWork
from crewbie.services import intents, linking
from crewbie.services._common import (
    RoomChange,
    add_update,
    discord_user_id_of,
    enqueue,
    recompute_room,
    room_window,
    thread_url,
    window_payload,
)
from crewbie.services.context import ServiceContext
from crewbie.services.views import AcceptResult


def _owned_offer(uow: UnitOfWork, install_id: str, offer_id: str) -> tuple[OfferRow, IntentRow]:
    offer = uow.offers.get(offer_id)
    intent = uow.intents.get(offer.intent_id) if offer else None
    if offer is None or intent is None or intent.install_id != install_id:
        raise NotFound("Offer not found.")
    return offer, intent


def _expire(ctx: ServiceContext, uow: UnitOfWork, offer: OfferRow, intent: IntentRow) -> None:
    uow.offers.set_state(offer.id, OfferState.EXPIRED)
    if intent.state == IntentState.OFFERED.value:
        uow.intents.set_state(intent.id, IntentState.EXPIRED)
    add_update(uow, intent.install_id, "offer_expired", intent, offer_id=offer.id)


def accept(ctx: ServiceContext, install_id: str, offer_id: str) -> AcceptResult:
    now = ctx.clock()
    with ctx.uow_factory() as uow:
        offer, intent = _owned_offer(uow, install_id, offer_id)
        room = uow.rooms.get(offer.room_id) if offer.room_id else None
        try:
            ensure_acceptable(
                state=OfferState(offer.state),
                offer_type=OfferType(offer.type),
                expires_at=offer.expires_at,
                offered_room_version=offer.room_version,
                current_room_version=room.version if room else 0,
                now=now,
            )
        except OfferExpired:
            _expire(ctx, uow, offer, intent)
            uow.commit()
            raise
        except OfferStale:
            _rematch(ctx, uow, offer, intent)
            uow.commit()
            raise

        if uow.links.get_by_install(install_id) is None:
            # Commit first: the fresh code must survive the error response that carries it.
            link_code = linking.issue_code(ctx, uow, install_id)
            uow.commit()
            raise LinkRequired(
                "Link your Discord account first.",
                {
                    "link_code": link_code.code,
                    "invite_url": link_code.invite_url,
                    "expires_at": link_code.expires_at.isoformat(),
                },
            )

        if offer.type == OfferType.JOIN.value:
            assert room is not None
            try:
                result = _accept_join(ctx, uow, offer, intent, room.id)
            except OfferStale:
                uow.rollback()  # discard the half-applied join, then offer again
                offer, intent = _owned_offer(uow, install_id, offer_id)
                _rematch(ctx, uow, offer, intent)
                uow.commit()
                raise
        else:
            result = _accept_new_room(ctx, uow, offer, intent)
        uow.commit()
        return result


def _rematch(ctx: ServiceContext, uow: UnitOfWork, offer: OfferRow, intent: IntentRow) -> None:
    """FR-OFR-02: the room moved, so close this offer and make a fresh one."""
    uow.offers.set_state(offer.id, OfferState.STALE)
    ensure_transition(IntentState(intent.state), IntentState.MATCHING)
    uow.intents.set_state(intent.id, IntentState.MATCHING)
    intents.make_offer(ctx, uow, intent)


def _finish(uow: UnitOfWork, offer: OfferRow, intent: IntentRow) -> None:
    uow.offers.set_state(offer.id, OfferState.ACCEPTED)
    ensure_transition(IntentState(intent.state), IntentState.JOINED)
    uow.intents.set_state(intent.id, IntentState.JOINED)


def _result(ctx: ServiceContext, change: RoomChange) -> AcceptResult:
    room = change.room
    return AcceptResult("joined", room.id, room.size, room.status, thread_url(ctx, room))


def _accept_new_room(
    ctx: ServiceContext, uow: UnitOfWork, offer: OfferRow, intent: IntentRow
) -> AcceptResult:
    now = ctx.clock()
    window = TimeWindow(intent.window_start, intent.window_end)
    if now >= window.end:
        raise EventStarted("This plan has already ended.")
    room_id = ctx.new_id("r")
    uow.rooms.create(room_id, intent.event_key)
    uow.rooms.add_member(ctx.new_id("m"), room_id, intent.id, window, now)
    change = recompute_room(ctx, uow, room_id)
    _finish(uow, offer, intent)
    add_update(uow, intent.install_id, "joined", intent, room={"size": 1})
    enqueue(
        ctx,
        uow,
        "upsert_board_card",
        {"room_id": room_id},
        f"board:{room_id}:v{change.room.version}",
    )
    return _result(ctx, change)


def _accept_join(
    ctx: ServiceContext, uow: UnitOfWork, offer: OfferRow, intent: IntentRow, room_id: str
) -> AcceptResult:
    """FR-OFR-03: membership, windows, recompute, version bump and jobs in one transaction."""
    now = ctx.clock()
    assert offer.proposal_start is not None and offer.proposal_end is not None
    proposal = TimeWindow(offer.proposal_start, offer.proposal_end)
    current = uow.rooms.get(room_id)
    assert current is not None
    window_before = room_window(current)
    if window_before is not None:
        ensure_not_started(window_before, now)

    existing = uow.rooms.members(room_id)
    for member in existing:
        uow.rooms.set_effective_window(
            member.intent_id, extend_effective_window(member.effective_window, proposal)
        )
    own = TimeWindow(intent.window_start, intent.window_end)
    uow.rooms.add_member(
        ctx.new_id("m"), room_id, intent.id, extend_effective_window(own, proposal), now
    )
    change = recompute_room(ctx, uow, room_id)
    if change.state.window is None:
        # A negotiated proposal always fits; if not, treat it as stale rather than corrupt the room.
        raise OfferStale("The crew changed. A new offer is on its way.")
    _finish(uow, offer, intent)
    _notify_join(ctx, uow, change, intent, [m.intent_id for m in existing])
    return _result(ctx, change)


def _notify_join(
    ctx: ServiceContext,
    uow: UnitOfWork,
    change: RoomChange,
    joiner: IntentRow,
    existing_intent_ids: list[str],
) -> None:
    """Updates for students and outbox jobs for Discord (02-ARCHITECTURE section 4.4)."""
    room = change.room
    room_id = room.id
    size = change.state.size
    add_update(uow, joiner.install_id, "joined", joiner, room={"size": size})
    for intent_id in existing_intent_ids:
        other = uow.intents.get(intent_id)
        if other is None:
            continue
        add_update(uow, other.install_id, "member_joined", other, room={"size": size})
        if change.window_changed:
            add_update(
                uow, other.install_id, "window_changed", other,
                window=window_payload(change.state.window),
            )  # fmt: skip

    # Synthetic members exist only to make negotiation visible: never add or DM them.
    real = [m for m in uow.rooms.members(room_id) if not m.is_synthetic]
    if size == 2:
        enqueue(ctx, uow, "create_thread", {"room_id": room_id}, f"create_thread:{room_id}")
        for member in real:
            _enqueue_add_and_dm(
                ctx, uow, room_id, member.intent_id, member.install_id, member.alias
            )
        enqueue(
            ctx, uow, "post_message", {"room_id": room_id, "kind": "icebreaker"},
            f"post:icebreaker:{room_id}",
        )  # fmt: skip
    else:
        for member in real:
            if member.intent_id == joiner.id:
                _enqueue_add_and_dm(
                    ctx, uow, room_id, member.intent_id, member.install_id, member.alias
                )
                enqueue(
                    ctx, uow, "post_message",
                    {"room_id": room_id, "kind": "welcome", "alias": member.alias},
                    f"post:welcome:{room_id}:{joiner.id}",
                )  # fmt: skip
    if change.window_changed:
        notice = {
            "room_id": room_id,
            "kind": "window_changed",
            "window": window_payload(change.state.window),
        }
        enqueue(ctx, uow, "post_message", notice, f"post:window_changed:{room_id}:v{room.version}")
    enqueue(ctx, uow, "upsert_board_card", {"room_id": room_id}, f"board:{room_id}:v{room.version}")


def _enqueue_add_and_dm(
    ctx: ServiceContext, uow: UnitOfWork, room_id: str, intent_id: str, install_id: str, alias: str
) -> None:
    # The Discord id is snapshotted so the job still works if the install is deleted first.
    who = {
        "room_id": room_id,
        "install_id": install_id,
        "discord_user_id": discord_user_id_of(uow, install_id),
    }
    enqueue(ctx, uow, "add_member", {**who, "alias": alias}, f"add_member:{room_id}:{intent_id}")
    enqueue(ctx, uow, "dm_user", {**who, "kind": "thread_link"}, f"dm:{room_id}:{intent_id}")


def decline(ctx: ServiceContext, install_id: str, offer_id: str) -> str:
    now = ctx.clock()
    with ctx.uow_factory() as uow:
        offer, intent = _owned_offer(uow, install_id, offer_id)
        if offer.state != OfferState.OPEN.value:
            raise OfferClosed("This offer was already answered.")
        if is_expired(offer.expires_at, now):
            _expire(ctx, uow, offer, intent)
            uow.commit()
            raise OfferExpired("This offer has expired.")
        uow.offers.set_state(offer.id, OfferState.DECLINED)
        ensure_transition(IntentState(intent.state), IntentState.DECLINED)
        uow.intents.set_state(intent.id, IntentState.DECLINED)
        uow.commit()
    return OfferState.DECLINED.value


def sweep_expired(ctx: ServiceContext) -> int:
    """Mark open offers past their expiry as expired (FR-OFR-06). Returns how many."""
    with ctx.uow_factory() as uow:
        expired = uow.offers.open_expired(ctx.clock())
        for offer in expired:
            intent = uow.intents.get(offer.intent_id)
            if intent is not None:
                _expire(ctx, uow, offer, intent)
        uow.commit()
        return len(expired)
