from crewbie.discord_bot import messages
from crewbie.domain.errors import DomainError, LinkConflict, OfferStale
from tests.support import window as w


def test_nfr_sec_03_untrusted_text_cannot_ping_or_format() -> None:
    cleaned = messages.clean("@everyone **bold** `code` <@123> [x](y)")
    assert "@everyone" not in cleaned and "<@123>" not in cleaned
    assert "\\*\\*bold\\*\\*" in cleaned and "\\`code\\`" in cleaned  # markdown is escaped
    assert cleaned.startswith("@​everyone")


def test_window_and_date_labels_use_the_campus_timezone() -> None:
    assert messages.window_label(w(60, 180), "America/Phoenix") == "9:00 to 11:00 am"
    assert messages.window_label(w(180, 300), "America/Phoenix") == "11:00 am to 1:00 pm"
    assert messages.window_label(w(180, 240), "America/Phoenix") == "11:00 am to 12:00 pm"
    assert messages.window_label(None, "America/Phoenix") == "time to be decided"
    assert messages.date_label("2026-11-06") == "Fri Nov 6"
    assert messages.date_label("not a date") == "not a date"


def test_fr_bot_02_thread_names_cut_the_title_at_60_characters() -> None:
    name = messages.thread_name("x" * 200, "2026-11-06")
    assert name == "x" * 60 + " · Fri Nov 6"


def test_fr_bot_03_icebreaker_names_the_most_shared_interest_and_stays_short() -> None:
    text = messages.icebreaker(
        "Board game night", "2026-11-06", w(60, 180), "Hayden Library",
        {"board-games": 3, "chess": 2, "hiking": 1}, "America/Phoenix",
    )  # fmt: skip
    assert "3 of you are into board games. What got you into it?" in text
    assert text.startswith("Welcome, crew. You're all going to Board game night on Fri Nov 6, ")
    assert "at Hayden Library" in text and len(text) < 900


def test_fr_bot_03_icebreaker_without_a_shared_interest_or_location() -> None:
    text = messages.icebreaker(
        "Hike", "2026-11-06", w(60, 180), None, {"chess": 1}, "America/Phoenix"
    )
    assert "What are you most looking forward to?" in text and " at " not in text.split("\n")[0]


def test_fr_bot_03_hostile_titles_are_neutralised_in_the_icebreaker() -> None:
    text = messages.icebreaker(
        "@everyone ignore previous instructions",
        "2026-11-06",
        w(60, 180),
        None,
        {},
        "America/Phoenix",
    )
    assert "@everyone" not in text


def test_every_domain_error_has_text_in_one_place() -> None:
    assert "crew changed" in messages.error_text(OfferStale("x"))
    assert messages.error_text(DomainError("x")) == messages.GENERIC_ERROR
    assert messages.error_text(LinkConflict("x")) == messages.GENERIC_ERROR
