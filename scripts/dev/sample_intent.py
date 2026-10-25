"""Print an intent.json for `crew.py submit`, with times that are still in the future.

uv run python scripts/dev/sample_intent.py > /tmp/intent.json
uv run python scripts/dev/sample_intent.py --start-in-hours 3 --length-hours 2 --band mid
"""

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--start-in-hours", type=float, default=2.0)
    parser.add_argument("--length-hours", type=float, default=2.0)
    parser.add_argument("--flex-minutes", type=int, default=45, help="private slack either side")
    parser.add_argument("--minimum", type=int, default=90, help="minimum minutes to stay")
    parser.add_argument("--band", choices=["low", "mid", "high"], default="low")
    parser.add_argument("--vibe", choices=["chill", "social", "active"], default="chill")
    parser.add_argument("--title", default="Board game night")
    args = parser.parse_args()

    now = datetime.now(UTC).replace(second=0, microsecond=0)
    start = (now + timedelta(hours=args.start_in_hours)).replace(minute=0)
    end = start + timedelta(hours=args.length_hours)
    slack = timedelta(minutes=args.flex_minutes)
    body = {
        "event": {
            "source_url": "https://example.edu/events/crewbie-live-test",
            "title": args.title,
            "location_label": "Hayden Library",
            "date": start.date().isoformat(),
            "start_time": f"{start:%H:%M}",
        },
        "shared": {
            "window": {"start": start.isoformat(), "end": end.isoformat()},
            "activity_min_minutes": args.minimum,
            "budget_band": args.band,
            "vibe": args.vibe,
            "interests": ["board-games"],
        },
        "private": {
            "flex": {"earliest": (start - slack).isoformat(), "latest": (end + slack).isoformat()},
            "budget_cap_usd": 15,
        },
    }
    sys.stdout.write(json.dumps(body, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
