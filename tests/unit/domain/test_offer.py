import pytest

from crewbie.domain.errors import EventStarted, OfferClosed, OfferExpired, OfferStale
from crewbie.domain.offer import (
    OfferState,
    OfferType,
    ensure_acceptable,
    ensure_not_started,
    is_expired,
    is_stale,
    offer_expiry,
)

from .helpers import at, window


def accept(**overrides: object) -> None:
    args: dict[str, object] = {
        "state": OfferState.OPEN,
        "offer_type": OfferType.JOIN,
        "expires_at": at(15),
        "offered_room_version": 3,
        "current_room_version": 3,
        "now": at(5),
    }
    args.update(overrides)
    ensure_acceptable(**args)  # type: ignore[arg-type]


def test_fr_ofr_01_expiry_is_ttl_after_creation() -> None:
    assert offer_expiry(at(0), 15) == at(15)


def test_fr_ofr_06_expired_offer_rejected_at_and_after_expiry() -> None:
    assert not is_expired(at(15), at(14))
    assert is_expired(at(15), at(15))
    with pytest.raises(OfferExpired):
        accept(now=at(15))


def test_fr_ofr_02_stale_when_room_version_changed() -> None:
    with pytest.raises(OfferStale):
        accept(current_room_version=4)


def test_fr_ofr_02_new_room_offers_never_go_stale() -> None:
    assert not is_stale(OfferType.NEW_ROOM, None, 7)
    accept(offer_type=OfferType.NEW_ROOM, offered_room_version=None, current_room_version=7)


@pytest.mark.parametrize(
    "state", [OfferState.ACCEPTED, OfferState.DECLINED, OfferState.EXPIRED, OfferState.STALE]
)
def test_fr_ofr_05_answered_offers_are_closed(state: OfferState) -> None:
    with pytest.raises(OfferClosed):
        accept(state=state)


def test_open_valid_offer_is_acceptable() -> None:
    accept()


def test_closed_takes_precedence_over_expired_and_stale() -> None:
    with pytest.raises(OfferClosed):
        accept(state=OfferState.ACCEPTED, now=at(99), current_room_version=9)


def test_event_started_error() -> None:
    ensure_not_started(window(10, 20), at(9))
    with pytest.raises(EventStarted):
        ensure_not_started(window(10, 20), at(10))
