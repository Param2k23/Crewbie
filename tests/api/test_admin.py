import pytest
from fastapi.testclient import TestClient

from crewbie.api.app import create_app
from crewbie.config import Settings
from crewbie.services.context import ServiceContext
from tests.api.test_room_flow import start_room
from tests.conftest import ADMIN_TOKEN, make_settings
from tests.support import FakeClock

ADMIN = {"X-Admin-Token": ADMIN_TOKEN}


def test_nfr_sec_04_admin_is_hidden_when_no_token_is_configured(
    tmp_path,
    clock: FakeClock,  # type: ignore[no-untyped-def]
) -> None:
    settings = make_settings(tmp_path, CREWBIE_ADMIN_TOKEN="")
    with TestClient(create_app(settings, clock=clock, sweep_interval_seconds=3600)) as client:
        for headers in ({}, ADMIN):
            response = client.get("/v1/admin/rooms", headers=headers)
            assert response.status_code == 404


@pytest.mark.parametrize("headers", [{}, {"X-Admin-Token": "wrong"}, {"X-Admin-Token": ""}])
def test_nfr_sec_04_admin_requires_the_token(client: TestClient, headers: dict[str, str]) -> None:
    response = client.get("/v1/admin/rooms", headers=headers)
    assert response.status_code == 401 and response.json()["error"]["code"] == "UNAUTHORIZED"


def test_fr_adm_01_install_tokens_do_not_open_admin(client: TestClient, make_student) -> None:  # type: ignore[no-untyped-def]
    student = make_student()
    assert client.get("/v1/admin/rooms", headers=student.headers).status_code == 401


def test_fr_adm_01_lists_rooms_with_aliases_and_outbox_counts(
    client: TestClient,
    ctx: ServiceContext,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    student = make_student()
    start_room(ctx, student, start=60, end=180)
    body = client.get("/v1/admin/rooms", headers=ADMIN).json()
    (room,) = body["rooms"]
    assert room["members"] == [{"alias": "member-1", "is_synthetic": False}]
    assert room["size"] == 1 and room["status"] == "open"
    assert body["outbox"] == {"pending": 1, "failed": 0}
    assert student.install_id not in str(body)
    jobs = client.get("/v1/admin/outbox?state=pending", headers=ADMIN).json()["jobs"]
    assert [j["kind"] for j in jobs] == ["upsert_board_card"]
    assert client.get("/v1/admin/outbox", headers=ADMIN).json() == {"jobs": []}


def test_fr_adm_01_force_close_notifies_members_and_queues_archive(
    client: TestClient,
    ctx: ServiceContext,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    student = make_student()
    _, room_id = start_room(ctx, student, start=60, end=180)
    assert (
        client.post(f"/v1/admin/rooms/{room_id}/close", headers=ADMIN).json()["status"] == "closed"
    )
    assert client.post(f"/v1/admin/rooms/{room_id}/close", headers=ADMIN).status_code == 200
    assert client.post("/v1/admin/rooms/r_missing/close", headers=ADMIN).status_code == 404
    assert [u["kind"] for u in student.updates()][-1] == "room_closed"
    jobs = client.get("/v1/admin/outbox?state=pending", headers=ADMIN).json()["jobs"]
    assert "archive_thread" in {j["kind"] for j in jobs}


def test_fr_adm_02_seed_creates_synthetic_rooms_once(client: TestClient) -> None:
    first = client.post("/v1/admin/seed", headers=ADMIN).json()
    second = client.post("/v1/admin/seed", headers=ADMIN).json()
    assert first == second and len(first["rooms"]) == 2
    rooms = client.get("/v1/admin/rooms", headers=ADMIN).json()["rooms"]
    assert sorted(r["size"] for r in rooms) == [1, 2]
    assert all(m["is_synthetic"] for r in rooms for m in r["members"])
    big = next(r for r in rooms if r["size"] == 2)
    assert big["status"] == "active"


def test_fr_adm_02_seed_is_refused_in_prod(tmp_path, clock: FakeClock) -> None:  # type: ignore[no-untyped-def]
    from cryptography.fernet import Fernet

    settings: Settings = make_settings(
        tmp_path, CREWBIE_ENV="prod", CREWBIE_ENVELOPE_KEY=Fernet.generate_key().decode()
    )
    with TestClient(create_app(settings, clock=clock, sweep_interval_seconds=3600)) as client:
        response = client.post("/v1/admin/seed", headers=ADMIN)
        assert response.status_code == 403 and response.json()["error"]["code"] == "FORBIDDEN"
