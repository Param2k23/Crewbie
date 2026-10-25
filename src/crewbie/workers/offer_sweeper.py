"""Background task: expire stale offers (FR-OFR-06) and retry stranded matching (FR-INT-04)."""

import asyncio
import logging

from crewbie.services import matchmaking, offers
from crewbie.services.context import ServiceContext

logger = logging.getLogger("crewbie.workers.offer_sweeper")


async def run(ctx: ServiceContext, interval_seconds: float = 30.0) -> None:
    while True:
        try:
            expired = await asyncio.to_thread(offers.sweep_expired, ctx)
            if expired:
                logger.info("expired offers", extra={"count": expired})
            retried = await asyncio.to_thread(matchmaking.rematch_stuck, ctx)
            if retried:
                logger.info("rematched stuck intents", extra={"count": retried})
        except Exception:
            logger.exception("offer sweep failed")
        await asyncio.sleep(interval_seconds)
