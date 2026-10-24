"""NegotiationCoordinator: the typed state machine that drives proposal / counteroffer rounds.

Authority model
  * The coordinator orchestrates; it never *decides* a hard constraint. Public group rules are
    enforced by ``validator.validate_plan``; per-student limits by the students' evaluators.
  * Language models (``CandidateSuggester``) can only add candidates to the queue. Every candidate
    goes through the same validator and the same private evaluations.
  * Confirmation belongs to A5: ``confirm_if_approved`` only *reads* the commitment summary.
"""
from __future__ import annotations

import copy
import threading
from dataclasses import replace
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, Union

from . import events as ev
from .fairness import InMemoryFairnessHistory, rank_feasible
from .generation import DeterministicCandidateGenerator
from .models import (
    ALLOWED_HINTS,
    APPROVAL_INCOMPLETE,
    CONSENT_REQUIRED,
    NO_FEASIBLE_PLAN,
    PROPOSAL_STALE,
    PROVIDER_UNAVAILABLE,
    SEARCH_STATES,
    TRANSITIONS,
    CandidateRecord,
    CandidateStatus,
    ConfirmationResult,
    ConsentRequired,
    Evaluation,
    NegotiationConfig,
    NegotiationError,
    Session,
    SessionRequest,
    SessionState,
)
from .protocols import (
    CandidateSuggester,
    CommitmentGateway,
    EventSink,
    ExceptionAwareEvaluator,
    FairnessHistory,
    PrivateEvaluator,
    PrivateExceptionGateway,
)
from .validator import check_roster, normalize_candidate, parse_evaluation, signature, validate_plan

S = SessionState
CHANGE_KINDS = {"budget", "availability", "preference", "itinerary", "other"}


class _Stop(Exception):
    """Internal: end the current search run with a reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class NegotiationCoordinator:
    def __init__(
        self,
        evaluator: PrivateEvaluator,
        commitments: CommitmentGateway,
        sink: EventSink,
        *,
        config: Optional[NegotiationConfig] = None,
        suggester: Optional[CandidateSuggester] = None,
        fairness_history: Optional[FairnessHistory] = None,
        exception_gateway: Optional[PrivateExceptionGateway] = None,
        clock: Optional[Any] = None,
    ) -> None:
        self.evaluator = evaluator
        self.commitments = commitments
        self.sink = sink
        self.config = config or NegotiationConfig()
        self.generator = DeterministicCandidateGenerator(self.config)
        self.suggester = suggester
        self.history = fairness_history
        self.exception_gateway = exception_gateway
        self.clock = clock or ev.SystemClock()
        self._sessions: Dict[str, Session] = {}
        self._by_request: Dict[str, str] = {}
        self._handled_changes: Dict[Tuple[str, str], bool] = {}
        self.sink_errors = 0
        self.gateway_errors = 0

    # ==================================================================================
    # Public API (CONTRACTS.md section 3)
    # ==================================================================================
    def start_negotiation(self, session_request: Union[SessionRequest, Mapping[str, Any]]) -> str:
        req = session_request if isinstance(session_request, SessionRequest) else SessionRequest.from_mapping(session_request)
        if req.request_id in self._by_request:  # idempotent
            return self._by_request[req.request_id]
        sid = req.session_id or f"session_{req.request_id}"
        if sid in self._sessions:
            raise NegotiationError("DUPLICATE_SESSION", sid)
        s = Session(session_id=sid, request=req, roster=list(req.member_refs), initial_size=len(req.member_refs))
        self._sessions[sid] = s
        self._by_request[req.request_id] = sid
        self._transition(s, S.NEGOTIATING)
        self._emit(s, "negotiation_started", group_size=len(s.roster))

        code = check_roster(s.roster, req.rules, s.initial_size)
        if code:
            self._fail(s, NO_FEASIBLE_PLAN, "attendance_requirement")
            return sid
        seeds = self.generator.seeds(req, s.roster)
        s.base_plan = copy.deepcopy(seeds[0]) if seeds else None
        self._search(s, [(p, "seed", None, None) for p in seeds])
        return sid

    def revise_negotiation(self, session_id: str, changed_constraint_ref: Mapping[str, Any]) -> None:
        """A private or public constraint changed. The new VALUE stays on the owner's side; we only
        learn *that* something changed, so every approval is invalidated and the plan is re-validated."""
        s = self._get(session_id)
        kind = changed_constraint_ref.get("kind")
        if kind not in CHANGE_KINDS:
            raise NegotiationError("INVALID_CHANGE", "unknown constraint kind")
        who = changed_constraint_ref.get("student_ref")
        if who is not None and who not in s.roster:
            raise NegotiationError("UNKNOWN_MEMBER", "not a current participant")
        change_id = changed_constraint_ref.get("request_id")
        if change_id is not None:
            if (session_id, str(change_id)) in self._handled_changes:
                return  # idempotent replay
            self._handled_changes[(session_id, str(change_id))] = True
        if s.state not in (S.PROPOSED, S.APPROVAL_PENDING, S.CONFIRMED, S.AWAITING_EXCEPTION, S.FAILED):
            raise NegotiationError("INVALID_STATE", f"cannot revise from {s.state.value}")
        reason = "itinerary_changed" if kind == "itinerary" else "constraint_changed"
        self._renegotiate(s, reason)

    def withdraw_participant(self, session_id: str, member_ref: str) -> None:
        s = self._get(session_id)
        if member_ref not in s.roster:
            raise NegotiationError("UNKNOWN_MEMBER", "not a current participant")
        if s.state in (S.CREATED, S.CANCELLED):
            raise NegotiationError("INVALID_STATE", f"cannot withdraw from {s.state.value}")
        s.roster.remove(member_ref)
        s.cost_disclosure.discard(member_ref)
        for plan in (s.base_plan, s.current_plan):
            if plan:
                self._strip_member(plan, member_ref)
        code = check_roster(s.roster, s.request.rules, s.initial_size)
        if code:
            self._invalidate(s, "participant_change")
            self._fail(s, NO_FEASIBLE_PLAN, "attendance_requirement")
            return
        self._renegotiate(s, "participant_change")

    def resolve_private_exception(self, session_id: str, student_ref: str, approved: bool) -> None:
        """Called with the affected student's own explicit answer to a private exception request."""
        s = self._get(session_id)
        if s.state is not S.AWAITING_EXCEPTION or student_ref not in s.pending_exceptions:
            raise NegotiationError("INVALID_STATE", "no private exception pending for this participant")
        rec = s.exception_candidate
        assert rec is not None
        if s.pending_exceptions[student_ref] is not None:
            return  # idempotent
        if isinstance(self.evaluator, ExceptionAwareEvaluator):
            self.evaluator.record_exception_decision(
                student_ref, s.session_id, rec.plan["plan_id"], rec.version, bool(approved)
            )
        if not approved:
            s.pending_exceptions[student_ref] = False
            self._fail(s, NO_FEASIBLE_PLAN, "exception_declined")  # stays infeasible
            return
        s.pending_exceptions[student_ref] = True
        if any(v is None for v in s.pending_exceptions.values()):
            return
        # every affected student agreed: the plan is still only valid if THEY now say so
        self._transition(s, S.NEGOTIATING)
        try:
            self._evaluate_members(s, rec)
        except _Stop as stop:
            s.stop_reason = stop.reason
        if rec.status is CandidateStatus.FEASIBLE:
            s.exception_candidate = None
            self._publish(s, [rec])
        else:
            self._fail(s, self._stop_code(s) or NO_FEASIBLE_PLAN, "exception_declined")

    def record_member_decline(self, session_id: str, member_ref: str) -> None:
        """A member declined the published version: veto it and fall back to re-validated runners-up."""
        s = self._get(session_id)
        if s.state is not S.APPROVAL_PENDING or s.current_plan is None or member_ref not in s.roster:
            raise NegotiationError("INVALID_STATE", "no pending proposal to decline")
        s.vetoed.add(signature(s.current_plan))
        runners = [copy.deepcopy(r.plan) for r in s.ranked[1:]]
        self._renegotiate(s, "member_declined", runners_up=runners)

    def expire_pending_exceptions(self, session_id: str) -> None:
        """No answer to a private exception request: it stays unapproved, so the plan stays infeasible."""
        s = self._get(session_id)
        if s.state is S.AWAITING_EXCEPTION:
            self._fail(s, NO_FEASIBLE_PLAN, "exception_expired")

    def authorize_cost_disclosure(self, session_id: str, member_ref: str) -> None:
        """A member allows per-person cost estimates to appear in the public snapshot."""
        s = self._get(session_id)
        if member_ref in s.roster:
            s.cost_disclosure.add(member_ref)

    def confirm_if_approved(
        self, session_id: str, plan_id: Optional[str] = None, version: Optional[int] = None
    ) -> ConfirmationResult:
        """Ask A5's gateway whether every required member accepted THIS version. Never decides itself."""
        s = self._get(session_id)
        plan = s.current_plan
        if s.state is S.CONFIRMED and plan and (version in (None, plan["version"])):
            return ConfirmationResult("confirmed", None, len(s.roster), len(s.roster))
        if plan is None or s.state is not S.APPROVAL_PENDING:
            if version is not None and (plan is None or version != plan["version"]):
                return ConfirmationResult("stale", PROPOSAL_STALE)
            return ConfirmationResult("not_pending", APPROVAL_INCOMPLETE)
        if (version is not None and version != plan["version"]) or (plan_id is not None and plan_id != plan["plan_id"]):
            return ConfirmationResult("stale", PROPOSAL_STALE)
        try:
            summary = self.commitments.get_commitment_summary(s.session_id, plan["plan_id"], plan["version"])
        except Exception:
            self.gateway_errors += 1
            return ConfirmationResult("incomplete", PROVIDER_UNAVAILABLE)
        required = len(s.roster)
        if summary.get("version") != plan["version"] or summary.get("plan_id") != plan["plan_id"]:
            return ConfirmationResult("stale", PROPOSAL_STALE)
        accepted = summary.get("accepted_count")
        ok = (
            isinstance(accepted, int) and not isinstance(accepted, bool)
            and summary.get("required_count") == required
            and accepted == required
            and summary.get("confirmed", True) is True
            and not summary.get("declined_count") and not summary.get("withdrawn_count")
        )
        if not ok:
            return ConfirmationResult(
                "incomplete", APPROVAL_INCOMPLETE,
                accepted if isinstance(accepted, int) and not isinstance(accepted, bool) else 0, required,
            )
        self._transition(s, S.CONFIRMED)
        self._emit(s, "proposal_confirmed", plan_id=plan["plan_id"], version=plan["version"],
                   accepted_count=required, required_count=required)
        if self.history is not None and s.ranked:
            try:
                self.history.record_outcome(s.session_id, {r: e.soft_penalty for r, e in s.ranked[0].evaluations.items()})
            except Exception:
                self.gateway_errors += 1
        self._emit(s, "session_completed", outcome="confirmed")
        return ConfirmationResult("confirmed", None, required, required)

    def cancel_negotiation(self, session_id: str) -> None:
        s = self._get(session_id)
        if s.state is S.CANCELLED:
            return
        self._invalidate(s, "cancelled", emit=False)
        self._transition(s, S.CANCELLED)
        s.current_plan = None
        self._emit(s, "session_completed", outcome="cancelled")

    def get_public_snapshot(self, session_id: str) -> Dict[str, Any]:
        s = self._get(session_id)
        public_state = "negotiating" if s.state is S.AWAITING_EXCEPTION else s.state.value
        plan = s.current_plan
        snap: Dict[str, Any] = {
            "session_id": s.session_id,
            "state": public_state,
            "version": plan["version"] if plan else None,
            "plan": self._public_plan(s, plan) if plan else None,
            "required_count": len(s.roster) if plan else None,
            "error_code": s.error_code if s.state is S.FAILED else None,
            "reason_category": s.reason_category if s.state is S.FAILED else None,
            "candidates_evaluated": s.stats["candidates"],
            "rounds": s.stats["rounds"],
            "revisions": s.stats["revisions"],
            "synthetic": s.request.synthetic,
        }
        return snap

    def state_of(self, session_id: str) -> SessionState:
        return self._get(session_id).state

    def transitions_of(self, session_id: str) -> List[Tuple[str, str]]:
        return list(self._get(session_id).transitions)

    # ==================================================================================
    # State machine plumbing
    # ==================================================================================
    def _get(self, session_id: str) -> Session:
        try:
            return self._sessions[session_id]
        except KeyError:
            raise NegotiationError("UNKNOWN_SESSION", session_id) from None

    def _transition(self, s: Session, new: SessionState) -> None:
        if new not in TRANSITIONS[s.state]:
            raise NegotiationError("INVALID_TRANSITION", f"{s.state.value} -> {new.value}")
        s.transitions.append((s.state.value, new.value))
        s.state = new

    def _emit(self, s: Session, type_: str, **payload: Any) -> None:
        s.event_seq += 1
        event = ev.build_event(
            session_id=s.session_id, seq=s.event_seq, timestamp=self.clock.now_iso(),
            type_=type_, payload=payload, synthetic=s.request.synthetic,
        )
        try:
            self.sink.emit(event)
        except Exception:  # a broken UI sink must never corrupt negotiation state
            self.sink_errors += 1

    def _fail(self, s: Session, code: str, reason: str) -> None:
        s.error_code, s.reason_category = code, reason
        s.current_plan = None
        s.pending_exceptions = {}
        s.exception_candidate = None
        self._transition(s, S.FAILED)
        self._emit(s, "negotiation_failed", error_code=code, reason_category=reason,
                   candidates_evaluated=s.stats["candidates"], rounds=s.stats["rounds"])

    def _invalidate(self, s: Session, reason: str, *, emit: bool = True) -> int:
        """Reset approvals for the published version. Returns the first version number of the new epoch."""
        new_floor = s.version_counter + 1
        old = s.current_plan
        if old is not None:
            try:
                self.commitments.invalidate_version(s.session_id, old["version"], new_floor)
            except Exception:
                self.gateway_errors += 1  # approvals are version-bound, so a stale one cannot match later
            if emit:
                self._emit(s, "proposal_revised", previous_plan_id=old["plan_id"], previous_version=old["version"],
                           version=new_floor, reason_category=reason, approvals_reset=True)
        s.current_plan = None
        s.cost_disclosure.clear()
        return new_floor

    def _renegotiate(self, s: Session, reason: str, runners_up: Optional[List[Dict[str, Any]]] = None) -> None:
        had_plan = s.current_plan is not None
        base = copy.deepcopy(s.current_plan or s.base_plan)
        if had_plan:
            self._invalidate(s, reason)
        else:  # nothing was published: still announce the new epoch
            floor = s.version_counter + 1
            self._emit(s, "proposal_revised", previous_plan_id=(base or {}).get("plan_id", "none"),
                       previous_version=(base or {}).get("version", 0), version=floor,
                       reason_category=reason, approvals_reset=False)
        s.pending_exceptions = {}
        s.exception_candidate = None
        s.error_code = s.reason_category = None
        s.stats["revisions"] += 1
        self._transition(s, S.RENEGOTIATING)
        seeds: List[Mapping[str, Any]] = list(runners_up or [])
        if base and runners_up is None:
            seeds.append(base)
        seeds += self.generator.seeds(s.request, s.roster) if s.request.seed_plans else []
        seeds = [self._for_roster(p, s.roster) for p in seeds]
        self._search(s, [(p, "seed", None, None) for p in seeds])

    @staticmethod
    def _strip_member(plan: Dict[str, Any], ref: str) -> None:
        plan["member_refs"] = [m for m in plan.get("member_refs", []) if m != ref]
        plan.get("estimated_cost_cents_by_ref", {}).pop(ref, None)

    @staticmethod
    def _for_roster(plan: Mapping[str, Any], roster: List[str]) -> Dict[str, Any]:
        out = copy.deepcopy(dict(plan))
        out["member_refs"] = [m for m in out.get("member_refs", roster) if m in roster]
        out["estimated_cost_cents_by_ref"] = {
            m: c for m, c in out.get("estimated_cost_cents_by_ref", {}).items() if m in roster
        }
        return out

    # ==================================================================================
    # Search
    # ==================================================================================
    Item = Tuple[Mapping[str, Any], str, Optional[int], Optional[str]]

    def _search(self, s: Session, queue: List["NegotiationCoordinator.Item"]) -> None:
        cfg = self.config
        s.records, s.ranked, s.seen_signatures = [], [], set(s.vetoed)
        s.stop_reason = None
        s.run_started_at = self.clock.monotonic()
        run_candidates = 0
        rounds = 0
        try:
            while queue:
                if rounds >= cfg.max_rounds:
                    raise _Stop("rounds_exhausted")
                rounds += 1
                s.stats["rounds"] += 1
                batch, queue = queue, []
                batch_records: List[CandidateRecord] = []
                for raw, origin, derived, summary in batch:
                    self._check_budget(s, run_candidates)
                    rec = self._consider(s, raw, origin, derived, summary)
                    if rec is None:
                        continue
                    run_candidates += 1
                    batch_records.append(rec)
                    if s.state is S.CANCELLED:
                        return
                if sum(r.status is CandidateStatus.FEASIBLE for r in s.records) >= cfg.target_feasible:
                    raise _Stop("target_reached")
                queue = self._expand(s, batch_records)
            s.stop_reason = "no_new_candidates"
        except _Stop as stop:
            s.stop_reason = stop.reason
        if s.state is S.CANCELLED:
            return
        self._conclude(s)

    def _check_budget(self, s: Session, run_candidates: int) -> None:
        if s.state is S.CANCELLED:
            raise _Stop("cancelled")
        if run_candidates >= self.config.max_candidates:
            raise _Stop("candidate_limit")
        if self.clock.monotonic() - s.run_started_at > self.config.session_timeout_s:
            raise _Stop("timeout")

    def _consider(self, s: Session, raw: Mapping[str, Any], origin: str,
                  derived: Optional[int], summary: Optional[str]) -> Optional[CandidateRecord]:
        version = s.version_counter + 1
        plan = normalize_candidate(
            raw, session_id=s.session_id, plan_id=f"{s.request.plan_slug}_{version:03d}",
            version=version, request=s.request, roster=s.roster,
        )
        sig = signature(plan)
        if sig in s.seen_signatures:
            return None  # same content already tried this run: do not spend another probe
        s.seen_signatures.add(sig)
        s.version_counter = version
        s.stats["candidates"] += 1
        if origin in ("counteroffer", "refinement"):
            self._emit(s, "counteroffer_proposed", plan_id=plan["plan_id"], version=version,
                       derived_from_version=derived, summary=summary or "Adjusted itinerary")
        else:
            self._emit(s, "candidate_proposed", plan_id=plan["plan_id"], version=version)

        violations = validate_plan(plan, s.request, s.roster)
        rec = CandidateRecord(plan, CandidateStatus.INVALID, origin, derived, rule_violations=tuple(violations))
        s.records.append(rec)
        if violations:  # cheap deterministic checks come BEFORE any private probe
            self._emit(s, "proposal_rejected", plan_id=plan["plan_id"], version=version,
                       reason_category="group_rule_violation")
            return rec
        self._evaluate_members(s, rec)
        if rec.status is CandidateStatus.REJECTED:
            self._emit(s, "proposal_rejected", plan_id=plan["plan_id"], version=version,
                       reason_category="constraint_conflict")
        return rec

    # -- private evaluations -----------------------------------------------------------
    def _call(self, fn: Callable[..., Any], *args: Any) -> Any:
        box: Dict[str, Any] = {}

        def run() -> None:
            try:
                box["v"] = fn(*args)
            except BaseException as exc:  # propagate to caller thread
                box["e"] = exc

        t = threading.Thread(target=run, daemon=True)
        t.start()
        t.join(self.config.evaluator_timeout_s)
        if t.is_alive():
            raise TimeoutError("evaluator timed out")
        if "e" in box:
            raise box["e"]
        return box["v"]

    def _probe(self, s: Session, ref: str) -> None:
        if s.eval_counts.get(ref, 0) >= self.config.max_evaluations_per_member_per_session:
            raise _Stop("probe_limit")
        s.eval_counts[ref] = s.eval_counts.get(ref, 0) + 1

    def _evaluate_members(self, s: Session, rec: CandidateRecord) -> None:
        plan = rec.plan
        evals: Dict[str, Evaluation] = {}
        for ref in s.roster:
            # data minimisation: a student's agent sees only its own cost line
            view = copy.deepcopy(plan)
            view["estimated_cost_cents_by_ref"] = {ref: plan["estimated_cost_cents_by_ref"][ref]}
            self._probe(s, ref)
            try:
                raw = self._call(self.evaluator.evaluate_plan_private, ref, view)
            except ConsentRequired:
                raise _Stop("consent_required") from None
            except Exception:
                raise _Stop("provider_unavailable") from None
            extra: Tuple[str, ...] = ()
            parsed = parse_evaluation(raw, student_ref=ref, plan=plan)
            if not parsed.feasible:
                self._probe(s, ref)
                try:
                    hint_raw = self._call(self.evaluator.propose_private_counteroffer, ref, view)
                    if isinstance(hint_raw, Mapping):
                        extra = tuple(h for h in (hint_raw.get("hints") or ()) if h in ALLOWED_HINTS)
                except ConsentRequired:
                    raise _Stop("consent_required") from None
                except Exception:
                    extra = ()  # hints are optional; the verdict above already stands
            evals[ref] = replace(parsed, hints=tuple(h for h in ALLOWED_HINTS if h in set(parsed.hints) | set(extra)))
        rec.evaluations = evals
        rec.status = (
            CandidateStatus.FEASIBLE if all(e.feasible for e in evals.values()) else CandidateStatus.REJECTED
        )

    # -- expansion ---------------------------------------------------------------------
    def _expand(self, s: Session, batch: List[CandidateRecord]) -> List["NegotiationCoordinator.Item"]:
        out: List[NegotiationCoordinator.Item] = []
        seen = list(s.seen_signatures)
        for kind_filter, origin in ((CandidateStatus.REJECTED, "counteroffer"), (CandidateStatus.FEASIBLE, "refinement")):
            for rec in batch:
                if rec.status is not kind_filter:
                    continue
                hints = sorted({h for e in rec.evaluations.values() for h in e.hints}, key=ALLOWED_HINTS.index)
                for cand, summary in self.generator.derive(rec.plan, hints, s.request, s.roster, seen):
                    seen.append(signature(cand))
                    out.append((cand, origin, rec.version, summary))
        if self.suggester is not None:
            out += self._suggestions(s)
        return out

    def _suggestions(self, s: Session) -> List["NegotiationCoordinator.Item"]:
        context = {  # PUBLIC data only
            "session_id": s.session_id,
            "group_size": len(s.roster),
            "window_start": s.request.window_start,
            "window_end": s.request.window_end,
            "cost_tiers_cents": list(self.config.cost_tiers_cents),
            "tried": [
                {"plan_id": r.plan["plan_id"], "version": r.version, "start_at": r.plan["start_at"],
                 "end_at": r.plan["end_at"], "outcome": r.status.value}
                for r in s.records
            ],
        }
        try:
            raw = list(self.suggester.suggest(context))[: self.config.max_suggestions_per_round]  # type: ignore[union-attr]
        except Exception:
            return []  # a failing model is simply not heard from
        return [(c, "suggestion", None, None) for c in raw if isinstance(c, Mapping)]

    # -- conclusion --------------------------------------------------------------------
    def _stop_code(self, s: Session) -> Optional[str]:
        return {"consent_required": CONSENT_REQUIRED, "provider_unavailable": PROVIDER_UNAVAILABLE}.get(s.stop_reason or "")

    def _conclude(self, s: Session) -> None:
        pool = [r for r in s.records if r.status is CandidateStatus.FEASIBLE]
        if pool:
            self._publish(s, pool)
            return
        code = self._stop_code(s)
        if code:
            self._fail(s, code, "evaluator_unavailable" if code == PROVIDER_UNAVAILABLE else "consent_missing")
            return
        if self._request_exceptions(s):
            return
        bounded = s.stop_reason in ("rounds_exhausted", "candidate_limit", "timeout", "probe_limit")
        self._fail(s, NO_FEASIBLE_PLAN, "search_bounds_reached" if bounded else "search_exhausted")

    def _request_exceptions(self, s: Session) -> bool:
        """If the only blockers are hard limits a student may waive, ask THAT student privately."""
        if self.exception_gateway is None:
            return False
        eligible = [r for r in s.records if r.exception_eligible]
        if not eligible:
            return False
        eligible.sort(key=lambda r: (
            sum(not e.feasible for e in r.evaluations.values()),
            sum(r.plan["estimated_cost_cents_by_ref"].values()),
            signature(r.plan),
        ))
        rec = eligible[0]
        affected = [ref for ref, e in rec.evaluations.items() if not e.feasible]
        s.exception_candidate = rec
        s.pending_exceptions = {ref: None for ref in affected}
        self._transition(s, S.AWAITING_EXCEPTION)  # publicly this still reads as "negotiating"
        for ref in affected:
            try:
                self.exception_gateway.request_private_exception(ref, s.session_id, rec.plan["plan_id"], rec.version)
            except Exception:
                self.gateway_errors += 1
        return True

    def _publish(self, s: Session, pool: List[CandidateRecord]) -> None:
        history: Mapping[str, float] = {}
        if self.history is not None:
            try:
                history = self.history.burden_shares(list(s.roster))
            except Exception:
                history = {}
        scored = rank_feasible(pool, history, self.config)
        s.ranked = [x.record for x in scored]
        for rank, sc in enumerate(scored, 1):
            self._emit(
                s, "fairness_evaluated", plan_id=sc.record.plan["plan_id"], version=sc.record.version, rank=rank,
                feasible_count=len(scored),
                balance="balanced" if sc.spread <= self.config.balanced_spread_threshold else "uneven",
            )
        top = scored[0].record
        s.current_plan = copy.deepcopy(top.plan)
        s.base_plan = copy.deepcopy(top.plan)
        s.error_code = s.reason_category = None
        self._transition(s, S.PROPOSED)
        self._emit(s, "proposal_ready", plan_id=top.plan["plan_id"], version=top.version, approval_state="pending")
        self._transition(s, S.APPROVAL_PENDING)
        self._emit(s, "approval_requested", plan_id=top.plan["plan_id"], version=top.version,
                   required_count=len(s.roster))

    # -- public projection -------------------------------------------------------------
    def _public_plan(self, s: Session, plan: Mapping[str, Any]) -> Dict[str, Any]:
        costs: Mapping[str, int] = plan["estimated_cost_cents_by_ref"]
        out: Dict[str, Any] = {
            k: copy.deepcopy(plan[k])
            for k in ("plan_id", "session_id", "version", "opportunity_id", "title", "member_refs",
                      "start_at", "end_at", "activities", "estimate_disclaimer", "synthetic")
        }
        out["estimated_total_cents"] = sum(costs.values())  # aggregate only
        if set(s.roster) <= s.cost_disclosure:  # every member consented to per-person figures
            out["estimated_cost_cents_by_ref"] = dict(costs)
        return out
