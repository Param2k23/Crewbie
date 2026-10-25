"""General-social synthetic demo. Run: python -m services.participants.social_demo."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from .service import ParticipantService, PrivacyError


def load_social_demo():
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "social_scenarios.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    canonical_path = Path(__file__).resolve().parents[2] / "docs/implementation/fixtures/scenarios.json"
    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    originals = next(s["profiles"] for s in canonical["scenarios"] if "profiles" in s)
    service = ParticipantService(clock=lambda: datetime(2026, 10, 24, tzinfo=timezone.utc))
    for original in originals:
        ref = original["student_ref"]
        discovery = deepcopy(original)
        discovery.update(activity_scope=data["discovery_scope"], authorized=True, matching_opt_in=False,
                         introduction_opt_in=False, negotiation_opt_in=False, blocked_windows=[],
                         available_windows=data["evening_availability"],
                         social_preferences=deepcopy(data["discovery_preferences"][ref]))
        # Only deliberate shareable tags can appear in candidate results.
        discovery["shareable_interests"] = data["shareable_interests"][ref]
        service.seed_profile(discovery)
        private_trip = deepcopy(original)
        private_trip.update(activity_scope=data["trip_scope"], matching_opt_in=False,
                            introduction_opt_in=False, negotiation_opt_in=False,
                            social_preferences=data["trip_preferences"][ref])
        service.seed_profile(private_trip)
    for activity in data["activities"]:
        service.register_activity(data["discovery_scope"], activity)
    for plan in data["trip_plans"]:
        service.bind_session(plan["session_id"], data["trip_scope"], plan["member_refs"], activity_id=plan["activity_id"])
    return service, data


def run_scenarios():
    service, data = load_social_demo()
    scope = data["discovery_scope"]
    refs = data["trip_plans"][0]["member_refs"]
    # Independent owners explicitly choose discovery; nobody is enrolled by interests.
    for ref in refs:
        service.owner(ref).opt_in(ref, scope, {"matching_opt_in": True, "request_id": "discover"})
    alex = service.owner("stu_alex")
    candidates = alex.find_mutual_candidates(scope, "evening_games", 5)
    try:
        alex.introduction(scope, "evening_games", "stu_maya")
    except PrivacyError as error:
        introduction_gate = str(error)
    for ref, other in (("stu_alex", "stu_maya"), ("stu_maya", "stu_alex")):
        owner = service.owner(ref)
        owner.opt_in(ref, scope, {"introduction_opt_in": True, "request_id": "intro-consent"})
        owner.approve_introduction(scope, "evening_games", other, "pair-approval")
    introduction = alex.introduction(scope, "evening_games", "stu_maya")
    # Four selected friends privately opt into negotiation; public matching stays off.
    for ref in refs:
        service.owner(ref).opt_in(ref, data["trip_scope"], {"negotiation_opt_in": True, "request_id": "negotiate"})
    evaluator = service.evaluator(data["trip_plans"][0]["session_id"])
    outcomes = []
    for plan in data["trip_plans"]:
        results = [evaluator.evaluate_plan_private(ref, plan) for ref in refs]
        outcomes.append({"version": plan["version"], "all_feasible": all(r["feasible"] for r in results),
                         "public": service.public_evaluation({"feasible": all(r["feasible"] for r in results)})})
    first = data["trip_plans"][0]
    pending = evaluator.request_private_exception("stu_alex", first, "private-compromise")
    remains_infeasible = not evaluator.evaluate_plan_private("stu_alex", first)["feasible"]
    alex.respond_private_exception(data["trip_scope"], "private-compromise", False, "decline-compromise")
    alex.decline_activity(scope, "evening_games", "decline-activity")
    declined = alex.find_mutual_candidates(scope, "evening_games", 5)
    return {"synthetic": True, "notice": "Offline synthetic agents; no live provider integration",
            "scenario_a": {"candidates": candidates, "before_introduction_consent": introduction_gate,
                           "mutually_approved_introduction": introduction,
                           "after_activity_decline": declined},
            "scenario_b": {"existing_group_public_matching_required": False, "plans": outcomes,
                           "exception_request": pending, "request_did_not_approve_plan": remains_infeasible}}


def main():
    print(json.dumps(run_scenarios(), indent=2))


if __name__ == "__main__":
    main()
