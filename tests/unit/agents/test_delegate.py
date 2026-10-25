from datetime import timedelta

from hypothesis import given
from hypothesis import strategies as st

from crewbie.agents.delegate import (
    DelegatePolicy,
    DeterministicChooser,
    allowed,
    closest_allowed,
)
from crewbie.agents.protocol import DelegateProfile, Proposal, Reply, Verdict
from crewbie.domain.budget import BudgetBand
from crewbie.domain.intent import SharedIntent
from crewbie.domain.vibe import Vibe
from crewbie.domain.windows import TimeWindow
from tests.unit.domain.helpers import at, window
from tests.unit.matching.helpers import profile

LOW, MID, HIGH = BudgetBand.LOW, BudgetBand.MID, BudgetBand.HIGH


def proposal(start: int, end: int) -> Proposal:
    return Proposal("r1", window(start, end), 1, "host")


def test_fr_mat_06_guard_requires_flex_minimum_and_budget() -> None:
    p = profile(60, 180, flex=(30, 210), minimum=90)
    assert allowed(p, window(60, 150), LOW)
    assert allowed(p, window(30, 210), LOW)
    assert not allowed(p, window(20, 120), LOW)  # starts before flex
    assert not allowed(p, window(120, 220), LOW)  # ends after flex
    assert not allowed(p, window(60, 140), LOW)  # shorter than the minimum
    assert not allowed(p, window(60, 150), HIGH)  # budget bands two steps apart
    assert allowed(p, window(60, 150), MID)


def test_delegate_accepts_what_the_guard_allows_and_counters_otherwise() -> None:
    delegate = DelegatePolicy(profile(60, 180, flex=(30, 210)))
    assert delegate.evaluate(proposal(60, 150), LOW).verdict is Verdict.ACCEPT
    counter = delegate.evaluate(proposal(0, 120), LOW)
    assert counter.verdict is Verdict.COUNTER
    assert counter.counter is not None and counter.counter == window(30, 120)


def test_delegate_rejects_when_no_allowed_window_exists() -> None:
    narrow = DelegatePolicy(profile(60, 180, flex=(60, 120), minimum=90))
    assert narrow.evaluate(proposal(60, 150), LOW).verdict is Verdict.REJECT
    assert DelegatePolicy(profile()).evaluate(proposal(60, 180), HIGH).verdict is Verdict.REJECT


def test_closest_allowed_extends_a_too_short_overlap_to_the_minimum() -> None:
    p = profile(60, 180, flex=(30, 300), minimum=90)
    counter = closest_allowed(p, window(150, 180), LOW)
    assert counter is not None and counter.duration == timedelta(minutes=90)
    assert allowed(p, counter, LOW)
    assert abs((counter.start + counter.duration / 2) - (at(165))) <= timedelta(minutes=15)


def test_counters_snap_inward_so_the_private_bound_is_not_revealed() -> None:
    odd = profile(60, 180).flex
    shifted = TimeWindow(
        odd.start + timedelta(minutes=7, seconds=19), odd.end - timedelta(minutes=4, seconds=41)
    )
    p = DelegateProfile(profile(60, 180).shared, shifted)
    counter = closest_allowed(p, window(0, 400), LOW)
    assert counter is not None
    assert counter.start != shifted.start and counter.end != shifted.end
    assert counter.start.minute % 15 == 0 and counter.end.minute % 15 == 0
    assert shifted.contains(counter)


class AlwaysAccept:
    def choose(self, profile: DelegateProfile, proposal: Proposal, room_band: BudgetBand) -> Reply:
        return Reply(Verdict.ACCEPT)


class WildCounter:
    """A chooser (stand-in for a misbehaving LLM) that counters far outside the flex window."""

    def choose(self, profile: DelegateProfile, proposal: Proposal, room_band: BudgetBand) -> Reply:
        return Reply(Verdict.COUNTER, window(-500, 900))


def test_fr_mat_06_guard_overrides_an_unsafe_accept() -> None:
    delegate = DelegatePolicy(profile(60, 180, flex=(60, 180)), AlwaysAccept())
    assert delegate.evaluate(proposal(0, 400), LOW).verdict is not Verdict.ACCEPT
    assert delegate.evaluate(proposal(60, 180), LOW).verdict is Verdict.ACCEPT


def test_fr_mat_06_guard_replaces_an_unsafe_counter_with_a_safe_decision() -> None:
    delegate = DelegatePolicy(profile(60, 180, flex=(60, 180)), WildCounter())
    reply = delegate.evaluate(proposal(0, 400), LOW)
    assert reply.verdict is Verdict.COUNTER and reply.counter == window(60, 180)


def test_initial_proposal_uses_the_overlap_when_it_is_long_enough() -> None:
    joiner = DelegatePolicy(profile(60, 180, flex=(30, 210)))
    opening = joiner.initial_proposal("r1", window(90, 240), 90, LOW)
    assert opening is not None and opening.window == window(90, 180)
    assert (opening.round, opening.from_kind) == (1, "delegate")


def test_initial_proposal_asks_for_a_longer_window_near_the_room_when_overlap_is_short() -> None:
    joiner = DelegatePolicy(profile(150, 270, flex=(120, 300), minimum=90))
    opening = joiner.initial_proposal("r1", window(60, 180), 90, LOW)
    assert opening is not None
    assert opening.window.duration >= timedelta(minutes=90)
    assert window(120, 300).contains(opening.window)


def test_initial_proposal_is_none_when_nothing_fits() -> None:
    joiner = DelegatePolicy(profile(60, 180, flex=(60, 120), minimum=90))
    assert joiner.initial_proposal("r1", window(300, 400), 90, LOW) is None
    assert DelegatePolicy(profile()).initial_proposal("r1", window(60, 180), 90, HIGH) is None


def test_the_profile_never_prints_its_private_bounds() -> None:
    assert "redacted" in repr(profile()) and str(profile(60, 180, flex=(17, 400))) == repr(
        profile()
    )


bands = st.sampled_from(list(BudgetBand))
profiles = st.builds(
    lambda start, length, lead, tail, minimum, band: DelegateProfile(
        SharedIntent("e", window(start, start + length), minimum, band, Vibe.CHILL),
        window(start - lead, start + length + tail),
    ),
    st.integers(-300, 300),
    st.integers(30, 400),
    st.integers(0, 200),
    st.integers(0, 200),
    st.integers(15, 300),
    bands,
)
proposals = st.builds(
    lambda start, length: Proposal("r", window(start, start + length), 1, "host"),
    st.integers(-600, 600),
    st.integers(1, 700),
)


@given(profiles, proposals, bands)
def test_p_1_the_deterministic_chooser_never_accepts_outside_the_limits(
    prof: DelegateProfile, prop: Proposal, band: BudgetBand
) -> None:
    reply = DelegatePolicy(prof).evaluate(prop, band)
    if reply.verdict is Verdict.ACCEPT:
        assert allowed(prof, prop.window, band)
    if reply.verdict is Verdict.COUNTER:
        assert reply.counter is not None and allowed(prof, reply.counter, band)


@given(
    profiles,
    proposals,
    bands,
    st.sampled_from([AlwaysAccept(), WildCounter(), DeterministicChooser()]),
)
def test_p_1_no_chooser_can_get_an_unsafe_accept_or_counter_through_the_guard(
    prof: DelegateProfile, prop: Proposal, band: BudgetBand, chooser: object
) -> None:
    reply = DelegatePolicy(prof, chooser).evaluate(prop, band)  # type: ignore[arg-type]
    if reply.verdict is Verdict.ACCEPT:
        assert allowed(prof, prop.window, band)
    if reply.verdict is Verdict.COUNTER:
        assert reply.counter is not None and allowed(prof, reply.counter, band)


@given(profiles, proposals, bands)
def test_p_1_every_opening_proposal_is_allowed(
    prof: DelegateProfile, prop: Proposal, band: BudgetBand
) -> None:
    opening = DelegatePolicy(prof).initial_proposal("r", prop.window, 90, band)
    if opening is not None:
        assert allowed(prof, opening.window, band)


odd_seconds = st.integers(1, 59).map(lambda s: timedelta(seconds=s))


@given(profiles, proposals, bands, odd_seconds, odd_seconds)
def test_p_2_a_counter_never_equals_a_private_flex_bound(
    prof: DelegateProfile, prop: Proposal, band: BudgetBand, lead: timedelta, tail: timedelta
) -> None:
    flex = TimeWindow(prof.flex.start - lead, prof.flex.end + tail)  # bounds with odd seconds
    private = DelegateProfile(prof.shared, flex)
    reply = DelegatePolicy(private).evaluate(prop, band)
    if reply.verdict is Verdict.COUNTER:
        assert reply.counter is not None
        assert reply.counter.start != flex.start and reply.counter.end != flex.end
    opening = DelegatePolicy(private).initial_proposal("r", prop.window, 90, band)
    if opening is not None and opening.window != private.shared.window.intersect(prop.window):
        assert opening.window.start != flex.start and opening.window.end != flex.end
