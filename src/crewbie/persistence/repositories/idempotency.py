from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from crewbie.persistence.tables import IdempotencyKeyRow


class IdempotencyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, install_id: str, key: str) -> IdempotencyKeyRow | None:
        return self._session.get(IdempotencyKeyRow, (install_id, key))

    def store(
        self,
        install_id: str,
        key: str,
        scope: str,
        status: int,
        body: dict[str, Any],
        created_at: datetime,
    ) -> None:
        self._session.merge(
            IdempotencyKeyRow(
                install_id=install_id,
                created_at=created_at,
                key=key,
                scope=scope,
                response_status=status,
                response_body=body,
            )
        )
        self._session.flush()
