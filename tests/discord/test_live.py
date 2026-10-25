"""Opt-in smoke test against the real Discord server: `uv run pytest -m discord_live`.

Creates and removes a private thread in #crews and posts one message to the test channel, which
proves the bot token, channel IDs and permissions (Create Private Threads, Manage Threads, Send
Messages in Threads) are right. Needs CREWBIE_DISCORD_TEST_CHANNEL_ID in .env.
"""

import asyncio

import pytest

from crewbie.config import Settings

pytestmark = pytest.mark.discord_live


def test_the_bot_can_post_and_make_private_threads_in_the_real_server() -> None:
    import discord

    settings = Settings()
    test_channel = settings.discord_test_channel_id
    if not (settings.discord_token and settings.discord_crews_channel_id and test_channel):
        pytest.skip("Discord settings or CREWBIE_DISCORD_TEST_CHANNEL_ID missing")

    async def scenario() -> None:
        client = discord.Client(intents=discord.Intents.default())
        ready = asyncio.Event()

        @client.event
        async def on_ready() -> None:
            ready.set()

        login = asyncio.create_task(client.start(settings.discord_token))
        try:
            await asyncio.wait_for(ready.wait(), timeout=30)
            channel = await client.fetch_channel(int(test_channel))
            assert isinstance(channel, discord.TextChannel)
            message = await channel.send("Crewbie live test: permissions check (safe to delete).")
            await message.delete()

            crews = await client.fetch_channel(int(settings.discord_crews_channel_id))
            assert isinstance(crews, discord.TextChannel)
            thread = await crews.create_thread(
                name="crewbie-live-test",
                type=discord.ChannelType.private_thread,
                invitable=False,
            )
            await thread.send("Private thread works.")
            await thread.edit(archived=True, locked=True)
            await thread.delete()
        finally:
            await client.close()
            login.cancel()

    asyncio.run(scenario())
