from datetime import UTC, datetime, timedelta, timezone

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect, text
from sqlalchemy.orm import Session

from crewbie.persistence.db import create_db_engine, migrate_to_head
from crewbie.persistence.tables import Base, InstallRow


def test_migration_matches_models(engine: Engine) -> None:
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == []


def test_migrate_to_head_is_idempotent(engine: Engine) -> None:
    migrate_to_head(engine)
    assert "outbox" in inspect(engine).get_table_names()


def test_all_architecture_tables_exist(engine: Engine) -> None:
    expected = {
        "installs", "discord_links", "link_codes", "events", "intents", "envelopes", "rooms",
        "memberships", "offers", "negotiations", "negotiation_steps", "updates", "outbox",
        "public_events",
    }  # fmt: skip
    assert expected <= set(inspect(engine).get_table_names())


def test_sqlite_uses_wal_and_enforces_foreign_keys(engine: Engine) -> None:
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_database_file_parent_is_created(tmp_path) -> None:  # type: ignore[no-untyped-def]
    engine = create_db_engine(f"sqlite:///{tmp_path / 'nested' / 'dir' / 'x.db'}")
    migrate_to_head(engine)
    assert (tmp_path / "nested" / "dir" / "x.db").exists()


def test_datetimes_round_trip_as_aware_utc(engine: Engine) -> None:
    phoenix = timezone(timedelta(hours=-7))
    with Session(engine) as session:
        session.add(InstallRow(id="i1", token_hash="h", kind="cubbie"))
        session.commit()
        row = session.get(InstallRow, "i1")
        assert row is not None
        assert row.created_at.tzinfo is not None
        assert row.created_at.utcoffset() == timedelta(0)

    from crewbie.persistence.tables import LinkCodeRow

    moment = datetime(2026, 11, 6, 12, 0, tzinfo=phoenix)
    with Session(engine) as session:
        session.add(LinkCodeRow(code="K7QX2M", install_id="i1", expires_at=moment))
        session.commit()
        stored = session.get(LinkCodeRow, "K7QX2M")
        assert stored is not None
        assert stored.expires_at == moment
        assert stored.expires_at.tzinfo is not None


def test_naive_datetimes_are_refused(engine: Engine) -> None:
    from crewbie.persistence.tables import LinkCodeRow

    with Session(engine) as session:
        session.add(InstallRow(id="i1", token_hash="h", kind="cubbie"))
        session.add(LinkCodeRow(code="AAAAAA", install_id="i1", expires_at=datetime(2026, 1, 1)))
        with pytest.raises(Exception, match="naive"):
            session.commit()

    assert UTC.utcoffset(None) == timedelta(0)
