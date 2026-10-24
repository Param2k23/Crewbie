"""Shared test scaffolding for the negotiation suite (stdlib unittest; pytest also collects these)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.negotiation import (  # noqa: E402
    MemoryEventSink,
    NegotiationConfig,
    NegotiationCoordinator,
    SteppingClock,
)
from services.negotiation.mocks import (  # noqa: E402
    MockCommitmentGateway,
    MockExceptionGateway,
    MockPrivateEvaluator,
    flagstaff_agents,
    flagstaff_request,
)

PRIVATE_TOKENS = ["budget", "cap", "hard_", "penalty", "avoid_before", "blocked", "saturday", "work",
                  "6000", "7500", "9000", "10000", "7000", "5200", "6100", "4400", "3500", "issue"]


class Rig:
    """A coordinator wired to mock participants, commitments and a sink."""

    def __init__(self, *, config: Optional[NegotiationConfig] = None, evaluator: Any = None,
                 exception_gateway: bool = True, **kw: Any) -> None:
        self.agents = flagstaff_agents()
        self.by_ref = {a.student_ref: a for a in self.agents}
        self.evaluator = evaluator or MockPrivateEvaluator(self.agents)
        self.gateway = MockCommitmentGateway()
        self.exceptions = MockExceptionGateway()
        self.sink = MemoryEventSink()
        self.clock = SteppingClock()
        self.coordinator = NegotiationCoordinator(
            self.evaluator, self.gateway, self.sink, config=config, clock=self.clock,
            exception_gateway=self.exceptions if exception_gateway else None, **kw,
        )

    def start(self, **overrides: Any) -> str:
        sid = self.coordinator.start_negotiation(flagstaff_request(**overrides))
        self.open(sid)
        return sid

    def snap(self, sid: str) -> Dict[str, Any]:
        return self.coordinator.get_public_snapshot(sid)

    def open(self, sid: str) -> None:
        s = self.snap(sid)
        if s["plan"]:
            self.gateway.open_proposal(s)

    def accept_all(self, sid: str, response: str = "accepted") -> None:
        s = self.snap(sid)
        for m in s["plan"]["member_refs"]:
            self.gateway.record_approval(sid, s["plan"]["plan_id"], s["version"], m, response)

    def types(self) -> List[str]:
        return self.sink.types()

    def trace_text(self) -> str:
        return json.dumps(self.sink.events, sort_keys=True).lower()


def evaluation(plan: Mapping[str, Any], ref: str, *, feasible: bool = True, penalty: float = 0.0,
               hints: Sequence[str] = (), exception: bool = False, issues: Sequence[str] = ()) -> Dict[str, Any]:
    return {
        "session_id": plan["session_id"], "plan_id": plan["plan_id"], "version": plan["version"],
        "student_ref": ref, "feasible": feasible, "requires_private_exception": exception,
        "internal_issue_codes": list(issues) or ([] if feasible else ["HARD_BUDGET"]),
        "soft_penalty": penalty, "counteroffer_hints": list(hints), "synthetic": True,
    }


class FuncEvaluator:
    """PrivateEvaluator whose verdict is a function of (student_ref, plan)."""

    def __init__(self, fn: Callable[[str, Mapping[str, Any]], Any]) -> None:
        self.fn = fn
        self.calls: List[tuple] = []
        self.counteroffer_calls = 0
        self.seen_plans: List[Mapping[str, Any]] = []

    def evaluate_plan_private(self, student_ref: str, plan: Mapping[str, Any]) -> Any:
        self.calls.append((student_ref, plan["plan_id"], plan["version"]))
        self.seen_plans.append(plan)
        return self.fn(student_ref, plan)

    def propose_private_counteroffer(self, student_ref: str, plan: Mapping[str, Any]) -> Mapping[str, Any]:
        self.counteroffer_calls += 1
        return {"hints": []}


def plan_at(day: str, hour: int, *, cost: int = 5200, members: Sequence[str] = ("stu_alex", "stu_maya", "stu_jordan", "stu_taylor"),
            hours: int = 8, **extra: Any) -> Dict[str, Any]:
    start = f"{day}T{hour:02d}:00:00-07:00"
    end = f"{day}T{hour + hours:02d}:00:00-07:00"
    p = {"title": "Flagstaff day trip (DEMO)", "start_at": start, "end_at": end,
         "estimated_cost_cents_by_ref": {m: cost for m in members}, "activities": ["Scenic stop", "Return trip"]}
    p.update(extra)
    return p
