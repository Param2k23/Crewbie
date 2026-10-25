import hashlib
import re
import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from crewbie.domain.errors import LinkCodeInvalid, LinkConflict
from crewbie.services import installs, linking
from crewbie.services.context import ServiceContext
from tests.support import FakeClock, Student, intent_body


def test_fr_ins_01_server_stores_only_the_token_hash(client: TestClient, make_student) -> None:  # type: ignore[no-untyped-def]
    student = make_student()
    engine = client.app.state.crewbie.engine  # type: ignore[attr-defined]
    with engine.connect() as connection:
        stored = connection.execute(text("select token_hash from installs")).scalar_one()
    assert stored == hashlib.sha256(student.token.encode()).hexdigest()
    assert student.token not in stored


def test_fr_ins_03_registration_is_idempotent(client: TestClient) -> None:
    headers = {"Authorization": f"Bearer {secrets.token_urlsafe(32)}"}
    first = client.post("/v1/installs", json={"client": "crew.py/1.0"}, headers=headers)
    second = client.post("/v1/installs", json={}, headers=headers)
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json() == second.json()
    assert first.json()["discord_linked"] is False


@pytest.mark.parametrize("token", ["short", "has spaces " + "x" * 40, "!" * 40])
def test_fr_ins_01_rejects_weak_or_malformed_tokens(client: TestClient, token: str) -> None:
    response = client.post("/v1/installs", json={}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/v1/installs/me"),
        ("delete", "/v1/installs/me"),
        ("post", "/v1/installs/me/link-codes"),
        ("get", "/v1/rooms?event_key=abc"),
        ("get", "/v1/updates"),
        ("post", "/v1/intents/i_x/withdraw"),
        ("post", "/v1/offers/o_x/accept"),
    ],
)
def test_fr_ins_02_endpoints_require_a_known_bearer_token(
    client: TestClient, method: str, path: str
) -> None:
    for headers in ({}, {"Authorization": "Bearer " + "z" * 43}, {"Authorization": "Basic abc"}):
        response = getattr(client, method)(path, headers=headers)
        assert response.status_code == 401, (path, headers)
        assert response.json()["error"]["code"] == "UNAUTHORIZED"
        assert response.headers["WWW-Authenticate"] == "Bearer"


def test_healthz_is_public_and_reports_state(client: TestClient) -> None:
    body = client.get("/healthz").json()
    assert body == {
        "status": "ok",
        "db": "ok",
        "discord": "disabled",
        "outbox_backlog": 0,
        "llm_mode": "off",
    }


def test_healthz_answers_head_requests_for_uptime_monitors(client: TestClient) -> None:
    response = client.head("/healthz")
    assert response.status_code == 200 and response.headers["X-Request-Id"]


def test_fr_ins_04_per_install_rate_limit_returns_retry_after(limited_client: TestClient) -> None:
    student = Student(limited_client)  # registration is limited per IP, not per install
    codes = [student.get("/v1/installs/me").status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and 429 in codes
    limited = student.get("/v1/installs/me")
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    assert int(limited.headers["Retry-After"]) >= 1


def test_fr_ins_04_registration_is_rate_limited_per_source_ip(limited_client: TestClient) -> None:
    results = [
        limited_client.post(
            "/v1/installs",
            json={},
            headers={"Authorization": f"Bearer {secrets.token_urlsafe(32)}"},
        ).status_code
        for _ in range(3)
    ]
    assert results == [201, 201, 429]


def test_every_response_has_a_request_id_and_supplied_ids_are_echoed(client: TestClient) -> None:
    assert re.fullmatch(r"[0-9a-f]{32}", client.get("/healthz").headers["X-Request-Id"])
    echoed = client.get("/healthz", headers={"X-Request-Id": "trace-1234abcd"})
    assert echoed.headers["X-Request-Id"] == "trace-1234abcd"
    junk = client.get("/healthz", headers={"X-Request-Id": "bad id\twith spaces"})
    assert junk.headers["X-Request-Id"] != "bad id\twith spaces"


def test_unknown_routes_use_the_error_shape(client: TestClient) -> None:
    response = client.get("/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_whoami_reflects_link_state(client: TestClient, ctx: ServiceContext, make_student) -> None:  # type: ignore[no-untyped-def]
    student = make_student()
    assert student.get("/v1/installs/me").json() == {
        "install_id": student.install_id,
        "discord_linked": False,
    }
    student.link(ctx)
    me = student.get("/v1/installs/me").json()
    assert me["discord_linked"] is True and me["discord_username"] == student.name


def test_fr_lnk_01_link_code_shape_expiry_and_invite(
    client: TestClient,
    clock: FakeClock,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    student = make_student()
    response = student.post("/v1/installs/me/link-codes")
    body = response.json()
    assert response.status_code == 201
    assert re.fullmatch(r"[A-HJ-NP-Z2-9]{6}", body["code"])
    assert body["invite_url"] == "https://discord.gg/testinvite"
    assert body["command"] == f"/crew link code:{body['code']}"
    assert body["expires_at"].startswith("2026-11-06T15:10:00")


def test_fr_lnk_01_new_code_replaces_unused_ones(ctx: ServiceContext, make_student) -> None:  # type: ignore[no-untyped-def]
    student = make_student()
    first = student.post("/v1/installs/me/link-codes").json()["code"]
    second = student.post("/v1/installs/me/link-codes").json()["code"]
    with pytest.raises(LinkCodeInvalid) as exc:
        linking.complete(ctx, first, "123456789012345678", "x")
    assert exc.value.details["reason"] == "unknown"
    linking.complete(ctx, second, "123456789012345678", "x")


def test_fr_lnk_02_codes_are_single_use_and_expire(
    ctx: ServiceContext,
    clock: FakeClock,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    student = make_student()
    code = student.post("/v1/installs/me/link-codes").json()["code"]
    linking.complete(ctx, code.lower(), "123456789012345678", "dhaval")
    with pytest.raises(LinkCodeInvalid) as used:
        linking.complete(ctx, code, "123456789012345678", "dhaval")
    assert used.value.details["reason"] == "used"

    other = make_student()
    stale = other.post("/v1/installs/me/link-codes").json()["code"]
    clock.advance(minutes=10, seconds=1)
    with pytest.raises(LinkCodeInvalid) as expired:
        linking.complete(ctx, stale, "223456789012345678", "x")
    assert expired.value.details["reason"] == "expired"
    assert "install" not in str(expired.value.details).lower()


def test_fr_lnk_03_one_discord_user_per_install_and_replace_needs_confirmation(
    ctx: ServiceContext,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    a, b = make_student(), make_student()
    linking.complete(
        ctx, a.post("/v1/installs/me/link-codes").json()["code"], "111111111111111111", "a"
    )
    code_b = b.post("/v1/installs/me/link-codes").json()["code"]
    with pytest.raises(LinkConflict) as conflict:
        linking.complete(ctx, code_b, "111111111111111111", "a")
    assert conflict.value.details["reason"] == "discord_user_linked"
    again = a.post("/v1/installs/me/link-codes").json()["code"]
    with pytest.raises(LinkConflict) as install_conflict:
        linking.complete(ctx, again, "999999999999999999", "a2")
    assert install_conflict.value.details["reason"] == "install_linked"

    # The failed attempt did not burn b's code; with confirmation the link moves to b.
    linking.complete(ctx, code_b, "111111111111111111", "a", replace=True)
    assert b.get("/v1/installs/me").json()["discord_linked"] is True
    assert a.get("/v1/installs/me").json()["discord_linked"] is False


def test_fr_lnk_05_discord_only_install_is_created_once(ctx: ServiceContext) -> None:
    first = installs.ensure_discord_install(ctx, "333333333333333333", "walker")
    second = installs.ensure_discord_install(ctx, "333333333333333333", "walker")
    assert first.created and not second.created
    assert first.install_id == second.install_id and second.discord_linked


def test_nfr_prv_03_deleting_an_install_removes_its_data(client: TestClient, make_student) -> None:  # type: ignore[no-untyped-def]
    student = make_student()
    student.submit()
    response = student.client.delete("/v1/installs/me", headers=student.headers)
    assert response.status_code == 204
    assert student.get("/v1/installs/me").status_code == 401
    engine = client.app.state.crewbie.engine  # type: ignore[attr-defined]
    with engine.connect() as connection:
        for table in ("installs", "intents", "envelopes", "offers", "updates"):
            count = connection.execute(text(f"select count(*) from {table}")).scalar_one()
            assert count == 0, table


def test_intent_body_helper_is_valid_json_shape() -> None:
    assert set(intent_body()) == {"event", "shared", "private"}
