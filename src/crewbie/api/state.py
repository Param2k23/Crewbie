from dataclasses import dataclass, field

from sqlalchemy import Engine

from crewbie.api.rate_limit import TokenBucketLimiter
from crewbie.config import Settings
from crewbie.discord_bot.runtime import BotStatus
from crewbie.services.context import ServiceContext


@dataclass
class AppState:
    settings: Settings
    ctx: ServiceContext
    engine: Engine
    install_limiter: TokenBucketLimiter
    register_limiter: TokenBucketLimiter
    bot_status: BotStatus = field(default_factory=BotStatus)
