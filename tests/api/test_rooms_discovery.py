from fastapi.testclient import TestClient

from crewbie.domain.event_key import event_key
from crewbie.services.context import ServiceContext
from tests.api.test_room_flow import join, start_room
from tests.support import EVENT_URL, FakeClock, ScriptedMatcher, intent_body

ROOM_KEYS = {"room_id", "size", "status", "window", "vibe", "budget_band", "top_interests"}
KEY = event_key(EVENT_URL, "2026-11-06", "18:00")


def test_fr_dsc_01_lists_rooms_by_event_key_or_by_event_fields(
    ctx: ServiceContext,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    student = make_student()
    _, room_id = start_room(ctx, student, start=60, end=180)
    by_key = student.get(f"/v1/rooms?event_key={KEY}").json()
    by_fields = student.get(
        "/v1/rooms",
        params={
            "source_url": EVENT_URL + "/?utm_source=x",
            "date": "2026-11-06",
            "start_time": "18:00",
        },
    ).json()
    assert by_key == by_fields
    assert by_key["event_key"] == KEY
    (room,) = by_key["rooms"]
    assert room["room_id"] == room_id and room["size"] == 1 and room["status"] == "open"
    assert room["vibe"] == "chill" and room["budget_band"] == "low"
    assert room["top_interests"] == ["board-games"]
    assert set(room["window"]) == {"start", "end"}


def test_fr_dsc_02_summaries_contain_only_room_aggregates(
    ctx: ServiceContext,
    matcher: ScriptedMatcher,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    a, b = make_student(), make_student()
    _, room_id = start_room(ctx, a, start=60, end=180)
    join(ctx, matcher, b, room_id, (60, 180), start=60, end=180)
    response = b.get(f"/v1/rooms?event_key={KEY}")
    (room,) = response.json()["rooms"]
    assert set(room) == ROOM_KEYS and room["size"] == 2
    for needle in (a.install_id, b.install_id, "member-", "913", "discord"):
        assert needle not in response.text


def test_discovery_requires_event_key_or_event_fields_and_ignores_unknown_events(
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    student = make_student()
    assert student.get("/v1/rooms").status_code == 422
    assert student.get("/v1/rooms?source_url=https://x.test/e").status_code == 422
    assert student.get("/v1/rooms?event_key=0000000000000000").json()["rooms"] == []


def test_discovery_skips_rooms_whose_window_has_ended(
    ctx: ServiceContext,
    clock: FakeClock,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    student = make_student()
    start_room(ctx, student, start=60, end=180)
    assert len(student.get(f"/v1/rooms?event_key={KEY}").json()["rooms"]) == 1
    clock.advance(hours=4)
    assert student.get(f"/v1/rooms?event_key={KEY}").json()["rooms"] == []


def test_fr_dsc_03_batch_lookup_of_up_to_five_events(
    ctx: ServiceContext,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    student = make_student()
    start_room(ctx, student, start=60, end=180)
    events = [
        {"ref": "a", "source_url": EVENT_URL, "date": "2026-11-06", "start_time": "18:00"},
        {"ref": "b", "source_url": "https://other.test/x", "date": "2026-11-07"},
    ]
    results = student.post("/v1/rooms/lookup", {"events": events}).json()["results"]
    assert [r["ref"] for r in results] == ["a", "b"]
    assert len(results[0]["rooms"]) == 1 and results[1]["rooms"] == []
    too_many = [dict(events[0], ref=f"e{i}") for i in range(6)]
    assert student.post("/v1/rooms/lookup", {"events": too_many}).status_code == 422
    assert student.post("/v1/rooms/lookup", {"events": []}).status_code == 422


def test_discovery_is_scoped_to_the_event(
    client: TestClient,
    ctx: ServiceContext,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    student = make_student()
    start_room(ctx, student, start=60, end=180)
    other = make_student()
    other.post("/v1/intents", intent_body(url="https://other.test/e"))
    assert other.get(f"/v1/rooms?event_key={KEY}").json()["rooms"][0]["size"] == 1
