"""Drive synthetic students through the real API and matcher, then check every room.

Runs in-process against a throwaway database, so it needs no server and no Discord.

    uv run python scripts/dev/simulate.py --intents 50 --events 3 --seed 7
"""

import argparse
import random
import secrets
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from crewbie.api.app import create_app
from crewbie.api.rate_limit import RateLimits
from crewbie.config import Settings
from crewbie.services import linking
from crewbie.services.context import ServiceContext

PHOENIX = ZoneInfo("America/Phoenix")
INTERESTS = ["board-games", "hiking", "trivia", "anime", "coding", "live-music"]
TITLES = ["Board game night", "Sunset hike", "Trivia at the Memorial Union"]


class Student:
    def __init__(self, client: TestClient, number: int) -> None:
        self.client, self.number = client, number
        self.headers = {"Authorization": f"Bearer {secrets.token_urlsafe(32)}"}
        self.expect(client.post("/v1/installs", json={}, headers=self.headers), 201)

    def expect(self, response: Any, *statuses: int) -> Any:
        if response.status_code not in statuses:
            raise SystemExit(f"unexpected {response.status_code}: {response.text}")
        return response

    def call(self, method: str, path: str, body: Any = None, *ok: int) -> Any:
        response = self.client.request(method, path, json=body, headers=self.headers)
        return response if not ok else self.expect(response, *ok)


def make_intent(rng: random.Random, event: int, day: datetime) -> dict[str, Any]:
    base = datetime.combine(day.date(), time(17, 0), tzinfo=PHOENIX)
    start = base + timedelta(minutes=15 * rng.randint(0, 12))
    end = start + timedelta(minutes=15 * rng.randint(6, 12))
    minimum = 15 * rng.randint(4, 8)
    lead, tail = timedelta(minutes=rng.randint(0, 90)), timedelta(minutes=rng.randint(0, 90))
    return {
        "event": {
            "source_url": f"https://events.example.edu/sim/{event}",
            "title": TITLES[event % len(TITLES)],
            "date": day.date().isoformat(),
            "start_time": "17:00",
        },
        "shared": {
            "window": {"start": start.isoformat(), "end": end.isoformat()},
            "activity_min_minutes": minimum,
            "budget_band": rng.choice(["low", "low", "mid", "mid", "high"]),
            "vibe": rng.choice(["chill", "social", "active"]),
            "interests": rng.sample(INTERESTS, rng.randint(0, 3)),
        },
        "private": {
            "flex": {"earliest": (start - lead).isoformat(), "latest": (end + tail).isoformat()},
            "budget_cap_usd": rng.choice([None, 10, 20, 40]),
        },
    }


def run_student(
    client: TestClient, ctx: ServiceContext, rng: random.Random, number: int, event: int,
    day: datetime, tally: Counter[str],
) -> None:  # fmt: skip
    student = Student(client, number)
    linking.complete(
        ctx, student.call("POST", "/v1/installs/me/link-codes", None, 201).json()["code"],
        f"{10**17 + number}", f"sim{number}",
    )  # fmt: skip
    result = student.call("POST", "/v1/intents", make_intent(rng, event, day), 201).json()
    offer = result["offer"]
    tally[f"offer_{offer['type']}"] += 1
    if rng.random() < 0.15:
        student.call("POST", f"/v1/offers/{offer['offer_id']}/decline", None, 200)
        tally["declined"] += 1
        return
    response = student.call("POST", f"/v1/offers/{offer['offer_id']}/accept")
    if response.status_code == 409 and response.json()["error"]["code"] == "OFFER_STALE":
        tally["stale"] += 1
        fresh = [u for u in student.call("GET", "/v1/updates", None, 200).json()["updates"]
                 if u["kind"] == "offer_ready"][-1]  # fmt: skip
        response = student.call("POST", f"/v1/offers/{fresh['offer_id']}/accept")
    student.expect(response, 200)
    tally["joined"] += 1


def check_rooms(ctx: ServiceContext) -> list[str]:
    """P-1 end to end: every room window lies inside every member's private flex window."""
    problems: list[str] = []
    with ctx.uow_factory() as uow:
        for room in uow.rooms.list_all():
            if room.size == 0:
                continue
            window_ok = room.window_start is not None and room.window_end is not None
            if not window_ok:
                problems.append(f"{room.id}: members share no time")
                continue
            for member in uow.rooms.members(room.id):
                envelope = uow.intents.load_envelope(member.intent_id)
                assert envelope is not None
                flex = envelope.flex_window()
                if room.window_start < flex.start or room.window_end > flex.end:
                    problems.append(f"{room.id}: {member.alias} outside private flex window")
            if room.size != len(uow.rooms.members(room.id)):
                problems.append(f"{room.id}: size {room.size} does not match members")
    return problems


def print_summary(ctx: ServiceContext, tally: Counter[str]) -> None:
    print("\nroom summary (Phoenix time)")
    print(f"{'event':<30} {'room':<22} {'size':>4} {'status':<7} {'window':<15} vibe    budget")
    with ctx.uow_factory() as uow:
        for room in uow.rooms.list_all():
            event = uow.events.get(room.event_key)
            local = "-"
            if room.window_start and room.window_end:
                begin, finish = (
                    room.window_start.astimezone(PHOENIX),
                    room.window_end.astimezone(PHOENIX),
                )
                local = f"{begin:%H:%M}-{finish:%H:%M}"
            print(
                f"{(event.source_url[-30:] if event else '?'):<30} {room.id:<22} {room.size:>4} "
                f"{room.status:<7} {local:<15} {room.vibe or '-':<7} {room.budget_band or '-'}"
            )
    print("\n" + ", ".join(f"{key}={value}" for key, value in sorted(tally.items())))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--intents", type=int, default=50)
    parser.add_argument("--events", type=int, default=3)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    day = datetime.now(UTC) + timedelta(days=1)
    tally: Counter[str] = Counter()
    with tempfile.TemporaryDirectory() as directory:
        settings = Settings(
            _env_file=None, CREWBIE_ENV="dev",
            CREWBIE_DATABASE_URL=f"sqlite:///{Path(directory) / 'sim.db'}",
        )  # type: ignore[call-arg]  # fmt: skip
        app = create_app(
            settings, rate_limits=RateLimits(10_000, 10_000), sweep_interval_seconds=3600
        )
        with TestClient(app) as client:
            ctx: ServiceContext = app.state.crewbie.ctx
            for number in range(args.intents):
                run_student(client, ctx, rng, number, rng.randrange(args.events), day, tally)
            print_summary(ctx, tally)
            with ctx.uow_factory() as uow:
                negotiations = len(uow.public_events.after(0, 100000))
            problems = check_rooms(ctx)
    print(f"public events recorded: {negotiations}")
    if problems:
        print("\nPROBLEMS:\n  " + "\n  ".join(problems))
        return 1
    print(
        f"\nOK: {args.intents} intents, no errors, every room inside every member's private limits"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
