import argparse
import json

from .catalog import OpportunityCatalog
from .models import timestamp


def main():
    parser = argparse.ArgumentParser(description="Crewbie DEMO ONLY opportunity catalog; offline, fictional events")
    parser.add_argument("--campus")
    parser.add_argument("--starts-after")
    parser.add_argument("--ends-before")
    parser.add_argument("--food-only", action="store_true")
    parser.add_argument("--overlap", action="store_true")
    parser.add_argument("--now", help="Explicit demo clock with timezone offset")
    parser.add_argument("--include-stale", action="store_true")
    args = parser.parse_args()
    clock = timestamp(args.now) if args.now else None
    catalog = OpportunityCatalog(now=(lambda: clock) if clock else None)
    print(json.dumps({"mode": "DEMO ONLY", "synthetic": True, "diagnostics": catalog.diagnostics,
                      "opportunities": catalog.list_opportunities(
                          args.campus, args.starts_after, args.ends_before, args.food_only,
                          time_mode="overlap" if args.overlap else "contained",
                          include_stale=args.include_stale)}, indent=2))


if __name__ == "__main__":
    main()
