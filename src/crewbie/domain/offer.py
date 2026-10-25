"""Offer rules: expiry and staleness (FR-OFR-01, -02, -06)."""

from datetime import datetime, timedelta
from enum import StrEnum

from crewbie.domain.errors import EventStarted, OfferClosed, OfferExpired, OfferStale
from crewbie.domain.windows import TimeWindow


class OfferType(StrEnum):
    JOIN = "join"
    NEW_ROOM = "new_room"


class OfferState(StrEnum):
    OPEN = "open"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    STALE = "stale"


def offer_expiry(created_at: datetime, ttl_minutes: int) -> datetime:
    return created_at + timedelta(minutes=ttl_minutes)


def is_expired(expires_at: datetime, now: datetime) -> bool:
    return now >= expires_at


def is_stale(offer_type: OfferType, offered_room_version: int | None, current_version: int) -> bool:
    """Only join offers depend on a room; they go stale when the room version moves."""
    return offer_type is OfferType.JOIN and offered_room_version != current_version


def ensure_acceptable(
    *,
    state: OfferState,
    offer_type: OfferType,
    expires_at: datetime,
    offered_room_version: int | None,
    current_room_version: int,
    now: datetime,
) -> None:
    """Raise the contract error that stops an accept; return when it may proceed."""
    if state is not OfferState.OPEN:
        raise OfferClosed("This offer was already answered.")
    if is_expired(expires_at, now):
        raise OfferExpired("This offer has expired.")
    if is_stale(offer_type, offered_room_version, current_room_version):
        raise OfferStale("The crew changed. A new offer is on its way.")


def ensure_not_started(window: TimeWindow, now: datetime) -> None:
    if now >= window.start:
        raise EventStarted("This plan has already started.")
