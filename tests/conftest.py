import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

from crewbie.api.app import create_app
from crewbie.api.rate_limit import RateLimits
from crewbie.config import Settings
from crewbie.services.context import ServiceContext
from tests.support import FakeClock, ScriptedMatcher, Student

ADMIN_TOKEN = "test-admin-token-" + "x" * 24


def make_settings(tmp_path: Path, **overrides: str) -> Settings:
    values = {
        "CREWBIE_DATABASE_URL": f"sqlite:///{tmp_path / 'api.db'}",
        "CREWBIE_ADMIN_TOKEN": ADMIN_TOKEN,
        "CREWBIE_DISCORD_INVITE_URL": "https://discord.gg/testinvite",
        "CREWBIE_DISCORD_GUILD_ID": "111111111111111111",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def matcher() -> ScriptedMatcher:
    return ScriptedMatcher()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def client(settings: Settings, clock: FakeClock, matcher: ScriptedMatcher) -> Iterator[TestClient]:
    app = create_app(settings, matcher=matcher, clock=clock, sweep_interval_seconds=3600)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def real_client(settings: Settings, clock: FakeClock) -> Iterator[TestClient]:
    """The app with its default deterministic matcher, as deployed."""
    with TestClient(create_app(settings, clock=clock, sweep_interval_seconds=3600)) as test_client:
        yield test_client


@pytest.fixture
def real_ctx(real_client: TestClient) -> ServiceContext:
    context: ServiceContext = real_client.app.state.crewbie.ctx  # type: ignore[attr-defined]
    return context


@pytest.fixture
def make_real_student(real_client: TestClient):  # type: ignore[no-untyped-def]
    counter = iter(range(1, 100))

    def factory() -> Student:
        return Student(real_client, f"real{next(counter)}")

    return factory


@pytest.fixture
def ctx(client: TestClient) -> ServiceContext:
    context: ServiceContext = client.app.state.crewbie.ctx  # type: ignore[attr-defined]
    return context


@pytest.fixture
def make_student(client: TestClient):  # type: ignore[no-untyped-def]
    counter = iter(range(1, 100))

    def factory() -> Student:
        return Student(client, f"student{next(counter)}")

    return factory


@pytest.fixture
def limited_client(settings: Settings, clock: FakeClock) -> Iterator[TestClient]:
    app = create_app(
        settings,
        clock=clock,
        rate_limits=RateLimits(requests_per_minute=3, registrations_per_hour=2),
        sweep_interval_seconds=3600,
    )
    with TestClient(app) as test_client:
        yield test_client


@dataclass(frozen=True)
class LiveServer:
    url: str
    ctx: ServiceContext


@pytest.fixture
def live_server(tmp_path: Path) -> Iterator[LiveServer]:
    """A real HTTP server on a free port, for tests that run crew.py as a subprocess."""
    import socket

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    app = create_app(make_settings(tmp_path), sweep_interval_seconds=3600)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    assert server.started, "live server did not start"
    yield LiveServer(f"http://127.0.0.1:{port}", app.state.crewbie.ctx)
    server.should_exit = True
    thread.join(timeout=5)
