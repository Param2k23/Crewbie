"""Turn service results into the JSON shapes of the API contract."""

from typing import Any

from crewbie.domain.windows import TimeWindow
from crewbie.services.views import (
    AcceptResult,
    InstallView,
    IntentView,
    LinkCodeView,
    OfferView,
    RoomSummary,
    UpdateView,
)


def window_json(window: TimeWindow | None) -> dict[str, str] | None:
    if window is None:
        return None
    return {"start": window.start.isoformat(), "end": window.end.isoformat()}


def room_json(room: RoomSummary) -> dict[str, Any]:
    return {
        "room_id": room.room_id,
        "size": room.size,
        "status": room.status,
        "window": window_json(room.window),
        "vibe": room.vibe,
        "budget_band": room.budget_band,
        "top_interests": room.top_interests,
    }


def install_json(view: InstallView) -> dict[str, Any]:
    body: dict[str, Any] = {"install_id": view.install_id, "discord_linked": view.discord_linked}
    if view.discord_username:
        body["discord_username"] = view.discord_username
    return body


def link_code_json(view: LinkCodeView) -> dict[str, Any]:
    return {
        "code": view.code,
        "expires_at": view.expires_at.isoformat(),
        "invite_url": view.invite_url,
        "command": view.command,
    }


def offer_json(offer: OfferView) -> dict[str, Any]:
    room = None
    if offer.room is not None:
        room = {
            "room_id": offer.room.room_id,
            "size": offer.room.size,
            "vibe": offer.room.vibe,
            "budget_band": offer.room.budget_band,
            "top_interests": offer.room.top_interests,
        }
    return {
        "offer_id": offer.offer_id,
        "type": offer.type,
        "expires_at": offer.expires_at.isoformat(),
        "room": room,
        "proposal": window_json(offer.proposal),
        "window_changed_for_room": offer.window_changed_for_room,
    }


def accept_json(result: AcceptResult) -> dict[str, Any]:
    return {
        "state": result.state,
        "room": {"room_id": result.room_id, "size": result.size, "status": result.status},
        "thread_url": result.thread_url,
    }


def intent_json(view: IntentView) -> dict[str, Any]:
    return {
        "intent_id": view.intent_id,
        "state": view.state,
        "room_id": view.room_id,
        "thread_url": view.thread_url,
    }


def update_json(update: UpdateView) -> dict[str, Any]:
    return {"seq": update.seq, "kind": update.kind, **update.payload}
