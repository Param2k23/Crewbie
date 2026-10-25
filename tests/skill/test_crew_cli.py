"""crew.py as a subprocess against a live local server with a throwaway HOME (06-CUBBIE-SKILL)."""

import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from crewbie.services import linking
from tests.conftest import LiveServer
from tests.support import EVENT_URL

CREW = Path(__file__).resolve().parents[2] / "skills/crewbie-unlocks/scripts/crew.py"


class Cli:
    def __init__(self, home: Path, url: str) -> None:
        self.home, self.url = home, url
        self.outputs: list[str] = []

    def run(self, *args: str, url: str | None = None) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "HOME": str(self.home), "CREWBIE_API_URL": url or self.url}
        result = subprocess.run(
            [sys.executable, str(CREW), *args], capture_output=True, text=True, env=env, timeout=60
        )
        self.outputs += [result.stdout, result.stderr]
        return result

    @property
    def state(self) -> dict[str, Any]:
        return json.loads((self.home / ".config/crewbie/install.json").read_text())

    def lines(self, *args: str, code: int = 0) -> list[str]:
        result = self.run(*args)
        assert result.returncode == code, (result.returncode, result.stdout, result.stderr)
        return result.stdout.splitlines()


@pytest.fixture
def cli(tmp_path: Path, live_server: LiveServer) -> Cli:
    home = tmp_path / "home"
    home.mkdir()
    return Cli(home, live_server.url)


def intent_file(tmp_path: Path, **overrides: Any) -> Path:
    start = datetime.now(UTC).replace(second=0, microsecond=0) + timedelta(hours=2)
    end = start + timedelta(hours=2)
    body = {
        "event": {
            "source_url": EVENT_URL,
            "title": "Board game night",
            "location_label": "Hayden Library",
            "date": start.date().isoformat(),
            "start_time": "18:00",
        },
        "shared": {
            "window": {"start": start.isoformat(), "end": end.isoformat()},
            "activity_min_minutes": 90,
            "budget_band": "low",
            "vibe": "chill",
            "interests": ["board-games"],
        },
        "private": {
            "flex": {
                "earliest": (start - timedelta(minutes=30)).isoformat(),
                "latest": (end + timedelta(minutes=30)).isoformat(),
            },
            "budget_cap_usd": 15,
        },
    }
    body.update(overrides)
    path = tmp_path / "intent.json"
    path.write_text(json.dumps(body))
    return path


def test_fr_ins_01_register_stores_a_private_token_and_never_prints_it(cli: Cli) -> None:
    lines = cli.lines("register")
    assert lines[0].startswith("INSTALL in_") and lines[1] == "LINKED no"
    state_file = cli.home / ".config/crewbie/install.json"
    assert stat.S_IMODE(state_file.stat().st_mode) == 0o600
    assert len(cli.state["token"]) >= 32
    assert cli.lines("register")[0] == lines[0]  # idempotent: same install
    assert cli.state["token"] not in "".join(cli.outputs)


def test_commands_register_automatically_when_there_is_no_state_file(cli: Cli) -> None:
    lines = cli.lines("whoami")
    assert lines[0].startswith("INSTALL ") and "LINKED no" in lines
    assert (cli.home / ".config/crewbie/install.json").exists()


def test_a_forgotten_token_is_re_registered_transparently(cli: Cli) -> None:
    cli.lines("register")
    state = cli.state
    state["token"] = "R" * 43  # the server has never seen this one
    (cli.home / ".config/crewbie/install.json").write_text(json.dumps(state))
    assert cli.lines("whoami")[1] == "LINKED no"
    assert cli.state["token"] == "R" * 43


def test_fr_lnk_01_link_prints_code_invite_command_and_expiry(cli: Cli) -> None:
    lines = cli.lines("link")
    assert re.fullmatch(r"LINK_CODE [A-HJ-NP-Z2-9]{6}", lines[0])
    assert lines[1] == "INVITE https://discord.gg/testinvite"
    assert lines[2] == f"COMMAND /crew link code:{lines[0].split()[1]}"
    assert re.fullmatch(r"EXPIRES \d{1,2}:\d{2}(am|pm)", lines[3])


def test_as_1_end_to_end_through_crew_py(cli: Cli, live_server: LiveServer, tmp_path: Path) -> None:
    path = intent_file(tmp_path)
    submit = cli.lines("submit", "--file", str(path))
    assert submit[0].startswith("INTENT i_")
    offer = re.fullmatch(r"OFFER (o_\w+) TYPE new_room EXPIRES \d{1,2}:\d{2}(am|pm)", submit[1])
    assert offer and len(submit) == 2
    offer_id, intent_id = offer.group(1), submit[0].split()[1]

    # AS-7: not linked yet, so exit 2 with the link instructions.
    refused = cli.run("accept", "--offer", offer_id)
    assert refused.returncode == 2
    assert refused.stdout.splitlines()[0].startswith("LINK_CODE ")
    assert refused.stderr.startswith("ERROR LINK_REQUIRED")
    code = refused.stdout.splitlines()[0].split()[1]
    linking.complete(live_server.ctx, code, "777777777777777777", "walker")

    joined = cli.lines("accept", "--offer", offer_id)
    assert re.fullmatch(r"JOINED room=r_\w+ size=1", joined[0]) and joined[1] == "THREAD none"
    assert "DISCORD walker" in cli.lines("whoami")

    updates = cli.lines("updates")
    assert [line.split()[1] for line in updates] == ["offer_ready", "joined"]
    assert updates[0].startswith('UPDATE offer_ready event="Board game night"')
    assert cli.lines("updates") == ["NO_UPDATES"]  # the cursor was saved

    date = json.loads(path.read_text())["event"]["date"]
    event = json.dumps({"source_url": EVENT_URL, "date": date, "start_time": "18:00"})
    rooms = cli.lines("rooms", "--event", event)
    assert rooms[0] == "EVENT e1 ROOMS 1"
    assert re.fullmatch(
        r"ROOM size=1 window=\S+(am|pm) vibe=chill budget=low interests=board-games", rooms[1]
    )

    assert cli.lines("leave", "--intent", intent_id) == ["LEFT"]
    assert cli.state["token"] not in "".join(cli.outputs)


def test_decline_and_closed_offer_exit_codes(cli: Cli, tmp_path: Path) -> None:
    submit = cli.lines("submit", "--file", str(intent_file(tmp_path)))
    offer_id = submit[1].split()[1]
    assert cli.lines("decline", "--offer", offer_id) == ["DECLINED"]
    closed = cli.run("decline", "--offer", offer_id)
    assert closed.returncode == 4 and closed.stderr.startswith("ERROR OFFER_CLOSED")


def test_fr_skl_02_json_flag_prints_the_raw_api_response(cli: Cli, tmp_path: Path) -> None:
    body = json.loads(cli.run("submit", "--file", str(intent_file(tmp_path)), "--json").stdout)
    assert body["state"] == "offered" and body["offer"]["type"] == "new_room"
    assert json.loads(cli.run("register", "--json").stdout)["install_id"].startswith("in_")
    updates = json.loads(cli.run("updates", "--json").stdout)
    assert updates["updates"][0]["kind"] == "offer_ready"


def test_fr_skl_02_exit_code_3_when_the_api_is_unreachable(cli: Cli, tmp_path: Path) -> None:
    result = cli.run("whoami", url="http://127.0.0.1:1")
    assert result.returncode == 3 and result.stderr.startswith("ERROR UNREACHABLE")
    assert result.stdout == ""


def test_fr_skl_02_exit_code_4_for_invalid_input(cli: Cli, tmp_path: Path) -> None:
    assert cli.run("submit", "--file", str(tmp_path / "missing.json")).returncode == 4
    broken = tmp_path / "broken.json"
    broken.write_text("{nope")
    assert cli.run("submit", "--file", str(broken)).returncode == 4
    assert cli.run("rooms", "--event", "not json").returncode == 4
    six = [
        a
        for i in range(6)
        for a in ("--event", json.dumps({"source_url": "https://x.test", "date": "2026-01-01"}))
    ]
    assert cli.run("rooms", *six).returncode == 4
    assert cli.run("accept").returncode == 4  # missing required --offer
    assert cli.run("bogus").returncode == 4
    unknown = cli.run("accept", "--offer", "o_unknown")
    assert unknown.returncode == 4 and "NOT_FOUND" in unknown.stderr


def test_fr_skl_02_validation_errors_name_the_fields_but_not_the_values(
    cli: Cli, tmp_path: Path
) -> None:
    path = intent_file(tmp_path)
    body = json.loads(path.read_text())
    body["private"]["flex"]["earliest"] = "2099-01-01T00:00:00+00:00"
    path.write_text(json.dumps(body))
    result = cli.run("submit", "--file", str(path))
    assert result.returncode == 4
    assert "flex.earliest" in result.stderr and "2099" not in result.stderr


def test_help_documents_the_intent_file_format(cli: Cli) -> None:
    result = cli.run("--help")
    assert (
        result.returncode == 0 and "private" in result.stdout and "budget_cap_usd" in result.stdout
    )


def load_crew_module() -> Any:
    sys.dont_write_bytecode = True  # never leave a __pycache__ inside the Skill folder
    spec = importlib.util.spec_from_file_location("crew_under_test", CREW)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_window_formatting_uses_phoenix_time_and_compact_meridiem() -> None:
    crew = load_crew_module()
    assert (
        crew.fmt_window({"start": "2026-10-30T23:00:00+00:00", "end": "2026-10-31T01:00:00+00:00"})
        == "4:00-6:00pm"
    )
    assert (
        crew.fmt_window({"start": "2026-10-30T18:00:00+00:00", "end": "2026-10-30T20:30:00+00:00"})
        == "11:00am-1:30pm"
    )
    assert crew.fmt_time("2026-10-30T19:05:00Z") == "12:05pm"
    assert crew.fmt_time("2026-10-30T07:00:00+00:00") == "12:00am"


def test_crew_py_uses_only_the_standard_library() -> None:
    imported = set(re.findall(r"^\s*(?:import|from)\s+([\w.]+)", CREW.read_text(), re.M))
    third_party = {m.split(".")[0] for m in imported} - set(sys.stdlib_module_names)
    assert third_party == set()
    assert "ANTHROPIC" not in CREW.read_text().upper()  # C-2: no team secrets in skills/


def test_the_default_api_url_is_the_public_https_address_and_the_env_var_overrides_it() -> None:
    crew = load_crew_module()
    assert crew.DEFAULT_API_URL.startswith("https://") and "localhost" not in crew.DEFAULT_API_URL
    os.environ["CREWBIE_API_URL"] = "http://localhost:9/"
    try:
        assert crew.api_url() == "http://localhost:9"
    finally:
        del os.environ["CREWBIE_API_URL"]
    assert crew.api_url() == crew.DEFAULT_API_URL


def test_events_finds_a_crew_started_by_another_student_under_different_wording(
    tmp_path: Path, live_server: LiveServer
) -> None:
    host = Cli(tmp_path / "host", live_server.url)
    other = Cli(tmp_path / "other", live_server.url)
    for cli in (host, other):
        cli.home.mkdir()
    path = intent_file(tmp_path)
    date = json.loads(path.read_text())["event"]["date"]

    offer_id = host.lines("submit", "--file", str(path))[1].split()[1]
    code = host.run("accept", "--offer", offer_id).stdout.splitlines()[0].split()[1]
    linking.complete(live_server.ctx, code, "811111111111111111", "host")
    assert host.lines("accept", "--offer", offer_id)[0].startswith("JOINED")

    assert other.lines("events", "--title", "Nobody", "--date", date) == ["EVENTS 0"]
    lines = other.lines(
        "events", "--title", "Board Game Night (all welcome)", "--date", date,
        "--start-time", "18:20", "--place", "Hayden Library, Tempe",
    )  # fmt: skip
    assert lines[0] == "EVENTS 1"
    expected = f'EVENT 1 TITLE "Board game night" WHEN {date} 18:00 PLACE "Hayden Library"'
    assert lines[1] == f"{expected} GOING 1 LINK {EVENT_URL}"
    raw = json.loads(
        other.run("events", "--title", "Board game night", "--date", date, "--json").stdout
    )
    assert raw["events"][0]["source_url"] == EVENT_URL
    bad = other.run("events", "--title", "x", "--date", "tomorrow")
    assert bad.returncode == 4 and "VALIDATION_FAILED" in bad.stderr
    assert other.run("events", "--date", date).returncode == 4  # --title is required
