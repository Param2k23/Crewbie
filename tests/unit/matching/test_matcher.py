from datetime import timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from crewbie.agents.protocol import DelegateProfile
from crewbie.domain.budget import BudgetBand
from crewbie.domain.offer import OfferType
from crewbie.domain.vibe import Vibe
from crewbie.matching.matcher import DeterministicMatcher, MatchRequest, MatchResult
from crewbie.matching.snapshot import RoomSnapshot
from tests.unit.domain.helpers import at, window
from tests.unit.matching.helpers import member, profile, room, single


def match(
    joiner: DelegateProfile, rooms: list[RoomSnapshot], matcher: DeterministicMatcher | None = None
) -> MatchResult:
    request = MatchRequest("i1", "ev1", joiner, tuple(rooms), at(0))
    return (matcher or DeterministicMatcher()).match(request)


def test_fr_mat_07_no_rooms_gives_a_new_room_offer_with_the_joiners_window() -> None:
    result = match(profile(60, 180), [])
    assert result.offer_type is OfferType.NEW_ROOM
    assert result.proposal == window(60, 180) and result.room_id is None
    assert result.negotiations == ()


def test_as_2_compatible_room_gives_a_join_offer_with_the_room_version() -> None:
    result = match(profile(60, 180), [single("r1", profile(60, 180), version=7)])
    assert result.offer_type is OfferType.JOIN
    assert (result.room_id, result.room_version, result.proposal) == ("r1", 7, window(60, 180))
    assert result.window_changed_for_room is False


def test_as_3_extension_is_flagged_as_a_room_window_change() -> None:
    existing = single("r1", profile(60, 180, flex=(30, 240)))
    result = match(profile(150, 270, flex=(120, 300)), [existing])
    assert result.offer_type is OfferType.JOIN and result.proposal == window(120, 210)
    assert result.window_changed_for_room is True


def test_as_4_and_fr_mat_07_failed_negotiation_falls_back_to_a_new_room() -> None:
    existing = single("r1", profile(60, 180, flex=(30, 190)))
    result = match(profile(150, 270, flex=(120, 300)), [existing])
    assert result.offer_type is OfferType.NEW_ROOM and result.proposal == window(150, 270)
    assert [n.outcome for n in result.negotiations] == ["failed"]


def test_as_5_hard_filter_means_no_negotiation_with_an_incompatible_room() -> None:
    high_room = single("r1", profile(60, 180, band=BudgetBand.HIGH))
    result = match(profile(60, 180, band=BudgetBand.LOW), [high_room])
    assert result.offer_type is OfferType.NEW_ROOM and result.negotiations == ()


def test_fr_mat_05_every_member_must_agree() -> None:
    agreeable, stuck = profile(60, 180), profile(60, 180, flex=(60, 180), minimum=120)
    two = room("r1", [member("member-1", agreeable), member("member-2", stuck, joined=1)])
    # The joiner proposes 60-150 (their minimum is 90); member-2 needs 120 minutes, so they reject.
    result = match(profile(60, 150, minimum=90, flex=(60, 150)), [two])
    assert result.offer_type is OfferType.NEW_ROOM


def test_fr_mat_03_negotiates_with_at_most_three_rooms_best_first() -> None:
    rooms = [single(f"r{i}", profile(60, 180), created=i) for i in range(6)]
    result = match(profile(60, 180), rooms)
    assert [n.room_id for n in result.negotiations] == ["r0", "r1", "r2"]


def test_fr_mat_08_best_post_negotiation_score_wins() -> None:
    short = single("short", profile(60, 130, minimum=60, flex=(60, 130)))
    full = single("full", profile(60, 180, minimum=60), created=9)
    result = match(profile(60, 180, minimum=60), [short, full])
    assert result.room_id == "full"


def test_fr_mat_08_ties_go_to_the_larger_room_then_the_older_one() -> None:
    older = single("older", profile(60, 180), created=1)
    newer = single("newer", profile(60, 180), created=2)
    assert match(profile(60, 180), [newer, older]).room_id == "older"
    pair = [member("member-1", profile(60, 180)), member("member-2", profile(60, 180), joined=1)]
    big = room("big", pair, created=50)
    assert match(profile(60, 180), [older, big]).room_id == "big"


def test_fr_mat_08_shared_vibe_and_interests_break_equal_overlap() -> None:
    social = single("social", profile(60, 180, vibe=Vibe.SOCIAL))
    chill = single("chill", profile(60, 180, vibe=Vibe.CHILL, interests=("chess",)))
    result = match(profile(60, 180, vibe=Vibe.CHILL, interests=("chess",)), [social, chill])
    assert result.room_id == "chill"


def test_fr_mat_01_rooms_that_have_started_are_not_offered() -> None:
    request = MatchRequest("i1", "ev1", profile(60, 180), (single("r1", profile(60, 180)),), at(90))
    assert DeterministicMatcher().match(request).offer_type is OfferType.NEW_ROOM


def test_time_budget_stops_new_negotiations_but_still_returns_an_offer() -> None:
    ticks = iter(range(0, 1000, 100))
    matcher = DeterministicMatcher(time_budget_seconds=250, monotonic=lambda: float(next(ticks)))
    rooms = [single(f"r{i}", profile(60, 180), created=i) for i in range(3)]
    result = match(profile(60, 180), rooms, matcher)
    assert len(result.negotiations) == 2  # the third was not started
    assert result.offer_type is OfferType.JOIN


@given(st.integers(1, 4), st.integers(1, 4), st.integers(0, 9))
@settings(max_examples=25)
def test_p_4_work_per_intent_is_bounded(
    max_candidates: int, max_rounds: int, room_count: int
) -> None:
    matcher = DeterministicMatcher(max_candidates=max_candidates, max_rounds=max_rounds)
    rooms = [
        single(f"r{i}", profile(60, 180, flex=(30, 190)), created=i) for i in range(room_count)
    ]
    result = match(profile(150, 270, flex=(120, 300)), rooms, matcher)
    assert len(result.negotiations) <= max_candidates
    assert all(n.rounds <= max_rounds for n in result.negotiations)


off_grid = st.builds(timedelta, seconds=st.integers(1, 59))


@given(st.integers(-60, 60), st.integers(0, 90), off_grid, off_grid)
@settings(max_examples=40)
def test_p_2_recorded_windows_never_equal_a_private_flex_bound(
    shift: int, extra: int, lead: timedelta, tail: timedelta
) -> None:
    member_profile = profile(60, 180, flex=(30, 190 + extra))
    flex = member_profile.flex
    private = DelegateProfile(member_profile.shared, type(flex)(flex.start + lead, flex.end - tail))
    joiner = profile(150 + shift, 270 + shift, flex=(120 + shift, 300 + shift))
    result = match(joiner, [single("r1", private)])
    bounds = {private.flex.start, private.flex.end}
    for negotiation in result.negotiations:
        windows = [s.proposal for s in negotiation.steps if s.proposal] + [negotiation.opening]
        for w in windows:
            if w is not None:
                assert w.start not in bounds and w.end not in bounds
    if result.offer_type is OfferType.JOIN:
        assert result.proposal.start not in bounds and result.proposal.end not in bounds
