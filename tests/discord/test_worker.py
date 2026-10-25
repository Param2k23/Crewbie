"""Outbox worker against the fake gateway: AS-2, AS-3, AS-8 and the retry rules."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from crewbie.discord_bot.worker import OutboxWorker
from crewbie.persistence.tables import OutboxRow
from crewbie.services import lifecycle
from crewbie.services.context import ServiceContext
from tests.discord.fakes import FakeGateway
from tests.support import FakeClock, Student, at

Drain = Callable[[OutboxWorker], int]


def two_person_room(
    ctx: ServiceContext, make: Callable[[], Student], **joiner_window: int
) -> tuple[Student, Student, str]:
    first, second = make(), make()
    start = first.submit(start=60, end=180, flex_latest=at(240))
    first.link(ctx)
    room_id = first.post(f"/v1/offers/{start['offer']['offer_id']}/accept").json()["room"][
        "room_id"
    ]
    window = {"start": 60, "end": 180, **joiner_window}
    offer = second.submit(**window)["offer"]
    assert offer["type"] == "join"
    second.link(ctx)
    assert second.post(f"/v1/offers/{offer['offer_id']}/accept").status_code == 200
    return first, second, room_id


def db(client: TestClient, query: str) -> list[tuple[Any, ...]]:
    engine = client.app.state.crewbie.engine  # type: ignore[attr-defined]
    with engine.connect() as connection:
        return [tuple(r) for r in connection.execute(text(query))]


def test_as_2_second_student_gets_a_thread_icebreaker_dms_and_a_board_card(
    real_client: TestClient, real_ctx: ServiceContext, make_real_student,  # type: ignore[no-untyped-def]
    worker: OutboxWorker, gateway: FakeGateway, drain: Drain,
) -> None:  # fmt: skip
    first, second, room_id = two_person_room(real_ctx, make_real_student)
    drain(worker)

    # FR-BOT-02: one private thread named "<title> · <date>", holding both students.
    ((thread_id, name),) = gateway.threads.items()
    assert name == "Board game night · Fri Nov 6"
    assert gateway.members[thread_id] == {first.discord_id, second.discord_id}

    # FR-BOT-03: exactly one icebreaker, under 900 characters, from public fields only.
    posts = [text for t, text in gateway.posts if t == thread_id]
    assert len(posts) == 1 and len(posts[0]) < 900
    assert "Board game night" in posts[0] and "Fri Nov 6" in posts[0]
    assert "9:00 to 11:00 am" in posts[0] and "Hayden Library" in posts[0]
    assert "/crew meetpoint" in posts[0]

    # FR-BOT-04: both are DMed the thread link.
    link = f"https://discord.com/channels/111111111111111111/{thread_id}"
    assert sorted(user for user, _ in gateway.dms) == sorted([first.discord_id, second.discord_id])
    assert all(link in content for _, content in gateway.dms)

    # The thread is recorded, and each student's Cubbie hears about it.
    assert db(real_client, f"select discord_thread_id from rooms where id = '{room_id}'") == [
        (thread_id,)
    ]
    for student in (first, second):
        ready = [u for u in student.updates() if u["kind"] == "room_active"]
        assert len(ready) == 1 and ready[0]["thread_url"] == link
    assert first.get(f"/v1/intents/{first.updates()[0]['intent_id']}").json()["thread_url"] == link

    # FR-BOT-05: one board card with the room's public fields, remembered on the room.
    ((message_id, card),) = gateway.cards.items()
    assert (card.size, card.vibe, card.budget) == (2, "chill", "low")
    assert db(real_client, f"select board_message_id from rooms where id = '{room_id}'") == [
        (message_id,)
    ]
    assert db(real_client, "select count(*) from outbox where state != 'done'") == [(0,)]


def test_fr_bot_01_replaying_jobs_creates_nothing_twice(
    real_client: TestClient, real_ctx: ServiceContext, make_real_student,  # type: ignore[no-untyped-def]
    worker: OutboxWorker, gateway: FakeGateway, drain: Drain,
) -> None:  # fmt: skip
    _, _, room_id = two_person_room(real_ctx, make_real_student)
    drain(worker)
    with real_ctx.uow_factory() as uow:
        uow.outbox.enqueue(
            "again1", "create_thread", {"room_id": room_id}, "dup:1", real_ctx.clock()
        )
        uow.outbox.enqueue(
            "again2", "upsert_board_card", {"room_id": room_id}, "dup:2", real_ctx.clock()
        )
        uow.commit()
    drain(worker)
    assert len(gateway.threads) == 1 and len(gateway.cards) == 1
    assert gateway.card_history[-1][1] is not None  # the second call edited the existing card


def test_nfr_rel_01_failures_are_retried_with_backoff_and_succeed(
    real_client: TestClient, real_ctx: ServiceContext, make_real_student,  # type: ignore[no-untyped-def]
    worker: OutboxWorker, gateway: FakeGateway, drain: Drain,
) -> None:  # fmt: skip
    gateway.failures["create_thread"] = 2
    two_person_room(real_ctx, make_real_student)
    drain(worker, rounds=20)
    assert len(gateway.threads) == 1
    assert gateway.calls.count("create_thread") == 3
    assert db(real_client, "select count(*) from outbox where state != 'done'") == [(0,)]


def test_nfr_rel_01_a_job_that_keeps_failing_is_marked_failed_and_listed_for_the_operator(
    real_client: TestClient, real_ctx: ServiceContext, make_real_student,  # type: ignore[no-untyped-def]
    worker: OutboxWorker, gateway: FakeGateway, drain: Drain,
) -> None:  # fmt: skip
    gateway.failures["upsert_board_card"] = 99
    first = make_real_student()
    offer = first.submit()["offer"]["offer_id"]
    first.link(real_ctx)
    first.post(f"/v1/offers/{offer}/accept")
    drain(worker, rounds=30)
    assert gateway.calls.count("upsert_board_card") == 6  # first try plus five retries
    admin = real_client.get(
        "/v1/admin/outbox", headers={"X-Admin-Token": "test-admin-token-" + "x" * 24}
    ).json()
    assert [job["kind"] for job in admin["jobs"]] == ["upsert_board_card"]
    assert "ConnectionError" in admin["jobs"][0]["last_error"]


def test_jobs_that_run_before_the_thread_exists_wait_and_succeed_later(
    real_client: TestClient, real_ctx: ServiceContext, make_real_student,  # type: ignore[no-untyped-def]
    worker: OutboxWorker, gateway: FakeGateway, clock: FakeClock,
) -> None:  # fmt: skip
    _, _, room_id = two_person_room(real_ctx, make_real_student)
    with real_ctx.uow_factory() as uow:  # push create_thread behind the jobs that need it
        for row in uow.outbox.due(clock(), 50):
            if row.kind == "create_thread":
                stored = uow.outbox._session.get(OutboxRow, row.id)
                assert stored is not None
                stored.next_attempt_at = clock() + timedelta(seconds=5)
        uow.commit()
    asyncio.run(worker.process_once())
    assert gateway.threads == {} and gateway.posts == [] and gateway.dms == []
    pending = db(real_client, "select kind, attempts from outbox where state = 'pending'")
    assert ("post_message", 1) in pending and ("add_member", 1) in pending
    for _ in range(8):
        clock.advance(seconds=20)
        asyncio.run(worker.process_once())
    assert len(gateway.threads) == 1 and len(gateway.posts) == 1 and len(gateway.dms) == 2
    assert room_id


def test_fr_bot_04_closed_dms_do_not_fail_the_job_and_cubbie_still_gets_the_link(
    real_client: TestClient, real_ctx: ServiceContext, make_real_student,  # type: ignore[no-untyped-def]
    worker: OutboxWorker, gateway: FakeGateway, drain: Drain,
) -> None:  # fmt: skip
    first, second = make_real_student(), make_real_student()
    offer = first.submit(start=60, end=180)["offer"]["offer_id"]
    first.link(real_ctx)
    first.post(f"/v1/offers/{offer}/accept")
    joined = second.submit(start=60, end=180)["offer"]["offer_id"]
    second.link(real_ctx)
    gateway.dm_closed.add(second.discord_id)
    second.post(f"/v1/offers/{joined}/accept")
    drain(worker)
    assert [user for user, _ in gateway.dms] == [first.discord_id]
    assert db(real_client, "select count(*) from outbox where state = 'failed'") == [(0,)]
    assert any(u["kind"] == "room_active" and u["thread_url"] for u in second.updates())


def test_as_3_a_window_change_is_announced_in_the_thread(
    real_client: TestClient, real_ctx: ServiceContext, make_real_student,  # type: ignore[no-untyped-def]
    worker: OutboxWorker, gateway: FakeGateway, drain: Drain,
) -> None:  # fmt: skip
    two_person_room(
        real_ctx, make_real_student, start=150, end=270, flex_earliest=at(120), flex_latest=at(300)
    )
    drain(worker)
    notices = [text for _, text in gateway.posts if text.startswith("Plan moved to")]
    assert notices == ["Plan moved to 10:00 to 11:30 am."]


def test_as_8_a_member_leaving_a_three_person_room_is_removed_and_announced(
    real_client: TestClient, real_ctx: ServiceContext, make_real_student,  # type: ignore[no-untyped-def]
    worker: OutboxWorker, gateway: FakeGateway, drain: Drain,
) -> None:  # fmt: skip
    first, second, room_id = two_person_room(real_ctx, make_real_student)
    third = make_real_student()
    offer = third.submit(start=60, end=180)["offer"]["offer_id"]
    third.link(real_ctx)
    third.post(f"/v1/offers/{offer}/accept")
    drain(worker)
    (thread_id,) = gateway.threads
    assert gateway.members[thread_id] == {first.discord_id, second.discord_id, third.discord_id}
    welcome = [text for _, text in gateway.posts if "joined" in text]
    assert welcome == [f"{third.name} joined. Plan: 9:00 to 11:00 am."]

    leaving = second.updates()[0]["intent_id"]
    second.post(f"/v1/intents/{leaving}/withdraw")
    drain(worker)
    assert gateway.members[thread_id] == {first.discord_id, third.discord_id}
    assert gateway.posts[-1][1] == "member-2 left. Plan: 9:00 to 11:00 am."
    assert db(real_client, f"select size from rooms where id = '{room_id}'") == [(2,)]


def test_fr_bot_05_the_board_card_follows_the_room_and_disappears_when_it_closes(
    real_client: TestClient, real_ctx: ServiceContext, make_real_student,  # type: ignore[no-untyped-def]
    worker: OutboxWorker, gateway: FakeGateway, drain: Drain,
) -> None:  # fmt: skip
    first = make_real_student()
    offer = first.submit(start=60, end=180)["offer"]["offer_id"]
    first.link(real_ctx)
    room_id = first.post(f"/v1/offers/{offer}/accept").json()["room"]["room_id"]
    drain(worker)
    ((message_id, card),) = gateway.cards.items()
    assert card.size == 1

    second = make_real_student()
    joined = second.submit(start=60, end=180)["offer"]["offer_id"]
    second.link(real_ctx)
    second.post(f"/v1/offers/{joined}/accept")
    drain(worker)
    assert list(gateway.cards) == [message_id] and gateway.cards[message_id].size == 2

    real_client.post(
        f"/v1/admin/rooms/{room_id}/close",
        headers={"X-Admin-Token": "test-admin-token-" + "x" * 24},
    )
    drain(worker)
    assert gateway.cards == {}
    assert db(real_client, f"select board_message_id from rooms where id = '{room_id}'") == [
        (None,)
    ]
    assert len(gateway.archived) == 1


def test_fr_rom_03_rooms_close_then_archive_after_the_window_ends(
    real_client: TestClient, real_ctx: ServiceContext, make_real_student,  # type: ignore[no-untyped-def]
    worker: OutboxWorker, gateway: FakeGateway, drain: Drain, clock: FakeClock,
) -> None:  # fmt: skip
    first, _, room_id = two_person_room(real_ctx, make_real_student)
    drain(worker)
    assert lifecycle.advance_rooms(real_ctx) == 0
    clock.now = at(180 + 120)  # window end + 2 h
    assert lifecycle.advance_rooms(real_ctx) == 1
    assert db(real_client, f"select status from rooms where id = '{room_id}'") == [("closed",)]
    assert first.updates()[-1]["kind"] == "room_closed"
    drain(worker)
    assert gateway.cards == {} and gateway.archived == []
    clock.now = at(180 + 24 * 60)  # window end + 24 h
    assert lifecycle.advance_rooms(real_ctx) == 1
    drain(worker)
    assert len(gateway.archived) == 1
    assert lifecycle.advance_rooms(real_ctx) == 0


def test_synthetic_members_get_a_board_card_but_are_never_added_or_messaged(
    real_client: TestClient, real_ctx: ServiceContext, worker: OutboxWorker,
    gateway: FakeGateway, drain: Drain,
) -> None:  # fmt: skip
    real_client.post("/v1/admin/seed", headers={"X-Admin-Token": "test-admin-token-" + "x" * 24})
    with real_ctx.uow_factory() as uow:
        for room in uow.rooms.list_all():
            uow.outbox.enqueue(
                f"j{room.id}",
                "upsert_board_card",
                {"room_id": room.id},
                f"b:{room.id}",
                real_ctx.clock(),
            )
        uow.commit()
    drain(worker)
    assert sorted(card.size for card in gateway.cards.values()) == [1, 2]
    assert gateway.members == {} and gateway.dms == [] and gateway.posts == []


def test_unknown_job_kinds_fail_visibly_instead_of_disappearing(
    real_client: TestClient, real_ctx: ServiceContext, worker: OutboxWorker, drain: Drain
) -> None:
    with real_ctx.uow_factory() as uow:
        uow.outbox.enqueue("x1", "make_coffee", {}, "k", real_ctx.clock())
        uow.commit()
    drain(worker, rounds=30)
    assert db(real_client, "select state, last_error from outbox") == [
        ("failed", "ValueError: unknown job kind: make_coffee")
    ]


ADMIN = {"X-Admin-Token": "test-admin-token-" + "x" * 24}


def test_a_failed_board_card_can_be_requeued_after_the_cause_is_fixed(
    real_client: TestClient, real_ctx: ServiceContext, make_real_student,  # type: ignore[no-untyped-def]
    worker: OutboxWorker, gateway: FakeGateway, drain: Drain,
) -> None:  # fmt: skip
    """A missing-permission failure used to leave the card out for good."""
    gateway.failures["upsert_board_card"] = 99
    first = make_real_student()
    first.link(real_ctx)
    offer = first.submit()["offer"]["offer_id"]
    first.post(f"/v1/offers/{offer}/accept")
    drain(worker, rounds=30)
    assert gateway.cards == {}

    gateway.failures.clear()  # the owner fixed the channel permission
    assert real_client.post("/v1/admin/outbox/retry", headers=ADMIN).json() == {"requeued": 1}
    drain(worker)
    assert len(gateway.cards) == 1
    assert real_client.post("/v1/admin/outbox/retry", headers=ADMIN).json() == {"requeued": 0}
    assert real_client.post("/v1/admin/outbox/retry").status_code == 401


def test_fr_bot_05_startup_reconcile_queues_cards_only_for_rooms_that_lack_one(
    real_client: TestClient, real_ctx: ServiceContext, make_real_student,  # type: ignore[no-untyped-def]
    worker: OutboxWorker, gateway: FakeGateway, drain: Drain,
) -> None:  # fmt: skip
    from crewbie.services import outbox_jobs

    first = make_real_student()
    first.link(real_ctx)
    offer = first.submit()["offer"]["offer_id"]
    first.post(f"/v1/offers/{offer}/accept")
    gateway.failures["upsert_board_card"] = 99
    drain(worker, rounds=30)
    gateway.failures.clear()
    assert outbox_jobs.reconcile_board(real_ctx) == 1
    drain(worker)
    assert len(gateway.cards) == 1
    assert outbox_jobs.reconcile_board(real_ctx) == 0  # the room now has its card


def test_the_demo_seed_queues_board_cards_for_both_rooms(
    real_client: TestClient, real_ctx: ServiceContext, worker: OutboxWorker,
    gateway: FakeGateway, drain: Drain,
) -> None:  # fmt: skip
    real_client.post("/v1/admin/seed", headers=ADMIN)
    drain(worker)
    assert sorted(card.size for card in gateway.cards.values()) == [1, 2]
