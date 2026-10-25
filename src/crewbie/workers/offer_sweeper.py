"""Background task that expires stale offers (FR-OFR-06)."""

import asyncio
import logging

from crewbie.services import offers
from crewbie.services.context import ServiceContext

logger = logging.getLogger("crewbie.workers.offer_sweeper")


async def run(ctx: ServiceContext, interval_seconds: float = 30.0) -> None:
    while True:
        try:
            expired = await asyncio.to_thread(offers.sweep_expired, ctx)
            if expired:
                logger.info("expired offers", extra={"count": expired})
        except Exception:
            logger.exception("offer sweep failed")
        await asyncio.sleep(interval_seconds)
