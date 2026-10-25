"""Demo data (FR-ADM-02): one ASU event with two rooms of synthetic members."""

from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from crewbie.domain.budget import BudgetBand
from crewbie.domain.errors import Forbidden
from crewbie.domain.event_key import event_key
from crewbie.domain.intent import IntentState, PrivateEnvelope, SharedIntent
from crewbie.domain.vibe import Vibe
from crewbie.domain.windows import TimeWindow
from crewbie.services._common import enqueue, recompute_room
from crewbie.services.context import ServiceContext

SEED_URL = "https://sundevilcentral.eoss.asu.edu/events/demo-board-game-night"

# (room index, start offset minutes from 18:00, end offset, band, vibe, interests)
_MEMBERS = [
    (0, 0, 120, BudgetBand.LOW, Vibe.CHILL, ("board-games", "strategy")),
    (0, 30, 150, BudgetBand.LOW, Vibe.CHILL, ("board-games",)),
    (1, 60, 180, BudgetBand.HIGH, Vibe.SOCIAL, ("trivia",)),
]


def seed_demo(ctx: ServiceContext) -> dict[str, Any]:
    """Create the demo event, rooms and synthetic members. Refused in prod; safe to repeat."""
    if ctx.config.env == "prod":
        raise Forbidden("Seeding is disabled when CREWBIE_ENV=prod.")
    now = ctx.clock()
    local = ZoneInfo(ctx.config.timezone)
    day = (now.astimezone(local) + timedelta(days=1)).date()
    start_of_evening = datetime.combine(day, time(18, 0), tzinfo=local)
    key = event_key(SEED_URL, day.isoformat(), "18:00")

    with ctx.uow_factory() as uow:
        if uow.events.get(key) is not None:
            return {"event_key": key, "rooms": [r.id for r in uow.rooms.list_for_event(key)]}
        uow.events.ensure(
            key, source_url=SEED_URL, title="Board game night", location_label="Hayden Library",
            date=day.isoformat(), start_time="18:00", end_time="21:00",
        )  # fmt: skip
        room_ids = [ctx.new_id("r"), ctx.new_id("r")]
        for room_id in room_ids:
            uow.rooms.create(room_id, key)
        for room, start, end, band, vibe, interests in _MEMBERS:
            window = TimeWindow(
                start_of_evening + timedelta(minutes=start),
                start_of_evening + timedelta(minutes=end),
            )
            install = uow.installs.add(ctx.new_id("in"), None, "cubbie", is_synthetic=True)
            intent_id = ctx.new_id("i")
            shared = SharedIntent(key, window, 90, band, vibe, interests)
            envelope = PrivateEnvelope(
                window.start - timedelta(minutes=60), window.end + timedelta(minutes=60), 20.0
            )
            uow.intents.add(intent_id, install.id, shared, envelope, IntentState.JOINED)
            uow.rooms.add_member(ctx.new_id("m"), room_ids[room], intent_id, window, now)
        for room_id in room_ids:
            change = recompute_room(ctx, uow, room_id)
            enqueue(
                ctx, uow, "upsert_board_card", {"room_id": room_id},
                f"board:{room_id}:v{change.room.version}",
            )  # fmt: skip
        uow.commit()
    return {"event_key": key, "rooms": room_ids}
