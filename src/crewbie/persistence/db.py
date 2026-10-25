"""Engine, session factory and migration bootstrap."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def create_db_engine(database_url: str) -> Engine:
    """SQLite gets WAL, enforced foreign keys and a busy timeout (single writer, many readers)."""
    engine = create_engine(database_url)
    if engine.dialect.name == "sqlite":
        if engine.url.database not in (None, "", ":memory:"):
            Path(str(engine.url.database)).parent.mkdir(parents=True, exist_ok=True)

        @event.listens_for(engine, "connect")
        def _configure(dbapi_connection, _record) -> None:  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


def alembic_config(engine: Engine) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.attributes["engine"] = engine
    return config


def migrate_to_head(engine: Engine) -> None:
    """Bring the schema up to date. Safe to call on every start."""
    command.upgrade(alembic_config(engine), "head")
