"""Dependencies shared by every use case. Services take this instead of reaching for globals."""

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from crewbie.matching.matcher import Matcher
from crewbie.persistence.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class ServiceConfig:
    env: str = "dev"
    offer_ttl_minutes: int = 15
    link_code_ttl_minutes: int = 10
    invite_url: str = ""
    guild_id: str = ""
    timezone: str = "America/Phoenix"


def default_new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class ServiceContext:
    uow_factory: Callable[[], UnitOfWork]
    matcher: Matcher
    config: ServiceConfig = ServiceConfig()
    clock: Callable[[], datetime] = utc_now
    new_id: Callable[[str], str] = default_new_id
