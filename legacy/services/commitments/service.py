"""Versioned commitment state machine (the A5 CommitmentGateway implementation)."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional

from . import models as m
from .consent import ConsentGateway, MemoryConsentGateway
from .events import CommitmentListener, EventSink, MemoryEventSink, build_event
from .models import CommitmentError, CommitmentRecord, Proposal, TERMINAL_STATUSES
from .parser import ParsedReply, classify_reply
from .snapshot import fingerprint, normalise_snapshot

Clock = Callable[[], datetime]
_NON_FINAL_BLOCKING = ("declined", "withdrawn")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class CommitmentService:
    def __init__(
        self,
        event_sink: Optional[EventSink] = None,
        listener: Optional[CommitmentListener] = None,
        consent: Optional[ConsentGateway] = None,
        clock: Optional[Clock] = None,
        state_path: Optional[str] = None,
    ) -> None:
        self.sink = event_sink if event_sink is not None else MemoryEventSink()
        self.listener = listener
        self.consent = consent if consent is not None else MemoryConsentGateway()
        self.clock = clock or _utc_now
        self.state_path = state_path
        self._proposals: dict[tuple, Proposal] = {}
        self._active: dict[str, tuple] = {}
        self._records: dict[tuple, CommitmentRecord] = {}  # key + (member_ref,)
        self._processed: dict[str, dict] = {}  # "session|request_id" -> result
        self._event_seq = 0
        if state_path and os.path.exists(state_path):
            self._load(state_path)

    # ------------------------------------------------------------------ helpers
    def _now(self) -> str:
        return _iso(self.clock())

    def _emit(self, session_id: str, type_: str, payload: dict, synthetic: bool = True) -> None:
        self._event_seq += 1
        self.sink.emit(build_event(self._event_seq, session_id, self._now(), type_, payload, synthetic))

    def _notify(self, kind: str, p: Proposal, **extra: Any) -> None:
        if self.listener is None:
            return
        self.listener.on_commitment_event(
            {"kind": kind, "session_id": p.session_id, "plan_id": p.plan_id, "version": p.version,
             "timestamp": self._now(), **extra}
        )

    def _get(self, session_id: str, plan_id: str, version: int) -> Optional[Proposal]:
        return self._proposals.get((session_id, plan_id, version))

    def _active_proposal(self, session_id: str) -> Optional[Proposal]:
        key = self._active.get(session_id)
        return self._proposals.get(key) if key else None

    def _member_records(self, p: Proposal) -> dict[str, CommitmentRecord]:
        return {mem: self._records[p.key + (mem,)] for mem in p.required}

    def active_proposal(self, session_id: str) -> Optional[Proposal]:
        return self._active_proposal(session_id)

    # ------------------------------------------------------------- proposal API
    def register_proposal(self, raw_snapshot: Mapping[str, Any]) -> dict:
        """Accept a public snapshot from A4. A higher version supersedes the active one."""
        snap = normalise_snapshot(raw_snapshot)
        sid, plan_id, version = snap["session_id"], snap["plan_id"], snap["version"]
        fp = fingerprint(snap)
        active = self._active_proposal(sid)
        if active is not None:
            if version < active.version:
                raise CommitmentError(m.PROPOSAL_STALE, f"v{version} < active v{active.version}")
            if version == active.version:
                if active.plan_id == plan_id and active.fingerprint == fp:
                    if snap["validated"] != active.validated:
                        active.validated = snap["validated"]
                        self._save()
                    return self.get_commitment_summary(sid, plan_id, version)
                raise CommitmentError(m.VERSION_CONFLICT, "same version, different content")
            self.invalidate_version(sid, active.version, version)
        required = tuple(snap.get("required_member_refs") or snap["member_refs"])
        p = Proposal(
            session_id=sid, plan_id=plan_id, version=version, snapshot=snap, fingerprint=fp,
            required=required, activity_scope=snap.get("activity_scope", sid),
            validated=snap["validated"],
        )
        self._proposals[p.key] = p
        self._active[sid] = p.key
        now = self._now()
        for mem in required:
            self._records[p.key + (mem,)] = CommitmentRecord(sid, plan_id, version, mem, last_changed_at=now)
        self._save()
        return self.get_commitment_summary(sid, plan_id, version)

    def mark_presented(self, session_id: str, plan_id: str, version: int) -> None:
        """Called after the provider acknowledged the proposal message."""
        p = self._get(session_id, plan_id, version)
        if p is None:
            raise CommitmentError(m.UNKNOWN_PROPOSAL, f"{plan_id} v{version}")
        if p.presented_at is None and p.status == "open":
            p.presented_at = self._now()
            self._emit(session_id, "approval_requested",
                       {"plan_id": plan_id, "version": version, "required_count": len(p.required)},
                       p.snapshot.get("synthetic", True))
            self._save()

    def set_validated(self, session_id: str, plan_id: str, version: int, validated: bool) -> dict:
        p = self._get(session_id, plan_id, version)
        if p is None:
            raise CommitmentError(m.UNKNOWN_PROPOSAL, f"{plan_id} v{version}")
        p.validated = validated
        self._maybe_confirm(p)
        self._save()
        return self.get_commitment_summary(session_id, plan_id, version)

    def invalidate_version(self, session_id: str, old_version: int, new_version: int) -> None:
        """CommitmentGateway: drop every approval bound to ``old_version``.

        Approvals are never carried forward, whether or not the change looks
        material; the new version starts with everyone pending.
        """
        key = self._active.get(session_id)
        if key is None or key[2] != old_version:
            return
        p = self._proposals[key]
        if p.status in ("open", "confirmed", "revoked"):
            p.status = "superseded" if new_version > old_version else "invalidated"
        for mem in p.required:
            rec = self._records[p.key + (mem,)]
            rec.evidence = {"invalidated_by_version": new_version, "prior_state": rec.state}
            rec.state, rec.explicit_acceptance = "pending", False
        self._active.pop(session_id, None)
        self._notify("approvals_invalidated", p, new_version=new_version)
        self._save()

    # ----------------------------------------------------------- recording
    def record_approval(
        self,
        session_id: str,
        plan_id: str,
        version: int,
        member_ref: str,
        response: "str | Mapping[str, Any]",
        *,
        request_id: Optional[str] = None,
        sent_at: Optional[str] = None,
        referenced_version: Optional[int] = None,
        reply_scoped: bool = False,
    ) -> dict:
        """Record one member response against an exact proposal version.

        ``response`` is raw chat text (parsed conservatively) or a mapping
        ``{"state": ..., "explicit": bool}`` from a trusted UI control.
        """
        dedupe_key = f"{session_id}|{request_id}" if request_id else None
        if dedupe_key and dedupe_key in self._processed:
            return {**self._processed[dedupe_key], "outcome": "duplicate", "duplicate": True}
        result = self._record(session_id, plan_id, version, member_ref, response,
                              request_id, sent_at, referenced_version, reply_scoped)
        if dedupe_key:
            self._processed[dedupe_key] = result
        self._save()
        return result

    def _result(self, outcome: str, p: Optional[Proposal], *, error: Optional[str] = None,
                parsed: Optional[ParsedReply] = None, record: Optional[CommitmentRecord] = None,
                confirmed_now: bool = False, clarify: bool = False) -> dict:
        return {
            "outcome": outcome,
            "error_code": error,
            "duplicate": False,
            "record": record.to_contract() if record else None,
            "reply_state": parsed.state if parsed else None,
            "rule": parsed.rule if parsed else None,
            "needs_clarification": clarify,
            "confirmed_now": confirmed_now,
            "proposal_state": self._proposal_state(p) if p else None,
        }

    def _record(self, session_id, plan_id, version, member_ref, response, request_id, sent_at,
                referenced_version, reply_scoped) -> dict:
        p = self._get(session_id, plan_id, version)
        if p is None:
            raise CommitmentError(m.UNKNOWN_PROPOSAL, f"{plan_id} v{version}")
        if member_ref not in p.required:
            return self._result("ignored", p, error=m.NOT_A_PARTICIPANT)
        if p.status == "cancelled":
            return self._result("ignored", p, error="PROPOSAL_CANCELLED")

        if isinstance(response, Mapping):
            state = response.get("state")
            if state not in m.STATES or state == "pending":
                raise CommitmentError("INVALID_RESPONSE", str(state))
            parsed = ParsedReply(state, "structured", explicit=bool(response.get("explicit")) and state == "accepted",
                                 referenced_version=version)
        else:
            parsed = classify_reply(response, reply_scoped=reply_scoped)
            if referenced_version is not None:
                parsed = ParsedReply(parsed.state, parsed.rule, parsed.explicit, parsed.needs_clarification,
                                     referenced_version if parsed.referenced_version is None else parsed.referenced_version,
                                     parsed.referenced_plan_id)

        is_active = self._active.get(session_id) == p.key
        refers_elsewhere = (
            (parsed.referenced_version is not None and parsed.referenced_version != p.version)
            or (parsed.referenced_plan_id is not None and parsed.referenced_plan_id != p.plan_id)
        )
        # Withdrawal concerns the member's participation, so it always applies to the live proposal.
        if parsed.state != "withdrawn" and (not is_active or refers_elsewhere):
            return self._result("stale", self._active_proposal(session_id) or p, error=m.PROPOSAL_STALE, parsed=parsed)
        if not is_active:
            p = self._active_proposal(session_id)
            if p is None or member_ref not in p.required:
                return self._result("stale", None, error=m.PROPOSAL_STALE, parsed=parsed)

        if parsed.state is None:
            return self._result("clarify", p, parsed=parsed, clarify=True)

        # A reply that was typed before this version was shown cannot approve it.
        presented = _parse_ts(p.presented_at)
        sent = _parse_ts(sent_at)
        if parsed.state == "accepted" and presented and sent and sent < presented \
                and parsed.referenced_version != p.version:
            return self._result("stale", p, error=m.PROPOSAL_STALE, parsed=parsed)

        rec = self._records[p.key + (member_ref,)]
        if sent_at and rec.last_sent_at and _parse_ts(sent_at) < _parse_ts(rec.last_sent_at):
            return self._result("ignored", p, error="OUT_OF_ORDER", parsed=parsed, record=rec)

        if parsed.state == "accepted":
            if p.presented_at is None:
                return self._result("rejected", p, error=m.NOT_PRESENTED, parsed=parsed, record=rec)
            if not self.consent.has_consent(member_ref, p.activity_scope, "plan_acceptance"):
                return self._result("rejected", p, error=m.CONSENT_REQUIRED, parsed=parsed, record=rec)
            if p.status == "confirmed" and rec.state == "accepted":
                return self._result("recorded", p, parsed=parsed, record=rec)

        # A weak positive never overrides a firmer state (accepted, conditional, tentative, ...).
        if parsed.state == "interested" and rec.state not in ("pending", "interested"):
            return self._result("kept", p, parsed=parsed, record=rec)

        self._apply(p, rec, parsed, request_id, sent_at, response)
        confirmed_now = self._maybe_confirm(p) if parsed.state == "accepted" else False
        clarify = bool(parsed.needs_clarification and parsed.state == "interested")
        return self._result("recorded", p, parsed=parsed, record=rec, confirmed_now=confirmed_now, clarify=clarify)

    def _apply(self, p: Proposal, rec: CommitmentRecord, parsed: ParsedReply, request_id, sent_at, raw) -> None:
        was_confirmed = p.status == "confirmed"
        rec.state = parsed.state
        rec.explicit_acceptance = parsed.state == "accepted" and parsed.explicit
        rec.last_changed_at = self._now()
        rec.request_id = request_id
        rec.last_sent_at = sent_at or rec.last_sent_at
        text = raw if isinstance(raw, str) else json.dumps(dict(raw), sort_keys=True)
        rec.evidence = {"rule": parsed.rule, "text_sha256": hashlib.sha256(text.encode()).hexdigest()[:16],
                        "version": p.version}
        self._emit(p.session_id, "member_response_received",
                   {"plan_id": p.plan_id, "version": p.version, "member_ref": rec.member_ref, "state": rec.state},
                   p.snapshot.get("synthetic", True))
        if rec.state == "declined":
            self._notify("member_declined", p, member_ref=rec.member_ref)
        elif rec.state == "withdrawn":
            self._notify("member_withdrawn", p, member_ref=rec.member_ref)
        elif rec.state == "conditional":
            self._notify("conditional_response", p, member_ref=rec.member_ref)
        elif rec.state == "accepted":
            self._notify("approval_recorded", p, member_ref=rec.member_ref, explicit=rec.explicit_acceptance)
        if was_confirmed and rec.state != "accepted":
            p.status = "revoked"
            self._notify("confirmation_revoked", p, member_ref=rec.member_ref)

    def _can_confirm(self, p: Proposal) -> bool:
        if p.status != "open" or not p.validated or p.presented_at is None or not p.required:
            return False
        if self._active.get(p.session_id) != p.key:
            return False
        for mem in p.required:
            rec = self._records[p.key + (mem,)]
            if rec.state != "accepted" or not rec.explicit_acceptance or rec.version != p.version:
                return False
            if not self.consent.has_consent(mem, p.activity_scope, "plan_acceptance"):
                return False
        return True

    def _maybe_confirm(self, p: Proposal) -> bool:
        if p.confirmed_emitted or not self._can_confirm(p):
            return False
        p.status, p.confirmed_emitted = "confirmed", True
        n = len(p.required)
        self._emit(p.session_id, "proposal_confirmed",
                   {"plan_id": p.plan_id, "version": p.version, "required_count": n, "accepted_count": n},
                   p.snapshot.get("synthetic", True))
        self._notify("proposal_confirmed", p, required_count=n)
        return True

    def revoke_consent(self, session_id: str, member_ref: str) -> Optional[dict]:
        """Member revoked plan-acceptance consent: treat as withdrawal, void any confirmation."""
        revoke = getattr(self.consent, "revoke", None)
        p = self._active_proposal(session_id)
        if revoke and p:
            revoke(member_ref, p.activity_scope, "plan_acceptance")
        if p is None or member_ref not in p.required:
            return None
        rec = self._records[p.key + (member_ref,)]
        if rec.state == "withdrawn":
            return self.get_commitment_summary(session_id, p.plan_id, p.version)
        was_confirmed = p.status == "confirmed"
        rec.state, rec.explicit_acceptance = "withdrawn", False
        rec.last_changed_at = self._now()
        rec.evidence = {"rule": "consent_revoked", "version": p.version}
        self._emit(session_id, "member_response_received",
                   {"plan_id": p.plan_id, "version": p.version, "member_ref": member_ref, "state": "withdrawn"},
                   p.snapshot.get("synthetic", True))
        self._notify("consent_revoked", p, member_ref=member_ref)
        if was_confirmed:
            p.status = "revoked"
            self._notify("confirmation_revoked", p, member_ref=member_ref)
        self._save()
        return self.get_commitment_summary(session_id, p.plan_id, p.version)

    # -------------------------------------------------------------- summary
    def _proposal_state(self, p: Proposal) -> str:
        if p.status in TERMINAL_STATUSES:
            return p.status
        if not p.validated:
            return "awaiting_validation"
        recs = self._member_records(p).values()
        if any(r.state in _NON_FINAL_BLOCKING for r in recs):
            return "blocked"
        return "approval_pending"

    def get_commitment_summary(self, session_id: str, plan_id: str, version: int) -> dict:
        p = self._get(session_id, plan_id, version)
        if p is None:
            raise CommitmentError(m.UNKNOWN_PROPOSAL, f"{plan_id} v{version}")
        state = self._proposal_state(p)
        stale = self._active.get(session_id) != p.key
        counts = {s: 0 for s in m.STATES}
        members: dict[str, str] = {}
        for mem, rec in self._member_records(p).items():
            counts[rec.state] += 1
            members[mem] = rec.state
        error = None
        if stale and p.status in ("superseded", "invalidated"):
            error = m.PROPOSAL_STALE
            counts = {s: 0 for s in m.STATES}
            counts["pending"] = len(p.required)
            members = {mem: "pending" for mem in p.required}
        elif state != "confirmed":
            error = m.APPROVAL_INCOMPLETE
        return {
            "session_id": session_id, "plan_id": plan_id, "version": version,
            "proposal_state": state,
            "confirmed": state == "confirmed",
            "validated": p.validated,
            "presented": p.presented_at is not None,
            "required_count": len(p.required),
            "accepted_count": counts["accepted"],
            "counts": counts,
            "members": members,
            "pending_member_refs": [mm for mm, s in members.items() if s == "pending"],
            "error_code": error,
            "synthetic": p.snapshot.get("synthetic", True),
        }

    # -------------------------------------------------------- nudge tracking
    def pending_follow_up(self, session_id: str, now: datetime, min_interval_s: int, max_nudges: int) -> list[str]:
        """Members who may be gently nudged now (pending only; one-sided rate limit)."""
        p = self._active_proposal(session_id)
        if p is None or p.status != "open" or p.presented_at is None or p.nudge_count >= max_nudges:
            return []
        anchor = _parse_ts(p.last_nudge_at or p.presented_at)
        if (now - anchor).total_seconds() < min_interval_s:
            return []
        return [mem for mem, r in self._member_records(p).items() if r.state == "pending"]

    def note_nudge(self, session_id: str, now: datetime) -> None:
        p = self._active_proposal(session_id)
        if p:
            p.nudge_count += 1
            p.last_nudge_at = _iso(now)
            self._save()

    def note_clarified(self, session_id: str, member_ref: str) -> bool:
        """True the first time a member is prompted for clarification on this version."""
        p = self._active_proposal(session_id)
        if p is None or member_ref in p.clarified:
            return False
        p.clarified.append(member_ref)
        self._save()
        return True

    # ------------------------------------------------- cancel / change / memo
    def recall_request(self, session_id: str, request_id: str) -> Optional[dict]:
        return self._processed.get(f"{session_id}|{request_id}")

    def remember_request(self, session_id: str, request_id: str, result: dict) -> None:
        self._processed[f"{session_id}|{request_id}"] = result
        self._save()

    def request_change(self, session_id: str, member_ref: str, aspects: list, timeframe: Optional[str],
                       request_id: Optional[str] = None) -> Optional[dict]:
        """A member asked to change the plan: their answer becomes conditional and A4 is told what kind of change."""
        p = self._active_proposal(session_id)
        if p is None:
            return None
        res = self.record_approval(session_id, p.plan_id, p.version, member_ref, {"state": "conditional"},
                                   request_id=request_id)
        if not res.get("duplicate"):
            self._notify("change_requested", p, member_ref=member_ref, aspects=list(aspects), timeframe=timeframe)
        return res

    def request_cancellation(self, session_id: str, member_ref: str, request_id: Optional[str] = None) -> Optional[dict]:
        """A member asked to cancel: they count as declined; A4/integrator decides whether to close the plan."""
        p = self._active_proposal(session_id)
        if p is None:
            return None
        res = self.record_approval(session_id, p.plan_id, p.version, member_ref, {"state": "declined"},
                                   request_id=request_id)
        if not res.get("duplicate"):
            self._notify("cancellation_requested", p, member_ref=member_ref)
        return res

    def cancel_proposal(self, session_id: str) -> Optional[dict]:
        """Integrator/A4 closed the plan: nothing can be confirmed or approved on it any more."""
        p = self._active_proposal(session_id)
        if p is None:
            return None
        p.status = "cancelled"
        self._notify("proposal_cancelled", p)
        self._save()
        return self.get_commitment_summary(session_id, p.plan_id, p.version)

    # ---------------------------------------------------------- persistence
    def _save(self) -> None:
        if not self.state_path:
            return
        state = {
            "event_seq": self._event_seq,
            "active": {k: list(v) for k, v in self._active.items()},
            "proposals": [{**p.__dict__, "required": list(p.required)} for p in self._proposals.values()],
            "records": [r.__dict__ for r in self._records.values()],
            "processed": self._processed,
        }
        d = os.path.dirname(os.path.abspath(self.state_path))
        fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(state, f)
        os.replace(tmp, self.state_path)

    def _load(self, path: str) -> None:
        with open(path) as f:
            s = json.load(f)
        self._event_seq = s["event_seq"]
        self._active = {k: tuple(v) for k, v in s["active"].items()}
        for pd in s["proposals"]:
            pd["required"] = tuple(pd["required"])
            p = Proposal(**pd)
            self._proposals[p.key] = p
        for rd in s["records"]:
            r = CommitmentRecord(**rd)
            self._records[(r.session_id, r.plan_id, r.version, r.member_ref)] = r
        self._processed = s["processed"]
