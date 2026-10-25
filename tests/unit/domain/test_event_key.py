import pytest

from crewbie.domain.errors import ValidationFailed
from crewbie.domain.event_key import event_key, normalize_url

URL = "https://sundevilcentral.eoss.asu.edu/event/123"


def test_fr_evt_01_key_is_16_hex_chars() -> None:
    key = event_key(URL, "2026-11-06", "18:00")
    assert len(key) == 16
    int(key, 16)


def test_fr_evt_01_tracking_params_fragment_case_and_trailing_slash_do_not_change_key() -> None:
    plain = event_key(URL, "2026-11-06", "18:00")
    noisy = event_key(
        "HTTPS://SunDevilCentral.EOSS.asu.edu/event/123/?utm_source=x&fbclid=1&gclid=2&ref=a#top",
        "2026-11-06",
        "18:00",
    )
    assert plain == noisy


def test_fr_evt_01_meaningful_query_params_change_key() -> None:
    assert event_key(URL + "?id=1", "2026-11-06", "18:00") != event_key(
        URL + "?id=2", "2026-11-06", "18:00"
    )


def test_fr_evt_01_date_and_start_change_key_and_missing_start_is_na() -> None:
    base = event_key(URL, "2026-11-06", "18:00")
    assert base != event_key(URL, "2026-11-07", "18:00")
    assert base != event_key(URL, "2026-11-06", None)
    assert event_key(URL, "2026-11-06", None) == event_key(URL, "2026-11-06", None)


def test_fr_evt_01_normalized_form() -> None:
    assert normalize_url("HTTPS://Example.com:8443/a/b/?utm_x=1&k=v#f") == (
        "https://example.com:8443/a/b?k=v"
    )


@pytest.mark.parametrize("url", ["not a url", "/relative/path", "https://"])
def test_fr_evt_01_rejects_non_absolute_urls(url: str) -> None:
    with pytest.raises(ValidationFailed):
        event_key(url, "2026-11-06", None)


@pytest.mark.parametrize(("date", "start"), [("11/06/2026", None), ("2026-11-06", "6pm")])
def test_fr_evt_01_rejects_malformed_date_or_time(date: str, start: str | None) -> None:
    with pytest.raises(ValidationFailed):
        event_key(URL, date, start)


def test_fr_evt_01_ipv6_host_is_bracketed() -> None:
    assert normalize_url("http://[::1]:8000/x/") == "http://[::1]:8000/x"
