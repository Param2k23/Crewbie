"""Consent gateway interface and an in-memory stand-in for A3."""
from __future__ import annotations

from typing import Protocol

PURPOSES = ("matching", "introduction", "plan_acceptance")


class ConsentGateway(Protocol):
    def has_consent(self, member_ref: str, activity_scope: str, purpose: str) -> bool: ...


class MemoryConsentGateway:
    """Fake consent gateway (clearly a stub; A3 owns the real store)."""

    is_stub = True

    def __init__(self) -> None:
        self._granted: set[tuple[str, str, str]] = set()

    def grant(self, member_ref: str, activity_scope: str, *purposes: str) -> None:
        for p in purposes or PURPOSES:
            self._granted.add((member_ref, activity_scope, p))

    def revoke(self, member_ref: str, activity_scope: str, *purposes: str) -> None:
        for p in purposes or PURPOSES:
            self._granted.discard((member_ref, activity_scope, p))

    def has_consent(self, member_ref: str, activity_scope: str, purpose: str) -> bool:
        return (member_ref, activity_scope, purpose) in self._granted
