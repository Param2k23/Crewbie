from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from crewbie.persistence.tables import NegotiationRow, NegotiationStepRow


@dataclass(frozen=True)
class StepRecord:
    round: int
    actor_kind: str
    actor_alias: str
    proposal_start: datetime | None
    proposal_end: datetime | None
    verdict: str


class NegotiationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        negotiation_id: str,
        intent_id: str,
        room_id: str,
        outcome: str,
        rounds: int,
        steps: list[StepRecord],
    ) -> None:
        self._session.add(
            NegotiationRow(
                id=negotiation_id,
                intent_id=intent_id,
                room_id=room_id,
                outcome=outcome,
                rounds=rounds,
            )
        )
        self._session.flush()
        for step in steps:
            self._session.add(
                NegotiationStepRow(
                    negotiation_id=negotiation_id,
                    round=step.round,
                    actor_kind=step.actor_kind,
                    actor_alias=step.actor_alias,
                    proposal_start=step.proposal_start,
                    proposal_end=step.proposal_end,
                    verdict=step.verdict,
                )
            )
        self._session.flush()
