from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from crewbie.api import idempotency
from crewbie.api.auth import Principal, current_install, service_context
from crewbie.api.presenters import accept_json
from crewbie.services import offers
from crewbie.services.context import ServiceContext

router = APIRouter(prefix="/v1/offers")


@router.post("/{offer_id}/accept")
def accept(
    request: Request,
    offer_id: str,
    principal: Annotated[Principal, Depends(current_install)],
    ctx: Annotated[ServiceContext, Depends(service_context)],
    key: Annotated[str | None, Depends(idempotency.idempotency_key)],
) -> JSONResponse:
    scope = request.url.path
    if (stored := idempotency.replay(ctx, principal.install_id, key, scope)) is not None:
        return stored
    payload = accept_json(offers.accept(ctx, principal.install_id, offer_id))
    idempotency.remember(ctx, principal.install_id, key, scope, 200, payload)
    return JSONResponse(payload)


@router.post("/{offer_id}/decline")
def decline(
    request: Request,
    offer_id: str,
    principal: Annotated[Principal, Depends(current_install)],
    ctx: Annotated[ServiceContext, Depends(service_context)],
    key: Annotated[str | None, Depends(idempotency.idempotency_key)],
) -> JSONResponse:
    scope = request.url.path
    if (stored := idempotency.replay(ctx, principal.install_id, key, scope)) is not None:
        return stored
    payload: dict[str, Any] = {"state": offers.decline(ctx, principal.install_id, offer_id)}
    idempotency.remember(ctx, principal.install_id, key, scope, 200, payload)
    return JSONResponse(payload)
