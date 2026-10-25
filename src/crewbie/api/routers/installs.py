from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from crewbie.api.auth import Principal, app_state, bearer_token, current_install, service_context
from crewbie.api.presenters import install_json, link_code_json
from crewbie.api.schemas import RegisterIn
from crewbie.api.state import AppState
from crewbie.services import installs, linking
from crewbie.services.context import ServiceContext

router = APIRouter(prefix="/v1/installs")


@router.post("")
def register(
    request: Request,
    _: RegisterIn,
    token: Annotated[str, Depends(bearer_token)],
    state: Annotated[AppState, Depends(app_state)],
) -> JSONResponse:
    state.register_limiter.check(request.client.host if request.client else "unknown")
    view = installs.register(state.ctx, token)
    return JSONResponse(install_json(view), status_code=201 if view.created else 200)


@router.get("/me")
def whoami(
    principal: Annotated[Principal, Depends(current_install)],
    ctx: Annotated[ServiceContext, Depends(service_context)],
) -> dict[str, Any]:
    return install_json(installs.get_me(ctx, principal.install_id))


@router.delete("/me", status_code=204)
def delete_me(
    principal: Annotated[Principal, Depends(current_install)],
    ctx: Annotated[ServiceContext, Depends(service_context)],
) -> Response:
    installs.delete_me(ctx, principal.install_id)
    return Response(status_code=204)


@router.post("/me/link-codes", status_code=201)
def create_link_code(
    principal: Annotated[Principal, Depends(current_install)],
    ctx: Annotated[ServiceContext, Depends(service_context)],
) -> dict[str, Any]:
    return link_code_json(linking.create_link_code(ctx, principal.install_id))
