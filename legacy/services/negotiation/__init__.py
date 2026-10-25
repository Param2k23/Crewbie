"""Crewbie Agent 04: multi-agent negotiation, constraints and fairness engine."""
from .coordinator import NegotiationCoordinator
from .events import MemoryEventSink, SteppingClock, SystemClock
from .fairness import InMemoryFairnessHistory
from .models import (
    ConfirmationResult,
    GroupRules,
    NegotiationConfig,
    NegotiationError,
    SessionRequest,
    SessionState,
)

__all__ = [
    "NegotiationCoordinator", "MemoryEventSink", "SteppingClock", "SystemClock", "InMemoryFairnessHistory",
    "ConfirmationResult", "GroupRules", "NegotiationConfig", "NegotiationError", "SessionRequest", "SessionState",
]
