"""Production `Gateway`: performs the operations through a connected discord.py client."""

import contextlib
import logging
from collections.abc import Sequence

import discord

from crewbie.discord_bot.gateway import DmClosedError
from crewbie.discord_bot.messages import BoardCard
from crewbie.discord_bot.views.board_card import card_embed, card_view

logger = logging.getLogger("crewbie.discord.gateway")

THREAD_AUTO_ARCHIVE_MINUTES = 10080  # a week; the lifecycle worker archives sooner


class DiscordGateway:
    def __init__(
        self, client: discord.Client, crews_channel_id: int, board_channel_id: int
    ) -> None:
        self._client = client
        self._crews_channel_id = crews_channel_id
        self._board_channel_id = board_channel_id

    async def _channel(self, channel_id: int) -> discord.abc.GuildChannel | discord.Thread:
        found = self._client.get_channel(channel_id) or await self._client.fetch_channel(channel_id)
        if isinstance(found, discord.abc.PrivateChannel) or found is None:
            raise LookupError(f"channel {channel_id} is not a guild channel")
        return found

    async def _thread(self, thread_id: str) -> discord.Thread:
        channel = await self._channel(int(thread_id))
        if not isinstance(channel, discord.Thread):
            raise LookupError(f"{thread_id} is not a thread")
        return channel

    async def create_private_thread(self, name: str) -> str:
        parent = await self._channel(self._crews_channel_id)
        if not isinstance(parent, discord.TextChannel):
            raise LookupError("the crews channel must be a text channel")
        thread = await parent.create_thread(
            name=name[:100],
            type=discord.ChannelType.private_thread,
            invitable=False,
            auto_archive_duration=THREAD_AUTO_ARCHIVE_MINUTES,  # type: ignore[arg-type]
        )
        return str(thread.id)

    async def add_user(self, thread_id: str, user_id: str) -> None:
        await (await self._thread(thread_id)).add_user(discord.Object(id=int(user_id)))

    async def remove_user(self, thread_id: str, user_id: str) -> None:
        await (await self._thread(thread_id)).remove_user(discord.Object(id=int(user_id)))

    async def post_message(
        self, thread_id: str, content: str, mention_user_ids: Sequence[str] = ()
    ) -> str:
        mentions = discord.AllowedMentions(
            users=[discord.Object(id=int(uid)) for uid in mention_user_ids]
        )
        message = await (await self._thread(thread_id)).send(content, allowed_mentions=mentions)
        return str(message.id)

    async def send_dm(self, user_id: str, content: str) -> None:
        user = await self._client.fetch_user(int(user_id))
        try:
            await user.send(content, allowed_mentions=discord.AllowedMentions.none())
        except discord.Forbidden as error:
            raise DmClosedError(user_id) from error

    async def upsert_board_card(self, card: BoardCard, message_id: str | None) -> str:
        channel = await self._channel(self._board_channel_id)
        if not isinstance(channel, discord.TextChannel):
            raise LookupError("the board channel must be a text channel")
        embed, view = card_embed(card), card_view(card.room_id)
        if message_id:
            try:
                existing = await channel.fetch_message(int(message_id))
                await existing.edit(embed=embed, view=view)
                return message_id
            except discord.NotFound:
                logger.info("board card was deleted; posting a new one")
        sent = await channel.send(embed=embed, view=view)
        return str(sent.id)

    async def delete_board_card(self, message_id: str) -> None:
        channel = await self._channel(self._board_channel_id)
        if isinstance(channel, discord.TextChannel):
            with contextlib.suppress(discord.NotFound):
                await (await channel.fetch_message(int(message_id))).delete()

    async def archive_thread(self, thread_id: str) -> None:
        await (await self._thread(thread_id)).edit(archived=True, locked=True)
