import pytest

from crewbie.domain.budget import BudgetBand
from crewbie.domain.errors import DomainError, ValidationFailed
from crewbie.domain.intent import (
    LIVE_STATES,
    IntentState,
    PrivateEnvelope,
    SharedIntent,
    ensure_transition,
    validate_intent,
)
from crewbie.domain.vibe import Vibe

from .helpers import at, window


def shared(**overrides: object) -> SharedIntent:
    fields: dict[str, object] = {
        "event_key": "abc",
        "window": window(60, 180),
        "activity_min_minutes": 90,
        "budget_band": BudgetBand.LOW,
        "vibe": Vibe.CHILL,
        "interests": ("board-games",),
    }
    fields.update(overrides)
    return SharedIntent(**fields)  # type: ignore[arg-type]


def envelope(earliest: int = 30, latest: int = 240, cap: float | None = 913.0) -> PrivateEnvelope:
    return PrivateEnvelope(at(earliest), at(latest), cap)


@pytest.mark.parametrize("minutes", [14, 721])
def test_fr_int_02_activity_minutes_bounds(minutes: int) -> None:
    with pytest.raises(ValidationFailed) as exc:
        shared(activity_min_minutes=minutes)
    assert "activity_min_minutes" in exc.value.fields


def test_fr_int_02_activity_minutes_inclusive_bounds_ok() -> None:
    shared(activity_min_minutes=15)
    shared(activity_min_minutes=720)


def test_fr_int_02_interests_limit_and_slug_format() -> None:
    with pytest.raises(ValidationFailed):
        shared(interests=("a", "b", "c", "d"))
    with pytest.raises(ValidationFailed):
        shared(interests=("Bad Slug",))


def test_fr_int_02_flex_must_cover_window() -> None:
    validate_intent(shared(), envelope(), now=at(0))
    with pytest.raises(ValidationFailed) as early:
        validate_intent(shared(), envelope(earliest=90), now=at(0))
    assert "flex.earliest" in early.value.fields
    with pytest.raises(ValidationFailed) as late:
        validate_intent(shared(), envelope(latest=170), now=at(0))
    assert "flex.latest" in late.value.fields


def test_fr_int_02_window_entirely_in_past_rejected() -> None:
    with pytest.raises(ValidationFailed) as exc:
        validate_intent(shared(), envelope(), now=at(200))
    assert "window" in exc.value.fields


def test_fr_int_02_window_partly_in_past_allowed() -> None:
    validate_intent(shared(), envelope(), now=at(100))


def test_nfr_prv_01_envelope_repr_and_str_are_redacted() -> None:
    env = envelope(cap=913.0)
    for text in (repr(env), str(env), f"{env}", repr([env])):
        assert "913" not in text
        assert "redacted" in text


def test_envelope_rejects_negative_cap_and_naive_times() -> None:
    with pytest.raises(ValidationFailed):
        envelope(cap=-1)
    from datetime import datetime

    with pytest.raises(ValidationFailed):
        PrivateEnvelope(datetime(2026, 1, 1), datetime(2026, 1, 2))


def test_envelope_flex_window() -> None:
    assert envelope().flex_window() == window(30, 240)


def test_intent_state_machine_follows_architecture_diagram() -> None:
    assert ensure_transition(IntentState.MATCHING, IntentState.OFFERED) is IntentState.OFFERED
    for target in (
        IntentState.JOINED,
        IntentState.DECLINED,
        IntentState.MATCHING,
        IntentState.EXPIRED,
    ):
        ensure_transition(IntentState.OFFERED, target)
    ensure_transition(IntentState.JOINED, IntentState.WITHDRAWN)
    ensure_transition(IntentState.EXPIRED, IntentState.MATCHING)
    for current, target in [
        (IntentState.MATCHING, IntentState.JOINED),
        (IntentState.DECLINED, IntentState.MATCHING),
        (IntentState.WITHDRAWN, IntentState.JOINED),
    ]:
        with pytest.raises(DomainError):
            ensure_transition(current, target)


def test_fr_int_03_live_states() -> None:
    assert IntentState.JOINED in LIVE_STATES
    assert IntentState.DECLINED not in LIVE_STATES
    assert IntentState.WITHDRAWN not in LIVE_STATES
