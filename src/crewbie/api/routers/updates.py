from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from crewbie.api.auth import Principal, current_install, service_context
from crewbie.api.presenters import update_json
from crewbie.services import updates
from crewbie.services.context import ServiceContext

router = APIRouter(prefix="/v1/updates")


@router.get("")
def list_updates(
    principal: Annotated[Principal, Depends(current_install)],
    ctx: Annotated[ServiceContext, Depends(service_context)],
    cursor: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
) -> dict[str, Any]:
    next_cursor, items = updates.list_updates(ctx, principal.install_id, cursor, limit)
    return {"cursor": next_cursor, "updates": [update_json(u) for u in items]}
