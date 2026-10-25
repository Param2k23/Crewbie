"""Alembic environment; the engine is supplied by `crewbie.persistence.db`."""

from alembic import context

from crewbie.persistence.tables import Base

engine = context.config.attributes["engine"]

with engine.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_as_batch=engine.dialect.name == "sqlite",
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()
    connection.commit()
