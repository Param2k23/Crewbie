"""Compose the six existing modules. No private profile is exposed over HTTP."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from threading import RLock
import hashlib
import json
from pathlib import Path

from integrations.cubbie.core import parse_student_intent
from integrations.cubbie.handoff import request_handoff
from services.opportunities import OpportunityCatalog, ActivityFixtureProvider, DiscoveryService
from services.opportunities.models import timestamp
from services.opportunities.providers import FixtureProvider
from services.participants.service import ParticipantService, PrivacyError
from services.negotiation.coordinator import NegotiationCoordinator
from services.negotiation.models import NegotiationConfig, ConsentRequired
from services.commitments.service import CommitmentService
from services.realtime.sink import MemoryEventSink
from apps.chat_bot.host import CrewbieHost
from apps.chat_bot.providers import MockMessagingProvider

NOW = "2026-10-24T19:00:00Z"
MEMBERS = ["stu_alex", "stu_maya", "stu_jordan", "stu_taylor"]


class BoundaryError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class PublicEvents:
    """Normalize producer dialects, preserve IDs for dedupe, order all emitters."""
    def __init__(self):
        self.sink = MemoryEventSink()
        self.lock = RLock()
        self.seq = 0
        self.correlation = {}
        self.authority = {}

    def emit(self, raw):
        event = deepcopy(raw)
        actor, kind = event["actor_ref"], event["type"]
        if actor == "coordination_engine" and kind in {"approval_requested", "proposal_confirmed"}:
            return  # A5 alone attests delivery and human commitment.
        with self.lock:
            key = (event["session_id"], actor, event["event_id"])
            if key in self.authority:
                return
            self.seq += 1
            event["event_id"] = f"integrated_{self.seq:08d}"
            event["timestamp"] = (datetime(2026, 10, 24, 19, tzinfo=timezone.utc)
                                  + timedelta(seconds=self.seq)).isoformat()
            p = event["payload"]
            if "balance" in p:
                p["fairness_category"] = p.pop("balance")
            if "error_code" in p:
                p["failure_code"] = p.pop("error_code")
            if kind == "proposal_revised":
                # The new winner is not known until proposal_ready arrives.
                p["summary"] = "Proposal invalidated; fresh approvals required"
            if event["session_id"] in self.correlation:
                p["request_id"] = self.correlation[event["session_id"]]
            self.sink.emit(event)
            self.authority[key] = True

    def publish(self, sid, kind, **payload):
        self.emit({"event_id": f"runtime_{self.seq + 1}", "session_id": sid,
                   "timestamp": NOW, "type": kind, "actor_ref": "integration",
                   "visibility": "group_safe", "payload": payload, "synthetic": True})


class PrivateAgents:
    """Only session-scoped capabilities; cache hints to avoid extra private probes."""
    def __init__(self, service):
        self.service = service
        self.hints = {}
        self.calls = []

    def evaluate_plan_private(self, ref, plan):
        try:
            result = self.service.evaluator(plan["session_id"], minimized_costs=True).evaluate_plan_private(ref, plan)
        except PrivacyError as e:
            if str(e) in {"CONSENT_REQUIRED", "AUTHORIZATION_FAILED"}:
                raise ConsentRequired() from None
            raise
        result = deepcopy(result)
        names = {"try_alternate_day": "prefer_different_day"}
        result["counteroffer_hints"] = [names.get(h, h) for h in result["counteroffer_hints"]]
        self.hints[(ref, plan["session_id"], plan["version"])] = result["counteroffer_hints"]
        self.calls.append((plan["session_id"], ref, plan["version"]))
        return result

    def propose_private_counteroffer(self, ref, plan):
        return {"hints": self.hints.get((ref, plan["session_id"], plan["version"]), [])}


class ScopedConsent:
    """Separate explicit acceptance grants, checked against current A3 authorization."""
    def __init__(self, service):
        self.service = service
        self.grants = set()

    def has_consent(self, ref, scope, purpose):
        if (ref, scope, purpose) not in self.grants:
            return False
        try:
            p = self.service._active(ref, scope, matching=purpose == "matching")
            return purpose != "introduction" or p["introduction_opt_in"] is True
        except PrivacyError:
            return False


class Runtime:
    """In-memory synthetic sandbox. Live messages may drive synthetic students only."""
    def __init__(self, provider=None):
        self.lock = RLock()
        self.events = PublicEvents()
        self.participants = ParticipantService(clock=lambda: timestamp(NOW))
        self.evaluator = PrivateAgents(self.participants)
        self.consent = ScopedConsent(self.participants)
        self.commitments = CommitmentService(event_sink=self.events, consent=self.consent)
        self.coordinator = NegotiationCoordinator(self.evaluator, self.commitments, self.events,
            config=NegotiationConfig(max_candidates=3, target_feasible=1, max_rounds=3))
        self.provider = provider if provider is not None else MockMessagingProvider()
        self.catalog = OpportunityCatalog(ActivityFixtureProvider(), now=lambda: timestamp(NOW))
        self.discovery = DiscoveryService(self.catalog)
        self.sessions = {}
        self.requests = {}
        self.hosts = {}

    def seed(self, scenario, *, request_id=None, matching=False, sharing=False, introduction=False):
        """Explicit synthetic participant script. These grants are never real user consent."""
        if scenario not in {"unlocks", "evening", "weekend"}:
            raise BoundaryError("INVALID_SCENARIO")
        rid = request_id or "seed_" + scenario
        body = [scenario, matching, sharing, introduction]
        with self.lock:
            if rid in self.requests:
                old, sid = self.requests[rid]
                if old != body:
                    raise BoundaryError("REQUEST_ID_CONFLICT")
                # A retry must still check current consent, not revive a withdrawn session.
                if not all(self.consent.has_consent(r, sid, "plan_acceptance") for r in MEMBERS):
                    raise BoundaryError("CONSENT_REQUIRED")
                return self.snapshot(sid)
            sid = "session_" + hashlib.sha256(rid.encode()).hexdigest()[:12]
            if scenario == "unlocks" and not (matching is True and sharing is True and introduction is True):
                raise BoundaryError("CONSENT_REQUIRED")
            start, end = {"unlocks": ("2026-10-26T12:00:00-07:00", "2026-10-26T14:00:00-07:00"),
                          "evening": ("2026-11-06T17:00:00-07:00", "2026-11-08T23:00:00-07:00"),
                          "weekend": ("2026-11-13T08:00:00-07:00", "2026-11-16T20:00:00-07:00")}[scenario]
            discovery = self.discovery
            if scenario == "unlocks":
                discovery = DiscoveryService(OpportunityCatalog(
                    FixtureProvider(Path(__file__).with_name("fixtures") / "unlocks.json"), now=lambda: timestamp(NOW)))
            discovered = discovery.recommend(start, end, campus="Tempe", include_ideas=True)
            opportunity = None
            if scenario == "unlocks":
                sourced = [r for r in discovered["recommendations"] if r.get("opportunity")]
                if not sourced:
                    raise BoundaryError("SOURCE_UNAVAILABLE")
                opportunity = sourced[0]["opportunity"]
                self.participants.register_opportunity(sid, opportunity)
                self.events.publish(sid, "opportunity_discovered", opportunity_id=opportunity["opportunity_id"])
            for i, ref in enumerate(MEMBERS):
                profile = {"student_ref": ref, "activity_scope": sid, "authorized": True,
                           "matching_opt_in": matching is True, "introduction_opt_in": introduction is True,
                           "negotiation_opt_in": True, "hard_budget_cap_cents": 9000 if scenario == "weekend" and i == 2 else 15000,
                           "blocked_windows": [], "available_windows": [{"start_at": start, "end_at": end}],
                           "campus": "Tempe", "soft_preferences": {}, "shareable_interests": ["games"], "synthetic": True}
                if scenario == "evening" and i == 1:
                    profile["blocked_windows"] = [{"start_at": start, "end_at": "2026-11-06T20:00:00-07:00"}]
                if scenario == "weekend" and i == 3:
                    profile["blocked_windows"] = [{"start_at": "2026-11-13T00:00:00-07:00", "end_at": "2026-11-14T23:59:00-07:00"}]
                self.participants.seed_profile(profile)
                self.consent.grants.add((ref, sid, "plan_acceptance"))
                if matching:
                    self.consent.grants.add((ref, sid, "matching"))
                if introduction:
                    self.consent.grants.add((ref, sid, "introduction"))
            req = {"session_id": sid, "request_id": rid, "activity_scope": sid,
                   "member_refs": MEMBERS, "window_start": start, "window_end": end,
                   "mode": "intent_first", "intent": {"kind": "weekend_trip" if scenario == "weekend" else "dinner_games"},
                   "slot_limit": 1, "rules": {"min_attendees": 4, "max_duration_hours": 36 if scenario == "weekend" else 6,
                   "latest_end_local_hour": 23}, "cost_tiers_cents": [1000, 2000, 3000, 8800, 11800], "synthetic": True}
            context = {"authorized": True, "student_ref": MEMBERS[0], "campus": "Tempe",
                       "availability_start": start, "availability_end": end, "synthetic": True}
            brief = parse_student_intent("Find a crew" if scenario == "unlocks" else "Plan a group trip" if scenario == "weekend" else "Plan group dinner", context)
            if opportunity:
                brief.update(opportunity_id=opportunity["opportunity_id"], wants_companion=True, intent="find_companion")
                req.update(mode="seeded", opportunity=opportunity, group_origin="matched",
                           consent_context={"introduction_consent_refs": MEMBERS},
                           seed_plans=[{"title": opportunity["title"], "start_at": opportunity["start_at"],
                           "end_at": opportunity["end_at"], "estimated_cost_cents_by_ref": {r: 0 for r in MEMBERS},
                           "activities": ["Visit sourced synthetic opportunity"], "requires_transport": False}])
                context.update(activity_scope=sid, consent_scope=sid, consent_brief_id=brief["brief_id"],
                               sharing_opt_in=sharing, matching_opt_in=matching)
                class Handoff:
                    def submit(inner, request):
                        self.events.publish(sid, "match_requested", opportunity_id=opportunity["opportunity_id"])
                        matches = self.participants.owner(MEMBERS[0]).find_mutual_candidates(sid, opportunity["opportunity_id"], 4)
                        if {m["student_ref"] for m in matches} != set(MEMBERS[1:]):
                            raise BoundaryError("CONSENT_REQUIRED")
                        for i, left in enumerate(MEMBERS):
                            for right in MEMBERS[i+1:]:
                                self.participants.owner(left).approve_introduction(sid, opportunity["opportunity_id"], right, f"intro_{left}_{right}")
                                self.participants.owner(right).approve_introduction(sid, opportunity["opportunity_id"], left, f"intro_{right}_{left}")
                                self.participants.owner(left).introduction(sid, opportunity["opportunity_id"], right)
                        self.events.publish(sid, "match_suggested", group_size=4)
                        return {"status": "consented_handoff", "synthetic": True}
                request_handoff(brief, context, rid, gateway=Handoff())
            self.participants.bind_session(sid, sid, MEMBERS)
            self.sessions[sid] = {"scenario": scenario, "request": req, "opportunity": opportunity, "brief": brief,
                                  "synthetic": True, "changes": {}}
            self.hosts[sid] = CrewbieHost(self.commitments, self.provider, sid, {r: r for r in MEMBERS},
                                        session_id=sid, negotiation=self, trusted_identity_sources=("mock", "provider_verified"))
            self.coordinator.start_negotiation(req)
            self.present(sid)
            self.requests[rid] = (body, sid)
            return self.snapshot(sid)

    def present(self, sid):
        snap = self.coordinator.get_public_snapshot(sid)
        if not snap["plan"]:
            return self.hosts[sid].announce_no_solution(sid)
        plan = deepcopy(snap["plan"])
        plan.pop("estimated_cost_cents_by_ref", None)
        plan.pop("estimated_total_cents", None)
        plan.update(validated=True, activity_scope=sid,
                    cost_summary="Synthetic estimate; individual amounts withheld. No booking or enrollment.",
                    open_questions=plan.pop("unverified_items", []))
        return self.hosts[sid].present_proposal(plan)

    def snapshot(self, sid):
        if sid not in self.sessions:
            raise BoundaryError("NOT_FOUND")
        snap = self.coordinator.get_public_snapshot(sid)
        p = self.commitments.active_proposal(sid)
        summary = self.commitments.get_commitment_summary(sid, p.plan_id, p.version) if p else None
        # A4's cached confirmed state is never authoritative after a retraction.
        if snap["state"] == "confirmed" and (not summary or not summary["confirmed"]):
            snap["state"] = "approval_pending"
        snap.update(commitments=summary, mode="DEMO/SYNTHETIC", booking_confirmed=False)
        return snap

    def message(self, sid, ref, text, request_id, *, version=None, identity_source="mock"):
        with self.lock:
            if sid not in self.sessions:
                raise BoundaryError("NOT_FOUND")
            result = self.hosts[sid].handle_chat_message({"session_id": sid, "member_ref": ref, "text": text,
                "request_id": request_id, "identity_source": identity_source, "referenced_version": version})
            # The injected planner completes synchronously, unlike A5's standalone async port.
            if result.get("action") in {"change_requested", "planning_requested"}:
                self.hosts[sid]._outstanding.pop(sid, None)
            if result.get("action") != "duplicate":
                snap = self.snapshot(sid)
                if snap["commitments"] and snap["commitments"]["confirmed"]:
                    self.coordinator.confirm_if_approved(sid)
                p = self.commitments.active_proposal(sid)
                if p and result.get("action") == "cancellation_requested":
                    self.events.publish(sid, "proposal_revised", version=p.version + 1,
                                        reason_category="cancelled", summary="Proposal cancelled; approvals invalidated")
                    self.commitments.cancel_proposal(sid)
                    self.coordinator.cancel_negotiation(sid)
                elif p and result.get("reply_state") == "declined":
                    self.coordinator.record_member_decline(sid, ref)
                    self.present(sid)
                elif p and result.get("reply_state") == "withdrawn":
                    self.change(sid, {"request_id": "response_" + request_id, "synthetic_confirmed": True,
                        "changed_constraint_ref": {"member_ref": ref, "kind": "withdraw", "value": "withdraw"}})
            return {"action": result, "snapshot": self.snapshot(sid)}

    def change(self, sid, request):
        with self.lock:
            data = self.sessions.get(sid)
            if not data or data["synthetic"] is not True or request.get("synthetic_confirmed") is not True:
                raise BoundaryError("SYNTHETIC_ONLY")
            rid = request.get("request_id")
            change = request.get("changed_constraint_ref", {})
            ref, kind, value = change.get("member_ref"), change.get("kind"), change.get("value")
            if not isinstance(rid, str) or not rid or ref not in MEMBERS:
                raise BoundaryError("INVALID_CHANGE")
            if rid in data["changes"]:
                if data["changes"][rid] != change:
                    raise BoundaryError("REQUEST_ID_CONFLICT")
                return self.snapshot(sid)
            if kind == "hard_budget":
                if type(value) is not int or value < 0:
                    raise BoundaryError("INVALID_CHANGE")
                updates = {"hard_budget_cap_cents": value}
            elif kind == "block_window" and value in {"blocks_all_days", "blocks_current_day"}:
                req = data["request"]
                plan = self.snapshot(sid)["plan"]
                updates = {"blocked_windows": [{"start_at": plan["start_at"] if value == "blocks_current_day" and plan else req["window_start"],
                                                "end_at": plan["end_at"] if value == "blocks_current_day" and plan else req["window_end"]}]}
            elif kind == "withdraw" and value == "withdraw":
                updates = None
            else:
                raise BoundaryError("INVALID_CHANGE")
            self.events.correlation[sid] = rid
            try:
                owner = self.participants.owner(ref)
                if updates is None:
                    owner.revoke(sid, rid)
                    self.commitments.revoke_consent(sid, ref)
                    self.coordinator.withdraw_participant(sid, ref)
                else:
                    owner.update_preferences(sid, updates, rid)
                    self.coordinator.revise_negotiation(sid, {"student_ref": ref,
                        "kind": "budget" if kind == "hard_budget" else "availability", "request_id": rid})
                self.present(sid)
                data["changes"][rid] = deepcopy(change)
            finally:
                self.events.correlation.pop(sid, None)
            return self.snapshot(sid)

    def request_proposal(self, req):
        # Host planning is bound to a pre-authorized synthetic session/window.
        sid = req["session_id"]
        if sid not in self.sessions:
            raise BoundaryError("CONSENT_REQUIRED")
        self.present(sid)

    def request_revision(self, req):
        sid = req["session_id"]
        self.coordinator.revise_negotiation(sid, {"kind": "other", "request_id": req["request_id"]})
        self.present(sid)
