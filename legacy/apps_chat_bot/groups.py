"""Consent-gated group formation for newly matched participants.

Flow: verify introduction consent for this activity scope -> private invitations
(no other names) -> members reply "join" -> intro posted to the group only once
everyone invited has answered, naming only those who joined.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Optional, Sequence

from services.commitments import models as m

from . import copy

_JOIN = re.compile(r"^(join|yes|yep|yeah|i'?m in|count me in|add me|sure)\b")
_SKIP = re.compile(r"^(no|nope|nah|skip|not now|pass|leave me out)\b")


class GroupFormation:
    def __init__(self, host) -> None:
        self.host = host
        self.groups: dict[str, dict] = {}
        self._seen: set[str] = set()

    def form_group(self, group_id: str, activity_scope: str, activity_label: str, activity_kind: str,
                   candidates: Sequence[str], approved_interests: Mapping[str, Sequence[str]],
                   session_id: Optional[str] = None) -> dict:
        consent = self.host.service.consent
        consenting = [c for c in candidates if consent.has_consent(c, activity_scope, "introduction")]
        if len(consenting) < 2:
            return {"action": "blocked", "error_code": m.CONSENT_REQUIRED, "invited": [], "delivery": "none"}
        invites = {c: self.host._send_private(c, copy.group_invite_private(), f"invite:{group_id}:{c}")
                   for c in consenting}
        self.groups[group_id] = {
            "scope": activity_scope, "label": activity_label, "kind": activity_kind, "session_id": session_id,
            "invited": list(consenting), "joined": [], "declined": [], "interests": dict(approved_interests),
            "posted": False,
        }
        return {"action": "invited", "invited": consenting,
                "withheld_refs": [c for c in candidates if c not in consenting],  # integrator-only, never posted
                "delivery": {c: i["delivery"] for c, i in invites.items()}}

    def handle_private_message(self, msg: Mapping[str, Any]) -> dict:
        h = self.host
        member, rid = msg.get("member_ref"), msg.get("request_id") or msg.get("message_id")
        if msg.get("identity_source") not in h.trusted:
            return {"action": "ignored", "error_code": m.IDENTITY_UNVERIFIED}
        if rid and rid in self._seen:
            return {"action": "duplicate"}
        gid = next((g for g, s in self.groups.items() if member in s["invited"] and not s["posted"]), None)
        if gid is None:
            return {"action": "ignored", "error_code": m.NOT_A_PARTICIPANT}
        if rid:
            self._seen.add(rid)
        g = self.groups[gid]
        text = (msg.get("text") or "").lower().strip()
        if member in g["joined"] or member in g["declined"]:
            return {"action": "ignored"}
        if _SKIP.match(text):
            g["declined"].append(member)
            res = {"action": "declined"}
        elif _JOIN.match(text) and not re.search(r"\b(if|unless|maybe)\b", text):
            g["joined"].append(member)
            res = {"action": "joined"}
        else:
            return {"action": "clarify"}
        if len(g["joined"]) + len(g["declined"]) == len(g["invited"]):
            res["group"] = self.finalize(gid)
        return res

    def finalize(self, group_id: str) -> dict:
        """Post the introduction for those who joined (needs two or more, consent re-checked now)."""
        h, g = self.host, self.groups[group_id]
        if g["posted"]:
            return {"action": "already_posted"}
        consent = h.service.consent
        members = [c for c in g["joined"] if consent.has_consent(c, g["scope"], "introduction")]
        if len(members) < 2:
            return {"action": "not_enough_members", "error_code": m.CONSENT_REQUIRED, "delivery": "none"}
        h.participants = set(members)
        for ref in members:
            h.roster.setdefault(ref, ref.removeprefix("stu_").title())
        out = h.introduce(g["session_id"] or group_id, members, g["scope"], g["label"], g["interests"])
        if out.get("delivery") == "acknowledged":
            g["posted"] = True
            offer = h._send_group(copy.icebreaker_offer(), f"iceoffer:{group_id}")
            h.group_context = {"members": members, "activity_scope": g["scope"], "kind": g["kind"],
                               "session_id": g["session_id"] or group_id}
            out["icebreaker_offer"] = offer["delivery"]
        return out
