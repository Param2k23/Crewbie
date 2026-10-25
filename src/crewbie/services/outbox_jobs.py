"""What the Discord worker needs from the database: due jobs, results, and recorded Discord ids."""

from dataclasses import dataclass
from typing import Any

from crewbie.domain.room import RoomStatus
from crewbie.persistence.outbox import OutboxState
from crewbie.services._common import add_update, enqueue, thread_url
from crewbie.services.context import ServiceContext


@dataclass(frozen=True)
class Job:
    id: str
    kind: str
    payload: dict[str, Any]
    attempts: int


def due(ctx: ServiceContext, limit: int = 20) -> list[Job]:
    with ctx.uow_factory() as uow:
        return [
            Job(row.id, row.kind, dict(row.payload), row.attempts)
            for row in uow.outbox.due(ctx.clock(), limit)
        ]


def complete(ctx: ServiceContext, job_id: str) -> None:
    with ctx.uow_factory() as uow:
        uow.outbox.mark_done(job_id)
        uow.commit()


def fail(ctx: ServiceContext, job_id: str, error: str) -> OutboxState:
    """Record a failed attempt; the job is retried with backoff or marked failed (NFR-REL-01)."""
    with ctx.uow_factory() as uow:
        state = uow.outbox.mark_failed_attempt(job_id, error, ctx.clock())
        uow.commit()
        return state


def record_thread(ctx: ServiceContext, room_id: str, thread_id: str) -> str | None:
    """Store the thread and tell every member's Cubbie where it is (`room_active`)."""
    with ctx.uow_factory() as uow:
        room = uow.rooms.get(room_id)
        if room is None:
            return None
        uow.rooms.set_thread(room_id, thread_id)
        url = thread_url(ctx, room)
        for member in uow.rooms.members(room_id):
            if member.is_synthetic:
                continue
            intent = uow.intents.get(member.intent_id)
            if intent is not None:
                add_update(
                    uow, member.install_id, "room_active", intent,
                    room={"size": room.size}, thread_url=url,
                )  # fmt: skip
        uow.commit()
        return url


def record_board_message(ctx: ServiceContext, room_id: str, message_id: str | None) -> None:
    with ctx.uow_factory() as uow:
        room = uow.rooms.get(room_id)
        if room is not None:
            room.board_message_id = message_id
            uow.commit()


def retry_failed(ctx: ServiceContext) -> int:
    """Put failed jobs back in the queue, for example after fixing a Discord permission."""
    with ctx.uow_factory() as uow:
        count = uow.outbox.requeue_failed(ctx.clock())
        uow.commit()
        return count


def reconcile_board(ctx: ServiceContext) -> int:
    """Queue a board card for every open or active room that has none (FR-BOT-05).

    Runs when the bot starts, so cards lost to an earlier failure reappear on their own.
    """
    now = ctx.clock()
    with ctx.uow_factory() as uow:
        missing = [
            room
            for room in uow.rooms.list_all()
            if room.status in (RoomStatus.OPEN.value, RoomStatus.ACTIVE.value)
            and room.size > 0
            and not room.board_message_id
        ]
        for room in missing:
            enqueue(
                ctx, uow, "upsert_board_card", {"room_id": room.id},
                f"board:{room.id}:reconcile:{now.isoformat()}",
            )  # fmt: skip
        uow.commit()
        return len(missing)
