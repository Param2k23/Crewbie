"""Leaving and closing rooms. Used by withdraw, install deletion, the bot and the admin API."""

from crewbie.domain.intent import IntentState, ensure_transition
from crewbie.domain.room import RoomStatus
from crewbie.persistence.tables import IntentRow
from crewbie.persistence.unit_of_work import UnitOfWork
from crewbie.services._common import (
    add_update,
    discord_user_id_of,
    enqueue,
    recompute_room,
    window_payload,
)
from crewbie.services.context import ServiceContext


def leave(ctx: ServiceContext, uow: UnitOfWork, intent: IntentRow) -> None:
    """Take a joined intent out of its room and tell everyone who needs to know (FR-INT-06).

    Runs in the caller's transaction; the caller commits.
    """
    room_id = uow.rooms.current_room_id(intent.id)
    if room_id is None:
        ensure_transition(IntentState(intent.state), IntentState.WITHDRAWN)
        uow.intents.set_state(intent.id, IntentState.WITHDRAWN)
        return
    before = uow.rooms.members(room_id)
    leaver = next(member for member in before if member.intent_id == intent.id)
    # Snapshot now: the link may be deleted with the install before the bot runs the job.
    discord_user_id = discord_user_id_of(uow, leaver.install_id)

    uow.rooms.mark_left(intent.id, ctx.clock())
    ensure_transition(IntentState(intent.state), IntentState.WITHDRAWN)
    uow.intents.set_state(intent.id, IntentState.WITHDRAWN)
    change = recompute_room(ctx, uow, room_id)
    version = change.room.version

    if not leaver.is_synthetic:
        enqueue(
            ctx,
            uow,
            "remove_member",
            {"room_id": room_id, "alias": leaver.alias, "discord_user_id": discord_user_id},
            f"remove_member:{room_id}:{intent.id}",
        )
    if len(before) >= 2:
        enqueue(
            ctx,
            uow,
            "post_message",
            {
                "room_id": room_id,
                "kind": "member_left",
                "alias": leaver.alias,
                "window": window_payload(change.state.window),
                "window_changed": change.window_changed,
            },
            f"post:member_left:{room_id}:v{version}",
        )
    enqueue(ctx, uow, "upsert_board_card", {"room_id": room_id}, f"board:{room_id}:v{version}")

    for member in uow.rooms.members(room_id):
        member_intent = uow.intents.get(member.intent_id)
        if member_intent is None:
            continue
        add_update(
            uow, member.install_id, "member_left", member_intent, room={"size": change.state.size}
        )
        if change.window_changed:
            add_update(
                uow,
                member.install_id,
                "window_changed",
                member_intent,
                window=window_payload(change.state.window),
            )


def close(ctx: ServiceContext, room_id: str) -> bool:
    """Operator force-close. Returns False if the room does not exist."""
    with ctx.uow_factory() as uow:
        room = uow.rooms.get(room_id)
        if room is None:
            return False
        if room.status in (RoomStatus.CLOSED.value, RoomStatus.ARCHIVED.value):
            return True
        for member in uow.rooms.members(room_id):
            intent = uow.intents.get(member.intent_id)
            if intent is not None:
                add_update(uow, member.install_id, "room_closed", intent)
        room.status = RoomStatus.CLOSED.value
        room.version += 1
        enqueue(ctx, uow, "archive_thread", {"room_id": room_id}, f"archive:{room_id}")
        enqueue(
            ctx, uow, "upsert_board_card", {"room_id": room_id}, f"board:{room_id}:v{room.version}"
        )
        uow.commit()
        return True
