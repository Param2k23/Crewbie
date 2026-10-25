"""The discord.py client: guild-synced commands, persistent Join buttons, connection status."""

import logging
from collections.abc import Callable

import discord
from discord import app_commands

from crewbie.discord_bot.commands import crew, link
from crewbie.discord_bot.views.board_card import BoardJoinButton
from crewbie.services.context import ServiceContext

logger = logging.getLogger("crewbie.discord")


class CrewbieClient(discord.Client):
    def __init__(
        self, ctx: ServiceContext, guild_id: int, on_status: Callable[[str], None]
    ) -> None:
        # Default intents minus message content: slash commands, buttons and modals need no
        # privileged intents (C-4). Nothing may ping anyone unless a post asks for it explicitly.
        super().__init__(
            intents=discord.Intents.default(), allowed_mentions=discord.AllowedMentions.none()
        )
        self.ctx = ctx
        self._guild = discord.Object(id=guild_id)
        self._on_status = on_status
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        group = app_commands.Group(name="crew", description="Find and manage your crews")
        link.register(group, self.ctx)
        crew.register(group, self.ctx)
        self.tree.add_command(group, guild=self._guild)
        self.add_dynamic_items(BoardJoinButton)
        await self.tree.sync(guild=self._guild)  # instant availability in our guild only

    async def on_ready(self) -> None:
        logger.info("discord connected", extra={"guild_id": self._guild.id})
        self._on_status("connected")

    async def on_resumed(self) -> None:
        self._on_status("connected")

    async def on_disconnect(self) -> None:
        self._on_status("disconnected")
