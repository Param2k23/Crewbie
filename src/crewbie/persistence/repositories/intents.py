from sqlalchemy import select
from sqlalchemy.orm import Session

from crewbie.domain.intent import LIVE_STATES, IntentState, PrivateEnvelope, SharedIntent
from crewbie.persistence.crypto import EnvelopeCipher
from crewbie.persistence.tables import EnvelopeRow, IntentRow


class IntentRepository:
    def __init__(self, session: Session, cipher: EnvelopeCipher) -> None:
        self._session = session
        self._cipher = cipher

    def add(
        self,
        intent_id: str,
        install_id: str,
        shared: SharedIntent,
        envelope: PrivateEnvelope,
        state: IntentState = IntentState.MATCHING,
    ) -> IntentRow:
        """Store shared fields and the encrypted envelope together."""
        row = IntentRow(
            id=intent_id,
            install_id=install_id,
            event_key=shared.event_key,
            window_start=shared.window.start,
            window_end=shared.window.end,
            activity_min_minutes=shared.activity_min_minutes,
            budget_band=shared.budget_band.label,
            vibe=shared.vibe.value,
            interests=list(shared.interests),
            state=state.value,
        )
        self._session.add(row)
        self._session.flush()  # no ORM relationship, so order the FK insert explicitly
        self._session.add(
            EnvelopeRow(intent_id=intent_id, ciphertext=self._cipher.encrypt(envelope))
        )
        self._session.flush()
        return row

    def get(self, intent_id: str) -> IntentRow | None:
        return self._session.get(IntentRow, intent_id)

    def get_live(self, install_id: str, event_key: str) -> IntentRow | None:
        return self._session.scalar(
            select(IntentRow).where(
                IntentRow.install_id == install_id,
                IntentRow.event_key == event_key,
                IntentRow.state.in_([state.value for state in LIVE_STATES]),
            )
        )

    def set_state(self, intent_id: str, state: IntentState) -> None:
        row = self._session.get(IntentRow, intent_id)
        if row is not None:
            row.state = state.value
            self._session.flush()

    def load_envelope(self, intent_id: str) -> PrivateEnvelope | None:
        """Decrypt one intent's envelope. Only the owning delegate may call this."""
        row = self._session.get(EnvelopeRow, intent_id)
        return None if row is None else self._cipher.decrypt(row.ciphertext)
