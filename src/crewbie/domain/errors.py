"""Domain errors with stable codes; the API and Discord layers each map them once."""

from typing import Any


class DomainError(Exception):
    """Base class. `code` is part of the API contract (03-API-CONTRACT.md section 1)."""

    code = "INTERNAL"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}


class Unauthorized(DomainError):
    code = "UNAUTHORIZED"


class RateLimited(DomainError):
    code = "RATE_LIMITED"


class ValidationFailed(DomainError):
    code = "VALIDATION_FAILED"

    def __init__(self, fields: dict[str, str]) -> None:
        super().__init__("Some fields are invalid.", {"fields": fields})
        self.fields = fields


class NotFound(DomainError):
    code = "NOT_FOUND"


class LinkRequired(DomainError):
    code = "LINK_REQUIRED"


class AlreadyInRoom(DomainError):
    code = "ALREADY_IN_ROOM"


class OfferExpired(DomainError):
    code = "OFFER_EXPIRED"


class OfferStale(DomainError):
    code = "OFFER_STALE"


class OfferClosed(DomainError):
    code = "OFFER_CLOSED"


class EventStarted(DomainError):
    code = "EVENT_STARTED"


class LinkCodeInvalid(DomainError):
    """Bot-facing: `details["reason"]` is expired, used or unknown."""

    code = "LINK_CODE_INVALID"


class LinkConflict(DomainError):
    """Discord user or install is linked elsewhere; the bot must confirm a re-link."""

    code = "LINK_CONFLICT"


class Forbidden(DomainError):
    """Operation refused in this environment (for example seeding in prod)."""

    code = "FORBIDDEN"
