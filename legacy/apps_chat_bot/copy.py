"""Group-message copy. Pure functions; nothing here reads private data."""
from __future__ import annotations

from datetime import datetime
from typing import Mapping, Sequence


def fmt_window(start_at: str, end_at: str) -> str:
    s = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
    e = datetime.fromisoformat(end_at.replace("Z", "+00:00"))
    off = s.strftime("%z")
    off = f"UTC{off[:3]}:{off[3:]}" if off else ""
    day = f"{s:%a %b} {s.day}"
    return f"{day}, {s:%H:%M}-{e:%H:%M} ({off})" if s.date() == e.date() else f"{day} {s:%H:%M} to {e:%a %b} {e.day} {e:%H:%M} ({off})"


def names(refs: Sequence[str], roster: Mapping[str, str]) -> str:
    ns = [roster.get(r, r.removeprefix("stu_").title()) for r in refs]
    if len(ns) <= 2:
        return " and ".join(ns)
    return ", ".join(ns[:-1]) + f", and {ns[-1]}"


def proposal_message(snap: Mapping, roster: Mapping[str, str], revised_from: int | None = None) -> str:
    v = snap["version"]
    lines = []
    if revised_from is not None:
        lines.append(f"Update: here is version {v} of the plan. Earlier approvals (version {revised_from}) "
                     f"no longer apply, so please re-confirm.")
    else:
        lines.append(f"{LABELS.get(snap.get('activity_type'), 'Plan')} proposal, version {v}:")
    lines.append(f"{snap.get('title', 'Group plan')}")
    if snap.get("start_at") and snap.get("end_at"):
        lines.append(f"When: {fmt_window(snap['start_at'], snap['end_at'])}")
    if snap.get("location_label"):
        lines.append(f"Where: {snap['location_label']}")
    if snap.get("activities"):
        lines.append("Plan: " + " > ".join(snap["activities"]))
    if snap.get("cost_summary"):
        lines.append(f"Cost: {snap['cost_summary']}")
    if snap.get("estimate_disclaimer"):
        lines.append(snap["estimate_disclaimer"])
    if snap.get("open_questions"):
        lines.append("Still to settle: " + "; ".join(snap["open_questions"]))
    lines.append(f"To confirm, reply \"I accept version {v}\". \"Maybe\", \"sounds fun\" or \"yes if...\" "
                 f"won't count as a final yes. Reply \"no\" or \"I'm out\" any time.")
    return "\n".join(lines)


def accepted_ack(name: str, accepted: int, total: int, version: int) -> str:
    return f"Thanks {name}, recorded your yes for version {version} ({accepted}/{total} confirmed)."


def conditional_prompt(name: str, version: int) -> str:
    return (f"{name} has a condition on version {version}. That's not a final yes yet. "
            f"Can the group sort it out, or should I ask for a revised plan?")


def declined_ack(name: str, version: int) -> str:
    return f"Noted, {name} isn't in for version {version}. Nothing is confirmed; I'll ask for alternatives."


def withdrawn_ack(name: str) -> str:
    return f"Got it, {name} is stepping out. I'll pass that on so the plan can be rechecked."


def clarify_prompt(name: str, version: int) -> str:
    return (f"{name}, I want to be sure I read that right. For a final yes, reply "
            f"\"I accept version {version}\".")


def stale_prompt(name: str, current: int) -> str:
    return f"{name}, that reply was for an older version. The current plan is version {current}; reply \"I accept version {current}\" if you're in."


def confirmed_message(snap: Mapping, roster: Mapping[str, str]) -> str:
    when = f" {fmt_window(snap['start_at'], snap['end_at'])}." if snap.get("start_at") and snap.get("end_at") else ""
    return (f"Confirmed: all {len(snap['member_refs'])} of you ({names(snap['member_refs'], roster)}) "
            f"explicitly accepted version {snap['version']} of \"{snap.get('title', 'the plan')}\".{when} "
            f"No bookings or payments were made; this is a shared agreement only. "
            f"If anything changes I'll ask everyone to re-confirm.")


LABELS = {"meal": "Meal", "game": "Game", "trip": "Trip", "event": "Event"}


def planning_ack(label: str, timeframe: str | None) -> str:
    when = f" for {timeframe}" if timeframe else ""
    return f"On it. I'll ask for options{when} and post one plan to approve. Nothing is booked or decided yet."


def planning_busy() -> str:
    return "I'm already working on options for this, and will post one plan when it's ready."


def planner_unavailable() -> str:
    return "I noted that, but can't reach the planner right now. I'll try again shortly; nothing is decided."


def change_ack(name: str, version: int) -> str:
    return (f"Thanks {name}. I've asked for a revised option. {name}'s answer on version {version} is now "
            f"conditional, so it can't be confirmed until a new version arrives.")


def cancel_ack(name: str) -> str:
    return (f"{name} asked to cancel. I've passed that on and nothing is confirmed. "
            f"If anyone still wants to go ahead, say so and I'll ask for a new plan.")


def group_invite_private() -> str:
    return ("You opted in to meet others for an activity and a group is forming. Reply \"join\" to be added; "
            "names are shared with the group only after everyone has joined. Reply \"no\" to skip.")


def icebreaker_offer() -> str:
    return "If you'd like an icebreaker, just say \"icebreaker\". Totally optional."


def follow_up_message(pending: Sequence[str], roster: Mapping[str, str], version: int) -> str:
    return (f"Friendly nudge: still waiting on {names(pending, roster)} for version {version}. "
            f"No pressure; answer whenever you can, or say if you'd rather sit this one out.")


def no_solution_message() -> str:
    return ("I couldn't find a plan that works for everyone within the limits people set, so nothing is "
            "proposed. If someone changes dates or limits, I'll bring back a new option.")


def consent_revoked_message(name: str) -> str:
    return f"{name} withdrew their consent to take part. Any earlier yes from them is cleared."


def private_exception_prompt() -> str:
    return ("A plan needs your personal OK for an exception. This message is private to you and nothing is "
            "shared with the group. Reply here only if you want to review it.")


def introduction_message(names_: str, shared: Sequence[str], context_label: str) -> str:
    base = f"Welcome {names_}! You all agreed to be introduced for {context_label}."
    if shared:
        base += f" You share an interest in {' and '.join(shared[:2])}."
    return base


ICEBREAKERS = {
    "meal": [
        "Icebreaker (optional): what's a food you could eat every week?",
        "Icebreaker (optional): any place you've been meaning to try?",
    ],
    "game": [
        "Icebreaker (optional): what's your all-time favorite game or sport to play?",
        "Icebreaker (optional): casual or competitive, which side are you?",
    ],
    "event": [
        "Icebreaker (optional): what are you most looking forward to there?",
        "Icebreaker (optional): what's the best event you've been to this year?",
    ],
    "trip": [
        "Icebreaker (optional): what's your favorite kind of road-trip stop?",
        "Icebreaker (optional): if the trip had a theme song, what would it be?",
    ],
    "other": [
        "Icebreaker (optional): what's something you're looking forward to this month?",
        "Icebreaker (optional): what's a small thing that made your week better?",
    ],
    "interest": [
        "Icebreaker (optional): what got you into {interest}?",
        "Icebreaker (optional): what's one {interest} thing you'd recommend to this group?",
    ],
}
ICEBREAKERS["opportunity"] = ICEBREAKERS["event"]
