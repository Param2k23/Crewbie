"""Port to Agent 04. A5 asks for proposals; it never judges feasibility itself."""
from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol


class NegotiationClient(Protocol):
    def request_proposal(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        """Ask A4 for a validated public snapshot for a new plan. Returns an ack, not a plan."""

    def request_revision(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        """Ask A4 for a revised version of the active plan."""
