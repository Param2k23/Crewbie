"""Injected collaborators. Shapes follow CONTRACTS.md section 3; additions are marked OPTIONAL."""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Protocol, Sequence, runtime_checkable


class EventSink(Protocol):
    def emit(self, event: Mapping[str, Any]) -> None: ...


class PrivateEvaluator(Protocol):
    """A3's per-student private feasibility oracle. Results never leave the coordinator."""

    def evaluate_plan_private(self, student_ref: str, plan: Mapping[str, Any]) -> Mapping[str, Any]: ...

    def propose_private_counteroffer(self, student_ref: str, plan: Mapping[str, Any]) -> Mapping[str, Any]: ...


class CommitmentGateway(Protocol):
    """A5's approval authority. The coordinator never decides confirmation itself."""

    def invalidate_version(self, session_id: str, old_version: int, new_version: int) -> None: ...

    def get_commitment_summary(self, session_id: str, plan_id: str, version: int) -> Mapping[str, Any]: ...


@runtime_checkable
class PrivateExceptionGateway(Protocol):
    """OPTIONAL. Delivers an exception request to ONE affected student, never to the group."""

    def request_private_exception(self, student_ref: str, session_id: str, plan_id: str, version: int) -> None: ...


@runtime_checkable
class ExceptionAwareEvaluator(Protocol):
    """OPTIONAL. The student's own side records the decision; the coordinator re-evaluates after."""

    def record_exception_decision(
        self, student_ref: str, session_id: str, plan_id: str, version: int, approved: bool
    ) -> None: ...


class CandidateSuggester(Protocol):
    """Language-model hook. Receives PUBLIC context only; output is untrusted and validated."""

    def suggest(self, context: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]: ...


class FairnessHistory(Protocol):
    """Permissioned, opt-in burden history (A3). Returns shares in [0, 1] for opted-in members only."""

    def burden_shares(self, member_refs: Sequence[str]) -> Dict[str, float]: ...

    def record_outcome(self, session_id: str, burdens: Mapping[str, float]) -> None: ...


class Clock(Protocol):
    def now_iso(self) -> str: ...

    def monotonic(self) -> float: ...
