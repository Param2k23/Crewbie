"""Host agent: fans a proposal out to the room's member delegates and merges the answers."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta

from crewbie.agents.delegate import DelegatePolicy
from crewbie.agents.protocol import Proposal, Reply, Step, Verdict
from crewbie.domain.budget import BudgetBand
from crewbie.domain.windows import TimeWindow, intersect_all


@dataclass(frozen=True, slots=True)
class HostDecision:
    reply: Reply
    member_steps: tuple[Step, ...]


class HostPolicy:
    """Speaks for every current member. Sees verdicts and counter windows, never envelopes."""

    def __init__(
        self, members: Sequence[tuple[str, DelegatePolicy]], room_band: BudgetBand
    ) -> None:
        self._members = tuple(members)
        self._room_band = room_band
        self._required = max((policy.minimum_minutes for _, policy in members), default=0)

    @property
    def required_minutes(self) -> int:
        return self._required

    def evaluate(self, proposal: Proposal) -> HostDecision:
        """accept if all accept; reject if any rejects; otherwise the intersection of counters."""
        replies = [
            (ref, policy.evaluate(proposal, self._room_band)) for ref, policy in self._members
        ]
        # Member steps record the verdict only. A counter's window stays inside the host, which
        # passes on just the merged result.
        steps = tuple(
            Step(proposal.round, "delegate", ref, proposal.window, reply.verdict)
            for ref, reply in replies
        )
        verdicts = {reply.verdict for _, reply in replies}
        if verdicts == {Verdict.ACCEPT}:
            return HostDecision(Reply(Verdict.ACCEPT), steps)
        if Verdict.REJECT in verdicts or not replies:
            return HostDecision(Reply(Verdict.REJECT), steps)
        windows: list[TimeWindow] = [
            reply.counter for _, reply in replies if reply.counter is not None
        ]
        if Verdict.ACCEPT in verdicts:
            windows.append(proposal.window)
        merged = intersect_all(windows)
        if merged is None or merged.duration < timedelta(minutes=self._required):
            return HostDecision(Reply(Verdict.REJECT), steps)
        return HostDecision(Reply(Verdict.COUNTER, merged), steps)
