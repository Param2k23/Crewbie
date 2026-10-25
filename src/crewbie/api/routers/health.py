from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import text

from crewbie.api.auth import app_state
from crewbie.api.state import AppState

router = APIRouter()


@router.get("/healthz")
def healthz(state: Annotated[AppState, Depends(app_state)]) -> dict[str, Any]:
    try:
        with state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "error"
    with state.ctx.uow_factory() as uow:
        backlog = uow.outbox.backlog() if database == "ok" else 0
    return {
        "status": "ok" if database == "ok" else "degraded",
        "db": database,
        "discord": state.bot_status.value,
        "outbox_backlog": backlog,
        "llm_mode": state.settings.llm_mode,
    }
