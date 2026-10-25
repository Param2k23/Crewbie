from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from crewbie.api.auth import Principal, current_install, service_context
from crewbie.api.presenters import room_json
from crewbie.api.schemas import LookupIn
from crewbie.services import discovery
from crewbie.services.context import ServiceContext

router = APIRouter(prefix="/v1/rooms")


def _rooms_for(ctx: ServiceContext, key: str) -> dict[str, Any]:
    return {"event_key": key, "rooms": [room_json(r) for r in discovery.list_rooms(ctx, key)]}


@router.get("")
def list_rooms(
    _: Annotated[Principal, Depends(current_install)],
    ctx: Annotated[ServiceContext, Depends(service_context)],
    event_key: Annotated[str | None, Query(max_length=16)] = None,
    source_url: Annotated[str | None, Query(max_length=2048)] = None,
    date: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")] = None,
    start_time: Annotated[str | None, Query(pattern=r"^\d{2}:\d{2}$")] = None,
) -> dict[str, Any]:
    key = discovery.resolve_event_key(event_key, source_url, date, start_time)
    return _rooms_for(ctx, key)


@router.post("/lookup")
def lookup(
    body: LookupIn,
    _: Annotated[Principal, Depends(current_install)],
    ctx: Annotated[ServiceContext, Depends(service_context)],
) -> dict[str, Any]:
    results = []
    for event in body.events:
        key = discovery.resolve_event_key(None, event.source_url, event.date, event.start_time)
        results.append({"ref": event.ref, **_rooms_for(ctx, key)})
    return {"results": results}
