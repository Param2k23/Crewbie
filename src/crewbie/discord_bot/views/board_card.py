"""The crew-board card: an embed with a persistent Join button (FR-BOT-05)."""

import re
from typing import Any

import discord

from crewbie.discord_bot import messages
from crewbie.discord_bot.messages import BoardCard
from crewbie.discord_bot.views.join_modal import JoinModal

CUSTOM_ID_TEMPLATE = r"crew-join:(?P<room_id>[A-Za-z0-9_]+)"


class BoardJoinButton(discord.ui.DynamicItem[discord.ui.Button[Any]], template=CUSTOM_ID_TEMPLATE):
    """Survives restarts: Discord sends the custom id back and we rebuild the item from it."""

    def __init__(self, room_id: str) -> None:
        super().__init__(
            discord.ui.Button(
                label="Join", style=discord.ButtonStyle.primary, custom_id=f"crew-join:{room_id}"
            )
        )
        self.room_id = room_id

    @classmethod
    async def from_custom_id(
        cls, interaction: discord.Interaction, item: discord.ui.Item[Any], match: re.Match[str]
    ) -> "BoardJoinButton":
        return cls(match["room_id"])

    async def callback(self, interaction: discord.Interaction) -> None:
        ctx = interaction.client.ctx  # type: ignore[attr-defined]
        await interaction.response.send_modal(JoinModal(ctx, self.room_id))


def card_view(room_id: str) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(BoardJoinButton(room_id))
    return view


def card_embed(card: BoardCard) -> discord.Embed:
    embed = discord.Embed(title=card.title, color=discord.Color.blurple())
    embed.add_field(name="When", value=f"{card.date_label}, {card.window_label}", inline=False)
    embed.add_field(name="Going", value=str(card.size))
    embed.add_field(name="Vibe", value=card.vibe)
    embed.add_field(name="Budget", value=card.budget)
    if card.interests:
        embed.add_field(name="Into", value=", ".join(i.replace("-", " ") for i in card.interests))
    embed.set_footer(text=messages.BOARD_FOOTER)
    return embed
