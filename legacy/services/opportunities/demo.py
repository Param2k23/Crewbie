"""Two stable offline demonstrations: python -B -m services.opportunities.demo A."""
import argparse
import json

from .catalog import OpportunityCatalog
from .discovery import DiscoveryService
from .models import timestamp
from .providers import ActivityFixtureProvider


def scenario(name):
    catalog = OpportunityCatalog(ActivityFixtureProvider(), now=lambda: timestamp("2026-10-24T19:00:00Z"))
    discovery = DiscoveryService(catalog)
    if name == "A":
        result = discovery.recommend(
            "2026-10-26T12:00:00-07:00", "2026-10-26T14:00:00-07:00", campus="Tempe",
            location_context="local", distances={"demo_coffee": 250, "demo_games": 400}, max_distance_m=500)
    elif name == "B":
        result = discovery.recommend("2026-10-31T08:00:00-07:00", "2026-11-02T08:00:00-07:00", intent="trip")
    else:
        raise ValueError("Unknown scenario")
    return {"scenario": name, "mode": "offline_fixture_demo", **result}


def main():
    parser = argparse.ArgumentParser(description="Offline activity demonstrations with fixed dates and clock")
    parser.add_argument("scenario", choices=["A", "B"])
    print(json.dumps(scenario(parser.parse_args().scenario), indent=2))


if __name__ == "__main__":
    main()
