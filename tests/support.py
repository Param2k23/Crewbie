"""Helpers shared by API, skill and privacy tests."""

import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient

from crewbie.domain.offer import OfferType
from crewbie.domain.windows import TimeWindow
from crewbie.matching.matcher import MatchRequest, MatchResult

START = datetime(2026, 11, 6, 15, 0, tzinfo=UTC)
EVENT_URL = "https://sundevilcentral.eoss.asu.edu/events/board-game-night"


class FakeClock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


def at(minutes: int) -> datetime:
    """A moment `minutes` after the fake clock's start (15:00 UTC)."""
    return START + timedelta(minutes=minutes)


def window(start: int, end: int) -> TimeWindow:
    return TimeWindow(at(start), at(end))


class ScriptedMatcher:
    """Returns queued results, then falls back to a new-room offer (the Phase 2 stub)."""

    def __init__(self) -> None:
        self.script: list[Callable[[MatchRequest], MatchResult]] = []

    def queue(self, result: MatchResult) -> None:
        self.script.append(lambda _: result)

    def match(self, request: MatchRequest) -> MatchResult:
        if self.script:
            return self.script.pop(0)(request)
        return MatchResult(OfferType.NEW_ROOM, request.joiner.shared.window)


def intent_body(
    start: int = 60,
    end: int = 180,
    *,
    flex_earliest: datetime | None = None,
    flex_latest: datetime | None = None,
    cap: float | None = 15,
    title: str = "Board game night",
    band: str = "low",
    vibe: str = "chill",
    interests: tuple[str, ...] = ("board-games",),
    date: str = "2026-11-06",
    start_time: str = "18:00",
    url: str = EVENT_URL,
    minutes: int = 90,
) -> dict[str, Any]:
    private: dict[str, Any] = {
        "flex": {
            "earliest": (flex_earliest or at(start - 30)).isoformat(),
            "latest": (flex_latest or at(end + 30)).isoformat(),
        }
    }
    if cap is not None:
        private["budget_cap_usd"] = cap
    return {
        "event": {
            "source_url": url,
            "title": title,
            "location_label": "Hayden Library",
            "date": date,
            "start_time": start_time,
        },
        "shared": {
            "window": {"start": at(start).isoformat(), "end": at(end).isoformat()},
            "activity_min_minutes": minutes,
            "budget_band": band,
            "vibe": vibe,
            "interests": list(interests),
        },
        "private": private,
    }


class Student:
    """One registered install talking to the API through a test client."""

    def __init__(self, client: TestClient, name: str = "student") -> None:
        self.client = client
        self.name = name
        self.token = secrets.token_urlsafe(32)
        self.headers = {"Authorization": f"Bearer {self.token}"}
        response = client.post("/v1/installs", json={}, headers=self.headers)
        assert response.status_code == 201, response.text
        self.install_id: str = response.json()["install_id"]

    def get(self, path: str, **kw: Any) -> Any:
        return self.client.get(path, headers=self.headers, **kw)

    def post(self, path: str, body: Any = None, **kw: Any) -> Any:
        return self.client.post(
            path, json=body, headers={**self.headers, **kw.pop("headers", {})}, **kw
        )

    def submit(self, **kw: Any) -> dict[str, Any]:
        response = self.post("/v1/intents", intent_body(**kw))
        assert response.status_code == 201, response.text
        result: dict[str, Any] = response.json()
        return result

    def link(self, app_ctx: Any, discord_user_id: str | None = None) -> None:
        """Link this install to a Discord user the way the bot would."""
        from crewbie.services import linking

        code = self.post("/v1/installs/me/link-codes").json()["code"]
        linking.complete(
            app_ctx, code, discord_user_id or f"9{abs(hash(self.name)) % 10**16:016d}", self.name
        )

    def updates(self, cursor: int = 0) -> list[dict[str, Any]]:
        return list(self.get(f"/v1/updates?cursor={cursor}").json()["updates"])
