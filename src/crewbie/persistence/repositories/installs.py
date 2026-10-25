from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from crewbie.persistence.tables import InstallRow


class InstallRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self, install_id: str, token_hash: str | None, kind: str, is_synthetic: bool = False
    ) -> InstallRow:
        row = InstallRow(id=install_id, token_hash=token_hash, kind=kind, is_synthetic=is_synthetic)
        self._session.add(row)
        self._session.flush()
        return row

    def get(self, install_id: str) -> InstallRow | None:
        return self._session.get(InstallRow, install_id)

    def get_by_token_hash(self, token_hash: str) -> InstallRow | None:
        return self._session.scalar(select(InstallRow).where(InstallRow.token_hash == token_hash))

    def delete(self, install_id: str) -> None:
        """Delete the install; the database cascades to links, intents, envelopes and updates."""
        self._session.execute(delete(InstallRow).where(InstallRow.id == install_id))
