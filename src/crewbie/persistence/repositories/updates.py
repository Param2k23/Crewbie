from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from crewbie.persistence.tables import UpdateRow


class UpdateRepository:
    """Per-install updates read by `crew.py updates` (FR-UPD-01, FR-UPD-02)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, install_id: str, kind: str, payload: dict[str, Any]) -> int:
        row = UpdateRow(install_id=install_id, kind=kind, payload=payload)
        self._session.add(row)
        self._session.flush()
        return row.seq

    def after(self, install_id: str, cursor: int, limit: int = 100) -> list[UpdateRow]:
        return list(
            self._session.scalars(
                select(UpdateRow)
                .where(UpdateRow.install_id == install_id, UpdateRow.seq > cursor)
                .order_by(UpdateRow.seq)
                .limit(limit)
            )
        )
