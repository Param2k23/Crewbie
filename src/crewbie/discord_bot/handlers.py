"""Slash-command and modal logic, free of discord.py types so it can be tested directly.

Each handler returns a `Response`; `views/confirm.py` turns it into a Discord reply. Handlers
call services only, and blocking service calls run in a thread (the database layer is sync).
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, time

from crewbie.discord_bot import messages
from crewbie.domain.budget import BudgetBand
from crewbie.domain.errors import DomainError, LinkCodeInvalid, LinkConflict
from crewbie.domain.vibe import Vibe
from crewbie.services import bot_actions, linking, offers
from crewbie.services.context import ServiceContext


@dataclass(frozen=True)
class Confirm:
    label: str
    action: Callable[[], Awaitable["Response"]]


@dataclass(frozen=True)
class Response:
    text: str
    confirm: Confirm | None = None


def _failure(error: DomainError) -> Response:
    return Response(messages.error_text(error))


async def link(ctx: ServiceContext, code: str, user_id: str, username: str) -> Response:
    """`/crew link` (FR-LNK-02). Replies never reveal install data."""
    try:
        await asyncio.to_thread(linking.complete, ctx, code, user_id, username)
    except LinkCodeInvalid as error:
        return Response(
            messages.LINK_REASONS.get(error.details.get("reason", ""), messages.GENERIC_ERROR)
        )
    except LinkConflict as error:
        prompt = (
            messages.LINK_CONFLICT_DISCORD
            if error.details.get("reason") == "discord_user_linked"
            else messages.LINK_CONFLICT_INSTALL
        )

        async def replace() -> Response:
            await asyncio.to_thread(linking.complete, ctx, code, user_id, username, replace=True)
            return Response(messages.LINK_REPLACED)

        return Response(prompt, Confirm(messages.LINK_REPLACE_LABEL, replace))
    return Response(messages.LINK_OK)


async def status(ctx: ServiceContext, user_id: str) -> Response:
    crews = await asyncio.to_thread(bot_actions.crews_for_user, ctx, user_id)
    if not crews:
        return Response(messages.STATUS_EMPTY)
    lines = [
        messages.STATUS_LINE.format(
            title=messages.clean(crew.event_title),
            window_label=messages.window_label(crew.window, ctx.config.timezone),
            size=crew.size,
            thread=crew.thread_url or messages.STATUS_NO_THREAD,
        )
        for crew in crews
    ]
    return Response("\n".join(lines))


def help_text() -> Response:
    return Response(messages.HELP)


def meetpoint() -> Response:
    return Response(messages.MEETPOINT_SOON)


async def leave(ctx: ServiceContext, thread_id: str | None, user_id: str) -> Response:
    """`/crew leave` (FR-BOT-10): ask first, then withdraw."""
    if thread_id is None:
        return Response(messages.LEAVE_NOT_IN_THREAD)
    found = await asyncio.to_thread(bot_actions.member_in_thread, ctx, thread_id, user_id)
    if found is None:
        return Response(messages.LEAVE_NOT_MEMBER)

    async def confirmed() -> Response:
        try:
            await asyncio.to_thread(bot_actions.leave_thread, ctx, thread_id, user_id)
        except DomainError as error:
            return _failure(error)
        return Response(messages.LEAVE_DONE)

    return Response(messages.LEAVE_PROMPT, Confirm(messages.LEAVE_LABEL, confirmed))


class FormError(Exception):
    pass


def parse_join_form(fields: dict[str, str]) -> bot_actions.JoinForm:
    """Turn the modal's five text fields into a `JoinForm`, or raise `FormError` with advice."""

    def clock(name: str) -> time:
        try:
            return datetime.strptime(fields.get(name, "").strip(), "%H:%M").time()
        except ValueError:
            raise FormError(messages.JOIN_BAD_TIME) from None

    try:
        minutes = int(fields.get("minimum", "").strip())
    except ValueError:
        raise FormError(messages.JOIN_BAD_MINUTES) from None
    if not 15 <= minutes <= 720:
        raise FormError(messages.JOIN_BAD_MINUTES)
    try:
        band = BudgetBand.parse(fields.get("budget", "").strip())
    except ValueError:
        raise FormError(messages.JOIN_BAD_BUDGET) from None
    try:
        vibe = Vibe(fields.get("vibe", "").strip().lower())
    except ValueError:
        raise FormError(messages.JOIN_BAD_VIBE) from None
    return bot_actions.JoinForm(clock("earliest"), clock("latest"), minutes, band, vibe)


async def board_join(
    ctx: ServiceContext, user_id: str, username: str, room_id: str, fields: dict[str, str]
) -> Response:
    """The Join modal was submitted (FR-BOT-06): negotiate with that room, then ask to confirm."""
    try:
        form = parse_join_form(fields)
    except FormError as error:
        return Response(str(error))
    try:
        result = await asyncio.to_thread(
            bot_actions.request_board_join, ctx, user_id, username, room_id, form
        )
    except DomainError as error:
        return _failure(error)

    offer = result.offer
    window = messages.window_label(offer.proposal, ctx.config.timezone)
    joins = offer.type == "join"

    async def accept() -> Response:
        try:
            accepted = await asyncio.to_thread(
                offers.accept, ctx, result.install_id, offer.offer_id
            )
        except DomainError as error:
            return _failure(error)
        if not joins:
            return Response(messages.JOIN_STARTED)
        if accepted.thread_url:
            return Response(messages.JOIN_DONE_THREAD.format(thread_url=accepted.thread_url))
        return Response(messages.JOIN_DONE)

    if joins:
        return Response(
            messages.JOIN_OFFER.format(window_label=window),
            Confirm(messages.JOIN_CONFIRM_LABEL, accept),
        )
    return Response(
        messages.JOIN_NO_FIT.format(window_label=window), Confirm(messages.JOIN_NEW_LABEL, accept)
    )
