"""Fairness ranking over FEASIBLE candidates only.

    score = w_pref * mean(p) + w_var * var(p) + w_hist * mean(h * p)        (lower is better)

* ``p_i``  soft-compromise burden member *i* carries under the plan, in [0, 1] (from the
  student's own evaluator; used only inside the coordinator).
* ``var``  population variance of ``p``: a fair plan spreads compromises instead of piling them
  on one person.
* ``h_i``  consented burden-history share in [0, 1] (how much of past compromises member *i*
  already carried). Members who have not opted in contribute 0.

Ties break deterministically on (max p, total estimated cost, start time, signature).
Ranking can never make an infeasible plan eligible: ``rank_feasible`` refuses non-feasible input.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence, Set

from .models import CandidateRecord, CandidateStatus, NegotiationConfig
from .validator import signature


@dataclass(frozen=True)
class Scored:
    record: CandidateRecord
    score: float
    spread: float  # max(p) - min(p), used for the public balanced/uneven label
    burdens: Dict[str, float]


def _burdens(record: CandidateRecord) -> Dict[str, float]:
    return {ref: ev.soft_penalty for ref, ev in record.evaluations.items()}


def score_record(record: CandidateRecord, history: Mapping[str, float], cfg: NegotiationConfig) -> Scored:
    p = _burdens(record)
    n = len(p)
    vals = list(p.values())
    mean = sum(vals) / n
    var = sum((v - mean) ** 2 for v in vals) / n
    hist = sum(history.get(ref, 0.0) * v for ref, v in p.items()) / n
    score = cfg.weight_preference * mean + cfg.weight_variance * var + cfg.weight_history * hist
    return Scored(record, round(score, 9), max(vals) - min(vals), p)


def rank_feasible(
    records: Sequence[CandidateRecord], history: Mapping[str, float], cfg: NegotiationConfig
) -> List[Scored]:
    for r in records:
        if r.status is not CandidateStatus.FEASIBLE or not all(e.feasible for e in r.evaluations.values()):
            raise ValueError("fairness ranking accepts feasible candidates only")
    scored = [score_record(r, history, cfg) for r in records]
    scored.sort(
        key=lambda s: (
            s.score,
            round(max(s.burdens.values()), 9),
            sum(s.record.plan["estimated_cost_cents_by_ref"].values()),
            s.record.plan["start_at"],
            signature(s.record.plan),
        )
    )
    return scored


class InMemoryFairnessHistory:
    """Cumulative burden per opted-in member; non-opted-in members are never recorded or reported."""

    def __init__(self, opted_in: Set[str]) -> None:
        self.opted_in = set(opted_in)
        self._totals: Dict[str, float] = {}
        self._recorded: Set[str] = set()

    def burden_shares(self, member_refs: Sequence[str]) -> Dict[str, float]:
        known = {m: self._totals.get(m, 0.0) for m in member_refs if m in self.opted_in}
        top = max(known.values(), default=0.0)
        return {m: (v / top if top > 0 else 0.0) for m, v in known.items()}

    def record_outcome(self, session_id: str, burdens: Mapping[str, float]) -> None:
        if session_id in self._recorded:  # idempotent per session
            return
        self._recorded.add(session_id)
        for ref, burden in burdens.items():
            if ref in self.opted_in:
                self._totals[ref] = self._totals.get(ref, 0.0) + burden
