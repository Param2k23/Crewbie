"""Outbox consumer (FR-BOT-01). Runs each Discord side effect idempotently with retry/backoff."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from crewbie.discord_bot import messages
from crewbie.discord_bot.gateway import DmClosedError, Gateway
from crewbie.persistence.outbox import OutboxState
from crewbie.services import outbox_jobs, room_view
from crewbie.services.context import ServiceContext
from crewbie.services.outbox_jobs import Job
from crewbie.services.room_view import RoomContent

logger = logging.getLogger("crewbie.discord.worker")

BATCH_SIZE = 20


class NotReadyError(Exception):
    """A prerequisite job (usually `create_thread`) has not run yet; retry with backoff."""


@dataclass(frozen=True)
class WorkerConfig:
    guild_id: str
    timezone: str
    poll_seconds: float = 1.0


class OutboxWorker:
    def __init__(self, ctx: ServiceContext, gateway: Gateway, config: WorkerConfig) -> None:
        self._ctx = ctx
        self._gateway = gateway
        self._config = config
        self._handlers: dict[str, Callable[[Job], Awaitable[None]]] = {
            "create_thread": self._create_thread,
            "add_member": self._add_member,
            "remove_member": self._remove_member,
            "post_message": self._post_message,
            "dm_user": self._dm_user,
            "upsert_board_card": self._upsert_board_card,
            "archive_thread": self._archive_thread,
        }

    async def run(self) -> None:
        while True:
            try:
                handled = await self.process_once()
            except Exception:
                logger.exception("outbox poll failed")
                handled = 0
            if handled == 0:
                await asyncio.sleep(self._config.poll_seconds)

    async def process_once(self) -> int:
        """Run every due job, in order, once. Returns how many were attempted."""
        jobs = await asyncio.to_thread(outbox_jobs.due, self._ctx, BATCH_SIZE)
        for job in jobs:
            await self._attempt(job)
        return len(jobs)

    async def _attempt(self, job: Job) -> None:
        handler = self._handlers.get(job.kind)
        try:
            if handler is None:
                raise ValueError(f"unknown job kind: {job.kind}")
            await handler(job)
        except DmClosedError:
            # The thread link still reaches the student through Cubbie's `room_active` update.
            logger.info("dm closed", extra={"job_id": job.id})
        except Exception as error:
            state = await asyncio.to_thread(
                outbox_jobs.fail, self._ctx, job.id, f"{type(error).__name__}: {error}"
            )
            level = logging.ERROR if state is OutboxState.FAILED else logging.WARNING
            logger.log(
                level, "job attempt failed",
                extra={"job_id": job.id, "kind": job.kind, "attempts": job.attempts + 1,
                       "final": state is OutboxState.FAILED},
            )  # fmt: skip
            return
        await asyncio.to_thread(outbox_jobs.complete, self._ctx, job.id)
        logger.info("job done", extra={"job_id": job.id, "kind": job.kind})

    async def _room(self, job: Job) -> RoomContent:
        room = await asyncio.to_thread(room_view.load_room, self._ctx, job.payload["room_id"])
        if room is None:
            raise LookupError(f"room {job.payload['room_id']} no longer exists")
        return room

    def _thread(self, room: RoomContent) -> str:
        if not room.thread_id:
            raise NotReadyError("thread not created yet")
        return room.thread_id

    async def _create_thread(self, job: Job) -> None:
        room = await self._room(job)
        if room.thread_id:
            return  # already created: retries must not make a second thread
        name = messages.thread_name(room.event_title, room.event_date)
        thread_id = await self._gateway.create_private_thread(name)
        await asyncio.to_thread(outbox_jobs.record_thread, self._ctx, room.room_id, thread_id)

    async def _add_member(self, job: Job) -> None:
        room = await self._room(job)
        user_id = job.payload.get("discord_user_id")
        if user_id:
            await self._gateway.add_user(self._thread(room), user_id)

    async def _remove_member(self, job: Job) -> None:
        room = await self._room(job)
        user_id = job.payload.get("discord_user_id")
        if user_id and room.thread_id:
            await self._gateway.remove_user(room.thread_id, user_id)

    async def _post_message(self, job: Job) -> None:
        room = await self._room(job)
        thread_id = self._thread(room)
        timezone = self._config.timezone
        label = messages.window_label(room.window, timezone)
        kind = job.payload["kind"]
        if kind == "icebreaker":
            text = messages.icebreaker(
                room.event_title, room.event_date, room.window, room.location_label,
                room.interest_counts, timezone,
            )  # fmt: skip
        elif kind == "welcome":
            joined = next((m for m in room.members if m.alias == job.payload.get("alias")), None)
            name = messages.clean(joined.username or joined.alias) if joined else "Someone"
            text = messages.WELCOME.format(username=name, window_label=label)
        elif kind == "window_changed":
            text = messages.WINDOW_CHANGED.format(window_label=label)
        elif kind == "member_left":
            alias = str(job.payload.get("alias", "A member"))
            text = messages.MEMBER_LEFT.format(alias=alias, window_label=label)
        else:
            raise ValueError(f"unknown post kind: {kind}")
        await self._gateway.post_message(thread_id, text)

    async def _dm_user(self, job: Job) -> None:
        room = await self._room(job)
        user_id = job.payload.get("discord_user_id")
        if not user_id:
            return
        url = messages.thread_link(self._config.guild_id, self._thread(room))
        text = messages.THREAD_DM.format(
            event_title=messages.clean(room.event_title), thread_url=url
        )
        await self._gateway.send_dm(user_id, text)

    async def _upsert_board_card(self, job: Job) -> None:
        room = await self._room(job)
        gone = room.status in ("closed", "archived") or room.size == 0
        if gone:
            if room.board_message_id:
                await self._gateway.delete_board_card(room.board_message_id)
                await asyncio.to_thread(
                    outbox_jobs.record_board_message, self._ctx, room.room_id, None
                )
            return
        card = messages.BoardCard(
            room_id=room.room_id,
            title=messages.clean(room.event_title),
            date_label=messages.date_label(room.event_date),
            window_label=messages.window_label(room.window, self._config.timezone),
            size=room.size,
            vibe=room.vibe or "-",
            budget=room.budget_band or "-",
            interests=room.top_interests,
            status=room.status,
        )
        message_id = await self._gateway.upsert_board_card(card, room.board_message_id)
        if message_id != room.board_message_id:
            await asyncio.to_thread(
                outbox_jobs.record_board_message, self._ctx, room.room_id, message_id
            )

    async def _archive_thread(self, job: Job) -> None:
        room = await self._room(job)
        if room.thread_id:
            await self._gateway.archive_thread(room.thread_id)
