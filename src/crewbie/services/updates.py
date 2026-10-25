"""Per-install updates read by scheduled check-ins (FR-UPD-*)."""

from crewbie.services.context import ServiceContext
from crewbie.services.views import UpdateView

MAX_LIMIT = 50


def list_updates(
    ctx: ServiceContext, install_id: str, cursor: int, limit: int
) -> tuple[int, list[UpdateView]]:
    """Updates after `cursor`, and the cursor to send next time."""
    limit = max(1, min(limit, MAX_LIMIT))
    with ctx.uow_factory() as uow:
        rows = uow.updates.after(install_id, max(cursor, 0), limit)
        views = [UpdateView(row.seq, row.kind, dict(row.payload)) for row in rows]
    return (views[-1].seq if views else max(cursor, 0)), views
