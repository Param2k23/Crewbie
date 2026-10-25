"""Acceptance scenarios AS-2 to AS-6 through the API with the real deterministic matcher."""

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from crewbie.services import matchmaking
from crewbie.services.context import ServiceContext
from crewbie.telemetry.public_events import ALLOWED_FIELDS, EVENT_TYPES
from tests.support import FakeClock, ScriptedMatcher, Student, at, intent_body


def create_room(ctx: ServiceContext, student: Student, **kw: Any) -> str:
    """A first student confirms a new room. Returns the room id."""
    result = student.submit(**kw)
    assert result["offer"]["type"] == "new_room"
    student.link(ctx)
    accepted = student.post(f"/v1/offers/{result['offer']['offer_id']}/accept").json()
    return str(accepted["room"]["room_id"])


def rows(client: TestClient, query: str) -> list[tuple[Any, ...]]:
    engine = client.app.state.crewbie.engine  # type: ignore[attr-defined]
    with engine.connect() as connection:
        return [tuple(r) for r in connection.execute(text(query))]


def test_as_2_compatible_student_is_offered_the_room_and_joining_activates_it(
    real_client: TestClient,
    real_ctx: ServiceContext,
    make_real_student,  # type: ignore[no-untyped-def]
) -> None:
    a, b = make_real_student(), make_real_student()
    room_id = create_room(real_ctx, a, start=60, end=180)
    result = b.submit(start=60, end=180)
    offer = result["offer"]
    assert offer["type"] == "join" and offer["window_changed_for_room"] is False
    assert offer["room"]["room_id"] == room_id and offer["room"]["size"] == 1
    assert offer["proposal"] == {"start": at(60).isoformat(), "end": at(180).isoformat()}

    ((version,),) = rows(real_client, "select room_version from offers where type = 'join'")
    assert version == 2  # created at 1, bumped to 2 when the first student joined
    b.link(real_ctx)
    joined = b.post(f"/v1/offers/{offer['offer_id']}/accept").json()
    assert joined["room"]["size"] == 2 and joined["room"]["status"] == "active"
    kinds = [kind for (kind,) in rows(real_client, "select kind from outbox order by created_at")]
    assert "create_thread" in kinds and kinds.count("add_member") == 2


def test_as_3_short_overlap_is_extended_without_asking_the_existing_member(
    real_client: TestClient,
    real_ctx: ServiceContext,
    make_real_student,  # type: ignore[no-untyped-def]
) -> None:
    a, b = make_real_student(), make_real_student()
    room_id = create_room(real_ctx, a, start=60, end=180, flex_latest=at(240))
    a.updates()
    offer = b.submit(start=150, end=270, flex_earliest=at(120), flex_latest=at(300))["offer"]
    assert offer["type"] == "join" and offer["room"]["room_id"] == room_id
    assert offer["proposal"] == {"start": at(120).isoformat(), "end": at(210).isoformat()}
    assert offer["window_changed_for_room"] is True

    b.link(real_ctx)
    assert b.post(f"/v1/offers/{offer['offer_id']}/accept").status_code == 200
    changed = [u for u in a.updates() if u["kind"] == "window_changed"]
    assert changed and changed[0]["window"]["start"] == at(120).isoformat()
    jobs = rows(real_client, "select payload from outbox where kind = 'post_message'")
    assert any("window_changed" in str(payload) for (payload,) in jobs)


def test_as_4_a_member_whose_flex_forbids_the_extension_blocks_the_join(
    real_client: TestClient,
    real_ctx: ServiceContext,
    make_real_student,  # type: ignore[no-untyped-def]
) -> None:
    a, b = make_real_student(), make_real_student()
    create_room(real_ctx, a, start=60, end=180, flex_latest=at(190))
    offer = b.submit(start=150, end=270, flex_earliest=at(120), flex_latest=at(300))["offer"]
    assert offer["type"] == "new_room" and offer["room"] is None
    assert offer["proposal"]["start"] == at(150).isoformat()
    ((outcome, rounds),) = rows(real_client, "select outcome, rounds from negotiations")
    assert (outcome, rounds) == ("failed", 3)


def test_as_5_incompatible_budget_means_a_new_room_and_no_negotiation(
    real_client: TestClient,
    real_ctx: ServiceContext,
    make_real_student,  # type: ignore[no-untyped-def]
) -> None:
    a, b = make_real_student(), make_real_student()
    create_room(real_ctx, a, start=60, end=180, band="high")
    offer = b.submit(start=60, end=180, band="low")["offer"]
    assert offer["type"] == "new_room"
    assert rows(real_client, "select * from negotiations") == []
    assert rows(real_client, "select * from negotiation_steps") == []
    assert not [t for (t, p) in rows(real_client, "select type, payload from public_events")
                if t in ("negotiation_started", "candidate_proposed")]  # fmt: skip


def test_as_6_room_change_between_offer_and_accept_gives_a_fresh_offer(
    real_client: TestClient,
    real_ctx: ServiceContext,
    make_real_student,  # type: ignore[no-untyped-def]
) -> None:
    a, b, c = make_real_student(), make_real_student(), make_real_student()
    room_id = create_room(real_ctx, a, start=60, end=180)
    pending = b.submit(start=60, end=180)["offer"]
    other = c.submit(start=60, end=180)["offer"]
    c.link(real_ctx)
    assert c.post(f"/v1/offers/{other['offer_id']}/accept").status_code == 200  # moves the room

    b.link(real_ctx)
    stale = b.post(f"/v1/offers/{pending['offer_id']}/accept")
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "OFFER_STALE"
    offers_ready = [u for u in b.updates() if u["kind"] == "offer_ready"]
    assert len(offers_ready) == 2 and offers_ready[1]["offer_id"] != pending["offer_id"]
    assert (
        offers_ready[1]["offer_type"] == "join"
    )  # the room is still a fit, now at its new version

    fresh = b.post(f"/v1/offers/{offers_ready[1]['offer_id']}/accept")
    assert fresh.status_code == 200 and fresh.json()["room"]["size"] == 3
    assert fresh.json()["room"]["room_id"] == room_id


def test_fr_mat_09_every_step_emits_a_public_safe_event_in_the_mission_control_vocabulary(
    real_client: TestClient,
    real_ctx: ServiceContext,
    make_real_student,  # type: ignore[no-untyped-def]
) -> None:
    a, b = make_real_student(), make_real_student()
    room_id = create_room(real_ctx, a, start=60, end=180, flex_latest=at(240))
    b.submit(start=150, end=270, flex_earliest=at(120), flex_latest=at(300))
    events = rows(real_client, "select type, payload from public_events order by seq")
    types = [t for t, _ in events]
    assert types[0] == "match_requested" and "negotiation_started" in types
    assert "candidate_proposed" in types and "proposal_confirmed" in types
    assert set(types) <= EVENT_TYPES
    import json

    for _, payload in events:
        body = payload if isinstance(payload, dict) else json.loads(payload)
        assert set(body) <= ALLOWED_FIELDS
    flat = str(events)
    for private in (a.install_id, b.install_id, "discord", "flex", "budget"):
        assert private not in flat
    assert room_id in flat and "member-2" in flat and "host" in flat


def test_stored_steps_name_actors_by_alias_and_carry_no_reasons(
    real_client: TestClient,
    real_ctx: ServiceContext,
    make_real_student,  # type: ignore[no-untyped-def]
) -> None:
    a, b = make_real_student(), make_real_student()
    create_room(real_ctx, a, start=60, end=180, flex_latest=at(190))
    b.submit(start=150, end=270, flex_earliest=at(120), flex_latest=at(300))
    steps = rows(
        real_client,
        "select round, actor_kind, actor_alias, verdict from negotiation_steps order by id",
    )
    assert steps and {s[1] for s in steps} <= {"delegate", "host"}
    assert {s[2] for s in steps} <= {"member-1", "member-2", "host"}
    assert {s[3] for s in steps} <= {"accept", "reject", "counter"}
    assert max(s[0] for s in steps) <= 3
    columns = {c[1] for c in rows(real_client, "pragma table_info(negotiation_steps)")}
    assert not columns & {"reason", "message", "text"}


def test_fr_int_04_a_failed_match_leaves_the_intent_matching_and_the_sweep_retries(
    client: TestClient,
    ctx: ServiceContext,
    matcher: ScriptedMatcher,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    def explode(_: object) -> object:
        raise RuntimeError("boom")

    matcher.script.append(explode)  # type: ignore[arg-type]
    student = make_student()
    response = student.post("/v1/intents", intent_body())
    assert response.status_code == 202
    body = response.json()
    assert body["state"] == "matching" and "offer" not in body
    assert student.get(f"/v1/intents/{body['intent_id']}").json()["state"] == "matching"

    assert matchmaking.rematch_stuck(ctx) == 1
    assert student.get(f"/v1/intents/{body['intent_id']}").json()["state"] == "offered"
    assert [u["kind"] for u in student.updates()] == ["offer_ready"]
    assert matchmaking.rematch_stuck(ctx) == 0


def test_a_withdrawn_intent_is_not_matched_after_the_fact(
    ctx: ServiceContext,
    clock: FakeClock,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    student = make_student()
    result = student.submit()
    student.post(f"/v1/intents/{result['intent_id']}/withdraw")
    assert matchmaking.run(ctx, result["intent_id"]) is None
