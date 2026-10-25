"""Turns a handler `Response` into a Discord reply, with an optional confirm button."""

import logging

import discord

from crewbie.discord_bot import messages
from crewbie.discord_bot.handlers import Confirm, Response

logger = logging.getLogger("crewbie.discord")


class ConfirmView(discord.ui.View):
    def __init__(self, confirm: Confirm, user_id: int) -> None:
        super().__init__(timeout=180)
        self._confirm = confirm
        self._user_id = user_id
        button: discord.ui.Button[ConfirmView] = discord.ui.Button(
            label=confirm.label, style=discord.ButtonStyle.primary
        )
        button.callback = self._pressed  # type: ignore[method-assign]
        self.add_item(button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self._user_id

    async def _pressed(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            result = await self._confirm.action()
        except Exception:
            logger.exception("confirm action failed")
            result = Response(messages.GENERIC_ERROR)
        self.stop()
        view = ConfirmView(result.confirm, self._user_id) if result.confirm else None
        await interaction.edit_original_response(content=result.text, view=view)


async def respond(interaction: discord.Interaction, response: Response) -> None:
    """Send an ephemeral reply. Call `interaction.response.defer(ephemeral=True)` first."""
    if response.confirm is None:
        await interaction.followup.send(response.text, ephemeral=True)
        return
    view = ConfirmView(response.confirm, interaction.user.id)
    await interaction.followup.send(response.text, ephemeral=True, view=view)
