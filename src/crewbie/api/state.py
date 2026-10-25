from dataclasses import dataclass

from sqlalchemy import Engine

from crewbie.api.rate_limit import TokenBucketLimiter
from crewbie.config import Settings
from crewbie.services.context import ServiceContext


@dataclass
class AppState:
    settings: Settings
    ctx: ServiceContext
    engine: Engine
    install_limiter: TokenBucketLimiter
    register_limiter: TokenBucketLimiter
    discord_status: str = "disabled"
