"""Create the demo event with two rooms of synthetic members (FR-ADM-02). Dev only."""

import sys

from crewbie.api.app import build_state
from crewbie.config import Settings
from crewbie.services import seed


def main() -> int:
    settings = Settings()
    if settings.env != "dev":
        sys.stderr.write("Refusing to seed: set CREWBIE_ENV=dev.\n")
        return 1
    result = seed.seed_demo(build_state(settings).ctx)
    sys.stdout.write(f"event_key={result['event_key']} rooms={','.join(result['rooms'])}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
