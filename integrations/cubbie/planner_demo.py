"""Offline Crewbie Planner examples. Synthetic inputs; no live venue claims."""
import json

from .core import PulseError
from .handoff import MockPlanningGateway, request_handoff
from .planner import plan_request


def main():
    context = {"authorized": True, "student_ref": "demo_student", "synthetic": True,
               "campus": "Tempe", "location": "Tempe", "budget_cents": 2000,
               "travel_tolerance_minutes": 15, "group_size": 1,
               "interests": ["outdoors"], "availability_start": "2026-10-26T12:00:00-07:00",
               "availability_end": "2026-10-26T14:00:00-07:00"}
    print("Crewbie Planner | LOCAL PREVIEW | native runtime UNVERIFIED")
    for message, c in (("I have two free hours", context),
                       ("Plan a two-day trip", {"authorized": True, "student_ref": "demo_student", "synthetic": True})):
        result = plan_request(message, c, now="2026-10-24T18:00:00Z")
        print(message, json.dumps(result, indent=2))
    result = plan_request("Find people to join", context)
    brief = result["brief"]
    consent = dict(context, activity_scope="demo_activity", consent_scope="demo_activity",
                   consent_brief_id=brief["brief_id"], sharing_opt_in=True, matching_opt_in=True)
    try:
        request_handoff(brief, context, "demo-1")
    except PulseError as error:
        print("Without consent:", error.code)
    try:
        request_handoff(brief, consent, "demo-1")
    except PulseError as error:
        print("With consent, backend absent:", error.code)
    print("Explicit mock:", json.dumps(request_handoff(brief, consent, "demo-1", gateway=MockPlanningGateway())))


if __name__ == "__main__":
    main()
