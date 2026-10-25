"""The Join modal (FR-BOT-06). Five text fields; parsing and matching live in `handlers`."""

import discord

from crewbie.discord_bot import handlers, messages
from crewbie.discord_bot.views.confirm import respond
from crewbie.services.context import ServiceContext

_PLACEHOLDERS = {
    "earliest": "17:30",
    "latest": "21:00",
    "minimum": "90",
    "budget": "low",
    "vibe": "chill",
}


class JoinModal(discord.ui.Modal, title=messages.JOIN_TITLE):
    def __init__(self, ctx: ServiceContext, room_id: str) -> None:
        super().__init__()
        self._ctx = ctx
        self._room_id = room_id
        self._inputs: dict[str, discord.ui.TextInput[JoinModal]] = {}
        for name, label in messages.JOIN_FIELDS.items():
            field: discord.ui.TextInput[JoinModal] = discord.ui.TextInput(
                label=label[:45], placeholder=_PLACEHOLDERS[name], max_length=12, required=True
            )
            self._inputs[name] = field
            self.add_item(field)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        fields = {name: item.value for name, item in self._inputs.items()}
        response = await handlers.board_join(
            self._ctx, str(interaction.user.id), interaction.user.name, self._room_id, fields
        )
        await respond(interaction, response)
