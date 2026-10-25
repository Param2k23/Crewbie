"""Privacy guards: inbound snapshot scrubbing and outbound message checks."""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from .models import PRIVATE_FIELD_IN_SNAPSHOT, CommitmentError

# Keys from CONTRACTS.md that must never reach A5 (private profile / evaluation
# data, or per-member costs that were not explicitly approved for the group).
FORBIDDEN_SNAPSHOT_KEYS = frozenset(
    {
        "hard_budget_cap_cents",
        "blocked_windows",
        "soft_preferences",
        "internal_issue_codes",
        "soft_penalty",
        "counteroffer_hints",
        "estimated_cost_cents_by_ref",
        "requires_private_exception",
        "feasible",
        "private_reason",
        "raw_prompt",
        "reasoning",
    }
)

_FORBIDDEN_TEXT = re.compile(
    r"hard[ _]budget|budget cap|spending cap|hard_budget|blocked[ _]window|internal_issue"
    r"|HARD_BUDGET|soft_penalty|chain[- ]of[- ]thought|system prompt|my reasoning",
    re.IGNORECASE,
)
_AMOUNT = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)")


class PrivacyViolation(Exception):
    pass


def assert_snapshot_public(snapshot: Mapping[str, Any]) -> None:
    """Reject a plan snapshot that still carries private fields."""

    def walk(node: Any, path: str) -> None:
        if isinstance(node, Mapping):
            for k, v in node.items():
                if k in FORBIDDEN_SNAPSHOT_KEYS:
                    raise CommitmentError(PRIVATE_FIELD_IN_SNAPSHOT, f"{path}{k}")
                walk(v, f"{path}{k}.")
        elif isinstance(node, (list, tuple)):
            for i, v in enumerate(node):
                walk(v, f"{path}{i}.")

    walk(snapshot, "")


def check_outbound(text: str, allowed_amounts: Iterable[str] = ()) -> None:
    """Raise PrivacyViolation if a group message could leak private data.

    Dollar figures are blocked unless the caller listed them as an approved,
    public estimate; budget-cap wording is always blocked.
    """
    if _FORBIDDEN_TEXT.search(text):
        raise PrivacyViolation("forbidden private-data wording")
    allowed = {a.replace(",", "") for a in allowed_amounts}
    for m in _AMOUNT.finditer(text):
        if m.group(1).replace(",", "") not in allowed:
            raise PrivacyViolation("unapproved dollar amount")
