"""Optional FastAPI router for the integrator: ``app.include_router(create_router(sink))``.

Imported lazily so the rest of the package has no third-party dependencies.
"""
from __future__ import annotations

import re

from .sink import MemoryEventSink
from .sse import stream_session

_SESSION = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")


def create_router(sink: MemoryEventSink):
    from fastapi import APIRouter, Header, HTTPException  # type: ignore[import-not-found]
    from fastapi.responses import StreamingResponse  # type: ignore[import-not-found]

    router = APIRouter()

    @router.get("/v1/sessions/{session_id}/events")
    def session_events(session_id: str, last_event_id: str | None = Header(default=None, alias="Last-Event-ID")):
        if not _SESSION.match(session_id):
            raise HTTPException(status_code=400, detail="invalid session_id")
        return StreamingResponse(
            stream_session(sink, session_id, last_event_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    return router
