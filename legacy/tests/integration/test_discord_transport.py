import asyncio
import threading
import unittest
from types import SimpleNamespace

from apps.chat_bot.discord_live import DiscordProvider
from apps.chat_bot.providers import ProviderUnavailable


class DiscordTransportTests(unittest.TestCase):
    """Fake external Discord channel only; real provider adapter and receipt logic."""
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        self.sent = []
        self.fail = False

        async def send(text, **kwargs):
            if self.fail:
                raise OSError("network down")
            self.sent.append((text, kwargs))
            return SimpleNamespace(id=123)
        client = SimpleNamespace(get_channel=lambda channel_id: SimpleNamespace(send=send))
        self.provider = DiscordProvider(client, self.loop, 1234)

    def tearDown(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(2)
        self.loop.close()

    def test_acknowledgement_and_idempotency(self):
        try:
            import discord
        except ImportError:
            self.skipTest("optional discord.py not installed")
        receipt = self.provider.send_group_message("synthetic_session", "Proposal v1", request_id="one")
        self.assertTrue(receipt.acknowledged)
        self.assertEqual(receipt.provider_message_id, "123")
        self.assertEqual(self.provider.send_group_message("synthetic_session", "Proposal v1", request_id="one"), receipt)
        self.assertEqual(len(self.sent), 1)
        self.assertTrue(self.sent[0][0].startswith("DEMO/SYNTHETIC"))
        self.assertFalse(self.sent[0][1]["allowed_mentions"].everyone)

    def test_unavailable_provider_never_acknowledges(self):
        self.fail = True
        with self.assertRaises(ProviderUnavailable):
            self.provider.send_group_message("session", "Proposal", request_id="failed")
        self.assertEqual(self.provider.receipts, {})

    def test_private_messages_are_unavailable(self):
        with self.assertRaises(ProviderUnavailable):
            self.provider.send_private_message("stu_alex", "Hello", request_id="private")
