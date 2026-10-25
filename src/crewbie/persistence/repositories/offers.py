from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from crewbie.domain.offer import OfferState, OfferType
from crewbie.domain.windows import TimeWindow
from crewbie.persistence.tables import OfferRow


class OfferRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        offer_id: str,
        intent_id: str,
        offer_type: OfferType,
        expires_at: datetime,
        *,
        room_id: str | None = None,
        room_version: int | None = None,
        proposal: TimeWindow | None = None,
    ) -> OfferRow:
        row = OfferRow(
            id=offer_id,
            intent_id=intent_id,
            type=offer_type.value,
            room_id=room_id,
            room_version=room_version,
            proposal_start=proposal.start if proposal else None,
            proposal_end=proposal.end if proposal else None,
            expires_at=expires_at,
            state=OfferState.OPEN.value,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def get(self, offer_id: str) -> OfferRow | None:
        return self._session.get(OfferRow, offer_id)

    def set_state(self, offer_id: str, state: OfferState) -> None:
        row = self._session.get(OfferRow, offer_id)
        if row is not None:
            row.state = state.value
            self._session.flush()

    def open_expired(self, now: datetime) -> list[OfferRow]:
        """Open offers past their expiry; the sweeper marks them expired (FR-OFR-06)."""
        return list(
            self._session.scalars(
                select(OfferRow).where(
                    OfferRow.state == OfferState.OPEN.value, OfferRow.expires_at <= now
                )
            )
        )
