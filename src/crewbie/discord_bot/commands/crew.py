"""`/crew status`, `/crew leave`, `/crew help` and `/crew meetpoint`."""

import discord
from discord import app_commands

from crewbie.discord_bot import handlers
from crewbie.discord_bot.views.confirm import respond
from crewbie.services.context import ServiceContext


def register(group: app_commands.Group, ctx: ServiceContext) -> None:
    @group.command(name="status", description="Show the crews you are in")
    async def status(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await respond(interaction, await handlers.status(ctx, str(interaction.user.id)))

    @group.command(name="leave", description="Leave the crew whose thread you are in")
    async def leave(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        in_thread = isinstance(interaction.channel, discord.Thread)
        thread_id = str(interaction.channel_id) if in_thread else None
        await respond(interaction, await handlers.leave(ctx, thread_id, str(interaction.user.id)))

    @group.command(name="help", description="How Crewbie works")
    async def help_command(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await respond(interaction, handlers.help_text())

    @group.command(name="meetpoint", description="Suggest meeting spots (coming soon)")
    async def meetpoint(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await respond(interaction, handlers.meetpoint())
