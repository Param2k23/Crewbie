"""Fernet encryption of the private envelope (SRS 5.2)."""

import json
import os
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from crewbie.domain.intent import PrivateEnvelope


class EnvelopeKeyError(Exception):
    """The envelope key is missing, malformed, or cannot decrypt stored data."""


class EnvelopeCipher:
    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode())
        except (ValueError, TypeError) as exc:
            raise EnvelopeKeyError("CREWBIE_ENVELOPE_KEY is not a valid Fernet key") from exc

    def encrypt(self, envelope: PrivateEnvelope) -> bytes:
        document = {
            "flex_earliest": envelope.flex_earliest.isoformat(),
            "flex_latest": envelope.flex_latest.isoformat(),
            "budget_cap_usd": envelope.budget_cap_usd,
        }
        return self._fernet.encrypt(json.dumps(document).encode())

    def decrypt(self, ciphertext: bytes) -> PrivateEnvelope:
        try:
            document = json.loads(self._fernet.decrypt(ciphertext))
        except InvalidToken as exc:
            raise EnvelopeKeyError("envelope cannot be decrypted with the configured key") from exc
        return PrivateEnvelope(
            flex_earliest=datetime.fromisoformat(document["flex_earliest"]),
            flex_latest=datetime.fromisoformat(document["flex_latest"]),
            budget_cap_usd=document["budget_cap_usd"],
        )


def load_cipher(configured_key: str, env: str, dev_key_path: Path) -> EnvelopeCipher:
    """Use the configured key. In dev only, create and reuse a key file so restarts keep working."""
    if configured_key:
        return EnvelopeCipher(configured_key)
    if env != "dev":
        raise EnvelopeKeyError("CREWBIE_ENVELOPE_KEY is required outside dev")
    if dev_key_path.exists():
        return EnvelopeCipher(dev_key_path.read_text().strip())
    key = Fernet.generate_key().decode()
    dev_key_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(dev_key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write(key)
    return EnvelopeCipher(key)
