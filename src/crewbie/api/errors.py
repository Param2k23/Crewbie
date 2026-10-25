"""One mapping from domain errors to HTTP (03-API-CONTRACT section 1)."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from crewbie.domain.errors import DomainError
from crewbie.logging import request_id_var

logger = logging.getLogger("crewbie.api")

STATUS_BY_CODE = {
    "UNAUTHORIZED": 401,
    "RATE_LIMITED": 429,
    "VALIDATION_FAILED": 422,
    "NOT_FOUND": 404,
    "FORBIDDEN": 403,
    "LINK_REQUIRED": 409,
    "ALREADY_IN_ROOM": 409,
    "OFFER_EXPIRED": 410,
    "OFFER_STALE": 409,
    "OFFER_CLOSED": 409,
    "EVENT_STARTED": 409,
    "INTERNAL": 500,
}


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message, "details": details or {}}
    return {"error": body}


def error_response(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        error_body(code, message, details),
        status_code=STATUS_BY_CODE.get(code, 500),
        headers=headers,
    )


def internal_error_response() -> JSONResponse:
    request_id = request_id_var.get()
    return error_response(
        "INTERNAL", "Something went wrong on our side.", {"request_id": request_id}
    )


def _domain_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    headers: dict[str, str] = {}
    if exc.code == "RATE_LIMITED":
        headers["Retry-After"] = str(int(exc.details.get("retry_after", 60)))
    if exc.code == "UNAUTHORIZED":
        headers["WWW-Authenticate"] = "Bearer"
    if exc.code not in STATUS_BY_CODE:
        logger.error("unmapped domain error", extra={"code": exc.code})
        return internal_error_response()
    return error_response(exc.code, exc.message, exc.details, headers)


def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    """List problem fields only. Never echo `input`: it may hold private envelope values."""
    assert isinstance(exc, RequestValidationError)
    fields: dict[str, str] = {}
    for problem in exc.errors():
        location = [str(part) for part in problem["loc"] if part not in ("body", "query")]
        fields[".".join(location) or "request"] = str(problem["msg"])
    return error_response("VALIDATION_FAILED", "Some fields are invalid.", {"fields": fields})


def _http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    if exc.status_code == 404:
        return error_response("NOT_FOUND", "Not found.")
    if exc.status_code == 405:
        return error_response("NOT_FOUND", "Method not allowed.")
    return internal_error_response()


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
