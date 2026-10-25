from sqlalchemy.orm import Session

from crewbie.persistence.tables import EventRow


class EventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, event_key: str) -> EventRow | None:
        return self._session.get(EventRow, event_key)

    def ensure(
        self,
        event_key: str,
        *,
        source_url: str,
        title: str,
        location_label: str | None,
        date: str,
        start_time: str | None,
        end_time: str | None,
    ) -> EventRow:
        """Create the event on first sight; later calls never overwrite it (FR-EVT-02)."""
        existing = self.get(event_key)
        if existing is not None:
            return existing
        row = EventRow(
            event_key=event_key,
            source_url=source_url,
            title=title,
            location_label=location_label,
            date=date,
            start_time=start_time,
            end_time=end_time,
        )
        self._session.add(row)
        self._session.flush()
        return row
