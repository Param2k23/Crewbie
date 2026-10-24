"""Contract-compliant stand-ins for A3 (private evaluators), A5 (commitments) and a language model.

Everything here is SYNTHETIC. Each ``MockParticipantAgent`` owns its private profile and answers
only through the PrivateEvaluation shape from CONTRACTS.md; the coordinator never reads a profile.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from .models import (
    HINT_DIFFERENT_DAY,
    HINT_LATER_START,
    HINT_LOWER_COST,
    ConsentRequired,
    parse_ts,
)

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "docs" / "implementation" / "fixtures"


class MockParticipantAgent:
    def __init__(self, profile: Mapping[str, Any], *, exception_margin_cents: int = 0) -> None:
        self._p: Dict[str, Any] = json.loads(json.dumps(profile))
        self._margin = exception_margin_cents
        self._granted: Set[Tuple[str, str, int]] = set()
        self.evaluations: List[Tuple[str, int]] = []  # (plan_id, version) it was asked about
        self.counteroffer_requests = 0

    @property
    def student_ref(self) -> str:
        return self._p["student_ref"]

    # -- mutators used by the demo / tests to play "the student changed something" ------
    def set_hard_budget_cap(self, cents: int) -> None:
        self._p["hard_budget_cap_cents"] = cents

    def set_blocked_windows(self, windows: Sequence[Mapping[str, str]]) -> None:
        self._p["blocked_windows"] = [dict(w) for w in windows]

    def set_exception_margin(self, cents: int) -> None:
        self._margin = cents

    def record_exception(self, session_id: str, plan_id: str, version: int, approved: bool) -> None:
        key = (session_id, plan_id, version)
        (self._granted.add if approved else self._granted.discard)(key)

    # -- assessment ---------------------------------------------------------------------
    def _assess(self, plan: Mapping[str, Any]) -> Tuple[List[str], bool, float, List[str]]:
        if not self._p.get("authorized", False):
            raise ConsentRequired(self.student_ref)
        ref = self.student_ref
        cost = plan["estimated_cost_cents_by_ref"][ref]
        start, end = parse_ts(plan["start_at"]), parse_ts(plan["end_at"])
        issues: List[str] = []
        hints: List[str] = []
        exception_possible = False

        cap = self._p["hard_budget_cap_cents"]
        if cost > cap:
            granted = (plan["session_id"], plan["plan_id"], plan["version"]) in self._granted
            if not granted:
                issues.append("HARD_BUDGET")
                exception_possible = cost <= cap + self._margin
                hints.append(HINT_LOWER_COST)
        for w in self._p.get("blocked_windows", []):
            if start < parse_ts(w["end_at"]) and end > parse_ts(w["start_at"]):
                issues.append("HARD_AVAILABILITY")
                exception_possible = False  # time conflicts are never waived by this mock
                hints.append(HINT_DIFFERENT_DAY)
                break

        soft = self._p.get("soft_preferences", {})
        penalty = 0.0
        early = max(0, int(soft.get("avoid_before_local_hour", 0)) - start.hour)
        if early:
            penalty += 0.1 * early
            hints.append(HINT_LATER_START)
        if soft.get("prefers_low_cost"):
            cost_pen = min(1.0, max(0.0, cost - 3000) / 10000)
            penalty += cost_pen
            if cost_pen > 0.15:
                hints.append(HINT_LOWER_COST)
        return issues, exception_possible, round(min(1.0, penalty), 4), hints

    # -- PrivateEvaluator surface (delegated to by MockPrivateEvaluator) ---------------
    def evaluate(self, plan: Mapping[str, Any]) -> Dict[str, Any]:
        self.evaluations.append((plan["plan_id"], plan["version"]))
        issues, exc, penalty, hints = self._assess(plan)
        return {
            "session_id": plan["session_id"], "plan_id": plan["plan_id"], "version": plan["version"],
            "student_ref": self.student_ref, "feasible": not issues,
            "requires_private_exception": bool(issues) and exc and "HARD_AVAILABILITY" not in issues,
            "internal_issue_codes": issues, "soft_penalty": penalty,
            "counteroffer_hints": hints, "synthetic": True,
        }

    def counteroffer(self, plan: Mapping[str, Any]) -> Dict[str, Any]:
        self.counteroffer_requests += 1
        _, _, _, hints = self._assess(plan)
        return {"hints": hints, "synthetic": True}


class MockPrivateEvaluator:
    """Routes ``student_ref`` to that student's own agent (what A3's service does in production)."""

    def __init__(self, agents: Sequence[MockParticipantAgent]) -> None:
        self.agents: Dict[str, MockParticipantAgent] = {a.student_ref: a for a in agents}

    def evaluate_plan_private(self, student_ref: str, plan: Mapping[str, Any]) -> Mapping[str, Any]:
        return self.agents[student_ref].evaluate(plan)

    def propose_private_counteroffer(self, student_ref: str, plan: Mapping[str, Any]) -> Mapping[str, Any]:
        return self.agents[student_ref].counteroffer(plan)

    def record_exception_decision(
        self, student_ref: str, session_id: str, plan_id: str, version: int, approved: bool
    ) -> None:
        self.agents[student_ref].record_exception(session_id, plan_id, version, approved)

    def total_evaluations(self) -> int:
        return sum(len(a.evaluations) for a in self.agents.values())


class MockCommitmentGateway:
    """Stands in for A5. Approvals are version-bound; ``invalidate_version`` drops older ones."""

    def __init__(self) -> None:
        self.invalidations: List[Tuple[str, int, int]] = []
        self._floor: Dict[str, int] = {}
        self._votes: Dict[Tuple[str, str, int], Dict[str, str]] = {}
        self._required: Dict[str, int] = {}

    def open_proposal(self, snapshot: Mapping[str, Any]) -> None:
        self._required[snapshot["session_id"]] = int(snapshot["required_count"])

    def record_approval(self, session_id: str, plan_id: str, version: int, member_ref: str, response: str) -> str:
        if version < self._floor.get(session_id, 0):
            return "PROPOSAL_STALE"
        self._votes.setdefault((session_id, plan_id, version), {})[member_ref] = response
        return "recorded"

    def invalidate_version(self, session_id: str, old_version: int, new_version: int) -> None:
        self.invalidations.append((session_id, old_version, new_version))
        self._floor[session_id] = max(self._floor.get(session_id, 0), new_version)

    def get_commitment_summary(self, session_id: str, plan_id: str, version: int) -> Mapping[str, Any]:
        votes = {} if version < self._floor.get(session_id, 0) else self._votes.get((session_id, plan_id, version), {})
        accepted = sum(v == "accepted" for v in votes.values())
        required = self._required.get(session_id, 0)
        return {
            "session_id": session_id, "plan_id": plan_id, "version": version,
            "required_count": required, "accepted_count": accepted,
            "declined_count": sum(v == "declined" for v in votes.values()),
            "withdrawn_count": sum(v == "withdrawn" for v in votes.values()),
            "confirmed": bool(required) and accepted == required,
        }


class MockExceptionGateway:
    """Collects private exception requests; each is addressed to exactly one student."""

    def __init__(self) -> None:
        self.requests: List[Tuple[str, str, str, int]] = []

    def request_private_exception(self, student_ref: str, session_id: str, plan_id: str, version: int) -> None:
        self.requests.append((student_ref, session_id, plan_id, version))


class ScriptedSuggester:
    """Stand-in for a language model: returns scripted (possibly hostile or sloppy) candidates.

    It also records the context it was given so tests can assert it never saw private data.
    """

    def __init__(self, rounds: Sequence[Sequence[Mapping[str, Any]]]) -> None:
        self._rounds = list(rounds)
        self.contexts: List[Mapping[str, Any]] = []

    def suggest(self, context: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        self.contexts.append(context)
        return self._rounds.pop(0) if self._rounds else []


def load_flagstaff_fixture(path: Optional[Path] = None) -> Dict[str, Any]:
    data = json.loads((path or FIXTURE_DIR / "scenarios.json").read_text(encoding="utf-8"))
    return next(s for s in data["scenarios"] if s["id"] == "flagstaff_private_negotiation")


def flagstaff_request(fixture: Optional[Mapping[str, Any]] = None, **overrides: Any) -> Dict[str, Any]:
    """Session request for the flagship four-student trip, built from the shared fixture."""
    fx = fixture or load_flagstaff_fixture()
    seed = dict(fx["candidate_plans"][0])  # the infeasible v1 plan: Saturday 07:00, $70
    for k in ("plan_id", "version", "session_id"):
        seed.pop(k, None)
    req: Dict[str, Any] = {
        "request_id": "req_trip_001",
        "session_id": "session_trip_001",
        "plan_slug": "plan_flagstaff",
        "title": "Flagstaff day trip (DEMO)",
        "member_refs": [p["student_ref"] for p in fx["profiles"]],
        "window_start": "2026-10-30T00:00:00-07:00",
        "window_end": "2026-11-02T23:59:00-07:00",
        "seed_plans": [seed],
        "rules": {"min_attendees": 3, "latest_end_local_hour": 22},
        "synthetic": True,
    }
    req.update(overrides)
    return req


def flagstaff_agents(fixture: Optional[Mapping[str, Any]] = None) -> List[MockParticipantAgent]:
    fx = fixture or load_flagstaff_fixture()
    return [MockParticipantAgent(p) for p in fx["profiles"]]
