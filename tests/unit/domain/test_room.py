from datetime import timedelta

from hypothesis import given
from hypothesis import strategies as st

from crewbie.domain.budget import BudgetBand
from crewbie.domain.room import (
    MemberState,
    RoomStatus,
    derive_room_state,
    extend_effective_window,
    lifecycle_status,
)
from crewbie.domain.vibe import Vibe

from .helpers import at, member, window


def test_fr_rom_01_empty_room_is_closed() -> None:
    state = derive_room_state([])
    assert (state.size, state.status, state.window, state.vibe) == (
        0,
        RoomStatus.CLOSED,
        None,
        None,
    )


def test_fr_rom_02_status_follows_size() -> None:
    assert derive_room_state([member()]).status is RoomStatus.OPEN
    assert derive_room_state([member(), member("member-2")]).status is RoomStatus.ACTIVE


def test_srs_5_3_window_is_intersection_of_effective_windows() -> None:
    state = derive_room_state([member(start=0, end=120), member("member-2", start=60, end=180)])
    assert state.window == window(60, 120)


def test_srs_5_3_disjoint_windows_give_no_window() -> None:
    assert derive_room_state([member(end=60), member("member-2", start=90, end=150)]).window is None


def test_as_3_accepted_proposal_extends_effective_window() -> None:
    existing = member(start=0, end=90)
    joiner = member("member-2", start=60, end=150)
    proposal = window(30, 150)
    extended = [
        MemberState(
            m.alias,
            extend_effective_window(m.effective_window, proposal),
            m.budget_band,
            m.vibe,
            m.interests,
            m.joined_at,
        )
        for m in (existing, joiner)
    ]
    assert derive_room_state(extended).window == window(30, 150)


def test_srs_5_3_leave_can_widen_window() -> None:
    wide, narrow = member(start=0, end=240), member("member-2", start=90, end=120)
    assert derive_room_state([wide, narrow]).window == window(90, 120)
    assert derive_room_state([wide]).window == window(0, 240)


def test_srs_5_3_budget_is_most_constrained_band() -> None:
    state = derive_room_state(
        [member(band=BudgetBand.HIGH), member("member-2", band=BudgetBand.MID)]
    )
    assert state.budget_band is BudgetBand.MID


def test_srs_5_3_vibe_majority_and_tie_goes_to_earliest_member() -> None:
    majority = derive_room_state(
        [member(vibe=Vibe.ACTIVE), member("m2", vibe=Vibe.SOCIAL), member("m3", vibe=Vibe.SOCIAL)]
    )
    assert majority.vibe is Vibe.SOCIAL
    tie = derive_room_state(
        [
            member("m1", vibe=Vibe.ACTIVE, joined=5),
            member("m2", vibe=Vibe.SOCIAL, joined=1),
        ]
    )
    assert tie.vibe is Vibe.SOCIAL


def test_srs_5_3_top_interests_by_frequency_then_alphabetical_max_three() -> None:
    state = derive_room_state(
        [
            member("m1", interests=("chess", "anime", "hiking")),
            member("m2", interests=("hiking", "chess")),
            member("m3", interests=("zines", "anime")),
        ]
    )
    assert state.top_interests == ("anime", "chess", "hiking")


def test_lifecycle_closes_two_hours_and_archives_24_hours_after_window_end() -> None:
    end = at(120)
    assert lifecycle_status(RoomStatus.ACTIVE, RoomStatus.ACTIVE, end, end) is RoomStatus.ACTIVE
    just_before = end + timedelta(hours=2) - timedelta(seconds=1)
    assert lifecycle_status(RoomStatus.ACTIVE, RoomStatus.ACTIVE, end, just_before) is (
        RoomStatus.ACTIVE
    )
    closed = end + timedelta(hours=2)
    assert lifecycle_status(RoomStatus.ACTIVE, RoomStatus.ACTIVE, end, closed) is RoomStatus.CLOSED
    archived = end + timedelta(hours=24)
    assert lifecycle_status(RoomStatus.ACTIVE, RoomStatus.CLOSED, end, archived) is (
        RoomStatus.ARCHIVED
    )


def test_lifecycle_closed_and_archived_are_terminal_and_empty_rooms_close() -> None:
    assert lifecycle_status(RoomStatus.OPEN, RoomStatus.CLOSED, at(500), at(0)) is RoomStatus.CLOSED
    assert lifecycle_status(RoomStatus.CLOSED, RoomStatus.ACTIVE, None, at(0)) is RoomStatus.CLOSED
    assert lifecycle_status(RoomStatus.OPEN, RoomStatus.ARCHIVED, None, at(0)) is (
        RoomStatus.ARCHIVED
    )
    assert lifecycle_status(RoomStatus.OPEN, RoomStatus.OPEN, None, at(0)) is RoomStatus.OPEN


members = st.builds(
    lambda i, start, length, band, vibe, interests, joined: member(
        f"member-{i}", start, start + length, BudgetBand(band), Vibe(vibe), tuple(interests), joined
    ),
    st.integers(1, 9),
    st.integers(-60, 60),
    st.integers(60, 300),
    st.integers(0, 2),
    st.sampled_from(["chill", "social", "active"]),
    st.lists(st.sampled_from(["a", "b", "c", "d", "e"]), unique=True, max_size=3),
    st.integers(0, 50),
)


@given(st.lists(members, min_size=1, max_size=6, unique_by=lambda m: m.alias))
def test_property_derivation_ignores_member_order(items: list[MemberState]) -> None:
    assert derive_room_state(items) == derive_room_state(list(reversed(items)))


@given(st.lists(members, min_size=1, max_size=6))
def test_property_room_fields_are_consistent_with_members(items: list[MemberState]) -> None:
    state = derive_room_state(items)
    assert state.size == len(items)
    assert len(state.top_interests) <= 3
    assert state.budget_band == min(m.budget_band for m in items)
    assert state.vibe in {m.vibe for m in items}
    if state.window:
        assert all(m.effective_window.contains(state.window) for m in items)
    else:
        assert max(m.effective_window.start for m in items) >= min(
            m.effective_window.end for m in items
        )
