from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from crewbie.persistence.tables import DiscordLinkRow, LinkCodeRow


class LinkRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_code(self, code: str, install_id: str, expires_at: datetime) -> LinkCodeRow:
        row = LinkCodeRow(code=code, install_id=install_id, expires_at=expires_at)
        self._session.add(row)
        self._session.flush()
        return row

    def get_code(self, code: str) -> LinkCodeRow | None:
        return self._session.get(LinkCodeRow, code)

    def delete_unused_codes(self, install_id: str) -> None:
        self._session.execute(
            delete(LinkCodeRow).where(
                LinkCodeRow.install_id == install_id, LinkCodeRow.used_at.is_(None)
            )
        )

    def mark_code_used(self, code: str, used_at: datetime) -> None:
        row = self._session.get(LinkCodeRow, code)
        if row is not None:
            row.used_at = used_at
            self._session.flush()

    def get_by_install(self, install_id: str) -> DiscordLinkRow | None:
        return self._session.get(DiscordLinkRow, install_id)

    def get_by_discord_user(self, discord_user_id: str) -> DiscordLinkRow | None:
        return self._session.scalar(
            select(DiscordLinkRow).where(DiscordLinkRow.discord_user_id == discord_user_id)
        )

    def replace_link(self, install_id: str, discord_user_id: str, username: str) -> DiscordLinkRow:
        """Make the pair the only link for both sides (FR-LNK-03)."""
        self._session.execute(
            delete(DiscordLinkRow).where(
                (DiscordLinkRow.install_id == install_id)
                | (DiscordLinkRow.discord_user_id == discord_user_id)
            )
        )
        row = DiscordLinkRow(
            install_id=install_id, discord_user_id=discord_user_id, discord_username=username
        )
        self._session.add(row)
        self._session.flush()
        return row
