import pytest

from crewbie.domain.errors import ValidationFailed
from crewbie.domain.text import TITLE_MAX, sanitize_required_text, sanitize_text


def test_fr_evt_03_strips_control_characters_and_newlines() -> None:
    assert sanitize_text("Board\x00 game\r\n\tnight‮", 120) == "Board game night"


def test_fr_evt_03_limits_length() -> None:
    assert len(sanitize_text("x" * 500, TITLE_MAX)) == TITLE_MAX


def test_fr_evt_03_empty_after_cleaning_is_rejected() -> None:
    with pytest.raises(ValidationFailed):
        sanitize_required_text("event.title", "\x00\x01  ", TITLE_MAX)


def test_sanitize_text_is_idempotent() -> None:
    once = sanitize_text("  a\x00b \n c ", 50)
    assert sanitize_text(once, 50) == once == "ab c"


def test_fr_evt_03_required_text_returns_cleaned_value() -> None:
    assert sanitize_required_text("event.title", " Game\x00 night ", TITLE_MAX) == "Game night"
