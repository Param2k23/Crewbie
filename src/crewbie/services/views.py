"""Plain results returned by use cases. The API turns them into JSON; nothing here is private."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from crewbie.domain.windows import TimeWindow


@dataclass(frozen=True)
class InstallView:
    install_id: str
    discord_linked: bool
    discord_username: str | None = None
    created: bool = False


@dataclass(frozen=True)
class LinkCodeView:
    code: str
    expires_at: datetime
    invite_url: str | None
    command: str


@dataclass(frozen=True)
class RoomSummary:
    room_id: str
    size: int
    status: str
    window: TimeWindow | None
    vibe: str | None
    budget_band: str | None
    top_interests: list[str]


@dataclass(frozen=True)
class OfferView:
    offer_id: str
    type: str
    expires_at: datetime
    room: RoomSummary | None
    proposal: TimeWindow
    window_changed_for_room: bool


@dataclass(frozen=True)
class SubmitResult:
    intent_id: str
    state: str
    offer: OfferView | None
    replayed: bool = False


@dataclass(frozen=True)
class AcceptResult:
    state: str
    room_id: str
    size: int
    status: str
    thread_url: str | None


@dataclass(frozen=True)
class IntentView:
    intent_id: str
    state: str
    room_id: str | None
    thread_url: str | None


@dataclass(frozen=True)
class UpdateView:
    seq: int
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
