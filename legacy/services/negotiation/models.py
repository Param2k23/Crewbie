"""Typed models, state machine tables and error codes for the negotiation engine.

Private data (profiles, evaluations, issue codes, soft penalties) lives only in
``Session.private`` / ``CandidateRecord.evaluations`` and is never copied into
public snapshots or events.
"""
from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

# --- shared error codes (CONTRACTS.md section 5) -------------------------------------
CONSENT_REQUIRED = "CONSENT_REQUIRED"
HARD_CONSTRAINT_FAILED = "HARD_CONSTRAINT_FAILED"
PRIVATE_EXCEPTION_PENDING = "PRIVATE_EXCEPTION_PENDING"
NO_FEASIBLE_PLAN = "NO_FEASIBLE_PLAN"
APPROVAL_INCOMPLETE = "APPROVAL_INCOMPLETE"
PROPOSAL_STALE = "PROPOSAL_STALE"
PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"

# --- coarse feedback vocabulary (the only hints the coordinator will act on) ----------
HINT_LOWER_COST = "prefer_lower_cost"
HINT_DIFFERENT_DAY = "prefer_different_day"
HINT_LATER_START = "prefer_later_start"
HINT_SHORTER = "prefer_shorter_trip"
ALLOWED_HINTS = (HINT_SHORTER, HINT_DIFFERENT_DAY, HINT_LOWER_COST, HINT_LATER_START)  # application order

REQUEST_MODES = ("seeded", "time_first", "intent_first")
GROUP_ORIGINS = ("existing", "matched")

ISSUE_PREFIX_HARD = "HARD_"


class NegotiationError(Exception):
    """Raised for caller errors (unknown session, illegal transition)."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code


class ConsentRequired(Exception):
    """Raised by a PrivateEvaluator when a member has not authorised this scope."""

    code = CONSENT_REQUIRED


class SessionState(str, enum.Enum):
    CREATED = "created"
    NEGOTIATING = "negotiating"
    AWAITING_EXCEPTION = "awaiting_exception"
    PROPOSED = "proposed"
    APPROVAL_PENDING = "approval_pending"
    CONFIRMED = "confirmed"  # set only after A5's gateway reports every approval
    RENEGOTIATING = "renegotiating"
    FAILED = "failed"
    CANCELLED = "cancelled"


S = SessionState
TRANSITIONS: Mapping[SessionState, Set[SessionState]] = {
    S.CREATED: {S.NEGOTIATING, S.CANCELLED},
    S.NEGOTIATING: {S.PROPOSED, S.AWAITING_EXCEPTION, S.FAILED, S.CANCELLED},
    S.AWAITING_EXCEPTION: {S.NEGOTIATING, S.RENEGOTIATING, S.FAILED, S.CANCELLED},
    S.PROPOSED: {S.APPROVAL_PENDING, S.RENEGOTIATING, S.FAILED, S.CANCELLED},
    S.APPROVAL_PENDING: {S.CONFIRMED, S.RENEGOTIATING, S.FAILED, S.CANCELLED},
    S.CONFIRMED: {S.RENEGOTIATING, S.FAILED, S.CANCELLED},
    S.RENEGOTIATING: {S.PROPOSED, S.AWAITING_EXCEPTION, S.FAILED, S.CANCELLED},
    S.FAILED: {S.RENEGOTIATING, S.CANCELLED},
    S.CANCELLED: set(),
}
TERMINAL_STATES = {S.CANCELLED}
SEARCH_STATES = {S.NEGOTIATING, S.RENEGOTIATING}


def parse_ts(value: str) -> datetime:
    """Parse RFC 3339 (accepts a trailing ``Z``; Python 3.10 ``fromisoformat`` does not)."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must carry a UTC offset")
    return dt


# --- configuration -------------------------------------------------------------------
@dataclass(frozen=True)
class NegotiationConfig:
    max_rounds: int = 4
    max_candidates: int = 10  # per search run; also bounds private evaluations per member
    target_feasible: int = 3  # stop early once this many feasible candidates exist
    max_counteroffers_per_candidate: int = 3
    max_suggestions_per_round: int = 2
    max_evaluations_per_member_per_session: int = 40  # anti-probing lifetime cap
    evaluator_timeout_s: float = 2.0
    session_timeout_s: float = 30.0  # wall clock budget for one search run
    balanced_spread_threshold: float = 0.25  # public "balanced" label cut-off
    weight_preference: float = 1.0
    weight_variance: float = 2.0
    weight_history: float = 1.0
    start_shift_hours: Tuple[int, ...] = (1, 2)
    day_shift_options: Tuple[int, ...] = (1, 2)
    cost_tiers_cents: Tuple[int, ...] = (3500, 4400, 5200, 6100, 7000)  # synthetic estimates


@dataclass(frozen=True)
class GroupRules:
    """Public, group-level rules the deterministic validator enforces."""

    min_attendees: Optional[int] = None  # default: min(2, initial group size)
    essential_member_refs: Tuple[str, ...] = ()
    member_roles: Mapping[str, Tuple[str, ...]] = field(default_factory=dict)
    required_roles: Mapping[str, int] = field(default_factory=dict)  # role -> min covered
    max_duration_hours: float = 14.0
    earliest_start_local_hour: int = 6
    latest_end_local_hour: int = 22
    group_max_cost_per_person_cents: Optional[int] = None  # public cap, not a private one
    requires_verified_public_access: bool = False


@dataclass(frozen=True)
class SessionRequest:
    request_id: str
    member_refs: Tuple[str, ...]
    window_start: str
    window_end: str
    seed_plans: Tuple[Mapping[str, Any], ...]
    session_id: Optional[str] = None
    activity_scope: str = "group_activity"
    title: str = "Group activity (DEMO)"
    plan_slug: str = "plan"
    rules: GroupRules = field(default_factory=GroupRules)
    opportunity: Optional[Mapping[str, Any]] = None
    synthetic: bool = True
    mode: str = "seeded"  # seeded | time_first (free time, suggest activities) | intent_first (activity chosen)
    intent: Optional[Mapping[str, Any]] = None  # intent_first: {"kind": ..., "title"?: ...}
    cost_tiers_cents: Optional[Tuple[int, ...]] = None  # per-request synthetic price ladder
    group_origin: str = "existing"  # existing | matched (matched needs introduction consent for everyone)
    consent_context: Mapping[str, Any] = field(default_factory=dict)
    slot_limit: int = 8  # max catalog-generated starting candidates

    @staticmethod
    def from_mapping(raw: Mapping[str, Any]) -> "SessionRequest":
        r = dict(raw)
        rules_raw = dict(r.get("rules") or {})
        rules = GroupRules(
            min_attendees=rules_raw.get("min_attendees"),
            essential_member_refs=tuple(rules_raw.get("essential_member_refs", ())),
            member_roles={k: tuple(v) for k, v in dict(rules_raw.get("member_roles", {})).items()},
            required_roles=dict(rules_raw.get("required_roles", {})),
            max_duration_hours=float(rules_raw.get("max_duration_hours", 14.0)),
            earliest_start_local_hour=int(rules_raw.get("earliest_start_local_hour", 6)),
            latest_end_local_hour=int(rules_raw.get("latest_end_local_hour", 22)),
            group_max_cost_per_person_cents=rules_raw.get("group_max_cost_per_person_cents"),
            requires_verified_public_access=bool(rules_raw.get("requires_verified_public_access", False)),
        )
        members = tuple(r["member_refs"])
        if not members or len(set(members)) != len(members):
            raise NegotiationError("INVALID_REQUEST", "member_refs must be non-empty and unique")
        seeds = tuple(r.get("seed_plans", ()))
        mode = r.get("mode") or ("seeded" if seeds else "time_first")
        origin = r.get("group_origin", "existing")
        if mode not in REQUEST_MODES or origin not in GROUP_ORIGINS:
            raise NegotiationError("INVALID_REQUEST", "unknown mode or group_origin")
        if mode == "intent_first" and not (r.get("intent") or {}).get("kind"):
            raise NegotiationError("INVALID_REQUEST", "intent_first needs intent.kind")
        tiers = r.get("cost_tiers_cents")
        return SessionRequest(
            request_id=str(r["request_id"]),
            member_refs=members,
            window_start=r["window_start"],
            window_end=r["window_end"],
            seed_plans=tuple(r.get("seed_plans", ())),
            session_id=r.get("session_id"),
            activity_scope=r.get("activity_scope", "group_activity"),
            title=r.get("title", "Group activity (DEMO)"),
            plan_slug=str(r.get("plan_slug", "plan")),
            rules=rules,
            opportunity=r.get("opportunity"),
            synthetic=bool(r.get("synthetic", True)),
            mode=mode,
            intent=r.get("intent"),
            cost_tiers_cents=tuple(sorted(tiers)) if tiers else None,
            group_origin=origin,
            consent_context=dict(r.get("consent_context") or {}),
            slot_limit=int(r.get("slot_limit", 8)),
        )


# --- private evaluation result (parsed + validated; never leaves the coordinator) -----
@dataclass(frozen=True)
class Evaluation:
    student_ref: str
    feasible: bool
    requires_private_exception: bool
    issue_codes: Tuple[str, ...]
    soft_penalty: float
    hints: Tuple[str, ...]


class CandidateStatus(str, enum.Enum):
    FEASIBLE = "feasible"
    REJECTED = "rejected"  # a member's hard constraint failed
    INVALID = "invalid"  # failed public structural / group-rule validation


@dataclass
class CandidateRecord:
    plan: Dict[str, Any]
    status: CandidateStatus
    origin: str  # seed | counteroffer | refinement | suggestion
    derived_from_version: Optional[int] = None
    evaluations: Dict[str, Evaluation] = field(default_factory=dict)  # PRIVATE
    rule_violations: Tuple[str, ...] = ()  # public-rule codes only

    @property
    def version(self) -> int:
        return int(self.plan["version"])

    @property
    def exception_eligible(self) -> bool:
        failing = [e for e in self.evaluations.values() if not e.feasible]
        return (
            self.status is CandidateStatus.REJECTED
            and bool(failing)
            and all(e.requires_private_exception for e in failing)
        )


@dataclass
class Session:
    session_id: str
    request: SessionRequest
    state: SessionState = SessionState.CREATED
    roster: List[str] = field(default_factory=list)
    initial_size: int = 0
    version_counter: int = 0
    current_plan: Optional[Dict[str, Any]] = None  # published proposal (full, PRIVATE costs)
    base_plan: Optional[Dict[str, Any]] = None  # starting point for revisions
    error_code: Optional[str] = None
    reason_category: Optional[str] = None
    transitions: List[Tuple[str, str]] = field(default_factory=list)
    event_seq: int = 0
    # private bookkeeping ------------------------------------------------------------
    records: List[CandidateRecord] = field(default_factory=list)
    ranked: List[CandidateRecord] = field(default_factory=list)
    eval_counts: Dict[str, int] = field(default_factory=dict)
    seen_signatures: Set[str] = field(default_factory=set)
    vetoed: Set[str] = field(default_factory=set)  # content signatures a member declined
    pending_exceptions: Dict[str, Optional[bool]] = field(default_factory=dict)
    exception_candidate: Optional[CandidateRecord] = None
    cost_disclosure: Set[str] = field(default_factory=set)
    run_started_at: float = 0.0
    stats: Dict[str, int] = field(default_factory=lambda: {"candidates": 0, "rounds": 0, "revisions": 0})
    stop_reason: Optional[str] = None


@dataclass(frozen=True)
class ConfirmationResult:
    status: str  # confirmed | incomplete | stale | not_pending
    error_code: Optional[str] = None
    accepted_count: int = 0
    required_count: int = 0


def finite_unit(value: Any) -> Optional[float]:
    """Return ``value`` as a float in [0, 1] or None if it is not a finite real number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return min(1.0, max(0.0, float(value)))


def as_list(x: Optional[Sequence[Any]]) -> List[Any]:
    return list(x) if x else []
