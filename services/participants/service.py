"""Offline, trusted-server implementation of the frozen participant interfaces."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from threading import RLock
from typing import Any, Mapping, Protocol, TypedDict


class PrivateEvaluation(TypedDict):
    session_id: str
    plan_id: str
    version: int
    student_ref: str
    feasible: bool
    requires_private_exception: bool
    internal_issue_codes: list[str]
    soft_penalty: float
    counteroffer_hints: list[str]
    synthetic: bool


class CandidateDisplay(TypedDict):
    student_ref: str
    shared_interests: list[str]
    synthetic: bool


class CounterofferHints(TypedDict):
    counteroffer_hints: list[str]
    synthetic: bool


class PrivateEvaluator(Protocol):
    def evaluate_plan_private(self, student_ref: str, plan: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def propose_private_counteroffer(self, student_ref: str, plan: Mapping[str, Any]) -> Mapping[str, Any]: ...


class PrivacyError(Exception):
    """Safe errors carry fixed codes, never input values or private reasons."""


def instant(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError()
        return result
    except (ValueError, TypeError, AttributeError):
        raise PrivacyError("INVALID_INPUT") from None


def window(value):
    if not isinstance(value, Mapping) or not {"start_at", "end_at"} <= value.keys():
        raise PrivacyError("INVALID_INPUT")
    start, end = instant(value["start_at"]), instant(value["end_at"])
    if end <= start:
        raise PrivacyError("INVALID_INPUT")
    return start, end


def digest(value):
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError):
        raise PrivacyError("INVALID_INPUT") from None
    return sha256(encoded.encode()).hexdigest()


def identifier(value):
    if not isinstance(value, str) or not value:
        raise PrivacyError("INVALID_INPUT")
    return value


def validate_plan(plan):
    """Validate the canonical envelope before reading any student's policy."""
    required = {"session_id", "plan_id", "version", "opportunity_id", "title", "member_refs",
                "start_at", "end_at", "estimated_cost_cents_by_ref", "activities",
                "estimate_disclaimer", "synthetic"}
    if not isinstance(plan, Mapping) or not required <= plan.keys():
        raise PrivacyError("INVALID_INPUT")
    for field in ("session_id", "plan_id"):
        identifier(plan[field])
    if type(plan["version"]) is not int or plan["version"] < 1 or plan["synthetic"] is not True:
        raise PrivacyError("INVALID_INPUT")
    for field in ("title", "estimate_disclaimer"):
        if not isinstance(plan[field], str):
            raise PrivacyError("INVALID_INPUT")
    if plan["opportunity_id"] is not None:
        identifier(plan["opportunity_id"])
    for field in ("member_refs", "activities"):
        if not isinstance(plan[field], list) or not all(isinstance(v, str) for v in plan[field]):
            raise PrivacyError("INVALID_INPUT")
    members = plan["member_refs"]
    if not members or any(not m for m in members) or len(members) != len(set(members)):
        raise PrivacyError("INVALID_INPUT")
    costs = plan["estimated_cost_cents_by_ref"]
    if (not isinstance(costs, dict) or set(costs) != set(members)
            or any(type(c) is not int or c < 0 for c in costs.values())):
        raise PrivacyError("INVALID_INPUT")
    facts = plan.get("verified_conditions", {})
    if not isinstance(facts, dict) or any(not isinstance(k, str) or type(v) is not bool for k, v in facts.items()):
        raise PrivacyError("INVALID_INPUT")
    for field in ("activity_id", "activity_kind", "rough_area"):
        if field in plan:
            identifier(plan[field])
    if "estimated_travel_minutes_by_ref" in plan:
        travel = plan["estimated_travel_minutes_by_ref"]
        if (not isinstance(travel, dict) or set(travel) != set(members)
                or any(type(v) is not int or v < 0 for v in travel.values())):
            raise PrivacyError("INVALID_INPUT")
    window(plan)
    digest(plan)


class ProfileRepository(Protocol):
    def get(self, student_ref: str, scope: str) -> dict: ...
    def put(self, profile: Mapping[str, Any]) -> None: ...
    def list_scope(self, scope: str) -> list: ...
    def purge(self, student_ref: str, scope: str) -> None: ...


class MemoryRepository:
    def __init__(self):
        self._profiles = {}

    def get(self, student_ref, scope):
        try:
            return deepcopy(self._profiles[student_ref, scope])
        except KeyError:
            raise PrivacyError("CONSENT_REQUIRED") from None

    def put(self, profile):
        self._profiles[profile["student_ref"], profile["activity_scope"]] = deepcopy(profile)

    def list_scope(self, scope):
        return [deepcopy(p) for (s, a), p in self._profiles.items() if a == scope]

    def purge(self, student_ref, scope):
        self._profiles.pop((student_ref, scope), None)


class ParticipantService:
    """Composition root: only trusted application bootstrap receives this object.

    Owner/evaluator capabilities are issued after external identity verification.
    No user-supplied identity string is accepted as authentication here.
    """
    def __init__(self, repository=None, clock=None, probe_limit=8):
        if type(probe_limit) is not int or not 1 <= probe_limit <= 8:
            raise PrivacyError("INVALID_INPUT")
        self._repo = repository or MemoryRepository()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._limit = probe_limit
        self._lock = RLock()
        self._sessions = {}
        self._session_activities = {}
        self._opportunities = {}
        self._activities = {}
        self._search_counts = {}
        self._declines = set()
        self._pending_exceptions = {}
        self._private_decisions = {}
        self._counts = {}
        self._exceptions = set()
        self._introductions = set()
        self._requests = {}
        self._audit = []  # Protected, contains only operation labels.

    def seed_profile(self, profile):
        if not isinstance(profile, Mapping):
            raise PrivacyError("INVALID_INPUT")
        p = deepcopy(profile)
        required = {"student_ref", "activity_scope", "authorized", "matching_opt_in",
                    "introduction_opt_in", "hard_budget_cap_cents", "blocked_windows",
                    "soft_preferences", "shareable_interests", "synthetic"}
        if not required <= p.keys():
            raise PrivacyError("INVALID_INPUT")
        identifier(p["student_ref"])
        identifier(p["activity_scope"])
        if p.get("synthetic") is not True:
            raise PrivacyError("SYNTHETIC_ONLY")
        cap = p.get("hard_budget_cap_cents")
        if type(cap) is not int or cap < 0:
            raise PrivacyError("INVALID_INPUT")
        for field in ("blocked_windows", "available_windows"):
            if not isinstance(p.get(field, []), list):
                raise PrivacyError("INVALID_INPUT")
            for w in p.get(field, []):
                window(w)
        if "expires_at" in p:
            instant(p["expires_at"])
        for name in ("authorized", "matching_opt_in", "introduction_opt_in"):
            if type(p.get(name)) is not bool:
                raise PrivacyError("INVALID_INPUT")
        soft = p.get("soft_preferences")
        if not isinstance(soft, dict) or type(soft.get("avoid_before_local_hour", 0)) is not int:
            raise PrivacyError("INVALID_INPUT")
        if not 0 <= soft.get("avoid_before_local_hour", 0) <= 23:
            raise PrivacyError("INVALID_INPUT")
        if type(soft.get("prefers_low_cost", False)) is not bool:
            raise PrivacyError("INVALID_INPUT")
        for field in ("shareable_interests", "required_conditions"):
            values = p.get(field, [])
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                raise PrivacyError("INVALID_INPUT")
        offset = p.get("utc_offset_minutes", -420)
        if type(offset) is not int or not -840 <= offset <= 840:
            raise PrivacyError("INVALID_INPUT")
        p.setdefault("history_opt_in", False)
        p.setdefault("revision", 0)
        if type(p["history_opt_in"]) is not bool or type(p["revision"]) is not int or p["revision"] < 0:
            raise PrivacyError("INVALID_INPUT")
        if "negotiation_opt_in" in p and type(p["negotiation_opt_in"]) is not bool:
            raise PrivacyError("INVALID_INPUT")
        if "social_preferences" in p:
            from .social import validate_preferences
            validate_preferences(p["social_preferences"])
        self._repo.put(p)

    def register_opportunity(self, scope, opportunity):
        identifier(scope)
        window(opportunity)
        identifier(opportunity.get("opportunity_id"))
        identifier(opportunity.get("campus"))
        with self._lock:
            if (scope, opportunity["opportunity_id"]) in self._activities:
                raise PrivacyError("AUTHORIZATION_FAILED")
            if any(s == scope and o != opportunity["opportunity_id"] for s, o in self._opportunities):
                raise PrivacyError("AUTHORIZATION_FAILED")
            key = (scope, opportunity["opportunity_id"])
            if key in self._opportunities and self._opportunities[key] != opportunity:
                raise PrivacyError("PROPOSAL_STALE")
            self._opportunities[key] = deepcopy(opportunity)

    def register_activity(self, discovery_scope: str, activity: Mapping[str, Any]) -> None:
        """Trusted discovery request, not a live catalog event or enrollment."""
        from .social import validate_activity
        identifier(discovery_scope)
        validate_activity(activity)
        with self._lock:
            key = (discovery_scope, activity["activity_id"])
            if key in self._opportunities:
                raise PrivacyError("AUTHORIZATION_FAILED")
            if key in self._activities and self._activities[key] != activity:
                raise PrivacyError("PROPOSAL_STALE")
            self._activities[key] = deepcopy(activity)

    def bind_session(self, session_id, scope, member_refs, activity_id=None):
        identifier(session_id)
        identifier(scope)
        if not isinstance(member_refs, list) or not member_refs:
            raise PrivacyError("INVALID_INPUT")
        for ref in member_refs:
            identifier(ref)
        if len(member_refs) != len(set(member_refs)):
            raise PrivacyError("INVALID_INPUT")
        if activity_id is not None:
            identifier(activity_id)
        binding = (scope, frozenset(member_refs))
        with self._lock:
            if session_id in self._sessions and self._sessions[session_id] != binding:
                raise PrivacyError("AUTHORIZATION_FAILED")
            if session_id in self._sessions and self._session_activities.get(session_id) != activity_id:
                raise PrivacyError("AUTHORIZATION_FAILED")
            self._sessions[session_id] = binding
            self._session_activities[session_id] = activity_id

    def owner(self, verified_student_ref):
        """Trusted bootstrap only; production must verify session identity first."""
        return Owner(self, verified_student_ref)

    def evaluator(self, session_id):
        if session_id not in self._sessions:
            raise PrivacyError("AUTHORIZATION_FAILED")
        return Evaluator(self, session_id)

    def _active(self, ref, scope, matching=False):
        p = self._repo.get(ref, scope)
        if (not p["authorized"] or (matching and not p["matching_opt_in"])
                or (p.get("expires_at") and instant(p["expires_at"]) <= self._clock())):
            raise PrivacyError("CONSENT_REQUIRED")
        return p

    def _declined(self, profile, activity_id):
        ref, scope = profile["student_ref"], profile["activity_scope"]
        if (ref, scope, activity_id) in self._declines:
            return True
        joined = profile.get("joined_activity")
        return bool(joined and (ref, joined["discovery_scope"], joined["activity_id"]) in self._declines)

    def _mutate(self, ref, scope, request_id, operation, body, action):
        if not isinstance(request_id, str) or not request_id:
            raise PrivacyError("REQUEST_ID_REQUIRED")
        key = (ref, scope, request_id)
        fingerprint = digest([operation, body])
        with self._lock:
            if key in self._requests:
                if self._requests[key] != fingerprint:
                    raise PrivacyError("REQUEST_ID_CONFLICT")
                return
            action()
            self._requests[key] = fingerprint
            self._audit.append(operation)

    @staticmethod
    def public_evaluation(result):
        # Deliberately omit identity, codes, hints, penalties and arbitrary input.
        if not isinstance(result, Mapping) or type(result.get("feasible")) is not bool:
            raise PrivacyError("INVALID_INPUT")
        return {"reason_category": "constraints_satisfied" if result["feasible"] else "constraint_conflict",
                "synthetic": True}


class Owner:
    def __init__(self, service, ref):
        self._s, self._ref = service, ref

    def _identity(self, ref):
        if ref != self._ref:
            raise PrivacyError("AUTHORIZATION_FAILED")

    def opt_in(self, student_ref: str, activity_scope: str, consents: Mapping[str, Any]) -> None:
        self._identity(student_ref)
        if not isinstance(consents, Mapping):
            raise PrivacyError("INVALID_INPUT")
        consents = deepcopy(consents)
        allowed = {"authorized", "matching_opt_in", "introduction_opt_in", "history_opt_in", "negotiation_opt_in"}
        if not set(consents) <= allowed | {"request_id", "expires_at"}:
            raise PrivacyError("INVALID_INPUT")
        if any(type(v) is not bool for k, v in consents.items() if k in allowed):
            raise PrivacyError("INVALID_INPUT")
        if "expires_at" in consents:
            if instant(consents["expires_at"]) <= self._s._clock():
                raise PrivacyError("CONSENT_REQUIRED")
        def apply():
            p = self._s._repo.get(student_ref, activity_scope)
            p.update({k: v for k, v in consents.items() if k != "request_id"})
            p["revision"] += 1
            self._s._repo.put(p)
        self._s._mutate(student_ref, activity_scope, consents.get("request_id"), "consent", consents, apply)

    def revoke(self, activity_scope, request_id):
        self.opt_in(self._ref, activity_scope, {"authorized": False, "matching_opt_in": False,
                    "introduction_opt_in": False, "history_opt_in": False, "negotiation_opt_in": False,
                    "request_id": request_id})

    withdraw = revoke

    def purge(self, activity_scope, request_id):
        """Delete private profile and grants. Keep only replay/probe tombstones."""
        def apply():
            self._s._repo.purge(self._ref, activity_scope)
            self._s._exceptions = {e for e in self._s._exceptions if e[:2] != (self._ref, activity_scope)}
            self._s._introductions = {i for i in self._s._introductions
                                      if not (i[0] == activity_scope and self._ref in i[2:4])}
            self._s._pending_exceptions = {k: v for k, v in self._s._pending_exceptions.items()
                                            if k[:2] != (self._ref, activity_scope)}
            self._s._private_decisions = {k: v for k, v in self._s._private_decisions.items()
                                          if k[:2] != (self._ref, activity_scope)}
        self._s._mutate(self._ref, activity_scope, request_id, "purge", {}, apply)

    def update_preferences(self, activity_scope, changes, request_id):
        allowed = {"hard_budget_cap_cents", "blocked_windows", "available_windows", "soft_preferences",
                   "shareable_interests", "campus", "required_conditions", "social_preferences"}
        if not isinstance(changes, Mapping) or not set(changes) <= allowed:
            raise PrivacyError("INVALID_INPUT")
        changes = deepcopy(changes)
        def apply():
            p = self._s._repo.get(self._ref, activity_scope)
            p.update(deepcopy(changes))
            p["revision"] += 1
            self._s.seed_profile(p)
        self._s._mutate(self._ref, activity_scope, request_id, "preferences", changes, apply)

    def find_mutual_candidates(self, activity_scope: str, opportunity_id: str, limit: int) -> list[CandidateDisplay]:
        if type(limit) is not int or not 1 <= limit <= 20:
            raise PrivacyError("INVALID_INPUT")
        with self._s._lock:
            me = self._s._active(self._ref, activity_scope, True)
            key = (self._ref, activity_scope)
            if self._s._search_counts.get(key, 0) >= self._s._limit:
                raise PrivacyError("EVALUATION_LIMIT_REACHED")
            self._s._search_counts[key] = self._s._search_counts.get(key, 0) + 1
            activity = self._s._activities.get((activity_scope, opportunity_id))
            opportunity = self._s._opportunities.get((activity_scope, opportunity_id))
            if not opportunity and not activity:
                raise PrivacyError("CONSENT_REQUIRED")
            start, end = window(activity or opportunity)
            def compatible(p):
                if self._s._declined(p, opportunity_id):
                    return False
                if activity:
                    from .social import matches
                    return matches(p, activity)
                if p.get("campus") != opportunity["campus"]:
                    return False
                if not any(a <= start and end <= b for a, b in map(window, p.get("available_windows", []))):
                    return False
                return not any(start < b and a < end for a, b in map(window, p["blocked_windows"]))
            if not compatible(me):
                return []
            result = []
            for p in sorted(self._s._repo.list_scope(activity_scope), key=lambda p: p["student_ref"]):
                if p["student_ref"] == self._ref:
                    continue
                try:
                    self._s._active(p["student_ref"], activity_scope, True)
                except PrivacyError:
                    continue
                if compatible(p):
                    result.append({"student_ref": p["student_ref"], "shared_interests": sorted(
                        set(me["shareable_interests"]) & set(p["shareable_interests"])), "synthetic": True})
            return result[:limit]

    def join_activity(self, discovery_scope: str, activity_id: str, participation_scope: str, request_id: str) -> None:
        """Explicit owner enrollment creates a separate negotiation permission."""
        identifier(participation_scope)
        def apply():
            from .social import matches
            p = self._s._active(self._ref, discovery_scope, True)
            activity = self._s._activities.get((discovery_scope, activity_id))
            if not activity or self._s._declined(p, activity_id) or not matches(p, activity):
                raise PrivacyError("CONSENT_REQUIRED")
            if any(r["student_ref"] == self._ref for r in self._s._repo.list_scope(participation_scope)):
                raise PrivacyError("AUTHORIZATION_FAILED")
            p.update(activity_scope=participation_scope, matching_opt_in=False, introduction_opt_in=False,
                     negotiation_opt_in=True, history_opt_in=False, revision=0, joined_activity={"discovery_scope": discovery_scope,
                         "activity_id": activity_id, "query_hash": digest(activity)})
            self._s.seed_profile(p)
        self._s._mutate(self._ref, discovery_scope, request_id, "join_activity",
                        [activity_id, participation_scope], apply)

    def decline_activity(self, activity_scope: str, activity_id: str, request_id: str) -> None:
        identifier(activity_id)
        def apply():
            self._s._repo.get(self._ref, activity_scope)
            self._s._declines.add((self._ref, activity_scope, activity_id))
        self._s._mutate(self._ref, activity_scope, request_id, "decline_activity", activity_id, apply)

    def approve_introduction(self, scope, opportunity_id, other_ref, request_id):
        def apply():
            p = self._s._active(self._ref, scope, True)
            if not p["introduction_opt_in"]:
                raise PrivacyError("CONSENT_REQUIRED")
            self._s._introductions.add((scope, opportunity_id, self._ref, other_ref, p["revision"]))
        self._s._mutate(self._ref, scope, request_id, "introduction", [opportunity_id, other_ref], apply)

    def introduction(self, scope, opportunity_id, other_ref):
        with self._s._lock:
            candidates = self.find_mutual_candidates(scope, opportunity_id, 20)
            if other_ref not in {c["student_ref"] for c in candidates}:
                raise PrivacyError("CONSENT_REQUIRED")
            for a, b in ((self._ref, other_ref), (other_ref, self._ref)):
                p = self._s._active(a, scope, True)
                if not p["introduction_opt_in"] or (scope, opportunity_id, a, b, p["revision"]) not in self._s._introductions:
                    raise PrivacyError("CONSENT_REQUIRED")
            return {"member_refs": [self._ref, other_ref], "synthetic": True}

    def approve_private_exception(self, scope, plan, explicit_approval, request_id):
        plan = deepcopy(plan)
        validate_plan(plan)
        if explicit_approval is not True:
            raise PrivacyError("PRIVATE_EXCEPTION_PENDING")
        def apply():
            evaluator = self._s.evaluator(plan["session_id"])
            p = evaluator._authorize(self._ref, plan)
            if p["activity_scope"] != scope:
                raise PrivacyError("AUTHORIZATION_FAILED")
            self._s._exceptions.add((self._ref, scope, p["revision"], digest(plan)))
            self._s._private_decisions[self._ref, scope, p["revision"], digest(plan)] = True
        self._s._mutate(self._ref, scope, request_id, "exception", plan, apply)

    def revoke_private_exception(self, scope, plan, request_id):
        plan = deepcopy(plan)
        validate_plan(plan)
        def apply():
            p = self._s.evaluator(plan["session_id"])._authorize(self._ref, plan)
            if p["activity_scope"] != scope:
                raise PrivacyError("AUTHORIZATION_FAILED")
            self._s._exceptions.discard((self._ref, scope, p["revision"], digest(plan)))
            self._s._private_decisions[self._ref, scope, p["revision"], digest(plan)] = False
        self._s._mutate(self._ref, scope, request_id, "exception_revoked", plan, apply)

    def pending_private_exceptions(self, scope: str) -> list[Mapping[str, Any]]:
        """Owner-only inbox. Never pass these proposed personal costs to a group."""
        with self._s._lock:
            p = self._s._active(self._ref, scope)
            result = []
            seen = set()
            for (ref, activity_scope, request_id), entry in self._s._pending_exceptions.items():
                if (ref, activity_scope) != (self._ref, scope) or entry["status"] != "pending" or entry["revision"] != p["revision"]:
                    continue
                plan = entry["plan"]
                decision_key = (ref, scope, p["revision"], digest(plan))
                if decision_key in seen or decision_key in self._s._private_decisions:
                    continue
                seen.add(decision_key)
                result.append({"request_id": request_id, "plan_id": plan["plan_id"], "version": plan["version"],
                               "start_at": plan["start_at"], "end_at": plan["end_at"],
                               "proposed_cost_cents": plan["estimated_cost_cents_by_ref"][self._ref], "synthetic": True})
            return result

    def respond_private_exception(self, scope: str, pending_request_id: str, approved: bool, request_id: str) -> None:
        if type(approved) is not bool:
            raise PrivacyError("INVALID_INPUT")
        def apply():
            entry = self._s._pending_exceptions.get((self._ref, scope, pending_request_id))
            if not entry:
                raise PrivacyError("AUTHORIZATION_FAILED")
            plan = entry["plan"]
            p = self._s.evaluator(plan["session_id"])._authorize(self._ref, plan)
            if entry["revision"] != p["revision"] or entry["status"] != "pending":
                raise PrivacyError("PROPOSAL_STALE")
            key = (self._ref, scope, p["revision"], digest(plan))
            if approved:
                self._s._exceptions.add(key)
            self._s._private_decisions[key] = approved
            entry["status"] = "approved" if approved else "declined"
        self._s._mutate(self._ref, scope, request_id, "exception_response", [pending_request_id, approved], apply)


class Evaluator:
    def __init__(self, service, session):
        self._s, self._session = service, session

    def _authorize(self, ref, plan):
        validate_plan(plan)
        scope, members = self._s._sessions[self._session]
        proposed_members = plan.get("member_refs", [])
        if not isinstance(proposed_members, list) or not all(isinstance(m, str) for m in proposed_members):
            raise PrivacyError("INVALID_INPUT")
        if plan.get("session_id") != self._session or ref not in members or set(proposed_members) != members:
            raise PrivacyError("AUTHORIZATION_FAILED")
        if plan["opportunity_id"] is not None and (scope, plan["opportunity_id"]) not in self._s._opportunities:
            raise PrivacyError("AUTHORIZATION_FAILED")
        p = self._s._active(ref, scope)
        activity_id = self._s._session_activities.get(self._session)
        if activity_id is not None and plan.get("activity_id") != activity_id:
            raise PrivacyError("AUTHORIZATION_FAILED")
        if p.get("negotiation_opt_in", "social_preferences" not in p) is not True:
            raise PrivacyError("CONSENT_REQUIRED")
        if "social_preferences" in p and activity_id is None:
            raise PrivacyError("AUTHORIZATION_FAILED")
        if self._s._declined(p, plan.get("activity_id") or plan["opportunity_id"] or plan["plan_id"]):
            raise PrivacyError("CONSENT_REQUIRED")
        joined = p.get("joined_activity")
        if joined:
            activity = self._s._activities.get((joined["discovery_scope"], joined["activity_id"]))
            if not activity or digest(activity) != joined["query_hash"]:
                raise PrivacyError("PROPOSAL_STALE")
            if (plan.get("activity_id") != joined["activity_id"] or plan.get("activity_kind") != activity["activity_kind"]
                    or plan.get("rough_area") != activity["rough_area"] or len(proposed_members) != activity["group_size"]
                    or window(plan) != window(activity)):
                raise PrivacyError("AUTHORIZATION_FAILED")
        return p

    def evaluate_plan_private(self, student_ref: str, plan: Mapping[str, Any]) -> PrivateEvaluation:
        plan = deepcopy(plan)
        with self._s._lock:
            p = self._authorize(student_ref, plan)
            start, end = window(plan)
            cost = plan["estimated_cost_cents_by_ref"][student_ref]
            # Lifetime per participant/activity: new sessions and revisions cannot reset probing.
            key = (student_ref, p["activity_scope"])
            count = self._s._counts.get(key, 0)
            if count >= self._s._limit:
                raise PrivacyError("EVALUATION_LIMIT_REACHED")
            self._s._counts[key] = count + 1
            issues, hints = [], []
            if cost > p["hard_budget_cap_cents"]:
                issues.append("HARD_BUDGET")
                hints.append("prefer_lower_cost")
            if any(start < b and a < end for a, b in map(window, p["blocked_windows"])):
                issues.append("HARD_AVAILABILITY")
                hints.append("try_alternate_day")
            if "available_windows" in p and not any(a <= start and end <= b for a, b in map(window, p["available_windows"])):
                issues.append("HARD_AVAILABILITY")
                hints.append("try_alternate_day")
            # Private required conditions must be affirmatively verified in the plan.
            if not all(plan.get("verified_conditions", {}).get(c) is True for c in p.get("required_conditions", [])):
                issues.append("HARD_ACCESS")
                hints.append("verify_required_access")
            from .social import evaluate_policy
            social_issues, social_hints, social_penalty = evaluate_policy(p, plan)
            issues.extend(social_issues)
            hints.extend(social_hints)
            exception = (student_ref, p["activity_scope"], p["revision"], digest(plan)) in self._s._exceptions
            soft = p["soft_preferences"]
            # Convert to student's configured fixed offset, never trust caller's displayed hour.
            from datetime import timedelta
            local_hour = start.astimezone(timezone(timedelta(minutes=p.get("utc_offset_minutes", -420)))).hour
            penalty = (0.5 if local_hour < soft.get("avoid_before_local_hour", 0) else 0.0)
            penalty += 0.25 if soft.get("prefers_low_cost") and cost >= 5000 else 0.0
            penalty += social_penalty
            self._s._audit.append("evaluation")
            return {"session_id": self._session, "plan_id": plan["plan_id"], "version": plan["version"],
                    "student_ref": student_ref, "feasible": not issues or exception,
                    "requires_private_exception": bool(issues) and not exception,
                    "internal_issue_codes": [] if exception else sorted(set(issues)),
                    "soft_penalty": penalty, "counteroffer_hints": sorted(set(hints)), "synthetic": True}

    def propose_private_counteroffer(self, student_ref: str, plan: Mapping[str, Any]) -> CounterofferHints:
        return {"counteroffer_hints": self.evaluate_plan_private(student_ref, plan)["counteroffer_hints"], "synthetic": True}

    def request_private_exception(self, student_ref: str, plan: Mapping[str, Any], request_id: str) -> Mapping[str, Any]:
        """Queue a protected owner request; never send a message or approve it."""
        plan = deepcopy(plan)
        with self._s._lock:
            p = self._authorize(student_ref, plan)
            scope = p["activity_scope"]
            def apply():
                decision_key = (student_ref, scope, p["revision"], digest(plan))
                prior = self._s._private_decisions.get(decision_key)
                # One owner prompt per exact proposal/revision, even if the
                # coordinator retries with different request IDs.
                for (ref, entry_scope, _), existing in list(self._s._pending_exceptions.items()):
                    if (ref, entry_scope) == (student_ref, scope) and existing["revision"] == p["revision"] and digest(existing["plan"]) == digest(plan):
                        self._s._pending_exceptions[student_ref, scope, request_id] = existing
                        return
                if prior is not None:
                    status = "approved" if prior else "declined"
                else:
                    result = self.evaluate_plan_private(student_ref, plan)
                    status = "pending" if result["requires_private_exception"] else "not_required"
                self._s._pending_exceptions[student_ref, scope, request_id] = {
                    "status": status, "revision": p["revision"], "plan": deepcopy(plan)}
            self._s._mutate(student_ref, scope, request_id, "exception_request", plan, apply)
            entry = self._s._pending_exceptions[student_ref, scope, request_id]
            if entry["revision"] != p["revision"]:
                raise PrivacyError("PROPOSAL_STALE")
            decision = self._s._private_decisions.get((student_ref, scope, p["revision"], digest(plan)))
            status = entry["status"] if decision is None else ("approved" if decision else "declined")
            return {"status": status, "synthetic": True}
