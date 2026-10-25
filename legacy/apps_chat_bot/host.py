"""Crewbie Host: the single visible group-chat assistant."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional, Sequence

from services.commitments import CommitmentService, PrivacyViolation, check_outbound
from services.commitments.intent import classify_planning
from services.commitments import models as m
from services.commitments.models import CommitmentError

from . import copy
from .providers import MessagingProvider, ProviderUnavailable

_AMOUNT = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)")
DEFAULT_TRUSTED_IDENTITY = ("mock", "provider_verified")


class CrewbieHost:
    def __init__(
        self,
        service: CommitmentService,
        provider: Optional[MessagingProvider],
        channel_id: str,
        roster: Mapping[str, str],
        *,
        session_id: Optional[str] = None,
        negotiation: Any = None,
        participants: Optional[Sequence[str]] = None,
        trusted_identity_sources: Sequence[str] = DEFAULT_TRUSTED_IDENTITY,
        follow_up_after_s: int = 6 * 3600,
        max_follow_ups: int = 2,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.service = service
        self.provider = provider
        self.channel_id = channel_id
        self.roster = dict(roster)
        self.trusted = set(trusted_identity_sources)
        self.follow_up_after_s = follow_up_after_s
        self.max_follow_ups = max_follow_ups
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.session_id = session_id
        self.negotiation = negotiation  # Agent 04 port (NegotiationClient); None => planner unavailable
        self.participants = set(participants) if participants is not None else set(roster)
        self.group_context: Optional[dict] = None  # set when a consented group is formed
        self.undelivered: list[dict] = []  # group messages the provider never acknowledged
        self._outstanding: dict[str, str] = {}  # session_id -> planning request awaiting A4
        from .groups import GroupFormation
        self.groups = GroupFormation(self)

    # --------------------------------------------------------------- sending
    def _name(self, ref: str) -> str:
        return self.roster.get(ref, ref.removeprefix("stu_").title())

    def _send_group(self, text: str, request_id: str, allowed_amounts: Sequence[str] = ()) -> dict:
        try:
            check_outbound(text, allowed_amounts)
        except PrivacyViolation as e:
            return {"delivery": "blocked", "error_code": "PRIVACY_BLOCKED", "detail": str(e), "text": text}
        try:
            if self.provider is None:
                raise ProviderUnavailable("no messaging provider configured")
            receipt = self.provider.send_group_message(self.channel_id, text, request_id=request_id)
        except ProviderUnavailable:
            self._queue(text, request_id, allowed_amounts)
            return {"delivery": "failed", "error_code": m.PROVIDER_UNAVAILABLE, "text": text}
        if not receipt.acknowledged:
            self._queue(text, request_id, allowed_amounts)
            return {"delivery": "unacknowledged", "error_code": m.PROVIDER_UNAVAILABLE, "text": text}
        return {"delivery": "acknowledged", "error_code": None, "text": text,
                "provider_message_id": receipt.provider_message_id}

    def _queue(self, text: str, request_id: str, allowed_amounts: Sequence[str]) -> None:
        if not request_id.startswith(("present:", "nudge:")) and not any(u["request_id"] == request_id for u in self.undelivered):
            self.undelivered.append({"text": text, "request_id": request_id, "allowed_amounts": list(allowed_amounts)})

    def flush_undelivered(self) -> int:
        """Retry messages that were never acknowledged. Returns how many are still stuck."""
        pending, self.undelivered = self.undelivered, []
        for u in pending:
            self._send_group(u["text"], u["request_id"], u["allowed_amounts"])
        return len(self.undelivered)

    def _send_private(self, member_ref: str, text: str, request_id: str) -> dict:
        try:
            check_outbound(text)
            if self.provider is None:
                raise ProviderUnavailable("no messaging provider configured")
            receipt = self.provider.send_private_message(member_ref, text, request_id=request_id)
        except ProviderUnavailable:
            return {"delivery": "failed", "error_code": m.PROVIDER_UNAVAILABLE}
        except PrivacyViolation as e:
            return {"delivery": "blocked", "error_code": "PRIVACY_BLOCKED", "detail": str(e)}
        return {"delivery": "acknowledged" if receipt.acknowledged else "unacknowledged", "error_code": None,
                "provider_message_id": receipt.provider_message_id}

    # ------------------------------------------------------------- proposals
    def present_proposal(self, public_snapshot: Mapping[str, Any]) -> dict:
        """Register A4's public snapshot and post it. Approvals open only once the post is acknowledged."""
        sid = public_snapshot["session_id"]
        prev = self.service.active_proposal(sid)
        revised_from = prev.version if prev and prev.version < public_snapshot["version"] else None
        summary = self.service.register_proposal(public_snapshot)
        self._outstanding.pop(sid, None)
        snap = self.service.active_proposal(sid).snapshot
        if not summary["validated"]:
            return {"action": "awaiting_validation", "summary": summary, "delivery": "not_sent"}
        text = copy.proposal_message(snap, self.roster, revised_from)
        amounts = _AMOUNT.findall(" ".join(str(snap.get(k, "")) for k in ("cost_summary", "estimate_disclaimer")))
        sent = self._send_group(text, f"present:{sid}:{snap['plan_id']}:{snap['version']}", amounts)
        if sent["delivery"] == "acknowledged":
            self.service.mark_presented(sid, snap["plan_id"], snap["version"])
        return {"action": "proposal_presented" if sent["delivery"] == "acknowledged" else "proposal_not_sent",
                "summary": self.service.get_commitment_summary(sid, snap["plan_id"], snap["version"]), **sent}

    def announce_no_solution(self, session_id: str) -> dict:
        self._outstanding.pop(session_id, None)
        return {"action": "no_solution", **self._send_group(copy.no_solution_message(), f"nosol:{session_id}:{self.clock().isoformat()}")}

    def request_private_exception(self, member_ref: str, session_id: str, plan_id: str, version: int) -> dict:
        """Exception prompts go to the affected member only, never the group."""
        return {"action": "private_exception_requested",
                **self._send_private(member_ref, copy.private_exception_prompt(), f"exc:{session_id}:{plan_id}:{version}:{member_ref}")}

    # ---------------------------------------------------------- chat messages
    def handle_chat_message(self, msg: Mapping[str, Any]) -> dict:
        rid = msg.get("request_id") or msg.get("message_id")
        member = msg.get("member_ref")
        if msg.get("identity_source") not in self.trusted:
            return {"action": "ignored", "error_code": m.IDENTITY_UNVERIFIED, "reply": None, "request_id": rid}
        sid = msg.get("session_id") or self._default_session()
        if member not in self.participants:
            return {"action": "ignored", "error_code": m.NOT_A_PARTICIPANT, "reply": None, "request_id": rid}
        text_in = msg.get("text", "")
        p = self.service.active_proposal(sid) if sid else None
        if sid and rid and (self.service.recall_request(sid, rid) is not None):
            return {"action": "duplicate", "error_code": None, "reply": None, "request_id": rid}
        if self.group_context and re.search(r"\bice ?breaker\b", text_in.lower()):
            ctx = self.group_context
            out = self.suggest_icebreaker(ctx.get("session_id") or sid or "grp", ctx["members"], ctx["activity_scope"],
                                          ctx["kind"], existing_group=True)
            if sid and rid:
                self.service.remember_request(sid, rid, {"kind": "icebreaker"})
            return {"action": "icebreaker", "request_id": rid, "reply": out.get("text"), "error_code": out["error_code"]}
        live = bool(p and p.status in ("open", "confirmed", "revoked"))
        intent = classify_planning(text_in, has_open_proposal=live)
        if intent.kind == "none" and p is not None and p.status != "open":
            intent = classify_planning(text_in, has_open_proposal=False)  # a fresh request after a finished plan
        if intent.kind != "none":
            return self._handle_planning(intent, sid, p, member, rid)
        if p is None:
            return {"action": "ignored", "error_code": m.UNKNOWN_PROPOSAL, "reply": None, "request_id": rid}

        res = self.service.record_approval(
            sid, p.plan_id, p.version, member, msg.get("text", ""),
            request_id=rid, sent_at=msg.get("sent_at"),
            referenced_version=msg.get("referenced_version"),
            reply_scoped=bool(msg.get("reply_to_proposal")),
        )
        action = {"action": res["outcome"], "error_code": res["error_code"], "state": (res["record"] or {}).get("state"),
                  "reply_state": res["reply_state"], "proposal_state": res["proposal_state"],
                  "confirmed_now": res["confirmed_now"], "request_id": rid, "reply": None, "delivery": "none"}
        if res["outcome"] in ("duplicate", "ignored", "kept"):
            return action

        name, version = self._name(member), p.version
        reply = None
        state = res["reply_state"]
        if res["outcome"] == "stale":
            cur = self.service.active_proposal(sid)
            reply = copy.stale_prompt(name, cur.version) if cur else None
        elif res["error_code"] == m.CONSENT_REQUIRED:
            action["private"] = self._send_private(
                member, "I can't record your yes yet because plan-acceptance consent isn't on file for you.", f"consent:{rid}")
        elif res["outcome"] == "clarify" or res["needs_clarification"]:
            if self.service.note_clarified(sid, member):
                reply = copy.clarify_prompt(name, version)
        elif res["outcome"] == "recorded":
            summary = self.service.get_commitment_summary(sid, p.plan_id, version)
            if state == "accepted":
                reply = copy.accepted_ack(name, summary["accepted_count"], summary["required_count"], version)
            elif state == "conditional":
                reply = copy.conditional_prompt(name, version)
            elif state == "declined":
                reply = copy.declined_ack(name, version)
            elif state == "withdrawn":
                reply = copy.withdrawn_ack(name)
        if reply:
            sent = self._send_group(reply, f"reply:{rid}")
            action["delivery"], action["delivery_error"] = sent["delivery"], sent["error_code"]
            action["reply"] = reply
        if res["confirmed_now"]:
            conf = copy.confirmed_message(p.snapshot, self.roster)
            action["confirmation"] = self._send_group(conf, f"confirmed:{sid}:{p.plan_id}:{version}")
        return action

    def _handle_planning(self, intent, sid, p, member, rid) -> dict:
        """Turn a chat request into a structured ask to Agent 04. Never decides feasibility itself."""
        name = self._name(member)
        base = {"request_id": rid, "error_code": None, "reply": None, "state": None}
        if sid is None:
            return {**base, "action": "ignored", "error_code": m.UNKNOWN_PROPOSAL}
        if intent.kind == "cancel_request":
            res = self.service.request_cancellation(sid, member, request_id=rid)
            if res is None or res["outcome"] == "duplicate":
                return {**base, "action": "duplicate" if res else "ignored"}
            reply = copy.cancel_ack(name)
            return {**base, "action": "cancellation_requested", "state": "declined", "reply": reply,
                    **self._delivery(self._send_group(reply, f"reply:{rid}"))}
        if intent.kind == "change_request":
            res = self.service.request_change(sid, member, list(intent.aspects), intent.timeframe, request_id=rid)
            if res is None or res["outcome"] in ("duplicate", "ignored"):
                return {**base, "action": res["outcome"] if res else "ignored"}
            if not self._outstanding.get(sid):
                req = {"request_id": rid, "session_id": sid, "requested_by": member,
                       "base_plan": {"plan_id": p.plan_id, "version": p.version},
                       "aspects": list(intent.aspects), "timeframe_text": intent.timeframe,
                       "member_refs": sorted(p.required)}
                if not self._ask_planner("request_revision", req, sid, rid):
                    return {**base, "action": "planner_unavailable", "error_code": m.PROVIDER_UNAVAILABLE,
                            "state": "conditional", **self._reply_unavailable(rid)}
            reply = copy.change_ack(name, p.version)
            return {**base, "action": "change_requested", "state": "conditional", "reply": reply,
                    **self._delivery(self._send_group(reply, f"reply:{rid}"))}
        # new_plan
        if self._outstanding.get(sid):
            reply = copy.planning_busy()
            self.service.remember_request(sid, rid, {"kind": "planning_busy"}) if rid else None
            return {**base, "action": "planning_in_progress", "reply": reply,
                    **self._delivery(self._send_group(reply, f"reply:{rid}"))}
        req = {"request_id": rid, "session_id": sid, "requested_by": member, "activity_type": intent.activity_type,
               "activity_label": intent.activity_label, "timeframe_text": intent.timeframe,
               "member_refs": sorted(self.participants)}
        if not self._ask_planner("request_proposal", req, sid, rid):
            return {**base, "action": "planner_unavailable", "error_code": m.PROVIDER_UNAVAILABLE,
                    **self._reply_unavailable(rid)}
        reply = copy.planning_ack(intent.activity_label, intent.timeframe)
        return {**base, "action": "planning_requested", "reply": reply, "planning_request": req,
                **self._delivery(self._send_group(reply, f"reply:{rid}"))}

    def _ask_planner(self, method: str, req: dict, sid: str, rid) -> bool:
        if self.negotiation is None:
            return False
        try:
            getattr(self.negotiation, method)(req)
        except ProviderUnavailable:
            return False
        self._outstanding[sid] = rid or "req"
        if rid:
            self.service.remember_request(sid, rid, {"kind": method})
        return True

    def _reply_unavailable(self, rid) -> dict:
        reply = copy.planner_unavailable()
        return {"reply": reply, **self._delivery(self._send_group(reply, f"reply:{rid}"))}

    @staticmethod
    def _delivery(sent: dict) -> dict:
        return {"delivery": sent["delivery"], "delivery_error": sent["error_code"]}

    def _default_session(self) -> Optional[str]:
        if self.session_id:
            return self.session_id
        sessions = {k[0] for k in self.service._active.values()}
        return next(iter(sessions)) if len(sessions) == 1 else None

    def handle_consent_revoked(self, session_id: str, member_ref: str) -> dict:
        summary = self.service.revoke_consent(session_id, member_ref)
        if summary is None:
            return {"action": "ignored"}
        sent = self._send_group(copy.consent_revoked_message(self._name(member_ref)),
                                f"revoked:{session_id}:{member_ref}")
        return {"action": "consent_revoked", "summary": summary, **sent}

    # -------------------------------------------------------------- follow-up
    def follow_up(self, now: Optional[datetime] = None) -> dict:
        """One gentle group nudge for members who are still silent; rate-limited."""
        now = now or self.clock()
        sid = self._default_session()
        if sid is None:
            return {"action": "none"}
        pending = self.service.pending_follow_up(sid, now, self.follow_up_after_s, self.max_follow_ups)
        if not pending:
            return {"action": "none"}
        p = self.service.active_proposal(sid)
        sent = self._send_group(copy.follow_up_message(pending, self.roster, p.version),
                                f"nudge:{sid}:{p.version}:{p.nudge_count + 1}")
        if sent["delivery"] == "acknowledged":
            self.service.note_nudge(sid, now)
        return {"action": "follow_up", "pending": pending, **sent}

    # ----------------------------------------------------- introductions
    def _all_consent(self, refs: Sequence[str], scope: str, purpose: str) -> bool:
        return all(self.service.consent.has_consent(r, scope, purpose) for r in refs)

    def introduce(self, session_id: str, members: Sequence[str], activity_scope: str, context_label: str,
                  approved_interests: Mapping[str, Sequence[str]]) -> dict:
        """Introduce consenting members using only interests they approved for sharing."""
        if not self._all_consent(members, activity_scope, "introduction"):
            return {"action": "blocked", "error_code": m.CONSENT_REQUIRED, "delivery": "none"}
        sets = [{i.lower() for i in approved_interests.get(r, ())} for r in members]
        shared = sorted(set.intersection(*sets)) if sets else []
        text = copy.introduction_message(copy.names(members, self.roster), shared, context_label)
        return {"action": "introduced", "shared_interests": shared,
                **self._send_group(text, f"intro:{session_id}:{'+'.join(sorted(members))}")}

    def suggest_icebreaker(self, session_id: str, members: Sequence[str], activity_scope: str, kind: str,
                           interest: Optional[str] = None, existing_group: bool = False) -> dict:
        """Optional conversation starter; strangers need introduction consent first."""
        if not existing_group and not self._all_consent(members, activity_scope, "introduction"):
            return {"action": "blocked", "error_code": m.CONSENT_REQUIRED, "delivery": "none"}
        if interest:
            kind = "interest"
        pool = copy.ICEBREAKERS[kind]
        text = pool[sum(map(ord, session_id)) % len(pool)].format(interest=interest or "")
        return {"action": "icebreaker", **self._send_group(text, f"ice:{session_id}:{kind}:{interest}")}
