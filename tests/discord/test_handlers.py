"""Slash-command and modal logic (FR-LNK-02, FR-BOT-06, FR-BOT-10, AS-7, AS-11)."""

import asyncio
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from crewbie.discord_bot import handlers
from crewbie.discord_bot.handlers import Response
from crewbie.discord_bot.worker import OutboxWorker
from crewbie.services import seed
from crewbie.services.context import ServiceContext
from tests.discord.fakes import FakeGateway
from tests.support import FakeClock, Student, at, intent_body

Drain = Callable[[OutboxWorker], int]
ALICE, BOB, CARA = "711111111111111111", "722222222222222222", "733333333333333333"


def run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


def confirm(response: Response) -> Response:
    assert response.confirm is not None, response.text
    return run(response.confirm.action())  # type: ignore[no-any-return]


def room_for(student: Student, ctx: ServiceContext) -> str:
    student.link(ctx)
    offer = student.submit(start=60, end=180)["offer"]["offer_id"]
    return str(student.post(f"/v1/offers/{offer}/accept").json()["room"]["room_id"])


def join_fields(**overrides: str) -> dict[str, str]:
    fields = {
        "earliest": "08:00",
        "latest": "12:00",
        "minimum": "60",
        "budget": "low",
        "vibe": "chill",
    }
    fields.update(overrides)
    return fields


# --- /crew link ------------------------------------------------------------------------------


def test_as_7_accept_before_linking_then_link_in_discord_then_accept(
    real_ctx: ServiceContext,
    make_real_student,  # type: ignore[no-untyped-def]
) -> None:
    student = make_real_student()
    offer = student.submit()["offer"]["offer_id"]
    refused = student.post(f"/v1/offers/{offer}/accept")
    assert refused.json()["error"]["code"] == "LINK_REQUIRED"
    code = refused.json()["error"]["details"]["link_code"]

    reply = run(handlers.link(real_ctx, code, ALICE, "alice"))
    assert reply.text == "Linked. Cubbie can now add you to crews." and reply.confirm is None
    assert student.post(f"/v1/offers/{offer}/accept").status_code == 200


@pytest.mark.parametrize("reason", ["unknown", "used", "expired"])
def test_fr_lnk_02_failed_links_explain_the_reason_without_install_data(
    real_ctx: ServiceContext,
    clock: FakeClock,
    make_real_student,
    reason: str,  # type: ignore[no-untyped-def]
) -> None:
    student = make_real_student()
    code = student.post("/v1/installs/me/link-codes").json()["code"]
    attempt = "ZZZZZZ"
    if reason == "used":
        run(handlers.link(real_ctx, code, ALICE, "alice"))
        attempt = code
    elif reason == "expired":
        clock.advance(minutes=11)
        attempt = code
    reply = run(handlers.link(real_ctx, attempt, BOB, "bob"))
    assert reason in {"unknown", "used", "expired"}
    assert student.install_id not in reply.text and code not in reply.text
    assert reply.text.endswith("Ask Cubbie for a new one.")
    assert {"unknown": "isn't valid", "used": "already used", "expired": "expired"}[
        reason
    ] in reply.text


def test_fr_lnk_03_relinking_asks_before_replacing(
    real_ctx: ServiceContext,
    make_real_student,  # type: ignore[no-untyped-def]
) -> None:
    first, second = make_real_student(), make_real_student()
    run(
        handlers.link(
            real_ctx, first.post("/v1/installs/me/link-codes").json()["code"], ALICE, "alice"
        )
    )
    code = second.post("/v1/installs/me/link-codes").json()["code"]
    ask = run(handlers.link(real_ctx, code, ALICE, "alice"))
    assert "Replace that link" in ask.text and ask.confirm is not None
    assert second.get("/v1/installs/me").json()["discord_linked"] is False
    assert confirm(ask).text == "Replaced. Cubbie can now add you to crews."
    assert second.get("/v1/installs/me").json()["discord_linked"] is True
    assert first.get("/v1/installs/me").json()["discord_linked"] is False


# --- /crew status and /crew help -----------------------------------------------------------------


def test_status_lists_the_callers_crews_and_nothing_for_strangers(
    real_ctx: ServiceContext,
    make_real_student,  # type: ignore[no-untyped-def]
) -> None:
    student = make_real_student()
    assert "not in any crews" in run(handlers.status(real_ctx, ALICE)).text
    room_for(student, real_ctx)
    text_ = run(handlers.status(real_ctx, student.discord_id)).text
    assert "Board game night" in text_ and "9:00 to 11:00 am" in text_ and "1 going" in text_
    assert "chat opens when a second person joins" in text_
    assert "not in any crews" in run(handlers.status(real_ctx, BOB)).text


def test_help_and_meetpoint_are_static() -> None:
    assert "/crew link" in handlers.help_text().text
    assert "coming soon" in handlers.meetpoint().text


# --- /crew leave -------------------------------------------------------------------------------


def test_fr_bot_10_leave_needs_a_thread_and_membership_then_confirms_then_withdraws(
    real_client: TestClient, real_ctx: ServiceContext, make_real_student,  # type: ignore[no-untyped-def]
    worker: OutboxWorker, gateway: FakeGateway, drain: Drain,
) -> None:  # fmt: skip
    first, second = make_real_student(), make_real_student()
    room_for(first, real_ctx)
    offer = second.submit(start=60, end=180)["offer"]["offer_id"]
    second.link(real_ctx)
    second.post(f"/v1/offers/{offer}/accept")
    drain(worker)
    (thread_id,) = gateway.threads

    assert (
        "inside your crew's thread" in run(handlers.leave(real_ctx, None, second.discord_id)).text
    )
    assert "not in this crew" in run(handlers.leave(real_ctx, thread_id, BOB)).text
    ask = run(handlers.leave(real_ctx, thread_id, second.discord_id))
    assert "Leave this crew?" in ask.text
    size = lambda: real_client.get(  # noqa: E731
        "/v1/admin/rooms", headers={"X-Admin-Token": "test-admin-token-" + "x" * 24}
    ).json()["rooms"][0]["size"]
    assert size() == 2  # nothing happens until the button is pressed
    assert confirm(ask).text == "You've left the crew."
    assert size() == 1
    drain(worker)
    assert second.discord_id not in gateway.members[thread_id]
    assert "not in this crew" in run(handlers.leave(real_ctx, thread_id, second.discord_id)).text


# --- Join modal ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("override", "advice"),
    [
        ({"earliest": "5pm"}, "24-hour times"),
        ({"latest": "25:00"}, "24-hour times"),
        ({"minimum": "ten"}, "between 15 and 720"),
        ({"minimum": "5"}, "between 15 and 720"),
        ({"budget": "luxury"}, "low, mid or high"),
        ({"vibe": "wild"}, "chill, social or active"),
    ],
)
def test_fr_bot_06_bad_modal_input_gets_specific_advice(
    real_ctx: ServiceContext,
    make_real_student,
    override: dict[str, str],
    advice: str,  # type: ignore[no-untyped-def]
) -> None:
    room_id = room_for(make_real_student(), real_ctx)
    reply = run(handlers.board_join(real_ctx, ALICE, "alice", room_id, join_fields(**override)))
    assert advice in reply.text and reply.confirm is None


def test_as_11_a_discord_only_student_joins_from_the_board_and_gets_into_the_thread(
    real_client: TestClient, real_ctx: ServiceContext, make_real_student,  # type: ignore[no-untyped-def]
    worker: OutboxWorker, gateway: FakeGateway, drain: Drain,
) -> None:  # fmt: skip
    host = make_real_student()
    room_id = room_for(host, real_ctx)

    offer = run(handlers.board_join(real_ctx, ALICE, "alice", room_id, join_fields()))
    assert offer.text == "You can join: 9:00 to 11:00 am. Join this crew?"
    assert db_count(real_client, "installs where kind = 'discord'") == 1
    assert db_count(real_client, "memberships") == 1  # nothing joined yet
    done = confirm(offer)
    assert done.text == "You're in. Watch for a DM with the thread link."

    drain(worker)
    (thread_id,) = gateway.threads
    assert gateway.members[thread_id] == {host.discord_id, ALICE}
    assert [user for user, _ in gateway.dms if user == ALICE]
    assert "Board game night" in run(handlers.status(real_ctx, ALICE)).text


def test_a_second_modal_submission_by_the_same_person_reuses_their_discord_install(
    real_client: TestClient,
    real_ctx: ServiceContext,
    make_real_student,  # type: ignore[no-untyped-def]
) -> None:
    room_id = room_for(make_real_student(), real_ctx)
    run(handlers.board_join(real_ctx, ALICE, "alice", room_id, join_fields()))
    run(handlers.board_join(real_ctx, ALICE, "alice", room_id, join_fields(minimum="75")))
    assert db_count(real_client, "installs where kind = 'discord'") == 1


def test_board_join_with_a_timing_that_does_not_fit_offers_a_new_crew_instead(
    real_client: TestClient,
    real_ctx: ServiceContext,
    make_real_student,  # type: ignore[no-untyped-def]
) -> None:
    first = make_real_student()
    first.link(real_ctx)
    offer = first.submit(start=60, end=180, flex_latest=at(190))["offer"]["offer_id"]
    first.post(f"/v1/offers/{offer}/accept")
    with real_ctx.uow_factory() as uow:
        room_id = uow.rooms.list_all()[0].id
    # Room is 9:00-11:00 Phoenix; this person is free 10:30-12:00 but needs 90 minutes.
    reply = run(
        handlers.board_join(
            real_ctx,
            BOB,
            "bob",
            room_id,
            join_fields(earliest="10:30", latest="12:00", minimum="90"),
        )
    )
    assert "doesn't fit" in reply.text and reply.confirm is not None
    assert reply.confirm.label == "Start new crew"
    assert "Started a new crew" in confirm(reply).text
    assert db_count(real_client, "rooms") == 2


def test_board_join_rejects_times_that_never_touch_the_crews_plan(
    real_ctx: ServiceContext,
    make_real_student,  # type: ignore[no-untyped-def]
) -> None:
    room_id = room_for(make_real_student(), real_ctx)
    reply = run(
        handlers.board_join(
            real_ctx, BOB, "bob", room_id, join_fields(earliest="14:00", latest="16:00")
        )
    )
    assert "Those details don't work" in reply.text and reply.confirm is None


def test_board_join_is_refused_for_closed_started_or_unknown_rooms_and_for_members(
    real_client: TestClient,
    real_ctx: ServiceContext,
    make_real_student,
    clock: FakeClock,  # type: ignore[no-untyped-def]
) -> None:
    host = make_real_student()
    room_id = room_for(host, real_ctx)
    unknown = run(handlers.board_join(real_ctx, ALICE, "alice", "r_nope", join_fields()))
    assert unknown.text == "That isn't available any more."
    run(handlers.board_join(real_ctx, host.discord_id, host.name, room_id, join_fields()))
    member = run(handlers.board_join(real_ctx, host.discord_id, host.name, room_id, join_fields()))
    assert "already in a crew" in member.text
    clock.now = at(61)
    started = run(handlers.board_join(real_ctx, CARA, "cara", room_id, join_fields()))
    assert started.text == "That plan has already started."


def test_board_join_accepting_a_stale_offer_says_so(
    real_client: TestClient,
    real_ctx: ServiceContext,
    make_real_student,  # type: ignore[no-untyped-def]
) -> None:
    room_id = room_for(make_real_student(), real_ctx)
    pending = run(handlers.board_join(real_ctx, ALICE, "alice", room_id, join_fields()))
    other = make_real_student()
    other.link(real_ctx)
    offer = other.submit(start=60, end=180)["offer"]["offer_id"]
    other.post(f"/v1/offers/{offer}/accept")  # moves the room
    assert "crew changed" in confirm(pending).text


def test_the_demo_seed_rooms_can_be_joined_from_the_board(
    real_client: TestClient, real_ctx: ServiceContext, clock: FakeClock
) -> None:
    seeded = seed.seed_demo(real_ctx)
    with real_ctx.uow_factory() as uow:
        room = next(r for r in uow.rooms.list_for_event(seeded["event_key"]) if r.size == 2)
        room_id = room.id
    fields = join_fields(earliest="00:00", latest="23:59", minimum="60")
    reply = run(handlers.board_join(real_ctx, ALICE, "alice", room_id, fields))
    assert reply.confirm is not None, reply.text


def db_count(client: TestClient, source: str) -> int:
    engine = client.app.state.crewbie.engine  # type: ignore[attr-defined]
    with engine.connect() as connection:
        return int(connection.execute(text(f"select count(*) from {source}")).scalar_one())


def test_intent_body_is_unchanged_by_this_phase() -> None:
    assert intent_body()["shared"]["budget_band"] == "low"
