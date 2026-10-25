"""Synthetic activity templates for time-first and intent-first planning.

Duration is an *attribute* of a template, never the thing that picks the category: a three-hour
window can host dinner, games or a hike, and a long window can still host a short activity.
All prices are labelled demonstration estimates, not quotes; transport, lodging and venue hours are
reported as "needs human verification" unless the template says they are genuinely not needed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .models import SessionRequest, parse_ts
from .validator import DEFAULT_DISCLAIMER


@dataclass(frozen=True)
class ActivityTemplate:
    kind: str
    title: str
    duration_hours: float
    start_hours: Tuple[int, ...]  # candidate local start hours on each day of the window
    cost_cents: int  # per person, synthetic
    activities: Tuple[str, ...]
    requires_transport: bool = True
    venue_bound: bool = False  # depends on venue opening times we do not know
    nights: int = 0


DEFAULT_CATALOG: Tuple[ActivityTemplate, ...] = (
    ActivityTemplate("dinner", "Group dinner (DEMO)", 2.5, (17, 18, 19), 2500, ("Dinner",), True, True),
    ActivityTemplate("games", "Game night (DEMO)", 3, (18, 19, 20), 800, ("Board and card games",), False),
    ActivityTemplate("dinner_games", "Dinner and game night (DEMO)", 4, (17, 18, 19), 3000,
                     ("Dinner", "Game night"), True, True),
    ActivityTemplate("sports", "Pickup sports (DEMO)", 2, (9, 10, 16, 17), 500, ("Pickup game",), False),
    ActivityTemplate("hiking", "Morning hike (DEMO)", 5, (7, 8, 9), 1200, ("Trail hike", "Trailhead return"), True),
    ActivityTemplate("local_event", "Local event outing (DEMO)", 3, (11, 13, 18), 1800, ("Event visit",), True, True),
    ActivityTemplate("day_trip", "Day trip (DEMO)", 10, (7, 8, 9), 5200, ("Scenic stop", "Low-cost lunch", "Return trip")),
    ActivityTemplate("weekend_trip", "Two-day trip (DEMO)", 30, (8,), 11800,
                     ("Outbound trip", "Main activity", "Overnight stay", "Return trip"), True, False, nights=1),
)


class ActivityCatalog:
    def __init__(self, templates: Sequence[ActivityTemplate] = DEFAULT_CATALOG) -> None:
        self.templates = tuple(templates)

    def kinds(self) -> List[str]:
        return [t.kind for t in self.templates]

    def for_request(self, request: SessionRequest) -> List[ActivityTemplate]:
        """intent_first => only the requested kind; time_first => every kind that could fit."""
        if request.mode == "intent_first":
            kind = (request.intent or {}).get("kind")
            return [t for t in self.templates if t.kind == kind]
        return list(self.templates)

    def seeds(self, request: SessionRequest, roster: Sequence[str]) -> List[Dict[str, Any]]:
        w0, w1 = parse_ts(request.window_start), parse_ts(request.window_end)
        per_template: List[List[Dict[str, Any]]] = []
        for tpl in self.for_request(request):
            slots: List[Dict[str, Any]] = []
            day = w0.replace(hour=0, minute=0, second=0, microsecond=0)
            while day <= w1:
                for hour in tpl.start_hours:
                    start = day.replace(hour=hour)
                    end = start + timedelta(hours=tpl.duration_hours)
                    if start >= w0 and end <= w1:  # the WHOLE interval must fit the planning window
                        slots.append(self._plan(tpl, start.isoformat(), end.isoformat(), request, roster))
                day += timedelta(days=1)
            per_template.append(slots)
        ordered: List[Dict[str, Any]] = []  # round-robin so early candidates span activity kinds
        for i in range(max((len(s) for s in per_template), default=0)):
            for slots in per_template:
                if i < len(slots):
                    ordered.append(slots[i])
        return ordered[: request.slot_limit]

    @staticmethod
    def _plan(tpl: ActivityTemplate, start_at: str, end_at: str, request: SessionRequest,
              roster: Sequence[str]) -> Dict[str, Any]:
        title = (request.intent or {}).get("title") or tpl.title
        return {
            "title": title,
            "activity_kind": tpl.kind,
            "start_at": start_at,
            "end_at": end_at,
            "estimated_cost_cents_by_ref": {m: tpl.cost_cents for m in roster},
            "activities": list(tpl.activities),
            "requires_transport": tpl.requires_transport,
            "venue_bound": tpl.venue_bound,
            "estimate_disclaimer": DEFAULT_DISCLAIMER,
        }
