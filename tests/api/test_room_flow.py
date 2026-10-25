"""Join, stale, window-extension and leave flows (AS-2, AS-3, AS-6, AS-8).

The Phase 2 matcher only ever offers new rooms, so these tests script join offers directly.
"""

from collections import Counter

from fastapi.testclient import TestClient

from crewbie.domain.offer import OfferType
from crewbie.matching.matcher import MatchResult
from crewbie.services.context import ServiceContext
from tests.support import ScriptedMatcher, Student, at, window


def room_of(ctx: ServiceContext, room_id: str):  # type: ignore[no-untyped-def]
    with ctx.uow_factory() as uow:
        row = uow.rooms.get(room_id)
        assert row is not None
        return row


def outbox(ctx: ServiceContext) -> list[tuple[str, dict]]:  # type: ignore[type-arg]
    with ctx.uow_factory() as uow:
        return [(job.kind, job.payload) for job in uow.outbox.due(at(10**6), limit=1000)]


def start_room(ctx: ServiceContext, student: Student, **window_args: int) -> tuple[str, str]:
    """Submit, link and accept a new-room offer. Returns (intent_id, room_id)."""
    result = student.submit(**window_args)
    student.link(ctx)
    accepted = student.post(f"/v1/offers/{result['offer']['offer_id']}/accept").json()
    return result["intent_id"], accepted["room"]["room_id"]


def offer_join(
    matcher: ScriptedMatcher, ctx: ServiceContext, room_id: str, start: int, end: int
) -> None:
    matcher.queue(
        MatchResult(OfferType.JOIN, window(start, end), room_id, room_of(ctx, room_id).version)
    )


def join(
    ctx: ServiceContext,
    matcher: ScriptedMatcher,
    student: Student,
    room_id: str,
    proposal: tuple[int, int],
    **window_args: int,
) -> dict:  # type: ignore[type-arg]
    offer_join(matcher, ctx, room_id, *proposal)
    result = student.submit(**window_args)
    assert result["offer"]["type"] == "join"
    student.link(ctx)
    response = student.post(f"/v1/offers/{result['offer']['offer_id']}/accept")
    assert response.status_code == 200, response.text
    return {"intent_id": result["intent_id"], **response.json()}


def test_as_2_second_student_joins_and_the_room_becomes_active(
    ctx: ServiceContext,
    matcher: ScriptedMatcher,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    first, second = make_student(), make_student()
    _, room_id = start_room(ctx, first, start=60, end=180)
    joined = join(ctx, matcher, second, room_id, (60, 180), start=60, end=180)
    assert joined["room"] == {"room_id": room_id, "size": 2, "status": "active"}
    assert joined["thread_url"] is None  # the bot creates the thread asynchronously

    jobs = Counter(kind for kind, _ in outbox(ctx))
    assert jobs["create_thread"] == 1 and jobs["add_member"] == 2 and jobs["dm_user"] == 2
    assert {p.get("kind") for k, p in outbox(ctx) if k == "post_message"} == {"icebreaker"}
    assert jobs["upsert_board_card"] >= 1
    assert [u["kind"] for u in first.updates()] == ["offer_ready", "joined", "member_joined"]
    assert [u["kind"] for u in second.updates()] == ["offer_ready", "joined"]
    assert first.updates()[-1]["room"] == {"size": 2}


def test_fr_ofr_03_join_extends_windows_and_derives_the_room(
    ctx: ServiceContext,
    matcher: ScriptedMatcher,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    first, second = make_student(), make_student()
    first_intent, room_id = start_room(ctx, first, start=60, end=180)
    before = room_of(ctx, room_id)
    # AS-3: only a 30-minute overlap, so both agree to 150-240, outside the first window.
    join(ctx, matcher, second, room_id, (150, 240), start=150, end=270)
    room = room_of(ctx, room_id)
    assert (room.window_start, room.window_end) == (at(150), at(240))
    assert room.version == before.version + 1
    with ctx.uow_factory() as uow:
        members = {m.alias: m.effective_window for m in uow.rooms.members(room_id)}
    assert members["member-1"] == window(60, 240)
    assert members["member-2"] == window(150, 270)

    assert any(u["kind"] == "window_changed" for u in first.updates())
    notice = [p for k, p in outbox(ctx) if k == "post_message" and p["kind"] == "window_changed"]
    assert notice and notice[0]["window"]["start"] == at(150).isoformat()
    assert first_intent  # the first student was never asked anything


def test_as_6_stale_offer_is_refused_and_a_fresh_one_is_delivered(
    ctx: ServiceContext,
    matcher: ScriptedMatcher,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    owner, early, late = make_student(), make_student(), make_student()
    _, room_id = start_room(ctx, owner, start=60, end=180)
    offer_join(matcher, ctx, room_id, 90, 180)
    pending = late.submit(start=90, end=200)["offer"]["offer_id"]
    late.link(ctx)
    join(ctx, matcher, early, room_id, (90, 180), start=90, end=200)  # moves the room version

    stale = late.post(f"/v1/offers/{pending}/accept")
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "OFFER_STALE"
    kinds = [u["kind"] for u in late.updates()]
    assert kinds == ["offer_ready", "offer_ready"]
    fresh = late.updates()[-1]["offer_id"]
    assert fresh != pending
    again = late.post(f"/v1/offers/{pending}/accept")
    assert again.json()["error"]["code"] == "OFFER_CLOSED"
    assert room_of(ctx, room_id).size == 2  # the stale accept changed nothing


def test_as_8_leaving_a_three_person_room_widens_the_window_and_notifies(
    ctx: ServiceContext,
    matcher: ScriptedMatcher,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    a, b, c = make_student(), make_student(), make_student()
    _, room_id = start_room(ctx, a, start=60, end=240)
    b_joined = join(ctx, matcher, b, room_id, (120, 180), start=120, end=180)
    join(ctx, matcher, c, room_id, (120, 180), start=100, end=200)
    assert (room_of(ctx, room_id).window_start, room_of(ctx, room_id).window_end) == (
        at(120),
        at(180),
    )
    for student in (a, c):
        student.updates()

    left = b.post(f"/v1/intents/{b_joined['intent_id']}/withdraw")
    assert left.json()["state"] == "withdrawn"
    room = room_of(ctx, room_id)
    assert (room.size, room.status) == (2, "active")
    assert (room.window_start, room.window_end) == (at(100), at(200))  # widened

    removal = [p for k, p in outbox(ctx) if k == "remove_member"]
    assert [p["alias"] for p in removal] == ["member-2"] and removal[0]["discord_user_id"]
    notice = [p for k, p in outbox(ctx) if k == "post_message" and p["kind"] == "member_left"]
    assert notice[0]["alias"] == "member-2" and notice[0]["window_changed"] is True
    for student in (a, c):
        kinds = [u["kind"] for u in student.updates()]
        assert "member_left" in kinds and "window_changed" in kinds
    assert not [u for u in b.updates() if u["kind"] == "member_left"]


def test_leaving_down_to_one_keeps_the_room_open_and_to_zero_closes_it(
    ctx: ServiceContext,
    matcher: ScriptedMatcher,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    a, b = make_student(), make_student()
    a_intent, room_id = start_room(ctx, a, start=60, end=180)
    b_joined = join(ctx, matcher, b, room_id, (90, 180), start=90, end=200)
    b.post(f"/v1/intents/{b_joined['intent_id']}/withdraw")
    assert room_of(ctx, room_id).status == "open"
    a.post(f"/v1/intents/{a_intent}/withdraw")
    closed = room_of(ctx, room_id)
    assert (closed.status, closed.size, closed.window_start) == ("closed", 0, None)
    assert a.get(f"/v1/intents/{a_intent}").json() == {
        "intent_id": a_intent,
        "state": "withdrawn",
        "room_id": None,
        "thread_url": None,
    }


def test_deleting_an_install_in_a_room_removes_it_from_the_room(
    ctx: ServiceContext,
    matcher: ScriptedMatcher,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    a, b = make_student(), make_student()
    _, room_id = start_room(ctx, a, start=60, end=180)
    join(ctx, matcher, b, room_id, (90, 180), start=90, end=200)
    assert b.client.delete("/v1/installs/me", headers=b.headers).status_code == 204
    assert room_of(ctx, room_id).size == 1
    removal = [p for k, p in outbox(ctx) if k == "remove_member"]
    assert removal and removal[0]["discord_user_id"]  # snapshotted before the link was deleted


def test_thread_url_is_built_from_the_guild_and_thread_ids(
    ctx: ServiceContext,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    a = make_student()
    intent_id, room_id = start_room(ctx, a, start=60, end=180)
    with ctx.uow_factory() as uow:
        uow.rooms.set_thread(room_id, "555")
        uow.commit()
    assert a.get(f"/v1/intents/{intent_id}").json()["thread_url"] == (
        "https://discord.com/channels/111111111111111111/555"
    )


def test_synthetic_members_are_never_added_or_dmed(
    client: TestClient,
    ctx: ServiceContext,
    matcher: ScriptedMatcher,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    from crewbie.services import seed

    seeded = seed.seed_demo(ctx)
    with ctx.uow_factory() as uow:
        solo = next(r for r in uow.rooms.list_for_event(seeded["event_key"]) if r.size == 1)
        room_id, version = solo.id, solo.version
        start, end = solo.window_start, solo.window_end
    event = {"url": "https://sundevilcentral.eoss.asu.edu/events/demo-board-game-night",
             "date": start.astimezone().date().isoformat(), "start_time": "18:00"}  # fmt: skip
    student = make_student()
    base = int((start - at(0)).total_seconds() // 60)
    matcher.queue(MatchResult(OfferType.JOIN, window(base, base + 120), room_id, version))
    # The seeded event date is in Phoenix local time; build the body from the stored event.
    with ctx.uow_factory() as uow:
        stored = uow.events.get(seeded["event_key"])
        assert stored is not None
        event["date"], event["url"] = stored.date, stored.source_url
    offer = student.submit(start=base, end=base + 120, url=event["url"], date=event["date"])
    student.link(ctx)
    response = student.post(f"/v1/offers/{offer['offer']['offer_id']}/accept")
    assert response.json()["room"]["size"] == 2
    people = [p for k, p in outbox(ctx) if k in ("add_member", "dm_user")]
    assert {p["install_id"] for p in people} == {student.install_id}
    assert end is not None
