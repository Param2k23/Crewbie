from crewbie.domain.budget import BudgetBand
from crewbie.domain.room import RoomStatus
from crewbie.domain.vibe import Vibe
from crewbie.matching.prescore import (
    is_candidate,
    overlap_ratio,
    post_score,
    prescore,
    rank_candidates,
)
from tests.unit.domain.helpers import at, window
from tests.unit.matching.helpers import profile, room, single

NOW = at(0)


def joiner(**kw):  # type: ignore[no-untyped-def]
    return profile(60, 180, **kw).shared


def test_fr_mat_01_only_open_or_active_unstarted_rooms_of_the_same_event() -> None:
    base = profile(60, 180)
    assert is_candidate(joiner(), single("ok", base), NOW)
    assert is_candidate(joiner(), single("active", base, status=RoomStatus.ACTIVE), NOW)
    assert not is_candidate(joiner(), single("closed", base, status=RoomStatus.CLOSED), NOW)
    assert not is_candidate(joiner(), single("other", base, event_key="ev2"), NOW)
    assert not is_candidate(joiner(), single("started", base), at(61))  # window already began
    assert is_candidate(joiner(), single("ok", base), at(59))


def test_fr_mat_02_budget_bands_two_steps_apart_are_filtered_out() -> None:
    high_room = single("high", profile(60, 180, band=BudgetBand.HIGH))
    assert not is_candidate(joiner(band=BudgetBand.LOW), high_room, NOW)
    assert is_candidate(joiner(band=BudgetBand.MID), high_room, NOW)


def test_overlap_ratio_is_overlap_over_the_joiner_window() -> None:
    assert overlap_ratio(window(0, 120), window(60, 300)) == 0.5
    assert overlap_ratio(window(0, 60), window(60, 120)) == 0.0
    assert overlap_ratio(window(0, 60), window(0, 600)) == 1.0


def test_fr_mat_03_prescore_is_overlap_plus_vibe_bonus() -> None:
    chill = single("a", profile(60, 180, vibe=Vibe.CHILL))
    social = single("b", profile(60, 180, vibe=Vibe.SOCIAL))
    assert prescore(joiner(), chill) == 1.5
    assert prescore(joiner(), social) == 1.0


def test_fr_mat_03_ranking_is_best_first_then_larger_then_older() -> None:
    far = single("far", profile(150, 270))  # overlap 30/120
    same = single("same", profile(60, 180))
    social = single("social", profile(60, 180, vibe=Vibe.SOCIAL))
    ranked = rank_candidates(joiner(), [far, social, same], NOW, 3)
    assert [r.room_id for r in ranked] == ["same", "social", "far"]

    a = single("a", profile(60, 180), created=5)
    b = single("b", profile(60, 180), created=1)
    big = room(
        "big", [single("x", profile(60, 180)).members[0], single("y", profile(60, 180)).members[0]]
    )
    assert [r.room_id for r in rank_candidates(joiner(), [a, b, big], NOW, 3)] == ["big", "b", "a"]


def test_fr_mat_03_at_most_the_requested_number_of_rooms() -> None:
    rooms = [single(f"r{i}", profile(60, 180), created=i) for i in range(6)]
    assert len(rank_candidates(joiner(), rooms, NOW, 3)) == 3


def test_post_score_rewards_duration_vibe_and_shared_interests() -> None:
    shared = profile(60, 180, interests=("chess", "anime")).shared
    chess = single("c", profile(60, 180, interests=("chess",)))
    plain = single("p", profile(60, 180, vibe=Vibe.SOCIAL))
    assert post_score(shared, chess, window(60, 180)) == 1.0 + 0.5 + 0.1
    assert post_score(shared, plain, window(60, 120)) == 0.5
