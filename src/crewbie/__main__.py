"""Run the API and, when enabled, the Discord bot in one process (`python -m crewbie`)."""

import os
import sys
from pathlib import Path

import uvicorn

from crewbie.config import Settings, collect_raw_values, startup_problems
from crewbie.logging import configure_logging

USAGE = """usage: python -m crewbie

Starts the Crewbie API (and the Discord bot when CREWBIE_DISCORD_ENABLED=true).
Configuration comes from environment variables or a .env file in the current directory;
check it with: python -m crewbie.config check
"""


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args in (["-h"], ["--help"]):
        sys.stdout.write(USAGE)
        return 0
    if args:
        sys.stderr.write(USAGE)
        return 2

    problems = startup_problems(collect_raw_values(Path(".env"), os.environ))
    if problems:
        sys.stderr.write("Refusing to start in production:\n")
        sys.stderr.write("".join(f"  {problem}\n" for problem in problems))
        return 1

    settings = Settings()
    configure_logging()
    uvicorn.run(
        "crewbie.api.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_config=None,
        access_log=False,
        workers=1,  # SQLite and the in-process locks assume one process (02 section 6)
        proxy_headers=settings.trust_proxy,
        forwarded_allow_ips="*" if settings.trust_proxy else None,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
