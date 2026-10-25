"""Messaging provider abstraction. Only the mock provider is implemented.

A real provider (e.g. Discord) must satisfy ``MessagingProvider`` and may only
report ``acknowledged=True`` when the platform itself returned a message id.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, Protocol

from services.commitments.models import PROVIDER_UNAVAILABLE, CommitmentError


class ProviderUnavailable(CommitmentError):
    def __init__(self, message: str = ""):
        super().__init__(PROVIDER_UNAVAILABLE, message)


@dataclass(frozen=True)
class SendReceipt:
    acknowledged: bool
    provider_message_id: Optional[str]
    request_id: str
    provider: str


class MessagingProvider(Protocol):
    name: str

    def send_group_message(self, channel_id: str, text: str, *, request_id: str) -> SendReceipt: ...

    def send_private_message(self, member_ref: str, text: str, *, request_id: str) -> SendReceipt: ...


@dataclass
class MockMessagingProvider:
    """In-memory provider. Acknowledges every send unless told to fail."""

    name: str = "mock"
    group_outbox: list = field(default_factory=list)
    private_outbox: list = field(default_factory=list)
    fail_next: int = 0  # number of upcoming sends to fail with PROVIDER_UNAVAILABLE
    _receipts: dict = field(default_factory=dict)
    _seq: int = 0

    def _send(self, box: list, target: str, text: str, request_id: str) -> SendReceipt:
        if request_id in self._receipts:  # idempotent resend
            return self._receipts[request_id]
        if self.fail_next > 0:
            self.fail_next -= 1
            raise ProviderUnavailable("mock provider forced failure")
        self._seq += 1
        receipt = SendReceipt(True, f"mock_msg_{self._seq:04d}", request_id, self.name)
        box.append({"target": target, "text": text, "request_id": request_id,
                    "provider_message_id": receipt.provider_message_id})
        self._receipts[request_id] = receipt
        return receipt

    def send_group_message(self, channel_id, text, *, request_id):
        return self._send(self.group_outbox, channel_id, text, request_id)

    def send_private_message(self, member_ref, text, *, request_id):
        return self._send(self.private_outbox, member_ref, text, request_id)


# What has and has not been verified; surfaced by the demo and docs.
PROVIDER_STATUS = {
    "mock": {"implemented": True, "verified_against_platform": False, "note": "default; no network"},
    "discord": {
        "implemented": False,
        "verified_against_platform": False,
        "note": "not implemented: no bot token, invite or documented permissions were available/authorised",
    },
}


def provider_from_env(env: Optional[dict] = None) -> MessagingProvider:
    """Return the configured provider. Anything but the mock raises until validated."""
    env = os.environ if env is None else env
    choice = env.get("CREWBIE_CHAT_PROVIDER", "mock").lower()
    if choice == "mock":
        return MockMessagingProvider()
    status = PROVIDER_STATUS.get(choice, {"note": "unknown provider"})
    raise ProviderUnavailable(f"provider '{choice}' unavailable: {status['note']}; use CREWBIE_CHAT_PROVIDER=mock")
