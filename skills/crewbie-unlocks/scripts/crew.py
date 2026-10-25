#!/usr/bin/env python3
"""crew.py - client for the Crewbie API, used by the Crewbie Unlocks Cubbie Skill.

Standard library only. Prints one `KEY value` line per fact (or raw JSON with --json).

Exit codes: 0 ok, 2 student action needed (link, expired, stale), 3 API unreachable,
4 invalid input, 5 server error. Errors are printed to stderr as `ERROR <code> <message>`.

Intent file (for `submit --file`), same body as POST /v1/intents:

  {
    "event": {"source_url": "https://...", "title": "Board game night",
              "location_label": "Hayden Library", "date": "2026-10-30",
              "start_time": "18:00", "end_time": "21:00"},
    "shared": {"window": {"start": "2026-10-30T18:00:00-07:00", "end": "2026-10-30T20:00:00-07:00"},
               "activity_min_minutes": 90, "budget_band": "low",
               "vibe": "chill", "interests": ["board-games"]},
    "private": {"flex": {"earliest": "2026-10-30T17:30:00-07:00",
                         "latest": "2026-10-30T20:30:00-07:00"},
                "budget_cap_usd": 15}
  }
"""

import argparse
import json
import os
import secrets
import socket
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_API_URL = "https://18-220-104-252.sslip.io"
CLIENT = "crew.py/1.0"
TIMEOUT_SECONDS = 15

EXIT_OK, EXIT_ACTION, EXIT_UNREACHABLE, EXIT_INPUT, EXIT_SERVER = 0, 2, 3, 4, 5
ACTION_CODES = {"LINK_REQUIRED", "OFFER_EXPIRED", "OFFER_STALE", "ALREADY_IN_ROOM", "EVENT_STARTED"}
INPUT_CODES = {"VALIDATION_FAILED", "NOT_FOUND", "OFFER_CLOSED"}


class ApiError(Exception):
    def __init__(self, status, code, message, details=None):
        Exception.__init__(self, message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}


class Unreachable(Exception):
    pass


class InputError(Exception):
    pass


# ---------------------------------------------------------------- local state


def state_path():
    return Path.home() / ".config" / "crewbie" / "install.json"


def load_state():
    try:
        return json.loads(state_path().read_text())
    except (OSError, ValueError):
        return {}


def save_state(state):
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_name(path.name + ".tmp")
    descriptor = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        json.dump(state, handle)
    os.replace(str(temp), str(path))


# ---------------------------------------------------------------- http


def api_url():
    return os.environ.get("CREWBIE_API_URL", DEFAULT_API_URL).rstrip("/")


def _send(method, path, token, body, headers):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(api_url() + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    request.add_header("Accept", "application/json")
    if token:
        request.add_header("Authorization", "Bearer " + token)
    for name, value in (headers or {}).items():
        request.add_header(name, value)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            payload = json.loads(raw).get("error", {})
        except (ValueError, AttributeError):
            payload = {}
        raise ApiError(
            error.code,
            payload.get("code", "INTERNAL"),
            payload.get("message", "Unexpected server response."),
            payload.get("details", {}),
        )


def request(method, path, token=None, body=None, headers=None):
    """One retry on connection errors; HTTP errors are raised as ApiError."""
    for attempt in (1, 2):
        try:
            return _send(method, path, token, body, headers)
        except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as error:
            if attempt == 2:
                raise Unreachable(str(getattr(error, "reason", error)))


def register(state):
    """Create the local token if needed and register it (idempotent on the server)."""
    if not state.get("token"):
        state["token"] = secrets.token_urlsafe(32)
        state.setdefault("cursor", 0)
        save_state(state)
    _, body = request("POST", "/v1/installs", state["token"], {"client": CLIENT})
    state["install_id"] = body["install_id"]
    save_state(state)
    return body


def call(method, path, body=None, headers=None):
    """Authenticated call. Registers on first use and again if the server forgot the token."""
    state = load_state()
    if not state.get("token") or not state.get("install_id"):
        register(state)
    try:
        return request(method, path, state["token"], body, headers)
    except ApiError as error:
        if error.code != "UNAUTHORIZED":
            raise
        register(state)
        return request(method, path, state["token"], body, headers)


# ---------------------------------------------------------------- formatting


def local_zone():
    name = os.environ.get("CREWBIE_TZ", "America/Phoenix")
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:
        return timezone(timedelta(hours=-7))


def parse_time(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(local_zone())


def _clock(moment):
    hour = moment.hour % 12 or 12
    return "%d:%02d" % (hour, moment.minute), "am" if moment.hour < 12 else "pm"


def fmt_time(text):
    clock, suffix = _clock(parse_time(text))
    return clock + suffix


def fmt_window(window):
    start_clock, start_suffix = _clock(parse_time(window["start"]))
    end_clock, end_suffix = _clock(parse_time(window["end"]))
    if start_suffix == end_suffix:
        return "%s-%s%s" % (start_clock, end_clock, end_suffix)
    return "%s%s-%s%s" % (start_clock, start_suffix, end_clock, end_suffix)


def emit(lines):
    for line in lines:
        print(line)


def link_lines(details):
    code = details.get("link_code") or details.get("code")
    lines = ["LINK_CODE " + code]
    if details.get("invite_url"):
        lines.append("INVITE " + details["invite_url"])
    lines.append("COMMAND /crew link code:" + code)
    if details.get("expires_at"):
        lines.append("EXPIRES " + fmt_time(details["expires_at"]))
    return lines


def room_line(room):
    parts = ["size=%d" % room["size"]]
    if room.get("window"):
        parts.append("window=" + fmt_window(room["window"]))
    parts.append("vibe=%s" % room.get("vibe"))
    parts.append("budget=%s" % room.get("budget_band"))
    if room.get("top_interests"):
        parts.append("interests=" + ",".join(room["top_interests"]))
    return " ".join(parts)


# ---------------------------------------------------------------- commands


def cmd_register(args):
    body = register(load_state())
    if args.json:
        return print(json.dumps(body))
    emit(["INSTALL " + body["install_id"], "LINKED " + ("yes" if body["discord_linked"] else "no")])


def cmd_link(args):
    _, body = call("POST", "/v1/installs/me/link-codes")
    if args.json:
        return print(json.dumps(body))
    emit(link_lines(body))


def cmd_whoami(args):
    _, body = call("GET", "/v1/installs/me")
    if args.json:
        return print(json.dumps(body))
    lines = [
        "INSTALL " + body["install_id"],
        "LINKED " + ("yes" if body["discord_linked"] else "no"),
    ]
    if body.get("discord_username"):
        lines.append("DISCORD " + body["discord_username"])
    emit(lines)


def cmd_rooms(args):
    if len(args.event) > 5:
        raise InputError("at most 5 --event values")
    events = []
    for index, text in enumerate(args.event, 1):
        try:
            item = json.loads(text)
        except ValueError:
            raise InputError("--event must be a JSON object")
        if not isinstance(item, dict):
            raise InputError("--event must be a JSON object")
        item.setdefault("ref", "e%d" % index)
        events.append(item)
    _, body = call("POST", "/v1/rooms/lookup", {"events": events})
    if args.json:
        return print(json.dumps(body))
    lines = []
    for result in body["results"]:
        lines.append("EVENT %s ROOMS %d" % (result["ref"], len(result["rooms"])))
        lines.extend("ROOM " + room_line(room) for room in result["rooms"])
    emit(lines)


def cmd_events(args):
    """Find existing events that look like this one and already have a crew."""
    body = {"title": args.title, "date": args.date}
    if args.start_time:
        body["start_time"] = args.start_time
    if args.place:
        body["location_label"] = args.place
    if args.link:
        body["source_url"] = args.link
    _, result = call("POST", "/v1/events/search", body)
    if args.json:
        return print(json.dumps(result))
    events = result["events"]
    lines = ["EVENTS %d" % len(events)]
    for index, event in enumerate(events, 1):
        when = event["date"] + (" " + event["start_time"] if event.get("start_time") else "")
        parts = [
            "EVENT %d" % index,
            'TITLE "%s"' % event["title"].replace('"', "'"),
            "WHEN " + when,
        ]
        if event.get("location_label"):
            parts.append('PLACE "%s"' % event["location_label"].replace('"', "'"))
        parts.append("GOING %d" % event["going"])
        parts.append("LINK " + event["source_url"])
        lines.append(" ".join(parts))
    emit(lines)


def cmd_submit(args):
    try:
        with open(args.file) as handle:
            intent = json.load(handle)
    except (OSError, ValueError) as error:
        raise InputError("cannot read intent file: %s" % error)
    headers = {"Idempotency-Key": uuid.uuid4().hex}
    status, body = call("POST", "/v1/intents", intent, headers)
    if args.json:
        return print(json.dumps(body))
    lines = ["INTENT " + body["intent_id"]]
    offer = body.get("offer")
    if offer is None:
        lines.append("MATCHING")
    else:
        lines.append(
            "OFFER %s TYPE %s EXPIRES %s"
            % (offer["offer_id"], offer["type"], fmt_time(offer["expires_at"]))
        )
        if offer["type"] == "join" and offer.get("room"):
            room = offer["room"]
            lines.append(
                "CREW size=%d window=%s vibe=%s budget=%s"
                % (
                    room["size"],
                    fmt_window(offer["proposal"]),
                    room.get("vibe"),
                    room.get("budget_band"),
                )
            )
            if offer.get("window_changed_for_room"):
                lines.append("CHANGED window")
    emit(lines)


def cmd_accept(args):
    headers = {"Idempotency-Key": uuid.uuid4().hex}
    try:
        _, body = call("POST", "/v1/offers/%s/accept" % args.offer, None, headers)
    except ApiError as error:
        if error.code == "LINK_REQUIRED":
            if args.json:
                print(
                    json.dumps(
                        {
                            "error": {
                                "code": error.code,
                                "message": error.message,
                                "details": error.details,
                            }
                        }
                    )
                )
            else:
                emit(link_lines(error.details))
        raise
    if args.json:
        return print(json.dumps(body))
    room = body["room"]
    lines = ["JOINED room=%s size=%d" % (room["room_id"], room["size"])]
    if body.get("thread_url"):
        lines.append("THREAD " + body["thread_url"])
    else:
        lines.append("THREAD pending" if room["size"] >= 2 else "THREAD none")
    emit(lines)


def cmd_decline(args):
    _, body = call(
        "POST", "/v1/offers/%s/decline" % args.offer, None, {"Idempotency-Key": uuid.uuid4().hex}
    )
    print(json.dumps(body) if args.json else "DECLINED")


def cmd_leave(args):
    _, body = call("POST", "/v1/intents/%s/withdraw" % args.intent)
    print(json.dumps(body) if args.json else "LEFT")


def update_line(update):
    parts = [
        "UPDATE",
        update["kind"],
        'event="%s"' % update.get("event_title", "").replace('"', "'"),
    ]
    if update.get("room"):
        parts.append("size=%d" % update["room"]["size"])
    if update.get("window"):
        parts.append("window=" + fmt_window(update["window"]))
    if update.get("thread_url"):
        parts.append("thread=" + update["thread_url"])
    if update.get("offer_id"):
        parts.append("offer=" + update["offer_id"])
    return " ".join(parts)


def cmd_updates(args):
    state = load_state()
    cursor = int(state.get("cursor", 0))
    collected = []
    while True:
        _, body = call("GET", "/v1/updates?cursor=%d&limit=50" % cursor)
        collected.extend(body["updates"])
        cursor = body["cursor"]
        if len(body["updates"]) < 50:
            break
    state = load_state()
    state["cursor"] = cursor
    save_state(state)
    if args.json:
        return print(json.dumps({"cursor": cursor, "updates": collected}))
    emit([update_line(u) for u in collected] or ["NO_UPDATES"])


# ---------------------------------------------------------------- entry point


class Parser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write("ERROR INVALID_INPUT %s\n" % message)
        sys.exit(EXIT_INPUT)


def build_parser():
    parser = Parser(
        prog="crew.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", parser_class=Parser)
    sub.required = True

    def add(name, handler, help_text):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--json", action="store_true", help="print raw API JSON")
        command.set_defaults(handler=handler)
        return command

    add("register", cmd_register, "register this install")
    add("link", cmd_link, "get a Discord link code")
    add("whoami", cmd_whoami, "show install and link status")
    rooms = add("rooms", cmd_rooms, "list crews for up to 5 events")
    rooms.add_argument(
        "--event", action="append", required=True, help='JSON {"source_url","date","start_time"}'
    )
    events = add("events", cmd_events, "find existing crews for an event described in other words")
    events.add_argument("--title", required=True, help="event title as the student knows it")
    events.add_argument("--date", required=True, help="YYYY-MM-DD")
    events.add_argument("--start-time", help="HH:MM, 24-hour")
    events.add_argument("--place", help="venue or location")
    events.add_argument("--link", help="the original listing link, if known")
    submit = add("submit", cmd_submit, "submit an intent and get an offer")
    submit.add_argument("--file", required=True, help="intent JSON file")
    for name, handler in (("accept", cmd_accept), ("decline", cmd_decline)):
        add(name, handler, name + " an offer").add_argument("--offer", required=True)
    add("leave", cmd_leave, "leave a crew or stop matching").add_argument("--intent", required=True)
    add("updates", cmd_updates, "print updates since the last check")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
        return EXIT_OK
    except InputError as error:
        sys.stderr.write("ERROR INVALID_INPUT %s\n" % error)
        return EXIT_INPUT
    except Unreachable as error:
        sys.stderr.write("ERROR UNREACHABLE cannot reach the Crewbie API (%s)\n" % error)
        return EXIT_UNREACHABLE
    except ApiError as error:
        message = error.message
        fields = error.details.get("fields")
        if fields:
            message += " (" + "; ".join("%s: %s" % item for item in sorted(fields.items())) + ")"
        sys.stderr.write("ERROR %s %s\n" % (error.code, message))
        if error.code in ACTION_CODES:
            return EXIT_ACTION
        if error.code in INPUT_CODES:
            return EXIT_INPUT
        return EXIT_SERVER


if __name__ == "__main__":
    sys.exit(main())
