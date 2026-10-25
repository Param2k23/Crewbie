"""Consent gate and injectable transport for future A3/A4 composition.

This is a local application protocol, not an official service endpoint. Private
planning sidecars are intentionally never forwarded. Authentication and durable
idempotency must be implemented by the integrator's real gateway.
"""
from copy import deepcopy
from typing import Protocol

from .core import PulseError


BRIEF_FIELDS = ("brief_id", "student_ref", "intent", "campus", "availability_start", "availability_end",
                "opportunity_id", "wants_companion", "requirements_to_verify", "source", "synthetic")


class PlanningGateway(Protocol):
    def submit(self, request): ...


class UnavailablePlanningGateway:
    def submit(self, request):
        raise PulseError("PROVIDER_UNAVAILABLE", "Crewbie matching/coordination is not connected; keep planning privately")


class MockPlanningGateway:
    """Synthetic receipt only; does not match, negotiate, introduce or message."""
    def __init__(self):
        self.requests = {}

    def submit(self, request):
        if request["brief"].get("synthetic") is not True:
            raise PulseError("VALIDATION_ERROR", "Mock accepts synthetic requests only")
        key = (request["brief"]["student_ref"], request["request_id"])
        if key in self.requests and self.requests[key] != request:
            raise PulseError("VALIDATION_ERROR", "request_id reused with changed content")
        self.requests[key] = deepcopy(request)
        return {"mode": "mock", "status": "mock_received", "request_id": request["request_id"],
                "matched": False, "confirmed": False, "sent": False}


def request_handoff(brief, context, request_id, *, action="matching", gateway=None):
    """Use trusted per-activity consent, rechecked on every request/retry."""
    if action not in ("matching", "coordination") or not isinstance(request_id, str) or not request_id.strip():
        raise PulseError("VALIDATION_ERROR", "Valid action and request_id required")
    scope = context.get("activity_scope")
    if (context.get("authorized") is not True or context.get("student_ref") != brief.get("student_ref")
            or not scope or context.get("sharing_opt_in") is not True
            or context.get("consent_scope") != scope or context.get("consent_brief_id") != brief.get("brief_id")):
        raise PulseError("CONSENT_REQUIRED", "Confirm this activity and minimum brief sharing before handoff")
    if action == "matching" and (context.get("matching_opt_in") is not True or not brief.get("wants_companion")):
        raise PulseError("CONSENT_REQUIRED", "Matching opt-in is required")
    if action == "coordination" and context.get("coordination_opt_in") is not True:
        raise PulseError("CONSENT_REQUIRED", "Coordination opt-in is required")
    if any(k not in brief for k in BRIEF_FIELDS):
        raise PulseError("VALIDATION_ERROR", "Complete canonical brief required")
    safe_brief = {k: deepcopy(brief[k]) for k in BRIEF_FIELDS}
    # This handoff's approved minimal fields do not include private dietary needs.
    safe_brief["requirements_to_verify"] = [r for r in safe_brief["requirements_to_verify"]
                                               if r in ("event_entry_policy", "matching_consent")]
    request = {"request_id": request_id, "activity_scope": scope, "action": action, "brief": safe_brief}
    return (gateway or UnavailablePlanningGateway()).submit(request)
