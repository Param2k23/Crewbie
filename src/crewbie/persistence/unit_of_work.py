"""Unit of work: the only place transactions begin and end (09-ENGINEERING-STANDARDS section 1)."""

from types import TracebackType

from sqlalchemy.orm import Session, sessionmaker

from crewbie.persistence.crypto import EnvelopeCipher
from crewbie.persistence.outbox import Outbox
from crewbie.persistence.repositories.events import EventRepository
from crewbie.persistence.repositories.idempotency import IdempotencyRepository
from crewbie.persistence.repositories.installs import InstallRepository
from crewbie.persistence.repositories.intents import IntentRepository
from crewbie.persistence.repositories.links import LinkRepository
from crewbie.persistence.repositories.offers import OfferRepository
from crewbie.persistence.repositories.rooms import RoomRepository
from crewbie.persistence.repositories.updates import UpdateRepository


class UnitOfWork:
    """Usage: `with uow_factory() as uow: ...; uow.commit()`. Leaving without commit rolls back."""

    def __init__(self, session_factory: sessionmaker[Session], cipher: EnvelopeCipher) -> None:
        self._session_factory = session_factory
        self._cipher = cipher
        self._session: Session | None = None

    def __enter__(self) -> "UnitOfWork":
        session = self._session_factory()
        self._session = session
        self.installs = InstallRepository(session)
        self.events = EventRepository(session)
        self.intents = IntentRepository(session, self._cipher)
        self.rooms = RoomRepository(session)
        self.offers = OfferRepository(session)
        self.updates = UpdateRepository(session)
        self.links = LinkRepository(session)
        self.idempotency = IdempotencyRepository(session)
        self.outbox = Outbox(session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        assert self._session is not None
        # Detach first so rows read inside the block stay readable (rollback would expire them).
        self._session.expunge_all()
        self._session.rollback()
        self._session.close()
        self._session = None

    def commit(self) -> None:
        assert self._session is not None
        self._session.commit()

    def rollback(self) -> None:
        assert self._session is not None
        self._session.rollback()
