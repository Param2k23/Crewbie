"""Deterministic validation. Nothing here consults a language model or private data.

Public group rules are enforced here; per-student hard limits are enforced by the
students' own evaluators and parsed fail-closed by ``parse_evaluation``.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .models import (
    ALLOWED_HINTS,
    ISSUE_PREFIX_HARD,
    Evaluation,
    GroupRules,
    SessionRequest,
    finite_unit,
    parse_ts,
)

PLAN_KEYS = (
    "plan_id", "session_id", "version", "opportunity_id", "title", "member_refs",
    "start_at", "end_at", "estimated_cost_cents_by_ref", "activities",
    "estimate_disclaimer", "synthetic",
)
DEFAULT_DISCLAIMER = "Synthetic estimates only; not live prices or travel quotes"


def normalize_candidate(
    raw: Mapping[str, Any], *, session_id: str, plan_id: str, version: int, request: SessionRequest, roster: Sequence[str]
) -> Dict[str, Any]:
    """Whitelist plan fields and overwrite identity fields.

    Anything an untrusted source attaches (``approved``, ``feasible``, ``version`` ...) is dropped.
    """
    plan: Dict[str, Any] = {k: raw[k] for k in PLAN_KEYS if k in raw}
    plan.update(session_id=session_id, plan_id=plan_id, version=version)
    plan.setdefault("title", request.title)
    plan.setdefault("opportunity_id", (request.opportunity or {}).get("opportunity_id"))
    plan.setdefault("member_refs", list(roster))
    plan.setdefault("activities", [])
    plan.setdefault("estimate_disclaimer", DEFAULT_DISCLAIMER)
    plan["synthetic"] = request.synthetic
    return plan


def signature(plan: Mapping[str, Any]) -> str:
    """Identity of a candidate's material content (ids and versions excluded)."""
    material = {
        "m": sorted(plan.get("member_refs", [])),
        "s": plan.get("start_at"),
        "e": plan.get("end_at"),
        "c": sorted((plan.get("estimated_cost_cents_by_ref") or {}).items()),
        "a": list(plan.get("activities", [])),
        "o": plan.get("opportunity_id"),
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True, default=str).encode()).hexdigest()[:16]


def check_roster(roster: Sequence[str], rules: GroupRules, initial_size: int) -> Optional[str]:
    """Return a public rule code if the current roster cannot satisfy attendance/role rules."""
    min_att = rules.min_attendees if rules.min_attendees is not None else min(2, initial_size)
    if len(roster) < min_att or len(roster) == 0:
        return "ATTENDANCE_MINIMUM"
    for ref in rules.essential_member_refs:
        if ref not in roster:
            return "ESSENTIAL_MEMBER_MISSING"
    for role, needed in rules.required_roles.items():
        covered = sum(1 for m in roster if role in rules.member_roles.get(m, ()))
        if covered < int(needed):
            return "ROLE_COVERAGE"
    return None


def validate_plan(plan: Mapping[str, Any], request: SessionRequest, roster: Sequence[str]) -> List[str]:
    """Deterministic structural and group-rule validation. Returns violation codes (empty = valid)."""
    rules = request.rules
    out: List[str] = []

    try:
        start, end = parse_ts(plan["start_at"]), parse_ts(plan["end_at"])
        w0, w1 = parse_ts(request.window_start), parse_ts(request.window_end)
    except (KeyError, ValueError, TypeError, AttributeError):
        return ["STRUCTURE"]

    members = plan.get("member_refs")
    if not isinstance(members, list) or len(set(members)) != len(members) or set(members) != set(roster):
        out.append("ATTENDANCE_MEMBERS")
    role_code = check_roster([m for m in (members or []) if m in roster], rules, len(request.member_refs))
    if role_code in ("ROLE_COVERAGE", "ESSENTIAL_MEMBER_MISSING"):
        out.append(role_code)

    costs = plan.get("estimated_cost_cents_by_ref")
    if not isinstance(costs, dict) or set(costs) != set(roster) or any(
        isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in costs.values()
    ):
        out.append("COST_INVALID")
    elif rules.group_max_cost_per_person_cents is not None and any(
        v > rules.group_max_cost_per_person_cents for v in costs.values()
    ):
        out.append("GROUP_COST_CAP")

    if end <= start:
        out.append("TIME_RANGE")
    else:
        if (end - start).total_seconds() / 3600 > rules.max_duration_hours:
            out.append("DURATION")
        if start < w0 or end > w1:
            out.append("OUT_OF_WINDOW")
        if start.hour < rules.earliest_start_local_hour or (end.hour, end.minute) > (rules.latest_end_local_hour, 0):
            out.append("LOCAL_HOURS")

    opp = request.opportunity
    if opp:
        if plan.get("opportunity_id") != opp.get("opportunity_id"):
            out.append("OPPORTUNITY_MISMATCH")
        elif opp.get("start_at") and opp.get("end_at") and end > start:
            if end <= parse_ts(opp["start_at"]) or start >= parse_ts(opp["end_at"]):
                out.append("OPPORTUNITY_TIME")
        if rules.requires_verified_public_access and opp.get("access_status") != "public":
            out.append("ACCESS_UNVERIFIED")  # unknown/restricted is never assumed open

    if plan.get("synthetic") is not request.synthetic:
        out.append("STRUCTURE")
    return sorted(set(out))


def parse_evaluation(
    raw: Any, *, student_ref: str, plan: Mapping[str, Any], extra_hints: Sequence[str] = ()
) -> Evaluation:
    """Strictly parse a PrivateEvaluation. Anything malformed or inconsistent fails closed.

    Hints outside the coarse whitelist are dropped, so an evaluator cannot steer the
    coordinator (or leak values) through free text.
    """
    def closed(code: str) -> Evaluation:
        return Evaluation(student_ref, False, False, (code,), 1.0, ())

    if not isinstance(raw, Mapping):
        return closed("HARD_MALFORMED_RESPONSE")
    if (
        raw.get("student_ref") != student_ref
        or raw.get("plan_id") != plan.get("plan_id")
        or raw.get("version") != plan.get("version")
        or raw.get("session_id") != plan.get("session_id")
    ):
        return closed("HARD_RESPONSE_MISMATCH")  # wrong student/plan/version (stale or replayed)
    if not isinstance(raw.get("feasible"), bool):
        return closed("HARD_MALFORMED_RESPONSE")

    codes = tuple(str(c) for c in raw.get("internal_issue_codes") or ())
    penalty = finite_unit(raw.get("soft_penalty", 0.0))
    if penalty is None:
        return closed("HARD_MALFORMED_RESPONSE")
    feasible = raw["feasible"]
    if feasible and any(c.startswith(ISSUE_PREFIX_HARD) for c in codes):
        feasible = False  # self-contradictory => not feasible
    hints_raw = list(raw.get("counteroffer_hints") or ()) + list(extra_hints)
    hints = tuple(h for h in ALLOWED_HINTS if h in hints_raw)
    return Evaluation(
        student_ref=student_ref,
        feasible=feasible,
        requires_private_exception=bool(raw.get("requires_private_exception")) and not feasible,
        issue_codes=codes,
        soft_penalty=penalty,
        hints=hints,
    )
