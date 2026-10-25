"""Deterministic candidate generation from coarse counteroffer hints.

All prices come from the configured synthetic cost-tier table; nothing is a live quote.
Steps are deliberately coarse (whole tiers / hours / days) so repeated counteroffers do not
become a fine-grained probe of anyone's exact limits.
"""
from __future__ import annotations

import copy
from datetime import timedelta
from itertools import combinations
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .models import (
    ALLOWED_HINTS,
    HINT_DIFFERENT_DAY,
    HINT_LATER_START,
    HINT_LOWER_COST,
    HINT_SHORTER,
    NegotiationConfig,
    SessionRequest,
    parse_ts,
)
from .catalog import ActivityCatalog
from .validator import normalize_candidate, signature, validate_plan

SUMMARY_PHRASES = {
    HINT_DIFFERENT_DAY: "alternative day",
    HINT_LOWER_COST: "reduced estimated cost",
    HINT_LATER_START: "later start",
    HINT_SHORTER: "shorter trip",
}


def summarize(hints: Sequence[str]) -> str:
    parts = [SUMMARY_PHRASES[h] for h in ALLOWED_HINTS if h in hints]
    if not parts:
        return "Adjusted itinerary"
    text = " and ".join(parts) if len(parts) < 3 else ", ".join(parts[:-1]) + " and " + parts[-1]
    return text[0].upper() + text[1:]


class DeterministicCandidateGenerator:
    def __init__(self, config: NegotiationConfig, catalog: Optional[ActivityCatalog] = None) -> None:
        self.config = config
        self.catalog = catalog or ActivityCatalog()

    # -- seeds ------------------------------------------------------------------------
    def seeds(self, request: SessionRequest, roster: Sequence[str]) -> List[Dict[str, Any]]:
        if request.seed_plans:
            return [copy.deepcopy(dict(p)) for p in request.seed_plans]
        return self.catalog.seeds(request, roster)

    # -- operators --------------------------------------------------------------------
    def _apply(self, plan: Mapping[str, Any], op: str, idx: int, tiers: Sequence[int]) -> Optional[Dict[str, Any]]:
        out = copy.deepcopy(dict(plan))
        start, end = parse_ts(plan["start_at"]), parse_ts(plan["end_at"])
        if op == HINT_DIFFERENT_DAY:
            opts = self.config.day_shift_options
            delta = timedelta(days=opts[min(idx, len(opts) - 1)])
            out["start_at"], out["end_at"] = (start + delta).isoformat(), (end + delta).isoformat()
        elif op == HINT_LATER_START:
            opts = self.config.start_shift_hours
            delta = timedelta(hours=opts[min(idx, len(opts) - 1)])
            out["start_at"], out["end_at"] = (start + delta).isoformat(), (end + delta).isoformat()
        elif op == HINT_LOWER_COST:
            new: Dict[str, int] = {}
            for ref, cost in plan["estimated_cost_cents_by_ref"].items():
                lower = [t for t in tiers if t < cost]
                step = min(len(lower), idx + 1)  # variant 0: one tier down; variant 1: two tiers down
                new[ref] = lower[-step] if lower else cost
            if new == plan["estimated_cost_cents_by_ref"]:
                return None  # cheapest tier already: operator not applicable
            out["estimated_cost_cents_by_ref"] = new
        elif op == HINT_SHORTER:
            nights = int(plan.get("nights", 0))
            if nights < 1:
                return None  # nothing to shorten
            end_local = start.replace(hour=21, minute=0)
            hours = min(9.0, (end_local - start).total_seconds() / 3600)
            if hours < 3:
                return None
            out["end_at"] = (start + timedelta(hours=hours)).isoformat()
            out["estimated_cost_cents_by_ref"] = {  # lodging and the extra day drop out
                r: -(-c // (nights + 1) // 100) * 100 for r, c in plan["estimated_cost_cents_by_ref"].items()
            }
            out["activities"] = [a for a in plan.get("activities", []) if not a.lower().startswith("overnight")]
            out["activity_kind"] = "day_trip"
            out["title"] = f"{plan.get('title', 'Trip')} (single-day version)"
            out.pop("logistics", None)  # re-derived: no lodging needed any more
            out.pop("nights", None)
            out.pop("overnight", None)
        return out

    def derive(
        self, plan: Mapping[str, Any], hints: Sequence[str], request: SessionRequest, roster: Sequence[str],
        seen: Sequence[str] = (), limit: Optional[int] = None,
    ) -> List[Tuple[Dict[str, Any], str]]:
        """Return up to ``limit`` (candidate, summary) pairs, best-matching first."""
        limit = self.config.max_counteroffers_per_candidate if limit is None else limit
        ops = [h for h in ALLOWED_HINTS if h in hints]
        if not ops:
            return []
        plans_ops: List[Tuple[Tuple[str, ...], int]] = [(tuple(ops), i) for i in range(2)]
        if len(ops) > 1:
            plans_ops += [((o,), 0) for o in ops]
            if len(ops) > 2:
                plans_ops += [(c, 0) for c in combinations(ops, 2)]
        tiers = sorted(request.cost_tiers_cents or self.config.cost_tiers_cents)
        seen_sigs = set(seen) | {signature(plan)}
        results: List[Tuple[Dict[str, Any], str]] = []
        for combo, idx in plans_ops:
            cand: Optional[Dict[str, Any]] = copy.deepcopy(dict(plan))
            for op in combo:
                cand = self._apply(cand, op, idx, tiers) if cand is not None else None
            if cand is None:
                continue
            cand = normalize_candidate(cand, session_id=plan.get("session_id", ""), plan_id=plan.get("plan_id", ""),
                                       version=plan.get("version", 1), request=request, roster=roster)
            sig = signature(cand)
            if sig in seen_sigs or validate_plan(cand, request, roster):
                continue  # duplicate, or would fail public rules: do not spend a private probe
            seen_sigs.add(sig)
            results.append((cand, summarize(combo)))
            if len(results) >= limit:
                break
        return results
