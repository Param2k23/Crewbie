"""FastAPI app factory and request middleware."""

import asyncio
import logging
import re
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, Response
from sqlalchemy.engine import make_url

from crewbie.api.errors import install_error_handlers, internal_error_response
from crewbie.api.rate_limit import RateLimits, TokenBucketLimiter
from crewbie.api.routers import admin, health, installs, intents, offers, rooms, updates
from crewbie.api.state import AppState
from crewbie.config import Settings
from crewbie.logging import install_ref_var, request_id_var
from crewbie.matching.matcher import DeterministicMatcher, Matcher
from crewbie.persistence.crypto import load_cipher
from crewbie.persistence.db import create_db_engine, make_session_factory, migrate_to_head
from crewbie.persistence.unit_of_work import UnitOfWork
from crewbie.services.context import ServiceConfig, ServiceContext, utc_now
from crewbie.workers import offer_sweeper

logger = logging.getLogger("crewbie.api")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9_\-]{8,64}$")


def build_state(
    settings: Settings,
    *,
    matcher: Matcher | None = None,
    clock: Callable[[], datetime] | None = None,
    rate_limits: RateLimits | None = None,
) -> AppState:
    engine = create_db_engine(settings.database_url)
    migrate_to_head(engine)
    database = make_url(settings.database_url).database
    key_dir = Path(database).parent if database else Path("data")
    cipher = load_cipher(settings.envelope_key, settings.env, key_dir / "dev_envelope.key")
    sessions = make_session_factory(engine)
    config = ServiceConfig(
        env=settings.env,
        offer_ttl_minutes=settings.offer_ttl_minutes,
        invite_url=settings.discord_invite_url,
        guild_id=settings.discord_guild_id,
        timezone=settings.timezone,
    )
    ctx = ServiceContext(
        uow_factory=lambda: UnitOfWork(sessions, cipher),
        matcher=matcher
        or DeterministicMatcher(
            max_candidates=settings.max_candidate_rooms,
            max_rounds=settings.max_rounds,
            time_budget_seconds=settings.match_time_budget_seconds,
        ),
        config=config,
        clock=clock or utc_now,
    )
    limits = rate_limits or RateLimits()
    return AppState(
        settings=settings,
        ctx=ctx,
        engine=engine,
        install_limiter=TokenBucketLimiter(limits.requests_per_minute, 60),
        register_limiter=TokenBucketLimiter(limits.registrations_per_hour, 3600),
    )


def create_app(
    settings: Settings | None = None,
    *,
    matcher: Matcher | None = None,
    clock: Callable[[], datetime] | None = None,
    rate_limits: RateLimits | None = None,
    sweep_interval_seconds: float = 30.0,
) -> FastAPI:
    state = build_state(
        settings or Settings(), matcher=matcher, clock=clock, rate_limits=rate_limits
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        sweeper = asyncio.create_task(offer_sweeper.run(state.ctx, sweep_interval_seconds))
        try:
            yield
        finally:
            sweeper.cancel()
            state.engine.dispose()

    app = FastAPI(
        title="Crewbie", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None
    )
    app.state.crewbie = state
    install_error_handlers(app)

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        supplied = request.headers.get("x-request-id", "")
        request_id = supplied if _REQUEST_ID.match(supplied) else uuid.uuid4().hex
        request_id_var.set(request_id)
        install_ref_var.set(None)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled error")
            response = internal_error_response()
        response.headers["X-Request-Id"] = request_id
        # One line per request. The path only: query strings may carry event details.
        logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                "install_ref": install_ref_var.get(),
            },
        )
        return response

    for router in (health.router, installs.router, rooms.router, intents.router, offers.router,
                   updates.router, admin.router):  # fmt: skip
        app.include_router(router)
    return app
