"""SQLAlchemy 2.0 typed mappings (02-ARCHITECTURE section 3). Kept Postgres-compatible."""

from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Index, MetaData, String, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class UtcDateTime(TypeDecorator[datetime]):
    """Timezone-aware datetimes in, timezone-aware UTC out (SQLite drops tzinfo)."""

    impl = sa.DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime cannot be stored")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )
    type_annotation_map = {  # noqa: RUF012
        datetime: UtcDateTime(timezone=True),
        dict[str, Any]: sa.JSON(),
        list[str]: sa.JSON(),
    }


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class InstallRow(Timestamps, Base):
    __tablename__ = "installs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # Discord-only installs have no Cubbie token; NULLs do not collide in the unique index.
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    kind: Mapped[str] = mapped_column(String(16))
    is_synthetic: Mapped[bool] = mapped_column(default=False)


class DiscordLinkRow(Timestamps, Base):
    __tablename__ = "discord_links"
    install_id: Mapped[str] = mapped_column(
        ForeignKey("installs.id", ondelete="CASCADE"), primary_key=True
    )
    discord_user_id: Mapped[str] = mapped_column(String(32), unique=True)
    discord_username: Mapped[str] = mapped_column(String(64))


class LinkCodeRow(Timestamps, Base):
    __tablename__ = "link_codes"
    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    install_id: Mapped[str] = mapped_column(ForeignKey("installs.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]


class EventRow(Timestamps, Base):
    __tablename__ = "events"
    event_key: Mapped[str] = mapped_column(String(16), primary_key=True)
    source_url: Mapped[str] = mapped_column(String(2048))
    title: Mapped[str] = mapped_column(String(120))
    location_label: Mapped[str | None] = mapped_column(String(120))
    date: Mapped[str] = mapped_column(String(10))
    start_time: Mapped[str | None] = mapped_column(String(5))
    end_time: Mapped[str | None] = mapped_column(String(5))


class IntentRow(Timestamps, Base):
    __tablename__ = "intents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    install_id: Mapped[str] = mapped_column(ForeignKey("installs.id", ondelete="CASCADE"))
    event_key: Mapped[str] = mapped_column(ForeignKey("events.event_key"))
    window_start: Mapped[datetime]
    window_end: Mapped[datetime]
    activity_min_minutes: Mapped[int]
    budget_band: Mapped[str] = mapped_column(String(8))
    vibe: Mapped[str] = mapped_column(String(8))
    interests: Mapped[list[str]] = mapped_column(default=list)
    state: Mapped[str] = mapped_column(String(16))

    __table_args__ = (
        # FR-INT-03: at most one live intent per install and event.
        Index(
            "uq_intents_live_install_event",
            "install_id",
            "event_key",
            unique=True,
            sqlite_where=sa.text("state IN ('matching', 'offered', 'joined')"),
            postgresql_where=sa.text("state IN ('matching', 'offered', 'joined')"),
        ),
    )


class EnvelopeRow(Timestamps, Base):
    """The only table that holds private envelope data, and only as ciphertext."""

    __tablename__ = "envelopes"
    intent_id: Mapped[str] = mapped_column(
        ForeignKey("intents.id", ondelete="CASCADE"), primary_key=True
    )
    ciphertext: Mapped[bytes] = mapped_column(sa.LargeBinary)


class RoomRow(Timestamps, Base):
    __tablename__ = "rooms"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_key: Mapped[str] = mapped_column(ForeignKey("events.event_key"), index=True)
    status: Mapped[str] = mapped_column(String(16))
    version: Mapped[int] = mapped_column(default=1)
    window_start: Mapped[datetime | None]
    window_end: Mapped[datetime | None]
    budget_band: Mapped[str | None] = mapped_column(String(8))
    vibe: Mapped[str | None] = mapped_column(String(8))
    top_interests: Mapped[list[str]] = mapped_column(default=list)
    size: Mapped[int] = mapped_column(default=0)
    discord_thread_id: Mapped[str | None] = mapped_column(String(32))
    board_message_id: Mapped[str | None] = mapped_column(String(32))


class MembershipRow(Timestamps, Base):
    __tablename__ = "memberships"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"), index=True)
    intent_id: Mapped[str] = mapped_column(
        ForeignKey("intents.id", ondelete="CASCADE"), unique=True
    )
    alias: Mapped[str] = mapped_column(String(16))
    effective_start: Mapped[datetime]
    effective_end: Mapped[datetime]
    joined_at: Mapped[datetime]
    left_at: Mapped[datetime | None]


class OfferRow(Timestamps, Base):
    __tablename__ = "offers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    intent_id: Mapped[str] = mapped_column(ForeignKey("intents.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(16))
    room_id: Mapped[str | None] = mapped_column(ForeignKey("rooms.id"))
    room_version: Mapped[int | None]
    proposal_start: Mapped[datetime | None]
    proposal_end: Mapped[datetime | None]
    expires_at: Mapped[datetime]
    state: Mapped[str] = mapped_column(String(16))


class NegotiationRow(Timestamps, Base):
    __tablename__ = "negotiations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    intent_id: Mapped[str] = mapped_column(ForeignKey("intents.id", ondelete="CASCADE"))
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"))
    outcome: Mapped[str] = mapped_column(String(16))
    rounds: Mapped[int]


class NegotiationStepRow(Timestamps, Base):
    __tablename__ = "negotiation_steps"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    negotiation_id: Mapped[str] = mapped_column(
        ForeignKey("negotiations.id", ondelete="CASCADE"), index=True
    )
    round: Mapped[int]
    actor_kind: Mapped[str] = mapped_column(String(16))
    actor_alias: Mapped[str] = mapped_column(String(16))
    proposal_start: Mapped[datetime | None]
    proposal_end: Mapped[datetime | None]
    verdict: Mapped[str] = mapped_column(String(16))


class UpdateRow(Timestamps, Base):
    __tablename__ = "updates"
    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    install_id: Mapped[str] = mapped_column(
        ForeignKey("installs.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)


class OutboxRow(Timestamps, Base):
    __tablename__ = "outbox"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)
    dedupe_key: Mapped[str] = mapped_column(String(200), unique=True)
    state: Mapped[str] = mapped_column(String(16), index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    next_attempt_at: Mapped[datetime]
    last_error: Mapped[str | None] = mapped_column(String(500))


class PublicEventRow(Timestamps, Base):
    __tablename__ = "public_events"
    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(48))
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)


class IdempotencyKeyRow(Timestamps, Base):
    """Stored public-safe responses for `Idempotency-Key` replays (03-API-CONTRACT section 1)."""

    __tablename__ = "idempotency_keys"
    install_id: Mapped[str] = mapped_column(
        ForeignKey("installs.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    scope: Mapped[str] = mapped_column(String(100))
    response_status: Mapped[int]
    response_body: Mapped[dict[str, Any]] = mapped_column(default=dict)
