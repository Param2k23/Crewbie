"""Private, offline Unlock models. Not sponsor tools or shared service schemas.

Native Cubbie obtains permissioned snapshots and researches sources. These helpers
test conservative policy only; they never read accounts, schedule or send messages.
"""
import re
from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .core import PulseError, _source_ok, instant


def assess_window(context):
    """Check a student-confirmed window against authorized, minimal snapshots.

    Calendar entries are busy intervals; Canvas obligations carry due_at and a
    user-approved reserve_minutes. Missing study allowance requires clarification.
    protected_windows are explicitly supplied rest/work/care/study blocks; reasons
    are never returned. Empty connected data never establishes availability.
    """
    if context.get("authorized") is not True:
        raise PulseError("CONSENT_REQUIRED", "Trusted student authorization required")
    if not context.get("availability_start") or not context.get("availability_end"):
        return {"status": "needs_confirmation", "reason": "Confirm an exact dated window and timezone."}
    start, end = instant(context["availability_start"]), instant(context["availability_end"])
    if end <= start:
        raise PulseError("VALIDATION_ERROR", "Window end must follow start")
    blocks = list(context.get("protected_windows", []))
    missing = []
    for source in ("calendar", "canvas"):
        if context.get(source + "_authorized") is not True:
            missing.append(source)
            continue
        if context.get(source + "_status") != "available":
            missing.append(source)
            continue
        if source == "calendar":
            blocks.extend(context.get("calendar_busy", []))
        else:
            for obligation in context.get("canvas_obligations", []):
                if obligation.get("completed") is True:
                    continue
                due = instant(obligation.get("due_at"))
                reserve = obligation.get("reserve_minutes")
                if type(reserve) is not int or reserve < 0:
                    # Do not assume no preparation simply because the due time is later.
                    return {"status": "needs_confirmation", "reason": "Confirm study time for upcoming academic obligations."}
                blocks.append({"start_at": due - timedelta(minutes=reserve), "end_at": due + timedelta(microseconds=1)})
    for block in blocks:
        bs, be = instant(block.get("start_at")), instant(block.get("end_at"))
        if be <= bs:
            raise PulseError("VALIDATION_ERROR", "Invalid protected interval")
        if start < be and bs < end:
            return {"status": "conflict", "reason": "This window overlaps a protected commitment; choose another window."}
    if context.get("window_confirmed") is not True:
        return {"status": "needs_confirmation", "reason": "A calendar gap is only a possible window. Are you actually available?"}
    return {"status": "student_confirmed", "minutes": int((end - start).total_seconds() // 60),
            "account_checks": "partial" if missing else "available_snapshots",
            "reason": "Student confirmed; recheck commitments before acting."}


def personality(context):
    chosen = context.get("personality", "Chill")
    if chosen not in ("Chill", "Playful", "Roast Me"):
        raise PulseError("VALIDATION_ERROR", "Choose Chill, Playful or Roast Me")
    if chosen == "Roast Me" and context.get("roast_opt_in") is not True:
        return "Chill"
    return chosen


def unlock_card(item, context, *, now):
    """Render one minimal source-backed card from trusted supplied evidence.

    Local record: title/category/source_url/checked_at/synthetic, eligibility
    (eligible|ineligible|unknown), restrictions string list, next_step; optional
    verified price and time/travel requirements. Never fetches or verifies a page.
    """
    if context.get("authorized") is not True:
        raise PulseError("CONSENT_REQUIRED", "Private context required")
    if not _source_ok(item) or type(item.get("synthetic")) is not bool:
        raise PulseError("EVENT_UNVERIFIED", "Original evidence link and provenance required")
    now, checked = instant(now), instant(item.get("checked_at"))
    if not timedelta(0) <= now - checked <= timedelta(hours=24):
        raise PulseError("EVENT_UNVERIFIED", "Source needs a fresh check before recommending")
    if item.get("expires_at") and instant(item["expires_at"]) <= now:
        raise PulseError("EVENT_UNVERIFIED", "Offer has expired")
    if item.get("eligibility") not in ("eligible", "ineligible", "unknown"):
        raise PulseError("VALIDATION_ERROR", "Explicit eligibility status required")
    if item["eligibility"] == "ineligible":
        raise PulseError("EVENT_UNVERIFIED", "Known ineligible benefit excluded")
    for key in ("title", "next_step"):
        if not isinstance(item.get(key), str) or not item[key].strip():
            raise PulseError("VALIDATION_ERROR", "Card title and next step required")
    restrictions = item.get("restrictions")
    if not isinstance(restrictions, list) or any(not isinstance(x, str) for x in restrictions):
        raise PulseError("VALIDATION_ERROR", "Restrictions must be explicit, including unknowns")
    window = assess_window(context)
    if window["status"] == "conflict":
        raise PulseError("HARD_CONSTRAINT_FAILED", window["reason"])
    duration, travel = item.get("duration_minutes"), item.get("travel_minutes_each_way")
    timing_known = all(type(x) is int and x >= 0 for x in (duration, travel)) and duration > 0
    if timing_known and window["status"] == "student_confirmed" and duration + 2 * travel > window["minutes"]:
        raise PulseError("HARD_CONSTRAINT_FAILED", "Activity and return travel exceed the window")
    if item.get("start_at") is not None or item.get("end_at") is not None:
        es, ee = instant(item.get("start_at")), instant(item.get("end_at"))
        if ee <= es or ee <= now:
            raise PulseError("EVENT_UNVERIFIED", "Invalid or expired event timing")
        if window["status"] == "student_confirmed":
            buffer = timedelta(minutes=travel if timing_known else 0)
            if es - buffer < instant(context["availability_start"]) or ee + buffer > instant(context["availability_end"]):
                raise PulseError("HARD_CONSTRAINT_FAILED", "Event and return travel do not fit")
    price = item.get("cost_cents")
    verified_price = item.get("cost_verified") is True and type(price) is int and price >= 0
    budget = context.get("budget_cents")
    if budget is not None and (type(budget) is not int or budget < 0):
        raise PulseError("VALIDATION_ERROR", "Invalid private budget")
    if verified_price and budget is not None and price > budget:
        raise PulseError("HARD_CONSTRAINT_FAILED", "Option exceeds the authorized spending limit")
    ready = (window["status"] == "student_confirmed" and timing_known
             and item["eligibility"] == "eligible" and verified_price)
    eligibility = "Source-listed eligibility fits the supplied criteria; confirm at redemption." if item["eligibility"] == "eligible" else "Eligibility not verified; check requirements first."
    cost = ("$%.2f listed; extras may apply." % (price / 100)) if verified_price else "Cost not verified."
    fit = "Fits the student-confirmed time window including estimated return travel." if window["status"] == "student_confirmed" and timing_known else "Tentative idea; availability or travel time still needs confirmation."
    style = personality(context)
    intro = {"Chill": "Here's an unlock.", "Playful": "Side quest unlocked!",
             "Roast Me": "This hidden perk has been playing hide-and-seek a little too well."}[style]
    label = "[FICTIONAL DEMO] " if item["synthetic"] else ""
    text = (f"{intro}\n{label}{item['title']}\nWhy: {fit}\nEligibility: {eligibility}\n"
            f"Cost: {cost}\nRestrictions: {'; '.join(restrictions) or 'Not verified; check the source.'}\n"
            f"Next: {item['next_step']}\n{item['source_url']}\nChecked: {checked.isoformat()} (within 24h; terms can change).")
    return {"visibility": "private", "text": text, "status": "candidate" if ready else "tentative",
            "personality": style, "synthetic": item["synthetic"], "sent": False,
            "booked": False, "source_url": item["source_url"]}


def checkin_draft(context, *, cadence, local_time, timezone, notification="text", empty="brief", weekday=None):
    """Prepare instructions for native scheduling; never registers a task."""
    if context.get("authorized") is not True or context.get("alerts_opt_in") is not True:
        raise PulseError("CONSENT_REQUIRED", "Explicit check-in permission required")
    if cadence not in ("daily", "weekdays", "weekly") or notification not in ("text", "silent") or empty not in ("brief", "silent"):
        raise PulseError("VALIDATION_ERROR", "Choose supported cadence and notification settings")
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", local_time) or not isinstance(timezone, str) or not timezone.strip():
        raise PulseError("VALIDATION_ERROR", "Confirm local time and timezone")
    # Windows may lack IANA tzdata; these two supported fixed zones need no package.
    if timezone not in ("America/Phoenix", "UTC"):
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise PulseError("VALIDATION_ERROR", "Timezone is unknown or local timezone data is unavailable")
    if cadence == "weekly" and (type(weekday) is not int or not 0 <= weekday <= 6):
        raise PulseError("VALIDATION_ERROR", "Choose a weekly day (Monday=0 through Sunday=6)")
    if cadence != "weekly" and weekday is not None:
        raise PulseError("VALIDATION_ERROR", "Weekday selection applies to weekly cadence")
    settings = {"cadence": cadence, "local_time": local_time, "timezone": timezone,
                "notification": notification, "empty": empty}
    if cadence == "weekly":
        settings["weekday"] = weekday
    if context.get("approved_checkin") != settings:
        raise PulseError("CONSENT_REQUIRED", "Confirm these exact notification settings")
    return {"mode": "native_instruction_draft", "settings": settings, "scheduled": False,
            "instructions": "Recheck authorized calendar/Canvas and protected time; confirm possible windows, browse fresh original sources, send concise Unlock Cards only to this student. Respect quiet hours, suppress duplicates, honor revocation and the empty-result preference. Update an existing Unlocks/Planner/Campus Pulse task rather than duplicating it.",
            "next": "Use Cubbie's native scheduled check-ins and confirm only its observed outcome."}


def solo_fallback():
    """No personal data in a shareable invitation; student chooses and sends it."""
    return {"mode": "solo_available", "sent": False, "scheduled": False,
            "next": "Choose a verified Unlock Card, confirm your window and entry requirements, then make a solo plan.",
            "invitation_draft": "Want to join me for an activity? We can choose a time and check the details together.",
            "reminder": "If you'd like a reminder, confirm the time and timezone; nothing has been scheduled."}
