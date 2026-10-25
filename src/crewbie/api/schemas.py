"""Request models. Unknown fields are rejected so clients cannot smuggle extra data in."""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
TIME_PATTERN = r"^\d{2}:\d{2}$"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterIn(Strict):
    client: str | None = Field(None, max_length=64)


class EventIn(Strict):
    source_url: str = Field(max_length=2048, pattern=r"^https://")
    title: str = Field(min_length=1, max_length=500)
    location_label: str | None = Field(None, max_length=500)
    date: str = Field(pattern=DATE_PATTERN)
    start_time: str | None = Field(None, pattern=TIME_PATTERN)
    end_time: str | None = Field(None, pattern=TIME_PATTERN)


class WindowIn(Strict):
    start: AwareDatetime
    end: AwareDatetime


class SharedIn(Strict):
    window: WindowIn
    activity_min_minutes: int
    budget_band: Literal["low", "mid", "high"]
    vibe: Literal["chill", "social", "active"]
    interests: list[str] = Field(default_factory=list, max_length=20)


class FlexIn(Strict):
    earliest: AwareDatetime
    latest: AwareDatetime


class PrivateIn(Strict):
    flex: FlexIn
    budget_cap_usd: float | None = None


class IntentIn(Strict):
    event: EventIn
    shared: SharedIn
    private: PrivateIn


class LookupEventIn(Strict):
    ref: str = Field(max_length=32)
    source_url: str = Field(max_length=2048)
    date: str = Field(pattern=DATE_PATTERN)
    start_time: str | None = Field(None, pattern=TIME_PATTERN)


class LookupIn(Strict):
    events: list[LookupEventIn] = Field(min_length=1, max_length=5)


class EventSearchIn(Strict):
    title: str = Field(min_length=1, max_length=500)
    date: str = Field(pattern=DATE_PATTERN)
    start_time: str | None = Field(None, pattern=TIME_PATTERN)
    location_label: str | None = Field(None, max_length=500)
    source_url: str | None = Field(None, max_length=2048, pattern=r"^https://")
