from crewbie.agents.delegate import DelegatePolicy
from crewbie.agents.host import HostPolicy
from crewbie.agents.protocol import Proposal, Verdict
from crewbie.domain.budget import BudgetBand
from tests.unit.domain.helpers import window
from tests.unit.matching.helpers import profile

LOW = BudgetBand.LOW


def host(*profiles) -> HostPolicy:  # type: ignore[no-untyped-def]
    members = [(f"member-{i}", DelegatePolicy(p)) for i, p in enumerate(profiles, 1)]
    return HostPolicy(members, LOW)


def ask(start: int, end: int) -> Proposal:
    return Proposal("r1", window(start, end), 1, "delegate")


def test_fr_mat_05_all_members_must_accept() -> None:
    wide = profile(60, 180, flex=(0, 300))
    decision = host(wide, wide).evaluate(ask(90, 180))
    assert decision.reply.verdict is Verdict.ACCEPT
    assert [s.verdict for s in decision.member_steps] == [Verdict.ACCEPT, Verdict.ACCEPT]


def test_any_reject_rejects() -> None:
    wide, stuck = profile(60, 180, flex=(0, 300)), profile(60, 180, flex=(60, 120), minimum=90)
    assert host(wide, stuck).evaluate(ask(90, 180)).reply.verdict is Verdict.REJECT


def test_counters_are_merged_by_intersection() -> None:
    early = profile(60, 180, flex=(60, 200), minimum=60)
    late = profile(60, 180, flex=(100, 300), minimum=60)
    decision = host(early, late).evaluate(ask(30, 260))
    assert decision.reply.verdict is Verdict.COUNTER
    assert decision.reply.counter == window(105, 195)  # each counter snapped inside its flex


def test_accepting_members_keep_the_proposal_in_the_merge() -> None:
    accepts = profile(0, 400, flex=(0, 400), minimum=60)
    counters = profile(60, 180, flex=(120, 300), minimum=60)
    reply = host(accepts, counters).evaluate(ask(90, 200)).reply
    assert reply.verdict is Verdict.COUNTER and reply.counter == window(120, 200)


def test_merged_counter_shorter_than_the_longest_minimum_is_rejected() -> None:
    needs_long = profile(60, 180, flex=(0, 300), minimum=120)
    flexible = profile(60, 180, flex=(150, 300), minimum=30)
    assert host(needs_long, flexible).evaluate(ask(60, 160)).reply.verdict is Verdict.REJECT


def test_member_steps_record_verdicts_not_counter_windows() -> None:
    p = profile(60, 180, flex=(100, 300), minimum=60)
    decision = host(p).evaluate(ask(30, 260))
    (step,) = decision.member_steps
    assert step.verdict is Verdict.COUNTER
    assert step.proposal == window(
        30, 260
    )  # the window that was evaluated, not the member's counter
    assert (step.actor_kind, step.actor_ref) == ("delegate", "member-1")


def test_an_empty_room_rejects() -> None:
    assert HostPolicy([], LOW).evaluate(ask(0, 60)).reply.verdict is Verdict.REJECT
