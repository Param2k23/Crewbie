import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from crewbie.services import offers
from crewbie.services.context import ServiceContext
from tests.support import FakeClock, Student, at, intent_body


def test_as_1_first_student_gets_a_new_room_offer_then_must_link(
    ctx: ServiceContext,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    student = make_student()
    result = student.submit()
    offer = result["offer"]
    assert (result["state"], offer["type"], offer["room"]) == ("offered", "new_room", None)
    assert offer["proposal"]["start"] == at(60).isoformat()

    # AS-7: accept before linking is refused with a fresh code, which then works.
    refused = student.post(f"/v1/offers/{offer['offer_id']}/accept")
    assert refused.status_code == 409
    details = refused.json()["error"]["details"]
    assert refused.json()["error"]["code"] == "LINK_REQUIRED"
    assert set(details) == {"link_code", "invite_url", "expires_at"}
    assert details["invite_url"] == "https://discord.gg/testinvite"

    from crewbie.services import linking

    linking.complete(ctx, details["link_code"], "444444444444444444", "walker")
    accepted = student.post(f"/v1/offers/{offer['offer_id']}/accept")
    assert accepted.status_code == 200
    body = accepted.json()
    assert body["state"] == "joined" and body["thread_url"] is None
    assert body["room"]["size"] == 1 and body["room"]["status"] == "open"
    assert [u["kind"] for u in student.updates()] == ["offer_ready", "joined"]


def test_fr_lnk_04_unlinked_accept_does_not_create_a_membership(
    client: TestClient,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    student = make_student()
    offer_id = student.submit()["offer"]["offer_id"]
    student.post(f"/v1/offers/{offer_id}/accept")
    engine = client.app.state.crewbie.engine  # type: ignore[attr-defined]
    with engine.connect() as connection:
        assert connection.execute(text("select count(*) from memberships")).scalar_one() == 0
        assert connection.execute(text("select count(*) from rooms")).scalar_one() == 0


def test_fr_int_02_validation_errors_list_fields_and_never_echo_values(
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    student = make_student()
    body = intent_body(flex_earliest=at(200), flex_latest=at(10), cap=913)
    response = student.post("/v1/intents", body)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_FAILED"
    assert set(error["details"]["fields"]) == {"flex.earliest", "flex.latest"}
    assert "913" not in response.text and at(200).isoformat() not in response.text


@pytest.mark.parametrize(
    ("mutate", "field"),
    [
        (lambda b: b["shared"].update(activity_min_minutes=10), "activity_min_minutes"),
        (lambda b: b["shared"].update(interests=["a", "b", "c", "d"]), "interests"),
        (lambda b: b["shared"].update(budget_band="luxury"), "shared.budget_band"),
        (lambda b: b["shared"]["window"].update(end="2026-11-06T16:00:00"), "shared.window.end"),
        (lambda b: b["shared"]["window"].update(end=b["shared"]["window"]["start"]), "window"),
        (lambda b: b["event"].update(source_url="http://insecure.test/x"), "event.source_url"),
        (lambda b: b["event"].update(date="06/11/2026"), "event.date"),
        (lambda b: b["event"].update(title=""), "event.title"),
        (lambda b: b.update(extra="nope"), "extra"),
        (lambda b: b["private"].pop("flex"), "private.flex"),
    ],
)
def test_fr_int_02_rejects_invalid_intents(mutate, field, make_student) -> None:  # type: ignore[no-untyped-def]
    student = make_student()
    body = intent_body()
    mutate(body)
    response = student.post("/v1/intents", body)
    assert response.status_code == 422, response.text
    assert field in response.json()["error"]["details"]["fields"]


def test_fr_int_02_window_entirely_in_the_past_is_rejected(
    clock: FakeClock,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    student = make_student()
    clock.advance(hours=5)
    response = student.post("/v1/intents", intent_body(start=60, end=180))
    assert response.status_code == 422
    assert "window" in response.json()["error"]["details"]["fields"]


def test_invalid_json_body_is_a_validation_error(make_student) -> None:  # type: ignore[no-untyped-def]
    student = make_student()
    response = student.client.post(
        "/v1/intents",
        content="{not json",
        headers={**student.headers, "Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_fr_evt_02_and_03_event_text_is_sanitised_and_first_write_wins(
    client: TestClient,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    first, second = make_student(), make_student()
    first.submit(title="Board\x00 game\nnight " + "x" * 300)
    second.submit(title="Hijacked title")
    engine = client.app.state.crewbie.engine  # type: ignore[attr-defined]
    with engine.connect() as connection:
        titles = [r[0] for r in connection.execute(text("select title from events"))]
    assert len(titles) == 1 and len(titles[0]) == 120
    assert titles[0].startswith("Board game night xxx") and "\x00" not in titles[0]


def test_fr_int_03_resubmitting_replaces_an_unjoined_intent(
    client: TestClient,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    student = make_student()
    first = student.submit()
    second = student.submit(start=70, end=190)
    assert first["intent_id"] != second["intent_id"]
    assert student.get(f"/v1/intents/{first['intent_id']}").json()["state"] == "withdrawn"
    assert student.get(f"/v1/intents/{second['intent_id']}").json()["state"] == "offered"
    stale = student.post(f"/v1/offers/{first['offer']['offer_id']}/accept")
    assert stale.json()["error"]["code"] == "OFFER_CLOSED"


def test_fr_int_03_joined_intent_blocks_resubmission(
    ctx: ServiceContext,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    student = make_student()
    student.link(ctx)
    student.post(f"/v1/offers/{student.submit()['offer']['offer_id']}/accept")
    again = student.post("/v1/intents", intent_body())
    assert again.status_code == 409 and again.json()["error"]["code"] == "ALREADY_IN_ROOM"


def test_fr_int_05_sixth_submission_for_one_event_in_a_day_is_limited(
    make_student,  # type: ignore[no-untyped-def]
    clock: FakeClock,
) -> None:
    student = make_student()
    for _ in range(5):
        student.submit(start=1500, end=1620)
    limited = student.post("/v1/intents", intent_body(start=1500, end=1620))
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) > 0
    # Other events are unaffected, and the allowance returns after 24 hours.
    other = student.post("/v1/intents", intent_body(start=1500, end=1620, url="https://o.test/e"))
    assert other.status_code == 201
    clock.advance(hours=24, minutes=1)
    assert student.post("/v1/intents", intent_body(start=1500, end=1620)).status_code == 201


def test_fr_int_06_withdrawing_before_joining_stops_matching(make_student) -> None:  # type: ignore[no-untyped-def]
    student = make_student()
    result = student.submit()
    withdrawn = student.post(f"/v1/intents/{result['intent_id']}/withdraw")
    assert withdrawn.json() == {"intent_id": result["intent_id"], "state": "withdrawn"}
    repeat = student.post(f"/v1/intents/{result['intent_id']}/withdraw")
    assert repeat.status_code == 200 and repeat.json()["state"] == "withdrawn"
    closed = student.post(f"/v1/offers/{result['offer']['offer_id']}/accept")
    assert closed.json()["error"]["code"] == "OFFER_CLOSED"


def test_other_students_cannot_see_or_change_an_intent_or_offer(make_student) -> None:  # type: ignore[no-untyped-def]
    owner, intruder = make_student(), make_student()
    result = owner.submit()
    for response in (
        intruder.get(f"/v1/intents/{result['intent_id']}"),
        intruder.post(f"/v1/intents/{result['intent_id']}/withdraw"),
        intruder.post(f"/v1/offers/{result['offer']['offer_id']}/accept"),
        intruder.post(f"/v1/offers/{result['offer']['offer_id']}/decline"),
    ):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"


def test_idempotency_key_replays_the_stored_response(
    client: TestClient,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    student = make_student()
    headers = {"Idempotency-Key": "11111111-2222-3333-4444-555555555555"}
    first = student.post("/v1/intents", intent_body(), headers=headers)
    second = student.post("/v1/intents", intent_body(), headers=headers)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    engine = client.app.state.crewbie.engine  # type: ignore[attr-defined]
    with engine.connect() as connection:
        assert connection.execute(text("select count(*) from intents")).scalar_one() == 1


def test_fr_ofr_07_accept_is_idempotent_with_a_key(ctx: ServiceContext, make_student) -> None:  # type: ignore[no-untyped-def]
    student = make_student()
    student.link(ctx)
    offer_id = student.submit()["offer"]["offer_id"]
    headers = {"Idempotency-Key": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"}
    first = student.post(f"/v1/offers/{offer_id}/accept", headers=headers)
    second = student.post(f"/v1/offers/{offer_id}/accept", headers=headers)
    assert first.status_code == second.status_code == 200 and first.json() == second.json()
    without_key = student.post(f"/v1/offers/{offer_id}/accept")
    assert without_key.json()["error"]["code"] == "OFFER_CLOSED"


def test_idempotency_key_cannot_be_reused_for_another_request(make_student) -> None:  # type: ignore[no-untyped-def]
    student = make_student()
    headers = {"Idempotency-Key": "reuse-key-12345678"}
    student.post("/v1/intents", intent_body(), headers=headers)
    other = student.post("/v1/offers/o_whatever/decline", headers=headers)
    assert other.status_code == 422
    assert (
        student.post("/v1/intents", intent_body(), headers={"Idempotency-Key": "x"}).status_code
        == 422
    )


def test_fr_ofr_05_decline_marks_offer_and_intent(make_student) -> None:  # type: ignore[no-untyped-def]
    student = make_student()
    result = student.submit()
    offer_id = result["offer"]["offer_id"]
    assert student.post(f"/v1/offers/{offer_id}/decline").json() == {"state": "declined"}
    assert student.get(f"/v1/intents/{result['intent_id']}").json()["state"] == "declined"
    again = student.post(f"/v1/offers/{offer_id}/decline")
    assert again.status_code == 409 and again.json()["error"]["code"] == "OFFER_CLOSED"
    # A declined intent does not block a new one (FR-INT-03).
    assert student.post("/v1/intents", intent_body()).status_code == 201


def test_fr_ofr_06_expired_offers_are_rejected_and_swept(
    ctx: ServiceContext,
    clock: FakeClock,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    student, sleeper = make_student(), make_student()
    student.link(ctx)
    expiring = student.submit()
    swept = sleeper.submit()
    clock.advance(minutes=15)
    rejected = student.post(f"/v1/offers/{expiring['offer']['offer_id']}/accept")
    assert rejected.status_code == 410 and rejected.json()["error"]["code"] == "OFFER_EXPIRED"
    assert student.get(f"/v1/intents/{expiring['intent_id']}").json()["state"] == "expired"
    assert [u["kind"] for u in student.updates()] == ["offer_ready", "offer_expired"]

    assert offers.sweep_expired(ctx) == 1  # the other offer; the first was handled on accept
    assert sleeper.get(f"/v1/intents/{swept['intent_id']}").json()["state"] == "expired"
    assert [u["kind"] for u in sleeper.updates()][-1] == "offer_expired"
    assert offers.sweep_expired(ctx) == 0


def test_fr_ofr_06_expired_intent_can_be_resubmitted(
    clock: FakeClock,
    ctx: ServiceContext,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    student = make_student()
    student.submit()
    clock.advance(minutes=16)
    offers.sweep_expired(ctx)
    assert student.post("/v1/intents", intent_body()).status_code == 201


def test_fr_upd_02_updates_use_a_cursor(make_student) -> None:  # type: ignore[no-untyped-def]
    student = make_student()
    student.submit()
    student.submit(start=70, end=190)
    body = student.get("/v1/updates?cursor=0&limit=1").json()
    assert body["cursor"] == 1 and len(body["updates"]) == 1
    rest = student.get(f"/v1/updates?cursor={body['cursor']}").json()
    assert [u["seq"] for u in rest["updates"]] == [2] and rest["cursor"] == 2
    empty = student.get("/v1/updates?cursor=2").json()
    assert empty == {"cursor": 2, "updates": []}
    assert student.get("/v1/updates?limit=51").status_code == 422
    update = rest["updates"][0]
    assert update["kind"] == "offer_ready" and update["event_title"] == "Board game night"
    json.dumps(update)


def test_updates_are_private_to_each_install(make_student) -> None:  # type: ignore[no-untyped-def]
    a, b = make_student(), make_student()
    a.submit()
    assert b.updates() == []
    assert isinstance(a, Student)
