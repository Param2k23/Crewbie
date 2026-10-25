"""Public-event gate for the realtime bridge.

Only ``visibility == "group_safe"`` events with allowlisted, typed payload fields may enter the
stream. Anything that looks like private data (budgets, calendars, prompts, reasoning, tokens,
diet, per-member cost) rejects the whole event: that is a producer bug, not something to scrub
silently. Mirrors apps/web/src/lib/events/sanitize.ts (the browser re-checks everything).
"""
from __future__ import annotations

import re
from typing import Any, Mapping

PUBLIC_EVENT_TYPES = frozenset(
    {
        "opportunity_discovered", "match_requested", "match_suggested", "consent_requested",
        "consent_granted", "negotiation_started", "candidate_proposed", "proposal_rejected",
        "counteroffer_proposed", "fairness_evaluated", "proposal_ready", "approval_requested",
        "member_response_received", "proposal_confirmed", "proposal_revised",
        "negotiation_failed", "session_completed",
    }
)
COMMITMENT_STATES = frozenset({"pending", "interested", "tentative", "conditional", "accepted", "declined", "withdrawn"})

_FORBIDDEN_KEY = re.compile(
    r"(budget|cap_cents|cost|price|calendar|blocked|window|prompt|reasoning|chain_of_thought|token|secret|password|diet|private|internal|hidden|raw_|llm)",
    re.I,
)
_REF = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
_SLUG = re.compile(r"^[a-z0-9_]{1,48}$")
_CODE = re.compile(r"^[A-Z_]{1,48}$")
_TZ = re.compile(r"(Z|[+-]\d{2}:\d{2})$")
_MAX_TEXT = 280


class EventRejected(ValueError):
    """Raised when an event is not safe or well-formed enough to publish. ``code`` is machine readable."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _int(lo: int, hi: int):
    return lambda v: v if isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi else None


def _match(rx: re.Pattern[str]):
    return lambda v: v if isinstance(v, str) and rx.match(v) else None


def clean_text(s: str) -> str | None:
    t = re.sub(r"[\x00-\x1f\x7f<>]", " ", s)
    t = re.sub(r"\s+", " ", t).strip()[:_MAX_TEXT]
    return t or None


_FIELDS = {
    "plan_id": _match(_REF),
    "opportunity_id": _match(_REF),
    "member_ref": _match(_REF),
    "request_id": _match(_REF),
    "version": _int(0, 9999),
    "group_size": _int(1, 12),
    "required_count": _int(0, 12),
    "accepted_count": _int(0, 12),
    "reason_category": _match(_SLUG),
    "condition_category": _match(_SLUG),
    "fairness_category": _match(_SLUG),
    "changed_constraint_kind": _match(_SLUG),
    "approval_state": _match(_SLUG),
    "failure_code": _match(_CODE),
    "state": lambda v: v if isinstance(v, str) and v in COMMITMENT_STATES else None,
    "summary": lambda v: clean_text(v) if isinstance(v, str) else None,
}


def _find_forbidden(value: Any, depth: int = 0) -> str | None:
    if depth > 6 or not isinstance(value, Mapping):
        return None
    for k, v in value.items():
        if _FORBIDDEN_KEY.search(str(k)):
            return str(k)[:32]
        found = _find_forbidden(v, depth + 1)
        if found:
            return found
    return None


def validate_public_event(raw: Any) -> dict[str, Any]:
    """Return a sanitized copy of ``raw`` or raise :class:`EventRejected`."""
    if not isinstance(raw, Mapping):
        raise EventRejected("NOT_OBJECT", "event is not an object")
    if raw.get("visibility") != "group_safe":
        raise EventRejected("NOT_GROUP_SAFE", f"visibility={str(raw.get('visibility'))[:24]}")
    for f in ("event_id", "session_id", "actor_ref"):
        if not isinstance(raw.get(f), str) or not _REF.match(raw[f]):
            raise EventRejected("BAD_FIELD", f"invalid {f}")
    ts = raw.get("timestamp")
    if not isinstance(ts, str) or not _TZ.search(ts):
        raise EventRejected("BAD_FIELD", "timestamp must be ISO 8601 with timezone")
    if raw.get("type") not in PUBLIC_EVENT_TYPES:
        raise EventRejected("BAD_TYPE", f"unknown type {str(raw.get('type'))[:32]}")
    payload = raw.get("payload")
    if not isinstance(payload, Mapping):
        raise EventRejected("BAD_PAYLOAD", "payload must be an object")
    leak = _find_forbidden(payload)
    if leak:
        raise EventRejected("FORBIDDEN_KEY", f'payload contains disallowed key "{leak}"')
    clean: dict[str, Any] = {}
    for key, rule in _FIELDS.items():
        if key in payload:
            v = rule(payload[key])
            if v is None:
                raise EventRejected("BAD_PAYLOAD", f"invalid payload.{key}")
            clean[key] = v
    return {
        "event_id": raw["event_id"],
        "session_id": raw["session_id"],
        "timestamp": ts,
        "type": raw["type"],
        "actor_ref": raw["actor_ref"],
        "visibility": "group_safe",
        "payload": clean,
        "synthetic": raw.get("synthetic") is True,
    }
