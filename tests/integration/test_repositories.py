from collections.abc import Callable

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from crewbie.domain.budget import BudgetBand
from crewbie.domain.intent import IntentState, PrivateEnvelope, SharedIntent
from crewbie.domain.offer import OfferState, OfferType
from crewbie.domain.room import RoomStatus, derive_room_state
from crewbie.domain.vibe import Vibe
from crewbie.persistence.unit_of_work import UnitOfWork
from tests.unit.domain.helpers import at, window

SENTINEL_CAP = 913.0
Factory = Callable[[], UnitOfWork]


def shared(event_key: str = "ev1", start: int = 60, end: int = 180, **kw: object) -> SharedIntent:
    fields: dict[str, object] = {
        "event_key": event_key,
        "window": window(start, end),
        "activity_min_minutes": 90,
        "budget_band": BudgetBand.MID,
        "vibe": Vibe.CHILL,
        "interests": ("chess",),
    }
    fields.update(kw)
    return SharedIntent(**fields)  # type: ignore[arg-type]


ENVELOPE = PrivateEnvelope(at(-30), at(400), SENTINEL_CAP)


def seed_event(uow: UnitOfWork, key: str = "ev1") -> None:
    uow.events.ensure(
        key,
        source_url="https://x.test/e",
        title="Game night",
        location_label="Hayden",
        date="2026-11-06",
        start_time="18:00",
        end_time=None,
    )


def seed_install(uow: UnitOfWork, install_id: str = "inst1") -> None:
    uow.installs.add(install_id, f"hash-{install_id}", "cubbie")


def test_installs_lookup_by_token_hash_and_unique_hash(uow_factory: Factory) -> None:
    with uow_factory() as uow:
        seed_install(uow)
        uow.commit()
    with uow_factory() as uow:
        found = uow.installs.get_by_token_hash("hash-inst1")
        assert found is not None and found.id == "inst1"
        assert uow.installs.get_by_token_hash("nope") is None
        with pytest.raises(IntegrityError):
            uow.installs.add("dup", "hash-inst1", "cubbie")


def test_discord_installs_may_omit_token(uow_factory: Factory) -> None:
    with uow_factory() as uow:
        uow.installs.add("d1", None, "discord")
        uow.installs.add("d2", None, "discord")
        uow.commit()


def test_fr_evt_02_event_fields_are_not_overwritten(uow_factory: Factory) -> None:
    with uow_factory() as uow:
        seed_event(uow)
        again = uow.events.ensure(
            "ev1", source_url="https://other", title="Changed", location_label=None,
            date="2026-11-07", start_time=None, end_time=None,
        )  # fmt: skip
        uow.commit()
        assert again.title == "Game night"
    with uow_factory() as uow:
        event = uow.events.get("ev1")
        assert event is not None and event.title == "Game night"


def test_intent_round_trip_and_envelope_decrypts_only_through_repository(
    uow_factory: Factory,
) -> None:
    with uow_factory() as uow:
        seed_install(uow)
        seed_event(uow)
        uow.intents.add("int1", "inst1", shared(), ENVELOPE)
        uow.commit()
    with uow_factory() as uow:
        row = uow.intents.get("int1")
        assert row is not None
        assert (row.budget_band, row.vibe, row.interests, row.state) == (
            "mid", "chill", ["chess"], "matching",
        )  # fmt: skip
        assert row.window_start == at(60)
        envelope = uow.intents.load_envelope("int1")
        assert envelope is not None and envelope.budget_cap_usd == SENTINEL_CAP
        assert uow.intents.load_envelope("missing") is None


def test_nfr_prv_01_envelope_values_only_exist_encrypted(
    uow_factory: Factory, engine: Engine
) -> None:
    with uow_factory() as uow:
        seed_install(uow)
        seed_event(uow)
        uow.intents.add("int1", "inst1", shared(), ENVELOPE)
        uow.commit()
    with engine.connect() as connection:
        tables = [
            r[0]
            for r in connection.execute(text("select name from sqlite_master where type='table'"))
        ]
        for table in tables:
            if table == "envelopes":
                continue
            for row in connection.execute(text(f'select * from "{table}"')):
                assert "913" not in repr(row) and "flex" not in repr(row)
        raw = connection.execute(text("select ciphertext from envelopes")).scalar_one()
    assert b"913" not in raw and b"flex" not in raw


def test_fr_int_03_one_live_intent_per_install_and_event(uow_factory: Factory) -> None:
    with uow_factory() as uow:
        seed_install(uow)
        seed_event(uow)
        uow.intents.add("int1", "inst1", shared(), ENVELOPE)
        uow.commit()
    with uow_factory() as uow:
        live = uow.intents.get_live("inst1", "ev1")
        assert live is not None and live.id == "int1"
        with pytest.raises(IntegrityError):
            uow.intents.add("int2", "inst1", shared(), ENVELOPE)


def test_fr_int_03_declined_intent_does_not_block_resubmission(uow_factory: Factory) -> None:
    with uow_factory() as uow:
        seed_install(uow)
        seed_event(uow)
        uow.intents.add("int1", "inst1", shared(), ENVELOPE)
        uow.intents.set_state("int1", IntentState.DECLINED)
        assert uow.intents.get_live("inst1", "ev1") is None
        uow.intents.add("int2", "inst1", shared(), ENVELOPE)
        uow.commit()
    with uow_factory() as uow:
        live = uow.intents.get_live("inst1", "ev1")
        assert live is not None and live.id == "int2"


def test_nfr_prv_03_deleting_install_removes_intents_envelopes_updates(
    uow_factory: Factory, engine: Engine
) -> None:
    with uow_factory() as uow:
        seed_install(uow)
        seed_event(uow)
        uow.intents.add("int1", "inst1", shared(), ENVELOPE)
        uow.updates.append("inst1", "joined", {})
        uow.commit()
    with uow_factory() as uow:
        uow.installs.delete("inst1")
        uow.commit()
    with engine.connect() as connection:
        for table in ("installs", "intents", "envelopes", "updates"):
            assert connection.execute(text(f"select count(*) from {table}")).scalar_one() == 0


def test_set_state_on_unknown_ids_is_a_no_op(uow_factory: Factory) -> None:
    with uow_factory() as uow:
        uow.intents.set_state("ghost", IntentState.EXPIRED)
        uow.offers.set_state("ghost", OfferState.EXPIRED)
        uow.rooms.mark_left("ghost", at(0))
        uow.rooms.set_effective_window("ghost", window(0, 10))
        uow.outbox.mark_done("ghost")
        assert uow.outbox.mark_failed_attempt("ghost", "x", at(0)).value == "failed"


def make_room(uow: UnitOfWork, count: int = 2) -> None:
    seed_event(uow)
    uow.rooms.create("room1", "ev1")
    for i in range(1, count + 1):
        seed_install(uow, f"inst{i}")
        uow.intents.add(
            f"int{i}",
            f"inst{i}",
            shared(start=60 * i, end=60 * i + 180, vibe=Vibe.SOCIAL),
            ENVELOPE,
        )
        uow.rooms.add_member(f"m{i}", "room1", f"int{i}", window(60 * i, 60 * i + 180), at(i))


def test_fr_rom_01_room_state_is_derived_from_memberships_and_version_bumps(
    uow_factory: Factory,
) -> None:
    with uow_factory() as uow:
        make_room(uow)
        members = uow.rooms.member_states("room1")
        assert [m.alias for m in members] == ["member-1", "member-2"]
        room = uow.rooms.apply_state("room1", derive_room_state(members))
        uow.commit()
        assert (room.size, room.status, room.version) == (2, "active", 2)
        assert room.window_start == at(120) and room.window_end == at(240)
        assert room.vibe == "social" and room.budget_band == "mid"
        assert room.top_interests == ["chess"]


def test_srs_5_3_leave_removes_member_and_aliases_are_not_reused(uow_factory: Factory) -> None:
    with uow_factory() as uow:
        make_room(uow, 2)
        uow.rooms.mark_left("int1", at(10))
        uow.rooms.mark_left("int1", at(99))
        seed_install(uow, "inst3")
        uow.intents.add("int3", "inst3", shared(), ENVELOPE)
        added = uow.rooms.add_member("m3", "room1", "int3", window(0, 60), at(11))
        assert added.alias == "member-3"
        remaining = [m.alias for m in uow.rooms.member_states("room1")]
        assert remaining == ["member-2", "member-3"]
        state = derive_room_state([])
        room = uow.rooms.apply_state("room1", state, bump_version=False)
        assert (room.status, room.version) == (RoomStatus.CLOSED.value, 1)
        assert room.window_start is None and room.vibe is None and room.budget_band is None


def test_effective_window_update_is_reflected_in_member_states(uow_factory: Factory) -> None:
    with uow_factory() as uow:
        make_room(uow, 1)
        uow.rooms.set_effective_window("int1", window(0, 400))
        assert uow.rooms.member_states("room1")[0].effective_window == window(0, 400)


def test_fr_mat_01_list_rooms_for_event_filters_by_status(uow_factory: Factory) -> None:
    with uow_factory() as uow:
        make_room(uow, 1)
        uow.rooms.create("room2", "ev1")
        uow.rooms.apply_state("room2", derive_room_state([]))
        assert [r.id for r in uow.rooms.list_for_event("ev1")] == ["room1"]
        assert {r.id for r in uow.rooms.list_for_event("ev1", (RoomStatus.CLOSED,))} == {"room2"}
        assert uow.rooms.list_for_event("other") == []


def test_apply_state_unknown_room_raises(uow_factory: Factory) -> None:
    with uow_factory() as uow, pytest.raises(LookupError):
        uow.rooms.apply_state("ghost", derive_room_state([]))


def test_fr_ofr_06_open_expired_offers(uow_factory: Factory) -> None:
    with uow_factory() as uow:
        seed_install(uow)
        seed_event(uow)
        uow.intents.add("int1", "inst1", shared(), ENVELOPE)
        uow.rooms.create("room1", "ev1")
        uow.offers.add("o1", "int1", OfferType.NEW_ROOM, at(15))
        uow.offers.add(
            "o2", "int1", OfferType.JOIN, at(30), room_id="room1", room_version=1,
            proposal=window(60, 120),
        )  # fmt: skip
        uow.offers.set_state("o2", OfferState.ACCEPTED)
        assert [o.id for o in uow.offers.open_expired(at(20))] == ["o1"]
        assert uow.offers.open_expired(at(14)) == []
        joined = uow.offers.get("o2")
        assert joined is not None
        assert (joined.room_version, joined.proposal_start, joined.proposal_end) == (
            1, at(60), at(120),
        )  # fmt: skip
        assert uow.offers.get("ghost") is None


def test_fr_upd_02_updates_are_returned_after_cursor_in_order(uow_factory: Factory) -> None:
    with uow_factory() as uow:
        seed_install(uow, "a")
        seed_install(uow, "b")
        first = uow.updates.append("a", "offer_ready", {"offer_id": "o1"})
        second = uow.updates.append("a", "joined", {})
        uow.updates.append("b", "joined", {})
        uow.commit()
        assert [u.kind for u in uow.updates.after("a", 0)] == ["offer_ready", "joined"]
        assert [u.seq for u in uow.updates.after("a", first)] == [second]
        assert uow.updates.after("a", second) == []
        assert len(uow.updates.after("a", 0, limit=1)) == 1


def test_uow_rolls_back_without_commit_and_on_error(uow_factory: Factory) -> None:
    with uow_factory() as uow:
        seed_install(uow)
    with uow_factory() as uow:
        assert uow.installs.get("inst1") is None
    with pytest.raises(RuntimeError), uow_factory() as uow:
        seed_install(uow)
        uow.commit()
        seed_install(uow, "inst2")
        raise RuntimeError
    with uow_factory() as uow:
        assert uow.installs.get("inst1") is not None
        assert uow.installs.get("inst2") is None


def test_uow_explicit_rollback(uow_factory: Factory) -> None:
    with uow_factory() as uow:
        seed_install(uow)
        uow.rollback()
        assert uow.installs.get("inst1") is None
