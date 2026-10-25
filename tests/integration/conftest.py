from collections.abc import Callable
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from crewbie.persistence.crypto import EnvelopeCipher
from crewbie.persistence.db import create_db_engine, make_session_factory, migrate_to_head
from crewbie.persistence.unit_of_work import UnitOfWork


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'test.db'}")
    migrate_to_head(engine)
    return engine


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return make_session_factory(engine)


@pytest.fixture
def cipher() -> EnvelopeCipher:
    return EnvelopeCipher(Fernet.generate_key().decode())


@pytest.fixture
def uow_factory(
    session_factory: sessionmaker[Session], cipher: EnvelopeCipher
) -> Callable[[], UnitOfWork]:
    return lambda: UnitOfWork(session_factory, cipher)
