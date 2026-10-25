"""Synthetic scenario kits: a request plus the private agents behind it. Nothing here is real data."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .mocks import MockParticipantAgent, flagstaff_agents, flagstaff_request


def _profile(ref: str, scope: str, cap: int, blocked: Tuple[Tuple[str, str], ...] = (), **soft: Any) -> Dict[str, Any]:
    extra = {k: soft.pop(k) for k in ("hard_max_nights",) if k in soft}
    return {
        "student_ref": ref, "activity_scope": scope, "authorized": True, "matching_opt_in": True,
        "introduction_opt_in": True, "hard_budget_cap_cents": cap,
        "blocked_windows": [{"start_at": a, "end_at": b} for a, b in blocked],
        "soft_preferences": soft, "shareable_interests": [], "synthetic": True, **extra,
    }


@dataclass
class ScenarioKit:
    name: str
    request: Dict[str, Any]
    agents: List[MockParticipantAgent]
    budget_member: str  # whose private cap the demo changes
    availability_member: str  # whose private calendar the demo changes
    exception_member: Optional[str] = None  # who would privately consider a small cap waiver
    default_change_cents: int = 4000  # the demo's "lowered cap" when no value is given


def flagstaff_kit() -> ScenarioKit:
    return ScenarioKit("flagstaff", flagstaff_request(), flagstaff_agents(), "stu_alex", "stu_taylor", "stu_alex")


def dinner_game_kit(request_id: str = "req_dinner_001", mode: str = "intent_first") -> ScenarioKit:
    """Scenario A: four friends want dinner + a game night; the first evening slots clash with someone."""
    scope = "dinner_game_001"
    agents = [
        MockParticipantAgent(_profile("stu_ari", scope, 4000, avoid_before_local_hour=17)),
        MockParticipantAgent(_profile("stu_bea", scope, 3500,
                                      (("2026-11-06T17:00:00-07:00", "2026-11-06T19:30:00-07:00"),))),
        MockParticipantAgent(_profile("stu_cam", scope, 5000,
                                      (("2026-11-07T17:00:00-07:00", "2026-11-07T18:00:00-07:00"),),
                                      prefers_kinds=["dinner_games", "games"])),
        MockParticipantAgent(_profile("stu_dev", scope, 3000, prefers_low_cost=True)),
    ]
    req: Dict[str, Any] = {
        "request_id": request_id, "session_id": "session_dinner_001", "plan_slug": "plan_dinner",
        "title": "Dinner and game night (DEMO)", "member_refs": [a.student_ref for a in agents],
        "window_start": "2026-11-06T17:00:00-07:00", "window_end": "2026-11-08T23:30:00-07:00",
        "mode": mode, "rules": {"min_attendees": 4, "latest_end_local_hour": 23, "max_duration_hours": 6},
        "cost_tiers_cents": [500, 1000, 1500, 2000, 2500, 3000, 3500], "synthetic": True,
    }
    if mode == "intent_first":
        req["intent"] = {"kind": "dinner_games"}
    return ScenarioKit("dinner", req, agents, "stu_dev", "stu_cam", "stu_dev", 1800)


def two_day_trip_kit(impossible: bool = False) -> ScenarioKit:
    """Scenario B: a two-day trip. Every full-length date fails (budget and/or a work shift) until
    the agents' counteroffers find a shorter version, unless ``impossible`` removes every option."""
    scope = "trip_two_day_001"
    wk = (("2026-11-14T00:00:00-07:00", "2026-11-14T23:59:00-07:00"),)
    everything = (("2026-11-13T00:00:00-07:00", "2026-11-16T23:59:00-07:00"),)
    agents = [
        MockParticipantAgent(_profile("stu_eli", scope, 15000)),
        MockParticipantAgent(_profile("stu_fay", scope, 12000, prefers_low_cost=True)),
        MockParticipantAgent(_profile("stu_gus", scope, 1000 if impossible else 9000)),
        MockParticipantAgent(_profile("stu_hal", scope, 14000, everything if impossible else wk)),
    ]
    req: Dict[str, Any] = {
        "request_id": "req_trip2_001", "session_id": "session_trip2_001", "plan_slug": "plan_trip2",
        "title": "Two-day mountain trip (DEMO)", "member_refs": [a.student_ref for a in agents],
        "window_start": "2026-11-13T08:00:00-07:00", "window_end": "2026-11-16T20:00:00-07:00",
        "mode": "intent_first", "intent": {"kind": "weekend_trip"},
        "rules": {"min_attendees": 4, "latest_end_local_hour": 22, "max_duration_hours": 36},
        "cost_tiers_cents": [2000, 3500, 4400, 5200, 6100, 7000, 8800, 11800, 14000], "synthetic": True,
    }
    return ScenarioKit("trip", req, agents, "stu_gus", "stu_eli", None, 4000)


KITS = {"flagstaff": flagstaff_kit, "dinner": dinner_game_kit, "trip": two_day_trip_kit}
