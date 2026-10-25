"""Local application interfaces, NOT claims about sponsor APIs."""
import json
from copy import deepcopy
from pathlib import Path
from typing import Protocol

from .core import PulseError, instant


class OpportunityCatalog(Protocol):
    def list_opportunities(self, campus, starts_after, ends_before, food_only): ...
    def get_opportunity(self, opportunity_id): ...


class CubbieProvider(Protocol):
    def register_alert(self, request_id, student_ref, preview, send_at, cadence, consent): ...
    def cancel(self, request_id, student_ref): ...


class FixtureOpportunityCatalog:
    """Explicitly synthetic A2 stand-in. Never loads live listings as fixtures."""
    def __init__(self, path):
        self.events = json.loads(Path(path).read_text(encoding="utf-8"))["opportunities"]
        if any(e.get("synthetic") is not True for e in self.events):
            raise PulseError("EVENT_UNVERIFIED", "Fixture adapter accepts synthetic events only")

    def list_opportunities(self, campus, starts_after, ends_before, food_only):
        # Match the contract's bounded query; core independently validates results.
        start, end = instant(starts_after), instant(ends_before)
        return deepcopy([e for e in self.events if e["campus"] == campus
                         and instant(e["start_at"]) >= start and instant(e["end_at"]) <= end
                         and (not food_only or e["food_status"] in ("listed", "confirmed_by_organizer"))])

    def get_opportunity(self, opportunity_id):
        return next((deepcopy(e) for e in self.events if e["opportunity_id"] == opportunity_id), None)


class UnavailableCubbieProvider:
    """Fail closed until sponsor identity, interface and permissions are verified."""
    def register_alert(self, *args, **kwargs):
        raise PulseError("PROVIDER_UNAVAILABLE", "Sponsor runtime and scheduled delivery are unverified; use private preview")

    def cancel(self, *args, **kwargs):
        raise PulseError("PROVIDER_UNAVAILABLE", "No verified sponsor cancellation interface")


class MockCubbieProvider:
    """In-memory scheduling simulation. No network, background worker or actual send.

    Consent is trusted adapter context, rechecked at registration and dispatch.
    State is process-local and is not a production idempotency implementation.
    """
    def __init__(self):
        self._registrations = {}

    def register_alert(self, request_id, student_ref, preview, send_at, cadence, consent):
        if not request_id or not student_ref:
            raise PulseError("VALIDATION_ERROR", "request_id and student_ref required")
        if (consent.get("authorized") is not True or consent.get("alerts_opt_in") is not True
                or consent.get("student_ref") != student_ref):
            raise PulseError("CONSENT_REQUIRED", "Explicit private alert permission required")
        if cadence not in ("daily", "weekly"):
            raise PulseError("VALIDATION_ERROR", "Choose daily or weekly cadence")
        if preview.get("student_ref") != student_ref or preview.get("visibility") != "private" or preview.get("synthetic") is not True:
            raise PulseError("VALIDATION_ERROR", "Mock scheduling requires a private synthetic preview")
        key = (student_ref, request_id)
        record = {"request_id": request_id, "student_ref": student_ref, "preview": deepcopy(preview),
                  "send_at": instant(send_at).isoformat(), "cadence": cadence,
                  "mode": "mock", "synthetic": True, "status": "registered", "delivered": False}
        if key in self._registrations:
            old = self._registrations[key]
            if any(old[k] != record[k] for k in ("preview", "send_at", "cadence")):
                raise PulseError("VALIDATION_ERROR", "request_id already used with different content")
            return deepcopy(old)
        self._registrations[key] = record
        return deepcopy(record)

    def cancel(self, request_id, student_ref):
        record = self._registrations.get((student_ref, request_id))
        if record:
            record["status"] = "cancelled"
        return {"mode": "mock", "cancelled": record is not None}

    def dispatch_due(self, now, consent, opportunities):
        """Simulate one occurrence only; caller must explicitly invoke this method.

        Missing/expired events suppress the notice; no event content is delivered.
        Cadence is metadata, not an implemented recurring sponsor schedule.
        """
        now = instant(now)
        delivered = []
        for (student, _), record in self._registrations.items():
            if student != consent.get("student_ref") or record["status"] != "registered":
                continue
            if consent.get("authorized") is not True or consent.get("alerts_opt_in") is not True:
                record["status"] = "cancelled"
                continue
            if instant(record["send_at"]) > now:
                continue
            # A notification prepared earlier is unsafe to reuse after event changes.
            available = {e.get("opportunity_id"): e for e in opportunities}
            ids = record["preview"]["opportunity_ids"]
            if not ids or any(i not in available or instant(available[i]["end_at"]) <= now for i in ids):
                record["status"] = "suppressed"
                continue
            record["status"] = "preview_due"
            delivered.append({"mode": "mock", "sent": False, "request_id": record["request_id"],
                              "student_ref": student, "message": "Mock reminder due; regenerate a private preview from current catalog before any real delivery."})
        return delivered
