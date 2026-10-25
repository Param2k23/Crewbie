import os
import stat
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from crewbie.domain.intent import PrivateEnvelope
from crewbie.persistence.crypto import EnvelopeCipher, EnvelopeKeyError, load_cipher
from tests.unit.domain.helpers import at

ENVELOPE = PrivateEnvelope(at(-30), at(300), 913.0)


def new_key() -> str:
    return Fernet.generate_key().decode()


def test_envelope_round_trip_through_encryption() -> None:
    cipher = EnvelopeCipher(new_key())
    restored = cipher.decrypt(cipher.encrypt(ENVELOPE))
    assert (restored.flex_earliest, restored.flex_latest, restored.budget_cap_usd) == (
        ENVELOPE.flex_earliest,
        ENVELOPE.flex_latest,
        913.0,
    )


def test_round_trip_without_budget_cap() -> None:
    cipher = EnvelopeCipher(new_key())
    assert cipher.decrypt(cipher.encrypt(PrivateEnvelope(at(0), at(60)))).budget_cap_usd is None


def test_ciphertext_does_not_contain_plaintext_values() -> None:
    blob = EnvelopeCipher(new_key()).encrypt(ENVELOPE)
    assert b"913" not in blob and b"2026" not in blob and b"flex" not in blob


def test_wrong_key_cannot_decrypt() -> None:
    blob = EnvelopeCipher(new_key()).encrypt(ENVELOPE)
    with pytest.raises(EnvelopeKeyError):
        EnvelopeCipher(new_key()).decrypt(blob)


def test_invalid_key_is_rejected() -> None:
    with pytest.raises(EnvelopeKeyError):
        EnvelopeCipher("not-a-key")


def test_configured_key_wins(tmp_path: Path) -> None:
    key = new_key()
    cipher = load_cipher(key, "prod", tmp_path / "dev.key")
    assert EnvelopeCipher(key).decrypt(cipher.encrypt(ENVELOPE)).budget_cap_usd == 913.0
    assert not (tmp_path / "dev.key").exists()


def test_prod_requires_a_key(tmp_path: Path) -> None:
    with pytest.raises(EnvelopeKeyError):
        load_cipher("", "prod", tmp_path / "dev.key")
    assert not (tmp_path / "dev.key").exists()


def test_dev_generates_a_private_key_file_once_and_reuses_it(tmp_path: Path) -> None:
    path = tmp_path / "data" / "dev.key"
    first = load_cipher("", "dev", path)
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    blob = first.encrypt(ENVELOPE)
    assert load_cipher("", "dev", path).decrypt(blob).budget_cap_usd == 913.0
