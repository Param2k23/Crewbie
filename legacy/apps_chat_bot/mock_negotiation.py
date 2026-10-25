"""Stand-in for Agent 04 so chat flows run offline. Clearly synthetic.

Real A4 validates against private constraints; this mock just builds a
plausible, already-"validated" public snapshot per activity type so the chat
side can be exercised. It must never be used to claim real feasibility.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Mapping, Optional

from apps.chat_bot.providers import ProviderUnavailable

DISCLAIMER = "Costs and times are demonstration estimates, not live offers."
_TEMPLATES = {
    "meal": ("Group dinner (DEMO)", "2026-10-25T19:00:00-07:00", "2026-10-25T21:00:00-07:00",
             ["Meet at the restaurant", "Dinner", "Optional walk after"], "about $18 per person (estimate)", "Public restaurant area (DEMO)"),
    "game": ("Badminton session (DEMO)", "2026-10-31T16:00:00-07:00", "2026-10-31T18:00:00-07:00",
             ["Warm-up", "Doubles rounds", "Cool-down"], "about $6 per person for court time (estimate)", "Campus rec courts (DEMO)"),
    "event": ("Group outing (DEMO)", "2026-10-30T19:00:00-07:00", "2026-10-30T22:00:00-07:00",
              ["Meet up", "Event", "Debrief"], "about $12 per person (estimate)", "Public venue (DEMO)"),
    "trip": ("Weekend trip to Flagstaff (DEMO)", "2026-10-31T09:00:00-07:00", "2026-11-01T18:00:00-07:00",
             ["Day 1: drive and scenic stop", "Day 1 evening: low-cost dinner", "Day 2: short hike", "Day 2: return trip"],
             "about $85 per person for the whole trip (estimate)", "Flagstaff area (DEMO)"),
    "other": ("Group hangout (DEMO)", "2026-10-31T15:00:00-07:00", "2026-10-31T17:00:00-07:00",
              ["Meet up", "Activity", "Wrap up"], "about $10 per person (estimate)", "Public campus location (DEMO)"),
}


def _shift(iso: str, **kw) -> str:
    return (datetime.fromisoformat(iso) + timedelta(**kw)).isoformat()


class MockNegotiationService:
    is_stub = True

    def __init__(self, session_id: str, member_refs: list[str]) -> None:
        self.session_id, self.members = session_id, list(member_refs)
        self.requests: list[dict] = []
        self.offline = False
        self._version = 0
        self._current: Optional[dict] = None

    def request_proposal(self, request: Mapping[str, Any]) -> dict:
        if self.offline:
            raise ProviderUnavailable("mock A4 offline")
        self.requests.append({"kind": "new", **request})
        return {"accepted": True, "request_id": request["request_id"]}

    def request_revision(self, request: Mapping[str, Any]) -> dict:
        if self.offline:
            raise ProviderUnavailable("mock A4 offline")
        self.requests.append({"kind": "revision", **request})
        return {"accepted": True, "request_id": request["request_id"]}

    def next_snapshot(self) -> dict:
        """Deliver the validated snapshot for the latest outstanding request (the A4 side of the loop)."""
        req = self.requests[-1]
        self._version += 1
        if req["kind"] == "new" or self._current is None:
            title, start, end, acts, cost, where = _TEMPLATES[req.get("activity_type") or "other"]
            snap = {"activity_type": req.get("activity_type") or "other", "title": title, "start_at": start,
                    "end_at": end, "activities": acts, "cost_summary": cost, "location_label": where}
        else:
            snap = {k: v for k, v in self._current.items() if k not in ("version", "plan_id")}
            aspects = set(req.get("aspects", []))
            if aspects & {"date", "details"}:
                snap["start_at"], snap["end_at"] = _shift(snap["start_at"], days=1), _shift(snap["end_at"], days=1)
            if "time" in aspects:
                snap["start_at"], snap["end_at"] = _shift(snap["start_at"], hours=1), _shift(snap["end_at"], hours=1)
            if aspects & {"date", "details", "time"}:
                snap["title"] = snap["title"].replace(" (DEMO)", ", revised (DEMO)") if "revised" not in snap["title"] else snap["title"]
            if "cost" in aspects:
                snap["cost_summary"] = re.sub(r"\$(\d+)", lambda m: f"${int(int(m.group(1)) * 0.8)}", snap["cost_summary"])
        snap.update({
            "session_id": self.session_id, "plan_id": f"plan_{self.session_id.split('_', 1)[-1]}_{self._version:03d}",
            "version": self._version, "member_refs": self.members, "validated": True,
            "estimate_disclaimer": DISCLAIMER, "synthetic": True,
        })
        self._current = snap
        return dict(snap)
