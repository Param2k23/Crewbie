from hypothesis import given, settings
from hypothesis import strategies as st

from crewbie.agents.delegate import DelegatePolicy
from crewbie.agents.host import HostPolicy
from crewbie.agents.protocol import DelegateProfile, Proposal, Reply, Verdict
from crewbie.domain.budget import BudgetBand
from crewbie.matching.negotiation import run_negotiation
from tests.unit.domain.helpers import window
from tests.unit.matching.helpers import profile

LOW = BudgetBand.LOW


def negotiate(joiner_profile: DelegateProfile, members: list[DelegateProfile], rounds: int = 3):  # type: ignore[no-untyped-def]
    joiner = DelegatePolicy(joiner_profile)
    host = HostPolicy([(f"member-{i}", DelegatePolicy(p)) for i, p in enumerate(members, 1)], LOW)
    room_window = members[0].shared.window
    opening = joiner.initial_proposal("r1", room_window, host.required_minutes, LOW)
    return run_negotiation(
        room_id="r1", room_band=LOW, joiner=joiner, joiner_ref=f"member-{len(members) + 1}",
        host=host, opening=opening, max_rounds=rounds,
    )  # fmt: skip


def test_agreement_in_round_one_when_the_overlap_works_for_everyone() -> None:
    result = negotiate(profile(60, 180), [profile(60, 180)])
    assert (result.outcome, result.rounds, result.agreed) == ("agreed", 1, window(60, 180))
    assert [(s.actor_kind, s.verdict) for s in result.steps][-1] == ("host", Verdict.ACCEPT)


def test_as_3_a_short_overlap_is_extended_when_existing_flex_allows() -> None:
    member = profile(60, 180, flex=(30, 240))
    joiner = profile(150, 270, flex=(120, 300))
    result = negotiate(joiner, [member])
    assert result.outcome == "agreed" and result.agreed == window(120, 210)
    assert result.agreed is not None and result.agreed.duration.total_seconds() >= 90 * 60


def test_as_4_no_agreement_when_one_members_flex_forbids_the_extension() -> None:
    member = profile(60, 180, flex=(30, 190))
    joiner = profile(150, 270, flex=(120, 300))
    result = negotiate(joiner, [member])
    assert result.outcome == "failed" and result.agreed is None
    assert result.failure_code == "rounds_exhausted" and result.rounds == 3


def test_fr_mat_05_a_counter_the_joiner_accepts_is_confirmed_by_the_whole_room() -> None:
    member = profile(60, 180, flex=(100, 200), minimum=60)
    joiner = profile(150, 270, flex=(60, 300), minimum=60)
    result = negotiate(joiner, [member])
    assert (result.outcome, result.agreed, result.rounds) == ("agreed", window(105, 165), 2)
    last = [(s.round, s.actor_kind, s.actor_ref, s.verdict) for s in result.steps][-3:]
    assert last == [
        (2, "delegate", "member-2", Verdict.ACCEPT),  # the joiner takes the host's counter
        (2, "delegate", "member-1", Verdict.ACCEPT),  # then the room confirms the same window
        (2, "host", "host", Verdict.ACCEPT),
    ]


def test_reject_ends_the_negotiation_at_once() -> None:
    member = profile(60, 180, flex=(60, 120), minimum=90)
    result = negotiate(profile(60, 180), [member])
    assert result.outcome == "failed" and result.failure_code == "rejected" and result.rounds == 1


def test_no_opening_proposal_means_no_negotiation() -> None:
    joiner = DelegatePolicy(profile(60, 180, flex=(60, 100), minimum=90))
    host = HostPolicy([("member-1", DelegatePolicy(profile()))], LOW)
    result = run_negotiation(
        room_id="r1", room_band=LOW, joiner=joiner, joiner_ref="member-2", host=host,
        opening=None, max_rounds=3,
    )  # fmt: skip
    assert (result.outcome, result.failure_code, result.rounds, result.steps) == (
        "failed", "no_allowed_window", 0, (),
    )  # fmt: skip


class Stubborn:
    """Always counters with a window the other side will not take, to exercise the round cap."""

    calls = 0

    def choose(self, profile: DelegateProfile, proposal: Proposal, room_band: BudgetBand) -> Reply:
        Stubborn.calls += 1
        shift = proposal.round * 15
        return Reply(Verdict.COUNTER, window(shift, shift + 120))


@given(st.integers(1, 6))
@settings(max_examples=12)
def test_p_4_rounds_are_bounded_by_the_configured_maximum(max_rounds: int) -> None:
    Stubborn.calls = 0
    member = DelegatePolicy(profile(0, 600, flex=(0, 600), minimum=15), Stubborn())  # type: ignore[arg-type]
    joiner = DelegatePolicy(profile(0, 600, flex=(0, 600), minimum=15), Stubborn())  # type: ignore[arg-type]
    host = HostPolicy([("member-1", member)], LOW)
    opening = Proposal("r1", window(0, 60), 1, "delegate")
    result = run_negotiation(
        room_id="r1", room_band=LOW, joiner=joiner, joiner_ref="member-2", host=host,
        opening=opening, max_rounds=max_rounds,
    )  # fmt: skip
    assert result.rounds <= max_rounds
    assert max(s.round for s in result.steps) <= max_rounds
    assert Stubborn.calls <= 2 * max_rounds  # one member per host round, one joiner per round
