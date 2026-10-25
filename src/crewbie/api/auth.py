"""Bearer-token authentication and per-install rate limiting (FR-INS-02, FR-INS-04)."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request

from crewbie.api.state import AppState
from crewbie.domain.errors import Unauthorized
from crewbie.logging import install_ref, install_ref_var
from crewbie.services import installs
from crewbie.services.context import ServiceContext


def app_state(request: Request) -> AppState:
    state: AppState = request.app.state.crewbie
    return state


def service_context(state: Annotated[AppState, Depends(app_state)]) -> ServiceContext:
    return state.ctx


def bearer_token(authorization: Annotated[str | None, Header()] = None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise Unauthorized("Missing or unknown token.")
    return token.strip()


@dataclass(frozen=True)
class Principal:
    install_id: str


def current_install(
    token: Annotated[str, Depends(bearer_token)],
    state: Annotated[AppState, Depends(app_state)],
) -> Principal:
    install_id = installs.authenticate(state.ctx, token)
    install_ref_var.set(install_ref(install_id))
    state.install_limiter.check(install_id)
    return Principal(install_id)
