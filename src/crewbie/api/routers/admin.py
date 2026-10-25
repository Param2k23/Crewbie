import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query

from crewbie.api.auth import app_state
from crewbie.api.state import AppState
from crewbie.domain.errors import NotFound, Unauthorized
from crewbie.persistence.outbox import OutboxState
from crewbie.services import admin, rooms, seed


def require_admin(
    state: Annotated[AppState, Depends(app_state)],
    x_admin_token: Annotated[str | None, Header()] = None,
) -> AppState:
    expected = state.settings.admin_token
    if not expected:
        raise NotFound("Not found.")  # NFR-SEC-04: disabled when unset, and not advertised
    if x_admin_token is None or not hmac.compare_digest(x_admin_token.encode(), expected.encode()):
        raise Unauthorized("Missing or unknown token.")
    return state


router = APIRouter(prefix="/v1/admin")


@router.get("/rooms")
def list_rooms(state: Annotated[AppState, Depends(require_admin)]) -> dict[str, Any]:
    return admin.list_rooms(state.ctx)


@router.post("/rooms/{room_id}/close")
def close_room(room_id: str, state: Annotated[AppState, Depends(require_admin)]) -> dict[str, str]:
    if not rooms.close(state.ctx, room_id):
        raise NotFound("Room not found.")
    return {"room_id": room_id, "status": "closed"}


@router.post("/seed")
def seed_demo(state: Annotated[AppState, Depends(require_admin)]) -> dict[str, Any]:
    return seed.seed_demo(state.ctx)


@router.get("/outbox")
def list_outbox(
    state: Annotated[AppState, Depends(require_admin)],
    outbox_state: Annotated[OutboxState, Query(alias="state")] = OutboxState.FAILED,
) -> dict[str, Any]:
    return {"jobs": admin.list_outbox(state.ctx, outbox_state)}
