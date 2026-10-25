from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from crewbie.api import idempotency
from crewbie.api.auth import Principal, current_install, service_context
from crewbie.api.presenters import intent_json, offer_json
from crewbie.api.schemas import IntentIn
from crewbie.domain.budget import BudgetBand
from crewbie.domain.vibe import Vibe
from crewbie.domain.windows import TimeWindow
from crewbie.services import intents
from crewbie.services.context import ServiceContext

router = APIRouter(prefix="/v1/intents")


def _to_request(body: IntentIn) -> intents.SubmitIntent:
    return intents.SubmitIntent(
        event=intents.EventInput(**body.event.model_dump()),
        window=TimeWindow(body.shared.window.start, body.shared.window.end),
        activity_min_minutes=body.shared.activity_min_minutes,
        budget_band=BudgetBand.parse(body.shared.budget_band),
        vibe=Vibe(body.shared.vibe),
        interests=tuple(body.shared.interests),
        flex_earliest=body.private.flex.earliest,
        flex_latest=body.private.flex.latest,
        budget_cap_usd=body.private.budget_cap_usd,
    )


@router.post("", status_code=201)
def submit(
    request: Request,
    body: IntentIn,
    principal: Annotated[Principal, Depends(current_install)],
    ctx: Annotated[ServiceContext, Depends(service_context)],
    key: Annotated[str | None, Depends(idempotency.idempotency_key)],
) -> JSONResponse:
    scope = request.url.path
    if (stored := idempotency.replay(ctx, principal.install_id, key, scope)) is not None:
        return stored
    result = intents.submit(ctx, principal.install_id, _to_request(body))
    payload: dict[str, Any] = {"intent_id": result.intent_id, "state": result.state}
    status = 201
    if result.offer is not None:
        payload["offer"] = offer_json(result.offer)
    else:
        status = 202
    idempotency.remember(ctx, principal.install_id, key, scope, status, payload)
    return JSONResponse(payload, status_code=status)


@router.get("/{intent_id}")
def get_intent(
    intent_id: str,
    principal: Annotated[Principal, Depends(current_install)],
    ctx: Annotated[ServiceContext, Depends(service_context)],
) -> dict[str, Any]:
    return intent_json(intents.get(ctx, principal.install_id, intent_id))


@router.post("/{intent_id}/withdraw")
def withdraw(
    intent_id: str,
    principal: Annotated[Principal, Depends(current_install)],
    ctx: Annotated[ServiceContext, Depends(service_context)],
) -> dict[str, Any]:
    view = intents.withdraw(ctx, principal.install_id, intent_id)
    return {"intent_id": view.intent_id, "state": view.state}
