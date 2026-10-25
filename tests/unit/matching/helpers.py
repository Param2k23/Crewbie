from datetime import timedelta

from crewbie.agents.protocol import DelegateProfile
from crewbie.domain.budget import BudgetBand
from crewbie.domain.intent import SharedIntent
from crewbie.domain.room import MemberState, RoomStatus
from crewbie.domain.vibe import Vibe
from crewbie.domain.windows import TimeWindow
from crewbie.matching.snapshot import MemberSnapshot, RoomSnapshot
from tests.unit.domain.helpers import BASE, at, window


def profile(
    start: int = 60,
    end: int = 180,
    *,
    flex: tuple[int, int] | None = None,
    minimum: int = 90,
    band: BudgetBand = BudgetBand.LOW,
    vibe: Vibe = Vibe.CHILL,
    interests: tuple[str, ...] = (),
    event_key: str = "ev1",
) -> DelegateProfile:
    flex_start, flex_end = flex or (start - 30, end + 30)
    shared = SharedIntent(event_key, window(start, end), minimum, band, vibe, interests)
    return DelegateProfile(shared, window(flex_start, flex_end))


def member(alias: str, prof: DelegateProfile, joined: int = 0) -> MemberSnapshot:
    state = MemberState(
        alias,
        prof.shared.window,
        prof.shared.budget_band,
        prof.shared.vibe,
        prof.shared.interests,
        at(-1000 + joined),
    )
    return MemberSnapshot(alias, state, prof)


def room(
    room_id: str,
    members: list[MemberSnapshot],
    *,
    version: int = 1,
    created: int = 0,
    status: RoomStatus = RoomStatus.OPEN,
    event_key: str = "ev1",
) -> RoomSnapshot:
    from crewbie.domain.room import derive_room_state

    derived = derive_room_state([m.state for m in members])
    return RoomSnapshot(
        room_id=room_id,
        event_key=event_key,
        version=version,
        created_at=BASE + timedelta(minutes=created),
        status=status,
        window=derived.window,
        budget_band=derived.budget_band,
        vibe=derived.vibe,
        top_interests=derived.top_interests,
        members=tuple(members),
        next_alias=f"member-{len(members) + 1}",
    )


def single(room_id: str, prof: DelegateProfile, **kw: object) -> RoomSnapshot:
    return room(room_id, [member("member-1", prof)], **kw)  # type: ignore[arg-type]


def w(start: int, end: int) -> TimeWindow:
    return window(start, end)
