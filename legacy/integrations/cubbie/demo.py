"""Run with python -m integrations.cubbie.demo. All output is synthetic."""
import argparse
import json
from pathlib import Path

from .adapters import FixtureOpportunityCatalog, MockCubbieProvider, UnavailableCubbieProvider
from .core import PulseError, parse_student_intent, preview_cubbie_alert


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=Path(__file__).resolve().parents[2] / "docs/implementation/fixtures/opportunities.json")
    parser.add_argument("--simulate-schedule", action="store_true")
    args = parser.parse_args()
    catalog = FixtureOpportunityCatalog(args.fixtures)
    context = {"student_ref": "stu_alex", "authorized": True, "synthetic": True,
               "campus": "Tempe", "dietary_preferences": ["vegetarian"],
               "availability_start": "2026-10-26T12:00:00-07:00",
               "availability_end": "2026-10-26T13:30:00-07:00"}
    brief = parse_student_intent("Find free pizza at lunch", context)
    events = catalog.list_opportunities(brief["campus"], brief["availability_start"], brief["availability_end"], True)
    preview = preview_cubbie_alert("stu_alex", events, brief=brief, now="2026-10-26T16:00:00Z")
    print("Campus Pulse | LOCAL SIMULATOR | Track 1 runtime UNVERIFIED")
    print(preview["text"])
    brief["opportunity_id"] = preview["opportunity_ids"][0] if preview["opportunity_ids"] else None
    print(json.dumps(brief, indent=2))
    companion = parse_student_intent("Find company", dict(context, opportunity_id=brief["opportunity_id"]))
    print("Find company (consent request only):", json.dumps(companion))
    try:
        UnavailableCubbieProvider().register_alert()
    except PulseError as error:
        print(error.code + ": " + str(error))
    if args.simulate_schedule:
        mock = MockCubbieProvider()
        consent = dict(context, alerts_opt_in=True)
        record = mock.register_alert("demo-alert-1", "stu_alex", preview, "2026-10-26T16:00:00Z", "daily", consent)
        print(json.dumps(record, indent=2))
        print(json.dumps(mock.dispatch_due("2026-10-26T16:00:00Z", consent, events)))


if __name__ == "__main__":
    main()
