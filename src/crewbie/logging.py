"""JSON logging with a redaction filter (09-ENGINEERING-STANDARDS section 4)."""

import hashlib
import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
install_ref_var: ContextVar[str | None] = ContextVar("install_ref", default=None)

REDACTED_KEYS = frozenset(
    {"token", "authorization", "flex", "budget_cap_usd", "envelope", "ciphertext"}
)
_STANDARD_ATTRIBUTES = frozenset(vars(logging.makeLogRecord({}))) | {
    "message",
    "asctime",
    "taskName",
}


def install_ref(install_id: str) -> str:
    """Stable, non-reversible reference for logs: first 8 hex of sha256(install_id)."""
    return hashlib.sha256(install_id.encode()).hexdigest()[:8]


def redact(value: Any) -> Any:
    """Drop redacted keys from nested mappings and lists."""
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items() if str(k).lower() not in REDACTED_KEYS}
    if isinstance(value, list | tuple):
        return [redact(item) for item in value]
    return value


class RedactionFilter(logging.Filter):
    """Removes private keys from structured fields passed with `extra=`."""

    def filter(self, record: logging.LogRecord) -> bool:
        for name in [n for n in vars(record) if n not in _STANDARD_ATTRIBUTES]:
            if name.lower() in REDACTED_KEYS:
                delattr(record, name)
            else:
                setattr(record, name, redact(getattr(record, name)))
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        document: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
            "install_ref": install_ref_var.get(),
        }
        for name, value in vars(record).items():
            if name not in _STANDARD_ATTRIBUTES:
                document[name] = value
        if record.exc_info:
            # The traceback is useful; exception messages are written by our code, not user input.
            document["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            document["exc"] = self.formatException(record.exc_info)
        return json.dumps(redact(document), default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactionFilter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    logging.getLogger("discord.client").setLevel(logging.ERROR)  # voice-library warnings
    for noisy in ("alembic", "httpx", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
