"""`/crew link` (FR-LNK-02)."""

import discord
from discord import app_commands

from crewbie.discord_bot import handlers
from crewbie.discord_bot.views.confirm import respond
from crewbie.services.context import ServiceContext


def register(group: app_commands.Group, ctx: ServiceContext) -> None:
    @group.command(name="link", description="Link your Discord account to your Cubbie")
    @app_commands.describe(code="The 6-character code Cubbie gave you")
    async def link(interaction: discord.Interaction, code: str) -> None:
        await interaction.response.defer(ephemeral=True)
        response = await handlers.link(ctx, code, str(interaction.user.id), interaction.user.name)
        await respond(interaction, response)
