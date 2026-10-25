"""Operator views and actions (FR-ADM-01). Reads aliases and counts, never private fields."""

from typing import Any

from crewbie.persistence.outbox import OutboxState
from crewbie.services._common import room_window, window_payload
from crewbie.services.context import ServiceContext


def list_rooms(ctx: ServiceContext) -> dict[str, Any]:
    with ctx.uow_factory() as uow:
        rooms = [
            {
                "room_id": room.id,
                "event_key": room.event_key,
                "status": room.status,
                "size": room.size,
                "version": room.version,
                "window": window_payload(room_window(room)),
                "thread_id": room.discord_thread_id,
                "members": [
                    {"alias": m.alias, "is_synthetic": m.is_synthetic}
                    for m in uow.rooms.members(room.id)
                ],
            }
            for room in uow.rooms.list_all()
        ]
        outbox = {
            "pending": uow.outbox.backlog(),
            "failed": len(uow.outbox.by_state(OutboxState.FAILED)),
        }
    return {"rooms": rooms, "outbox": outbox}


def list_outbox(ctx: ServiceContext, state: OutboxState) -> list[dict[str, Any]]:
    with ctx.uow_factory() as uow:
        return [
            {
                "id": job.id,
                "kind": job.kind,
                "state": job.state,
                "attempts": job.attempts,
                "last_error": job.last_error,
                "payload": job.payload,
            }
            for job in uow.outbox.by_state(state)
        ]
