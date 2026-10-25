"""Durable queue of Discord side effects (NFR-REL-01, NFR-REL-02)."""

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from crewbie.persistence.tables import OutboxRow

MAX_RETRIES = 5  # retries after the first failure, waiting 1, 2, 4, 8, 16 seconds


class OutboxState(StrEnum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


def backoff_seconds(failures: int) -> int:
    """Wait before the retry that follows failure number `failures` (1-based)."""
    return 1 << (failures - 1)


class Outbox:
    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue(
        self, job_id: str, kind: str, payload: dict[str, Any], dedupe_key: str, now: datetime
    ) -> bool:
        """Add a job unless one with the same dedupe key exists. Returns whether it was added."""
        exists = self._session.scalar(
            select(OutboxRow.id).where(OutboxRow.dedupe_key == dedupe_key)
        )
        if exists is not None:
            return False
        self._session.add(
            OutboxRow(
                id=job_id,
                kind=kind,
                payload=payload,
                dedupe_key=dedupe_key,
                state=OutboxState.PENDING.value,
                next_attempt_at=now,
            )
        )
        self._session.flush()
        return True

    def due(self, now: datetime, limit: int = 20) -> list[OutboxRow]:
        return list(
            self._session.scalars(
                select(OutboxRow)
                .where(
                    OutboxRow.state == OutboxState.PENDING.value, OutboxRow.next_attempt_at <= now
                )
                .order_by(OutboxRow.next_attempt_at, OutboxRow.created_at, OutboxRow.id)
                .limit(limit)
            )
        )

    def mark_done(self, job_id: str) -> None:
        row = self._session.get(OutboxRow, job_id)
        if row is not None:
            row.state = OutboxState.DONE.value
            self._session.flush()

    def mark_failed_attempt(self, job_id: str, error: str, now: datetime) -> OutboxState:
        """Record a failure: schedule a retry, or give up after `MAX_RETRIES` retries."""
        row = self._session.get(OutboxRow, job_id)
        if row is None:
            return OutboxState.FAILED
        row.attempts += 1
        row.last_error = error[:500]
        if row.attempts > MAX_RETRIES:
            row.state = OutboxState.FAILED.value
        else:
            row.next_attempt_at = now + timedelta(seconds=backoff_seconds(row.attempts))
        self._session.flush()
        return OutboxState(row.state)

    def backlog(self) -> int:
        return (
            self._session.scalar(
                select(func.count())
                .select_from(OutboxRow)
                .where(OutboxRow.state == OutboxState.PENDING.value)
            )
            or 0
        )

    def by_state(self, state: OutboxState, limit: int = 100) -> list[OutboxRow]:
        return list(
            self._session.scalars(
                select(OutboxRow)
                .where(OutboxRow.state == state.value)
                .order_by(OutboxRow.created_at, OutboxRow.id)
                .limit(limit)
            )
        )
