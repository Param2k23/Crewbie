"""Canonical event identity (SRS 5.1)."""

import hashlib
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from crewbie.domain.errors import ValidationFailed

_DROPPED_PARAMS = {"fbclid", "gclid", "ref"}


def _keep_param(name: str) -> bool:
    lowered = name.lower()
    return not lowered.startswith("utm_") and lowered not in _DROPPED_PARAMS


def normalize_url(url: str) -> str:
    """Lowercase scheme and host, drop fragment, tracking params, userinfo, trailing slash."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    if not parts.scheme or not host:
        raise ValidationFailed({"event.source_url": "must be an absolute URL"})
    if ":" in host:
        host = f"[{host}]"
    netloc = f"{host}:{parts.port}" if parts.port else host
    query = urlencode(
        [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if _keep_param(k)]
    )
    return urlunsplit((parts.scheme.lower(), netloc, parts.path.rstrip("/"), query, ""))


def _check_format(field: str, value: str, pattern: str) -> None:
    try:
        datetime.strptime(value, pattern)
    except ValueError:
        raise ValidationFailed({field: f"must match {pattern}"}) from None


def event_key(source_url: str, date: str, start_time: str | None) -> str:
    """First 16 hex chars of sha256(normalized_url|date|start or "na")."""
    _check_format("event.date", date, "%Y-%m-%d")
    if start_time is not None:
        _check_format("event.start_time", start_time, "%H:%M")
    material = f"{normalize_url(source_url)}|{date}|{start_time or 'na'}"
    return hashlib.sha256(material.encode()).hexdigest()[:16]
