"""initial schema

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("event_key", sa.String(length=16), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("location_label", sa.String(length=120), nullable=True),
        sa.Column("date", sa.String(length=10), nullable=False),
        sa.Column("start_time", sa.String(length=5), nullable=True),
        sa.Column("end_time", sa.String(length=5), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("event_key", name=op.f("pk_events")),
    )
    op.create_table(
        "installs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_installs")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_installs_token_hash")),
    )
    op.create_table(
        "outbox",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=200), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox")),
        sa.UniqueConstraint("dedupe_key", name=op.f("uq_outbox_dedupe_key")),
    )
    with op.batch_alter_table("outbox", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_outbox_state"), ["state"], unique=False)

    op.create_table(
        "public_events",
        sa.Column("seq", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("type", sa.String(length=48), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("seq", name=op.f("pk_public_events")),
    )
    op.create_table(
        "discord_links",
        sa.Column("install_id", sa.String(length=36), nullable=False),
        sa.Column("discord_user_id", sa.String(length=32), nullable=False),
        sa.Column("discord_username", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["install_id"],
            ["installs.id"],
            name=op.f("fk_discord_links_install_id_installs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("install_id", name=op.f("pk_discord_links")),
        sa.UniqueConstraint("discord_user_id", name=op.f("uq_discord_links_discord_user_id")),
    )
    op.create_table(
        "intents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("install_id", sa.String(length=36), nullable=False),
        sa.Column("event_key", sa.String(length=16), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activity_min_minutes", sa.Integer(), nullable=False),
        sa.Column("budget_band", sa.String(length=8), nullable=False),
        sa.Column("vibe", sa.String(length=8), nullable=False),
        sa.Column("interests", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_key"], ["events.event_key"], name=op.f("fk_intents_event_key_events")
        ),
        sa.ForeignKeyConstraint(
            ["install_id"],
            ["installs.id"],
            name=op.f("fk_intents_install_id_installs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_intents")),
    )
    with op.batch_alter_table("intents", schema=None) as batch_op:
        batch_op.create_index(
            "uq_intents_live_install_event",
            ["install_id", "event_key"],
            unique=True,
            sqlite_where=sa.text("state IN ('matching', 'offered', 'joined')"),
            postgresql_where=sa.text("state IN ('matching', 'offered', 'joined')"),
        )

    op.create_table(
        "link_codes",
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("install_id", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["install_id"],
            ["installs.id"],
            name=op.f("fk_link_codes_install_id_installs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_link_codes")),
    )
    op.create_table(
        "rooms",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_key", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("budget_band", sa.String(length=8), nullable=True),
        sa.Column("vibe", sa.String(length=8), nullable=True),
        sa.Column("top_interests", sa.JSON(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("discord_thread_id", sa.String(length=32), nullable=True),
        sa.Column("board_message_id", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_key"], ["events.event_key"], name=op.f("fk_rooms_event_key_events")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rooms")),
    )
    with op.batch_alter_table("rooms", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_rooms_event_key"), ["event_key"], unique=False)

    op.create_table(
        "updates",
        sa.Column("seq", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("install_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["install_id"],
            ["installs.id"],
            name=op.f("fk_updates_install_id_installs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("seq", name=op.f("pk_updates")),
    )
    with op.batch_alter_table("updates", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_updates_install_id"), ["install_id"], unique=False)

    op.create_table(
        "envelopes",
        sa.Column("intent_id", sa.String(length=36), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["intent_id"],
            ["intents.id"],
            name=op.f("fk_envelopes_intent_id_intents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("intent_id", name=op.f("pk_envelopes")),
    )
    op.create_table(
        "memberships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("room_id", sa.String(length=36), nullable=False),
        sa.Column("intent_id", sa.String(length=36), nullable=False),
        sa.Column("alias", sa.String(length=16), nullable=False),
        sa.Column("effective_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["intent_id"],
            ["intents.id"],
            name=op.f("fk_memberships_intent_id_intents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["room_id"], ["rooms.id"], name=op.f("fk_memberships_room_id_rooms")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memberships")),
        sa.UniqueConstraint("intent_id", name=op.f("uq_memberships_intent_id")),
    )
    with op.batch_alter_table("memberships", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_memberships_room_id"), ["room_id"], unique=False)

    op.create_table(
        "negotiations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("intent_id", sa.String(length=36), nullable=False),
        sa.Column("room_id", sa.String(length=36), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("rounds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["intent_id"],
            ["intents.id"],
            name=op.f("fk_negotiations_intent_id_intents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["room_id"], ["rooms.id"], name=op.f("fk_negotiations_room_id_rooms")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_negotiations")),
    )
    op.create_table(
        "offers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("intent_id", sa.String(length=36), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("room_id", sa.String(length=36), nullable=True),
        sa.Column("room_version", sa.Integer(), nullable=True),
        sa.Column("proposal_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("proposal_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["intent_id"],
            ["intents.id"],
            name=op.f("fk_offers_intent_id_intents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], name=op.f("fk_offers_room_id_rooms")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_offers")),
    )
    with op.batch_alter_table("offers", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_offers_intent_id"), ["intent_id"], unique=False)

    op.create_table(
        "negotiation_steps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("negotiation_id", sa.String(length=36), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("actor_kind", sa.String(length=16), nullable=False),
        sa.Column("actor_alias", sa.String(length=16), nullable=False),
        sa.Column("proposal_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("proposal_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verdict", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["negotiation_id"],
            ["negotiations.id"],
            name=op.f("fk_negotiation_steps_negotiation_id_negotiations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_negotiation_steps")),
    )
    with op.batch_alter_table("negotiation_steps", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_negotiation_steps_negotiation_id"), ["negotiation_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("negotiation_steps", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_negotiation_steps_negotiation_id"))

    op.drop_table("negotiation_steps")
    with op.batch_alter_table("offers", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_offers_intent_id"))

    op.drop_table("offers")
    op.drop_table("negotiations")
    with op.batch_alter_table("memberships", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_memberships_room_id"))

    op.drop_table("memberships")
    op.drop_table("envelopes")
    with op.batch_alter_table("updates", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_updates_install_id"))

    op.drop_table("updates")
    with op.batch_alter_table("rooms", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_rooms_event_key"))

    op.drop_table("rooms")
    op.drop_table("link_codes")
    with op.batch_alter_table("intents", schema=None) as batch_op:
        batch_op.drop_index(
            "uq_intents_live_install_event",
            sqlite_where=sa.text("state IN ('matching', 'offered', 'joined')"),
            postgresql_where=sa.text("state IN ('matching', 'offered', 'joined')"),
        )

    op.drop_table("intents")
    op.drop_table("discord_links")
    op.drop_table("public_events")
    with op.batch_alter_table("outbox", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_outbox_state"))

    op.drop_table("outbox")
    op.drop_table("installs")
    op.drop_table("events")
