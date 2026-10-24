"""Run with python -m services.participants.demo; no network or dependencies."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from .service import ParticipantService, PrivacyError
from .identity import DemoIdentityProvider, OwnerGateway


def load_demo():
    fixtures = Path(__file__).resolve().parents[2] / "docs/implementation/fixtures"
    scenarios = json.loads((fixtures / "scenarios.json").read_text(encoding="utf-8"))["scenarios"]
    trip = next(s for s in scenarios if s["id"] == "flagstaff_private_negotiation")
    pulse = next(s for s in scenarios if s["id"] == "campus_pulse")
    opportunity = json.loads((fixtures / "opportunities.json").read_text(encoding="utf-8"))["opportunities"][0]
    service = ParticipantService(clock=lambda: datetime(2026, 10, 24, tzinfo=timezone.utc))
    for profile in trip["profiles"]:
        service.seed_profile(profile)
    service.bind_session("session_trip_001", "trip_flagstaff_001", trip["candidate_plans"][0]["member_refs"])
    # Two scoped companion records derived from existing synthetic students.
    for original in trip["profiles"][:2]:
        p = deepcopy(original)
        p.update(activity_scope="campus_pulse", authorized=False, matching_opt_in=False,
                 campus="Tempe", blocked_windows=[], available_windows=[{
                     "start_at": pulse["student_brief"]["availability_start"],
                     "end_at": pulse["student_brief"]["availability_end"]}])
        service.seed_profile(p)
    service.register_opportunity("campus_pulse", opportunity)
    return service, trip


def main():
    service, trip = load_demo()
    # Explicit mock tokens are used only for this synthetic standalone run.
    owners = OwnerGateway(service, DemoIdentityProvider({
        "demo-token-alex": "stu_alex", "demo-token-maya": "stu_maya"}))
    alex, maya = owners.authenticate("demo-token-alex"), owners.authenticate("demo-token-maya")
    for owner, ref in ((alex, "stu_alex"), (maya, "stu_maya")):
        owner.opt_in(ref, "campus_pulse", {"authorized": True, "matching_opt_in": True,
                     "introduction_opt_in": True, "request_id": "demo-opt-in"})
    matches = alex.find_mutual_candidates("campus_pulse", "opp_demo_pizza", 5)
    try:
        alex.introduction("campus_pulse", "opp_demo_pizza", "stu_maya")
    except PrivacyError as error:
        intro_before = str(error)
    alex.approve_introduction("campus_pulse", "opp_demo_pizza", "stu_maya", "intro-alex")
    maya.approve_introduction("campus_pulse", "opp_demo_pizza", "stu_alex", "intro-maya")
    evaluator = service.evaluator("session_trip_001")
    results = []
    for plan in trip["candidate_plans"]:
        private = [evaluator.evaluate_plan_private(ref, plan) for ref in plan["member_refs"]]
        results.append({"version": plan["version"], "all_feasible": all(r["feasible"] for r in private),
                        "public": service.public_evaluation({"feasible": all(r["feasible"] for r in private)})})
    original = trip["candidate_plans"][0]
    alex.approve_private_exception("trip_flagstaff_001", original, True, "demo-exception")
    exception_feasible = evaluator.evaluate_plan_private("stu_alex", original)["feasible"]
    alex.revoke("trip_flagstaff_001", "demo-withdraw")
    try:
        evaluator.evaluate_plan_private("stu_alex", original)
    except PrivacyError as error:
        after_withdrawal = str(error)
    print(json.dumps({"synthetic": True, "notice": "DEMO ONLY; private evaluations remain on trusted server",
                      "matches": matches, "introduction_before_pair_approval": intro_before,
                      "introduction": alex.introduction("campus_pulse", "opp_demo_pizza", "stu_maya"),
                      "plans": results, "owner_approved_exception_feasible": exception_feasible,
                      "after_withdrawal": after_withdrawal}, indent=2))


if __name__ == "__main__":
    main()
