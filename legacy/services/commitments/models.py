"""Commitment data model: states, errors, records and proposal bookkeeping."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

STATES = (
    "pending",
    "interested",
    "tentative",
    "conditional",
    "accepted",
    "declined",
    "withdrawn",
)

# Shared error codes from CONTRACTS.md section 5, plus A5-internal codes.
CONSENT_REQUIRED = "CONSENT_REQUIRED"
APPROVAL_INCOMPLETE = "APPROVAL_INCOMPLETE"
PROPOSAL_STALE = "PROPOSAL_STALE"
PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
PRIVATE_FIELD_IN_SNAPSHOT = "PRIVATE_FIELD_IN_SNAPSHOT"
VERSION_CONFLICT = "VERSION_CONFLICT"
UNKNOWN_PROPOSAL = "UNKNOWN_PROPOSAL"
NOT_A_PARTICIPANT = "NOT_A_PARTICIPANT"
NOT_PRESENTED = "PROPOSAL_NOT_PRESENTED"
IDENTITY_UNVERIFIED = "IDENTITY_UNVERIFIED"


class CommitmentError(Exception):
    def __init__(self, code: str, message: str = ""):
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.message = message


@dataclass
class CommitmentRecord:
    """One member's latest response to one exact proposal version.

    The first seven fields are the contract shape; ``evidence`` is internal
    audit data (rule name and a text digest, never the raw message).
    """

    session_id: str
    plan_id: str
    version: int
    member_ref: str
    state: str = "pending"
    explicit_acceptance: bool = False
    last_changed_at: str = ""
    request_id: Optional[str] = None
    evidence: dict = field(default_factory=dict)
    last_sent_at: Optional[str] = None  # ordering guard, internal

    def to_contract(self) -> dict:
        return {
            "session_id": self.session_id,
            "plan_id": self.plan_id,
            "version": self.version,
            "member_ref": self.member_ref,
            "state": self.state,
            "explicit_acceptance": self.explicit_acceptance,
            "last_changed_at": self.last_changed_at,
            "request_id": self.request_id,
        }


TERMINAL_STATUSES = ("confirmed", "superseded", "invalidated", "revoked", "cancelled")


@dataclass
class Proposal:
    session_id: str
    plan_id: str
    version: int
    snapshot: dict[str, Any]
    fingerprint: str
    required: tuple
    activity_scope: str
    validated: bool = True
    presented_at: Optional[str] = None
    status: str = "open"  # open | confirmed | superseded | invalidated | revoked | cancelled
    confirmed_emitted: bool = False
    nudge_count: int = 0
    last_nudge_at: Optional[str] = None
    clarified: list = field(default_factory=list)  # members already given a clarification prompt

    @property
    def key(self) -> tuple:
        return (self.session_id, self.plan_id, self.version)
