"""Time-based room lifecycle: close 2 h and archive 24 h after the window ends (FR-ROM-03)."""

from crewbie.domain.room import RoomStatus, lifecycle_status
from crewbie.services._common import add_update, enqueue
from crewbie.services.context import ServiceContext


def advance_rooms(ctx: ServiceContext) -> int:
    """Move rooms along their lifecycle. Returns how many changed."""
    now = ctx.clock()
    changed = 0
    with ctx.uow_factory() as uow:
        for room in uow.rooms.list_all():
            current = RoomStatus(room.status)
            if current is RoomStatus.ARCHIVED:
                continue
            target = lifecycle_status(current, current, room.window_end, now)
            if target is current:
                continue
            changed += 1
            room.status = target.value
            room.version += 1
            if target is RoomStatus.CLOSED:
                for member in uow.rooms.members(room.id):
                    intent = uow.intents.get(member.intent_id)
                    if intent is not None and not member.is_synthetic:
                        add_update(uow, member.install_id, "room_closed", intent)
            if target is RoomStatus.ARCHIVED and room.discord_thread_id:
                enqueue(ctx, uow, "archive_thread", {"room_id": room.id}, f"archive:{room.id}")
            enqueue(
                ctx, uow, "upsert_board_card", {"room_id": room.id},
                f"board:{room.id}:v{room.version}",
            )  # fmt: skip
        uow.commit()
    return changed
