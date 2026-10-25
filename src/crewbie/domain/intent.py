"""Intent value objects and lifecycle (SRS 5.2, 02-ARCHITECTURE section 5)."""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from crewbie.domain.budget import BudgetBand
from crewbie.domain.errors import DomainError, ValidationFailed
from crewbie.domain.vibe import Vibe
from crewbie.domain.windows import TimeWindow

ACTIVITY_MIN_MINUTES = 15
ACTIVITY_MAX_MINUTES = 720
MAX_INTERESTS = 3
_INTEREST_SLUG = re.compile(r"^[a-z0-9-]{1,24}$")


@dataclass(frozen=True, slots=True)
class SharedIntent:
    """Fields other members may see, only as room aggregates."""

    event_key: str
    window: TimeWindow
    activity_min_minutes: int
    budget_band: BudgetBand
    vibe: Vibe
    interests: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        problems: dict[str, str] = {}
        if not ACTIVITY_MIN_MINUTES <= self.activity_min_minutes <= ACTIVITY_MAX_MINUTES:
            problems["activity_min_minutes"] = (
                f"must be between {ACTIVITY_MIN_MINUTES} and {ACTIVITY_MAX_MINUTES}"
            )
        if len(self.interests) > MAX_INTERESTS:
            problems["interests"] = f"at most {MAX_INTERESTS}"
        elif not all(_INTEREST_SLUG.match(slug) for slug in self.interests):
            problems["interests"] = "slugs must match [a-z0-9-]{1,24}"
        if problems:
            raise ValidationFailed(problems)


@dataclass(frozen=True, slots=True, repr=False)
class PrivateEnvelope:
    """Delegate-only fields. Never log, return or stream; repr is redacted on purpose."""

    flex_earliest: datetime
    flex_latest: datetime
    budget_cap_usd: float | None = None

    def __post_init__(self) -> None:
        if self.flex_earliest.tzinfo is None or self.flex_latest.tzinfo is None:
            raise ValidationFailed({"flex": "datetimes must include a UTC offset"})
        if self.budget_cap_usd is not None and self.budget_cap_usd < 0:
            raise ValidationFailed({"budget_cap_usd": "must not be negative"})

    def __repr__(self) -> str:
        return "PrivateEnvelope(<redacted>)"

    def flex_window(self) -> TimeWindow:
        return TimeWindow(self.flex_earliest, self.flex_latest)


def validate_intent(shared: SharedIntent, envelope: PrivateEnvelope, now: datetime) -> None:
    """FR-INT-02 checks that span the shared fields, the envelope and the clock."""
    problems: dict[str, str] = {}
    if envelope.flex_earliest > shared.window.start:
        problems["flex.earliest"] = "must be at or before window.start"
    if envelope.flex_latest < shared.window.end:
        problems["flex.latest"] = "must be at or after window.end"
    if shared.window.end <= now:
        problems["window"] = "must not be entirely in the past"
    if problems:
        raise ValidationFailed(problems)


class IntentState(StrEnum):
    MATCHING = "matching"
    OFFERED = "offered"
    JOINED = "joined"
    DECLINED = "declined"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"


LIVE_STATES = frozenset({IntentState.MATCHING, IntentState.OFFERED, IntentState.JOINED})

_TRANSITIONS: dict[IntentState, frozenset[IntentState]] = {
    IntentState.MATCHING: frozenset({IntentState.OFFERED}),
    IntentState.OFFERED: frozenset(
        {IntentState.JOINED, IntentState.DECLINED, IntentState.MATCHING, IntentState.EXPIRED}
    ),
    IntentState.JOINED: frozenset({IntentState.WITHDRAWN}),
    IntentState.EXPIRED: frozenset({IntentState.MATCHING}),
    IntentState.DECLINED: frozenset(),
    IntentState.WITHDRAWN: frozenset(),
}


def ensure_transition(current: IntentState, target: IntentState) -> IntentState:
    """Return `target` if the state machine allows it, else raise."""
    if target not in _TRANSITIONS[current]:
        raise DomainError(f"intent cannot move from {current} to {target}")
    return target
