"""Bounded negotiation between a joiner delegate and a room host (protocol section 4)."""

from dataclasses import dataclass
from typing import Literal

from crewbie.agents.aliases import HOST_REF
from crewbie.agents.delegate import DelegatePolicy
from crewbie.agents.host import HostPolicy
from crewbie.agents.protocol import Proposal, Reply, Step, Verdict
from crewbie.domain.budget import BudgetBand
from crewbie.domain.windows import TimeWindow


@dataclass(frozen=True, slots=True)
class NegotiationResult:
    room_id: str
    outcome: Literal["agreed", "failed"]
    agreed: TimeWindow | None
    rounds: int
    opening: TimeWindow | None
    joiner_ref: str
    steps: tuple[Step, ...]
    failure_code: str | None = None


def _failed(
    room_id: str, rounds: int, opening: TimeWindow | None, joiner_ref: str,
    steps: list[Step], code: str,
) -> NegotiationResult:  # fmt: skip
    return NegotiationResult(
        room_id, "failed", None, rounds, opening, joiner_ref, tuple(steps), code
    )


def run_negotiation(
    *,
    room_id: str,
    room_band: BudgetBand,
    joiner: DelegatePolicy,
    joiner_ref: str,
    host: HostPolicy,
    opening: Proposal | None,
    max_rounds: int,
) -> NegotiationResult:
    """Alternate proposals for at most `max_rounds` evaluations. Agreement needs every member."""
    if opening is None:
        return _failed(room_id, 0, None, joiner_ref, [], "no_allowed_window")
    steps: list[Step] = []
    proposal = opening
    joiner_is_proposing = True
    for round_number in range(1, max_rounds + 1):
        proposal = Proposal(room_id, proposal.window, round_number, proposal.from_kind)
        if joiner_is_proposing:
            decision = host.evaluate(proposal)
            steps.extend(decision.member_steps)
            reply: Reply = decision.reply
            steps.append(Step(round_number, "host", HOST_REF, proposal.window, reply.verdict))
        else:
            reply = joiner.evaluate(proposal, room_band)
            steps.append(Step(round_number, "delegate", joiner_ref, proposal.window, reply.verdict))
            if reply.verdict is Verdict.ACCEPT:
                # The host proposed this window; every member must still say yes to the same one.
                confirm = host.evaluate(
                    Proposal(room_id, proposal.window, round_number, "delegate")
                )
                steps.extend(confirm.member_steps)
                steps.append(
                    Step(round_number, "host", HOST_REF, proposal.window, confirm.reply.verdict)
                )
                reply = confirm.reply
        if reply.verdict is Verdict.ACCEPT:
            return NegotiationResult(
                room_id, "agreed", proposal.window, round_number, opening.window, joiner_ref,
                tuple(steps), None,
            )  # fmt: skip
        if reply.verdict is Verdict.REJECT or reply.counter is None:
            return _failed(room_id, round_number, opening.window, joiner_ref, steps, "rejected")
        proposal = Proposal(
            room_id,
            reply.counter,
            round_number + 1,
            "delegate" if not joiner_is_proposing else "host",
        )
        joiner_is_proposing = not joiner_is_proposing
    return _failed(room_id, max_rounds, opening.window, joiner_ref, steps, "rounds_exhausted")
