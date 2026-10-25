"""Runs the matcher for an intent and stores the offer, the negotiations and the public events.

Order matters (02-ARCHITECTURE section 6): snapshot rooms in a short read, negotiate with no
transaction open (so slow LLM calls never hold the database), then write everything in one
transaction. The offer records the `room_version` the negotiation used.
"""

import logging
from datetime import timedelta

from crewbie.agents.protocol import DelegateProfile
from crewbie.domain.budget import BudgetBand
from crewbie.domain.intent import IntentState, ensure_transition
from crewbie.domain.offer import OfferType, offer_expiry
from crewbie.domain.room import RoomStatus
from crewbie.domain.vibe import Vibe
from crewbie.matching.matcher import MatchRequest, MatchResult
from crewbie.matching.negotiation import NegotiationResult
from crewbie.matching.snapshot import MemberSnapshot, RoomSnapshot
from crewbie.persistence.repositories.negotiations import StepRecord
from crewbie.persistence.tables import IntentRow
from crewbie.persistence.unit_of_work import UnitOfWork
from crewbie.services._common import add_update, room_window, shared_from_row, summarize_room
from crewbie.services.context import ServiceContext
from crewbie.services.views import OfferView
from crewbie.telemetry.public_events import public_event

logger = logging.getLogger("crewbie.matching")

STUCK_AFTER = timedelta(seconds=30)


def build_snapshots(uow: UnitOfWork, event_key: str) -> list[RoomSnapshot]:
    """Open and active rooms for the event, with each member's delegate profile decrypted.

    The profiles hold private flex windows; they live only as long as the matching call.
    """
    snapshots: list[RoomSnapshot] = []
    for room in uow.rooms.list_for_event(event_key):
        states = {state.alias: state for state in uow.rooms.member_states(room.id)}
        members: list[MemberSnapshot] = []
        for ref in uow.rooms.members(room.id):
            intent = uow.intents.get(ref.intent_id)
            envelope = uow.intents.load_envelope(ref.intent_id)
            if intent is None or envelope is None or ref.alias not in states:
                members = []
                break
            profile = DelegateProfile(shared_from_row(intent), envelope.flex_window())
            members.append(MemberSnapshot(ref.alias, states[ref.alias], profile))
        if not members:
            continue
        snapshots.append(
            RoomSnapshot(
                room_id=room.id,
                event_key=room.event_key,
                version=room.version,
                created_at=room.created_at,
                status=RoomStatus(room.status),
                window=room_window(room),
                budget_band=BudgetBand.parse(room.budget_band) if room.budget_band else None,
                vibe=Vibe(room.vibe) if room.vibe else None,
                top_interests=tuple(room.top_interests),
                members=tuple(members),
                next_alias=uow.rooms.next_alias(room.id),
            )
        )
    return snapshots


def run(ctx: ServiceContext, intent_id: str) -> OfferView | None:
    """Match one intent that is in `matching`. Returns the new offer, or None if nothing to do."""
    with ctx.uow_factory() as uow:
        intent = uow.intents.get(intent_id)
        if intent is None or intent.state != IntentState.MATCHING.value:
            return None
        envelope = uow.intents.load_envelope(intent_id)
        if envelope is None:
            return None
        joiner = DelegateProfile(shared_from_row(intent), envelope.flex_window())
        event_key = intent.event_key
        room_ids = [room.id for room in uow.rooms.list_for_event(event_key)]

    with ctx.room_locks.hold(room_ids):
        with ctx.uow_factory() as uow:
            snapshots = build_snapshots(uow, event_key)
        result = ctx.matcher.match(
            MatchRequest(intent_id, event_key, joiner, tuple(snapshots), ctx.clock())
        )
        with ctx.uow_factory() as uow:
            current = uow.intents.get(intent_id)
            if current is None or current.state != IntentState.MATCHING.value:
                return None  # withdrawn or superseded while we were negotiating
            offer = _store(ctx, uow, current, result, {s.room_id: s for s in snapshots})
            uow.commit()
            return offer


def _store(
    ctx: ServiceContext,
    uow: UnitOfWork,
    intent: IntentRow,
    result: MatchResult,
    snapshots: dict[str, RoomSnapshot],
) -> OfferView:
    _record_public(uow, intent.event_key, result, snapshots)
    for negotiation in result.negotiations:
        uow.negotiations.add(
            ctx.new_id("n"),
            intent.id,
            negotiation.room_id,
            negotiation.outcome,
            negotiation.rounds,
            [
                StepRecord(
                    s.round,
                    s.actor_kind,
                    s.actor_ref,
                    s.proposal.start if s.proposal else None,
                    s.proposal.end if s.proposal else None,
                    s.verdict.value,
                )
                for s in negotiation.steps
            ],
        )

    expires_at = offer_expiry(ctx.clock(), ctx.config.offer_ttl_minutes)
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


def _record_public(
    uow: UnitOfWork, event_key: str, result: MatchResult, snapshots: dict[str, RoomSnapshot]
) -> None:
    """FR-MAT-09: one public-safe event per negotiation step, in Mission Control's vocabulary."""

    def emit(event_type: str, **fields: object) -> None:
        kind, payload = public_event(event_type, event_key=event_key, **fields)
        uow.public_events.append(kind, payload)

    emit("match_requested")
    verdict_events = {
        "counter": "counteroffer_proposed",
        "reject": "proposal_rejected",
        "accept": "proposal_confirmed",
    }
    for negotiation in result.negotiations:
        room_id = negotiation.room_id
        size = snapshots[room_id].size if room_id in snapshots else None
        emit("negotiation_started", room_id=room_id, size=size)
        if negotiation.opening is not None:
            emit(
                "candidate_proposed", room_id=room_id, size=size, round=1,
                proposal_window=negotiation.opening, actor_kind="delegate",
                actor_ref=negotiation.joiner_ref,
            )  # fmt: skip
        for step in negotiation.steps:
            emit(
                verdict_events[step.verdict.value], room_id=room_id, size=size, round=step.round,
                proposal_window=step.proposal, verdict=step.verdict, actor_kind=step.actor_kind,
                actor_ref=step.actor_ref,
            )  # fmt: skip
        if negotiation.outcome == "failed":
            emit(
                "negotiation_failed",
                room_id=room_id,
                size=size,
                failure_code=negotiation.failure_code,
            )


def rematch_stuck(ctx: ServiceContext) -> int:
    """Re-run matching for intents stranded in `matching` (an earlier run crashed)."""
    with ctx.uow_factory() as uow:
        stuck = [row.id for row in uow.intents.matching_since(ctx.clock() - STUCK_AFTER)]
    done = 0
    for intent_id in stuck:
        try:
            if run(ctx, intent_id) is not None:
                done += 1
        except Exception:
            logger.exception("rematch failed", extra={"intent_id": intent_id})
    return done


__all__ = ["NegotiationResult", "rematch_stuck", "run"]
