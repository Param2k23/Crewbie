from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from crewbie.persistence.tables import PublicEventRow


class PublicEventRepository:
    """Append-only log behind the Mission Control stream. Payloads come from the allowlist."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, event_type: str, payload: dict[str, Any]) -> int:
        row = PublicEventRow(type=event_type, payload=payload)
        self._session.add(row)
        self._session.flush()
        return row.seq

    def after(self, cursor: int, limit: int = 200) -> list[PublicEventRow]:
        return list(
            self._session.scalars(
                select(PublicEventRow)
                .where(PublicEventRow.seq > cursor)
                .order_by(PublicEventRow.seq)
                .limit(limit)
            )
        )
