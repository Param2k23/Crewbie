"""Real Discord gateway/delivery for authorized testers and synthetic plans only.

No token is required to import or unit-test this adapter. No student data is loaded.
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
from http.server import ThreadingHTTPServer

from apps.chat_bot.providers import SendReceipt, ProviderUnavailable
from services.api.runtime import Runtime, MEMBERS
from services.api.main import make_handler


class DiscordProvider:
    name = "discord"

    def __init__(self, client, loop, channel_id):
        self.client, self.loop, self.channel_id = client, loop, int(channel_id)
        self.receipts = {}

    def send_group_message(self, channel_id, text, *, request_id):
        if request_id in self.receipts:
            return self.receipts[request_id]

        async def send():
            import discord
            channel = self.client.get_channel(self.channel_id)
            if channel is None:
                channel = await self.client.fetch_channel(self.channel_id)
            if len(text) > 1850:
                raise ProviderUnavailable("proposal exceeds provider message limit")
            message = await channel.send("DEMO/SYNTHETIC planning; no booking.\n" + text,
                                         allowed_mentions=discord.AllowedMentions.none())
            return str(message.id)
        try:
            future = asyncio.run_coroutine_threadsafe(send(), self.loop)
            message_id = future.result(timeout=20)
        except Exception:
            if 'future' in locals():
                future.cancel()
            raise ProviderUnavailable("Discord did not acknowledge delivery") from None
        receipt = SendReceipt(True, message_id, request_id, "discord")
        self.receipts[request_id] = receipt
        return receipt

    def send_private_message(self, member_ref, text, *, request_id):
        # This minimal adapter has no DM permission or unprompted introduction path.
        raise ProviderUnavailable("private delivery is not configured")


def validate_members(raw):
    members = json.loads(raw)
    if (not isinstance(members, dict) or len(members) != 4 or set(members.values()) != set(MEMBERS)
            or not all(isinstance(k, str) and k.isdigit() for k in members)):
        raise ValueError("Configure four authorized Discord user IDs mapped to the four synthetic refs")
    return members


def main():
    import discord
    token = os.environ.get("DISCORD_BOT_TOKEN")
    channel_id = os.environ.get("DISCORD_CHANNEL_ID", "")
    if not token or not channel_id.isdigit():
        raise SystemExit("Set DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID; see SETUP_WINDOWS.md")
    members = validate_members(os.environ.get("CREWBIE_DISCORD_MEMBERS", "{}"))
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    runtime = None
    active = None
    server = None
    stop = threading.Event()
    seen = set()
    message_lock = asyncio.Lock()

    @client.event
    async def on_ready():
        nonlocal runtime, server
        if runtime is None:
            runtime = Runtime(DiscordProvider(client, asyncio.get_running_loop(), channel_id))
            server = ThreadingHTTPServer(("127.0.0.1", 8787), make_handler(runtime, stop))
            threading.Thread(target=server.serve_forever, daemon=True).start()
        print("Discord connected. Authorized test channel only; synthetic constraints; API 127.0.0.1:8787", flush=True)

    @client.event
    async def on_message(message):
        nonlocal active
        if (runtime is None or message.author.bot or message.channel.id != int(channel_id)
                or str(message.author.id) not in members):
            return
        async with message_lock:
            rid = str(message.id)
            if rid in seen:
                return
            text = message.content.strip()
            try:
                if text in {"!crewbie evening", "!crewbie weekend"}:
                    if active and runtime.snapshot(active)["state"] not in {"failed", "cancelled", "confirmed"}:
                        await message.channel.send("A proposal is open. Approve its exact version or request a change.")
                        return
                    scenario = text.split()[-1]
                    snap = await asyncio.to_thread(runtime.seed, scenario, request_id=rid)
                    active = snap["session_id"]
                    await message.channel.send(f"Synthetic session: {active}. Approve with `I accept version {snap['version']}`. Nothing is booked.")
                elif active:
                    await asyncio.to_thread(runtime.message, active, members[str(message.author.id)], text, rid,
                                            identity_source="provider_verified")
                else:
                    return
                seen.add(rid)
            except Exception:
                await message.channel.send("Planning/provider unavailable. No success is assumed; inspect the current proposal before retrying.")

    try:
        client.run(token, log_handler=None)
    finally:
        stop.set()
        if server:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
