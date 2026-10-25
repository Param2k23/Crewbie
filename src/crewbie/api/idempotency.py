"""`Idempotency-Key` replay (03-API-CONTRACT section 1). Only successful responses are stored."""

import re
from datetime import timedelta
from typing import Annotated, Any

from fastapi import Header
from fastapi.responses import JSONResponse

from crewbie.domain.errors import ValidationFailed
from crewbie.services.context import ServiceContext

_KEY_FORMAT = re.compile(r"^[A-Za-z0-9_\-]{8,64}$")
TTL = timedelta(hours=24)


def idempotency_key(idempotency_key: Annotated[str | None, Header()] = None) -> str | None:
    if idempotency_key is not None and not _KEY_FORMAT.match(idempotency_key):
        raise ValidationFailed({"Idempotency-Key": "must be 8 to 64 URL-safe characters"})
    return idempotency_key


def replay(
    ctx: ServiceContext, install_id: str, key: str | None, scope: str
) -> JSONResponse | None:
    if key is None:
        return None
    with ctx.uow_factory() as uow:
        row = uow.idempotency.get(install_id, key)
        if row is None or ctx.clock() - row.created_at > TTL:
            return None
        if row.scope != scope:
            raise ValidationFailed({"Idempotency-Key": "already used for a different request"})
        return JSONResponse(row.response_body, status_code=row.response_status)


def remember(
    ctx: ServiceContext,
    install_id: str,
    key: str | None,
    scope: str,
    status: int,
    body: dict[str, Any],
) -> None:
    if key is None:
        return
    with ctx.uow_factory() as uow:
        uow.idempotency.store(install_id, key, scope, status, body, ctx.clock())
        uow.commit()
