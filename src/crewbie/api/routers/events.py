from typing import Annotated, Any

from fastapi import APIRouter, Depends

from crewbie.api.auth import Principal, current_install, service_context
from crewbie.api.presenters import event_candidate_json
from crewbie.api.schemas import EventSearchIn
from crewbie.services import discovery
from crewbie.services.context import ServiceContext

router = APIRouter(prefix="/v1/events")


@router.post("/search")
def search_events(
    body: EventSearchIn,
    _: Annotated[Principal, Depends(current_install)],
    ctx: Annotated[ServiceContext, Depends(service_context)],
) -> dict[str, Any]:
    """Suggest existing events with a live crew that look like the one described."""
    candidates = discovery.search_events(
        ctx, body.title, body.date, body.start_time, body.location_label, body.source_url
    )
    return {"events": [event_candidate_json(c) for c in candidates]}
