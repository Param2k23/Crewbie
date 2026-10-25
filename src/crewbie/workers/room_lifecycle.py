"""Background task: close rooms 2 h after their window ends and archive them after 24 h."""

import asyncio
import logging

from crewbie.services import lifecycle
from crewbie.services.context import ServiceContext

logger = logging.getLogger("crewbie.workers.room_lifecycle")


async def run(ctx: ServiceContext, interval_seconds: float = 60.0) -> None:
    while True:
        try:
            changed = await asyncio.to_thread(lifecycle.advance_rooms, ctx)
            if changed:
                logger.info("rooms advanced", extra={"count": changed})
        except Exception:
            logger.exception("room lifecycle sweep failed")
        await asyncio.sleep(interval_seconds)
