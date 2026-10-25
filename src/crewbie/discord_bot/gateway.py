"""The only operations the bot performs on Discord. The worker depends on this protocol, so
tests use a fake and production uses `live_gateway.DiscordGateway`."""

from collections.abc import Sequence
from typing import Protocol

from crewbie.discord_bot.messages import BoardCard


class DmClosedError(Exception):
    """The user does not accept DMs from the bot."""


class Gateway(Protocol):
    async def create_private_thread(self, name: str) -> str: ...

    async def add_user(self, thread_id: str, user_id: str) -> None: ...

    async def remove_user(self, thread_id: str, user_id: str) -> None: ...

    async def post_message(
        self, thread_id: str, content: str, mention_user_ids: Sequence[str] = ()
    ) -> str: ...

    async def send_dm(self, user_id: str, content: str) -> None: ...

    async def upsert_board_card(self, card: BoardCard, message_id: str | None) -> str: ...

    async def delete_board_card(self, message_id: str) -> None: ...

    async def archive_thread(self, thread_id: str) -> None: ...
