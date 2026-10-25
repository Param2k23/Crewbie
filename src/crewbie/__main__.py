"""Run the API (and, from Phase 4, the Discord bot) in one process."""

import sys

import uvicorn

from crewbie.config import Settings
from crewbie.logging import configure_logging


def main() -> int:
    settings = Settings()
    configure_logging()
    uvicorn.run(
        "crewbie.api.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_config=None,
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
