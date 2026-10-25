"""Every user-facing Discord string, and the one mapping from domain errors to text."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from crewbie.domain.errors import DomainError
from crewbie.domain.windows import TimeWindow

_MARKDOWN = str.maketrans({c: f"\\{c}" for c in "*_~`|>#[]()"})


def clean(text: str) -> str:
    """Neutralise untrusted text (event titles, locations): no markdown, no mentions."""
    return text.translate(_MARKDOWN).replace("@", "@​")


def _clock(moment: datetime) -> tuple[str, str]:
    hour = moment.hour % 12 or 12
    return f"{hour}:{moment.minute:02d}", "am" if moment.hour < 12 else "pm"


def window_label(window: TimeWindow | None, timezone: str) -> str:
    """'5:00 to 6:30 pm', or '11:00 am to 1:00 pm' when it crosses noon."""
    if window is None:
        return "time to be decided"
    zone = ZoneInfo(timezone)
    start, start_suffix = _clock(window.start.astimezone(zone))
    end, end_suffix = _clock(window.end.astimezone(zone))
    if start_suffix == end_suffix:
        return f"{start} to {end} {end_suffix}"
    return f"{start} {start_suffix} to {end} {end_suffix}"


def date_label(iso_date: str) -> str:
    """'Fri Nov 6'."""
    try:
        parsed = datetime.strptime(iso_date, "%Y-%m-%d")
    except ValueError:
        return iso_date
    return f"{parsed:%a %b} {parsed.day}"


def thread_name(title: str, iso_date: str) -> str:
    return f"{title[:60]} · {date_label(iso_date)}"[:100]


def thread_link(guild_id: str, thread_id: str) -> str:
    return f"https://discord.com/channels/{guild_id}/{thread_id}"


# --- thread posts ---------------------------------------------------------------------------

ICEBREAKER = (
    "Welcome, crew. You're all going to {event_title} on {date_label}, "
    "{window_label}{location_part}.\n"
    "{interest_line}\n"
    "Pick a meeting spot: reply with one, or use /crew meetpoint."
)
INTEREST_LINE = "{count} of you are into {interest}. What got you into it?"
INTEREST_FALLBACK = "What are you most looking forward to?"
WELCOME = "{username} joined. Plan: {window_label}."
WINDOW_CHANGED = "Plan moved to {window_label}."
MEMBER_LEFT = "{alias} left. Plan: {window_label}."
THREAD_DM = "You're in! Your crew chat for {event_title}: {thread_url}"


def icebreaker(
    event_title: str,
    event_date: str,
    window: TimeWindow | None,
    location: str | None,
    interest_counts: Mapping[str, int],
    timezone: str,
) -> str:
    top = sorted(interest_counts.items(), key=lambda item: (-item[1], item[0]))
    shared = [(name, count) for name, count in top if count >= 2]
    line = (
        INTEREST_LINE.format(count=shared[0][1], interest=clean(shared[0][0].replace("-", " ")))
        if shared
        else INTEREST_FALLBACK
    )
    return ICEBREAKER.format(
        event_title=clean(event_title),
        date_label=date_label(event_date),
        window_label=window_label(window, timezone),
        location_part=f" at {clean(location)}" if location else "",
        interest_line=line,
    )[:900]


# --- board card -----------------------------------------------------------------------------


@dataclass(frozen=True)
class BoardCard:
    """Public fields only. The Join button's custom id is `crew-join:<room_id>`."""

    room_id: str
    title: str
    date_label: str
    window_label: str
    size: int
    vibe: str
    budget: str
    interests: tuple[str, ...]
    status: str


BOARD_FOOTER = "Press Join to tell your agent when you're free."


# --- slash commands -------------------------------------------------------------------------

LINK_OK = "Linked. Cubbie can now add you to crews."
LINK_REASONS = {
    "unknown": "That code isn't valid. Ask Cubbie for a new one.",
    "used": "That code was already used. Ask Cubbie for a new one.",
    "expired": "That code has expired. Ask Cubbie for a new one.",
}
LINK_CONFLICT_DISCORD = (
    "This Discord account is already linked to another Cubbie. Replace that link with this one?"
)
LINK_CONFLICT_INSTALL = (
    "This Cubbie is already linked to a different Discord account. Replace that link?"
)
LINK_REPLACE_LABEL = "Replace link"
LINK_REPLACED = "Replaced. Cubbie can now add you to crews."
STATUS_EMPTY = "You're not in any crews yet. Ask Cubbie to find one, or press Join on the board."
STATUS_LINE = "• {title}: {window_label}, {size} going — {thread}"
STATUS_NO_THREAD = "chat opens when a second person joins"
LEAVE_NOT_IN_THREAD = "Use /crew leave inside your crew's thread."
LEAVE_NOT_MEMBER = "You're not in this crew."
LEAVE_PROMPT = "Leave this crew? You can ask Cubbie to find another one."
LEAVE_LABEL = "Leave crew"
LEAVE_DONE = "You've left the crew."
HELP = (
    "**Crewbie** matches you with students going to the same activity.\n"
    "• Ask Cubbie to find a crew, then link your accounts with `/crew link code:<CODE>`.\n"
    "• `/crew status` shows your crews. `/crew leave` (inside a thread) leaves one.\n"
    "• Press Join on a card in the crew board to join without Cubbie."
)
MEETPOINT_SOON = "Meeting-point polls are coming soon. For now, reply with a spot."

# --- board join -----------------------------------------------------------------------------

JOIN_TITLE = "Join this crew"
JOIN_FIELDS = {
    "earliest": "Earliest you can start (HH:MM)",
    "latest": "Latest you can stay (HH:MM)",
    "minimum": "Minimum minutes you want there",
    "budget": "Budget: low, mid or high",
    "vibe": "Vibe: chill, social or active",
}
JOIN_BAD_TIME = "Use 24-hour times like 17:30 for earliest and latest."
JOIN_BAD_MINUTES = "Minimum minutes must be a number between 15 and 720."
JOIN_BAD_BUDGET = "Budget must be low, mid or high."
JOIN_BAD_VIBE = "Vibe must be chill, social or active."
JOIN_OFFER = "You can join: {window_label}. Join this crew?"
JOIN_CONFIRM_LABEL = "Join crew"
JOIN_NO_FIT = (
    "Your timing doesn't fit this crew's plan. I can start a new crew for you instead "
    "({window_label}). Start one?"
)
JOIN_NEW_LABEL = "Start new crew"
JOIN_DONE = "You're in. Watch for a DM with the thread link."
JOIN_DONE_THREAD = "You're in: {thread_url}"
JOIN_STARTED = "Started a new crew. I'll let you know when someone joins."
LINK_NEEDED = "Link your Cubbie first with `/crew link`."

# --- errors ---------------------------------------------------------------------------------

ERRORS = {
    "NOT_FOUND": "That isn't available any more.",
    "ALREADY_IN_ROOM": "You're already in a crew for this event. Use /crew status.",
    "OFFER_EXPIRED": "That offer expired. Press Join again.",
    "OFFER_STALE": "The crew changed while you were deciding. Press Join again.",
    "OFFER_CLOSED": "That offer was already answered.",
    "EVENT_STARTED": "That plan has already started.",
    "RATE_LIMITED": "You've tried this a lot today. Try again later.",
    "VALIDATION_FAILED": "Those details don't work. Check the times and try again.",
}
GENERIC_ERROR = "Something went wrong on our side. Please try again."


def error_text(error: DomainError) -> str:
    """The one place domain error codes become Discord text."""
    return ERRORS.get(error.code, GENERIC_ERROR)
