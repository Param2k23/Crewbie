"""Starts and stops the bot inside the API process (02-ARCHITECTURE section 1)."""

import asyncio
import contextlib
import logging

from crewbie.config import Settings
from crewbie.discord_bot.client import CrewbieClient
from crewbie.discord_bot.live_gateway import DiscordGateway
from crewbie.discord_bot.worker import OutboxWorker, WorkerConfig
from crewbie.services import outbox_jobs
from crewbie.services.context import ServiceContext

logger = logging.getLogger("crewbie.discord")


class BotStatus:
    """Read by `/healthz`: disabled, connecting, connected, disconnected or error."""

    def __init__(self, value: str = "disabled") -> None:
        self.value = value

    def set(self, value: str) -> None:
        self.value = value


class BotRuntime:
    def __init__(self, ctx: ServiceContext, settings: Settings, status: BotStatus) -> None:
        self._ctx = ctx
        self._settings = settings
        self._status = status
        self._client: CrewbieClient | None = None
        self._tasks: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        """Connect in the background so API startup never waits on Discord."""
        settings = self._settings
        self._status.set("connecting")
        client = CrewbieClient(self._ctx, int(settings.discord_guild_id), self._status.set)
        self._client = client
        gateway = DiscordGateway(
            client, int(settings.discord_crews_channel_id), int(settings.discord_board_channel_id)
        )
        worker = OutboxWorker(
            self._ctx, gateway, WorkerConfig(settings.discord_guild_id, settings.timezone)
        )
        await asyncio.to_thread(outbox_jobs.reconcile_board, self._ctx)
        self._tasks = [
            asyncio.create_task(self._connect(client), name="discord-client"),
            asyncio.create_task(self._work(client, worker), name="discord-outbox"),
        ]

    async def _connect(self, client: CrewbieClient) -> None:
        try:
            await client.start(self._settings.discord_token)
        except asyncio.CancelledError:
            raise
        except Exception as error:  # includes LoginFailure; never log the token itself
            logger.error("discord client stopped", extra={"error": type(error).__name__})
            self._status.set("error")

    async def _work(self, client: CrewbieClient, worker: OutboxWorker) -> None:
        await client.wait_until_ready()
        await worker.run()

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        if self._client is not None:
            with contextlib.suppress(Exception):
                await self._client.close()
        self._status.set("disabled")
