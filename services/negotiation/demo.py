"""Runnable offline simulation: four synthetic students negotiate a Flagstaff trip.

    python -m services.negotiation.demo                       # negotiate + human check-in (maybe stays pending)
    python -m services.negotiation.demo --change-budget       # judge lowers Alex's private cap -> re-plan
    python -m services.negotiation.demo --change-budget 3000  # below the cheapest option -> private exception path
    python -m services.negotiation.demo --change-budget 3000 --exception no   # ...declined: honest NO_FEASIBLE_PLAN
    python -m services.negotiation.demo --change-availability # Taylor becomes unavailable on the chosen day
    python -m services.negotiation.demo --withdraw stu_taylor # a participant leaves
    python -m services.negotiation.demo --jsonl               # only the group-safe AgentEvent stream

All transitions are produced by the coordinator reacting to the (private, mock) agents' answers.
No network, credentials or language model is used.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable, Dict, List, Optional, TextIO

from .coordinator import NegotiationCoordinator
from .events import MemoryEventSink, SteppingClock
from .fairness import InMemoryFairnessHistory
from .mocks import (
    MockCommitmentGateway,
    MockExceptionGateway,
    MockPrivateEvaluator,
    flagstaff_agents,
    flagstaff_request,
)

DEFAULT_CHANGED_CAP = 4000
MEMBERS = ("stu_alex", "stu_maya", "stu_jordan", "stu_taylor")


def run(args: argparse.Namespace, out: TextIO = sys.stdout) -> Dict[str, Any]:
    quiet = args.jsonl
    emitted = 0

    def say(text: str = "") -> None:
        if not quiet:
            print(text, file=out)

    def flush(sink: MemoryEventSink) -> None:
        nonlocal emitted
        for e in sink.events[emitted:]:
            print(json.dumps(e, sort_keys=True), file=out) if quiet else say(
                f"  {e['event_id']} {e['type']:<22} {json.dumps(e['payload'], sort_keys=True)}"
            )
        emitted = len(sink.events)

    agents = flagstaff_agents()
    by_ref = {a.student_ref: a for a in agents}
    by_ref["stu_alex"].set_exception_margin(1000)  # Alex *could* waive his cap by up to $10, if asked
    evaluator = MockPrivateEvaluator(agents)
    gateway, exc_gateway, sink = MockCommitmentGateway(), MockExceptionGateway(), MemoryEventSink()
    coordinator = NegotiationCoordinator(
        evaluator, gateway, sink, clock=SteppingClock(),
        exception_gateway=exc_gateway,
        fairness_history=InMemoryFairnessHistory(opted_in=set()),  # nobody opted in: no history used
    )

    say("== Crewbie negotiation demo (all participants and numbers are SYNTHETIC) ==")
    say("Phase 1-2: four private agents negotiate; the coordinator sees only coarse verdicts.")
    sid = coordinator.start_negotiation(flagstaff_request())
    flush(sink)
    snap = coordinator.get_public_snapshot(sid)
    gateway.open_proposal(snap) if snap["plan"] else None
    say(f"-> state={snap['state']} proposal=v{snap['version']} candidates_tried={snap['candidates_evaluated']} "
        f"private_checks={evaluator.total_evaluations()}")

    if snap["plan"]:
        say("\nHuman check-in (A5 owns this; coordinator only reads the summary):")
        p = snap["plan"]
        for member, answer in (("stu_alex", "accepted"), ("stu_maya", "accepted"), ("stu_jordan", "tentative")):
            gateway.record_approval(sid, p["plan_id"], p["version"], member, answer)
            say(f"  {member}: {answer}")
        r = coordinator.confirm_if_approved(sid, p["plan_id"], p["version"])
        say(f"-> confirm check: {r.status} ({r.accepted_count}/{r.required_count}) {r.error_code or ''}")

    changed = args.change_budget is not None or args.change_availability or args.withdraw
    if changed:
        say("\nPhase 3: a constraint changes on the student's own side (values stay private).")
        if args.change_budget is not None:
            by_ref["stu_alex"].set_hard_budget_cap(args.change_budget)
            say("  stu_alex lowers a private budget limit <value not shared>")
            coordinator.revise_negotiation(sid, {"kind": "budget", "student_ref": "stu_alex", "request_id": "chg_1"})
        elif args.change_availability:
            day = coordinator.get_public_snapshot(sid)["plan"]["start_at"][:10] if snap["plan"] else "2026-11-01"
            by_ref["stu_taylor"].set_blocked_windows(
                [{"start_at": f"{day}T00:00:00-07:00", "end_at": f"{day}T23:59:00-07:00"}])
            say("  stu_taylor becomes unavailable on the proposed day <details not shared>")
            coordinator.revise_negotiation(sid, {"kind": "availability", "student_ref": "stu_taylor",
                                                 "request_id": "chg_1"})
        else:
            say(f"  {args.withdraw} withdraws from the plan")
            coordinator.withdraw_participant(sid, args.withdraw)
        flush(sink)

        if exc_gateway.requests:
            who, _, plan_id, version = exc_gateway.requests[-1]
            say(f"\nPrivate exception request sent to ONE student only (not the group): {who} for {plan_id} v{version}")
            approved = args.exception == "yes"
            say(f"  {who} answers: {'approve' if approved else 'decline'}")
            coordinator.resolve_private_exception(sid, who, approved)
            flush(sink)

        snap = coordinator.get_public_snapshot(sid)
        if snap["plan"]:
            gateway.open_proposal(snap)
            p = snap["plan"]
            say(f"\nOld approvals invalidated: {gateway.invalidations}")
            say("Everyone accepts the NEW version:")
            for member in p["member_refs"]:
                gateway.record_approval(sid, p["plan_id"], p["version"], member, "accepted")
            r = coordinator.confirm_if_approved(sid, p["plan_id"], p["version"])
            say(f"-> confirm check: {r.status} ({r.accepted_count}/{r.required_count})")
            flush(sink)
        say(f"\n-> final state={snap['state'] if coordinator.state_of(sid).value != 'confirmed' else 'confirmed'} "
            f"error_code={snap['error_code']} reason={snap['reason_category']}")
    say("\nState transitions: " + " | ".join(f"{a}->{b}" for a, b in coordinator.transitions_of(sid)))
    flush(sink)
    return {"events": sink.events, "snapshot": coordinator.get_public_snapshot(sid),
            "state": coordinator.state_of(sid).value}


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m services.negotiation.demo", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", choices=["flagstaff"], default="flagstaff")
    ap.add_argument("--change-budget", nargs="?", type=int, const=DEFAULT_CHANGED_CAP, metavar="CENTS",
                    help="Alex's private hard cap changes (demo only; value is never sent to the coordinator)")
    ap.add_argument("--change-availability", action="store_true")
    ap.add_argument("--withdraw", choices=MEMBERS)
    ap.add_argument("--exception", choices=["yes", "no"], default="yes",
                    help="answer to a private exception request, if one is raised")
    ap.add_argument("--jsonl", action="store_true", help="print only the group-safe event stream as JSONL")
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    run(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
