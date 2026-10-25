from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from crewbie.api.app import create_app
from crewbie.discord_bot import runtime
from crewbie.discord_bot.runtime import BotRuntime, BotStatus
from tests.conftest import make_settings
from tests.support import FakeClock


def test_nfr_obs_02_health_reports_discord_disabled_by_default(client: TestClient) -> None:
    assert client.get("/healthz").json()["discord"] == "disabled"


def test_health_reports_the_bots_status_and_the_lifespan_starts_and_stops_it(
    tmp_path: Path, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []

    async def fake_start(self: BotRuntime) -> None:
        events.append("start")
        self._status.set("connected")

    async def fake_stop(self: BotRuntime) -> None:
        events.append("stop")
        self._status.set("disabled")

    monkeypatch.setattr(runtime.BotRuntime, "start", fake_start)
    monkeypatch.setattr(runtime.BotRuntime, "stop", fake_stop)
    settings = make_settings(tmp_path, CREWBIE_DISCORD_ENABLED="true")
    with TestClient(create_app(settings, clock=clock, sweep_interval_seconds=3600)) as client:
        assert client.get("/healthz").json()["discord"] == "connected"
    assert events == ["start", "stop"]


def test_the_bot_is_not_started_when_discord_is_disabled(
    tmp_path: Path, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[str] = []

    async def fake_start(self: BotRuntime) -> None:
        started.append("start")

    monkeypatch.setattr(runtime.BotRuntime, "start", fake_start)
    with TestClient(create_app(make_settings(tmp_path), clock=clock, sweep_interval_seconds=3600)):
        pass
    assert started == []


def test_bot_status_holds_the_latest_value() -> None:
    status = BotStatus()
    assert status.value == "disabled"
    status.set("connecting")
    assert status.value == "connecting"
