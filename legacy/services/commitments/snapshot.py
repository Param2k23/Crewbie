"""Normalisation of A4's public plan snapshot into the shape A5 stores."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .models import CommitmentError, PRIVATE_FIELD_IN_SNAPSHOT
from .privacy import assert_snapshot_public

# Fields whose change makes a new proposal version a *different proposal*.
MATERIAL_FIELDS = (
    "title",
    "member_refs",
    "start_at",
    "end_at",
    "activities",
    "cost_summary",
    "approved_per_person_estimate_cents",
    "location_label",
)

KEPT_FIELDS = MATERIAL_FIELDS + (
    "session_id",
    "plan_id",
    "version",
    "opportunity_id",
    "estimate_disclaimer",
    "open_questions",
    "validated",
    "activity_scope",
    "required_member_refs",
    "synthetic",
    "activity_type",
)


def normalise_snapshot(raw: Mapping[str, Any]) -> dict:
    """Return a public-only copy of the snapshot or raise CommitmentError."""
    assert_snapshot_public(raw)
    for k in ("session_id", "plan_id", "version", "member_refs"):
        if k not in raw:
            raise CommitmentError("INVALID_SNAPSHOT", f"missing {k}")
    snap = {k: raw[k] for k in KEPT_FIELDS if k in raw}
    if not isinstance(snap["version"], int) or snap["version"] < 1:
        raise CommitmentError("INVALID_SNAPSHOT", "version must be a positive integer")
    if not snap["member_refs"]:
        raise CommitmentError("INVALID_SNAPSHOT", "no members")
    if "approved_per_person_estimate_cents" in snap and not raw.get("cost_disclosure_approved"):
        raise CommitmentError(PRIVATE_FIELD_IN_SNAPSHOT, "per-person estimate without approval")
    snap["validated"] = raw.get("validated") is True or raw.get("status") in ("validated", "proposal_ready")
    snap.setdefault("synthetic", bool(raw.get("synthetic", False)))
    return snap


def fingerprint(snap: Mapping[str, Any]) -> str:
    material = {k: snap.get(k) for k in MATERIAL_FIELDS}
    blob = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]
