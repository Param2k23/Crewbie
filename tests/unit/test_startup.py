import base64
import subprocess
import sys

import pytest

from crewbie import __main__ as entrypoint
from crewbie.config import Settings, startup_problems

KEY = base64.urlsafe_b64encode(b"k" * 32).decode()
PROD = {
    "CREWBIE_ENV": "prod",
    "CREWBIE_PUBLIC_URL": "https://crewbie.example.com",
    "CREWBIE_ENVELOPE_KEY": KEY,
}


def test_nfr_dep_01_dev_starts_with_no_configuration() -> None:
    assert startup_problems({}) == []
    assert startup_problems({"CREWBIE_ENV": "dev", "CREWBIE_ENVELOPE_KEY": "garbage"}) == []


def test_production_refuses_to_start_without_its_secrets() -> None:
    problems = startup_problems({"CREWBIE_ENV": "prod"})
    assert "CREWBIE_ENVELOPE_KEY: missing" in problems and "CREWBIE_PUBLIC_URL: missing" in problems
    assert startup_problems(PROD) == []


def test_production_requires_https_and_a_valid_key_and_complete_discord_settings() -> None:
    assert startup_problems({**PROD, "CREWBIE_PUBLIC_URL": "http://crewbie.example.com"}) == [
        "CREWBIE_PUBLIC_URL: must be https in production"
    ]
    assert "CREWBIE_ENVELOPE_KEY: invalid" in startup_problems(
        {**PROD, "CREWBIE_ENVELOPE_KEY": "x"}
    )
    discord = startup_problems({**PROD, "CREWBIE_DISCORD_ENABLED": "true"})
    assert (
        "CREWBIE_DISCORD_TOKEN: missing" in discord
        and "CREWBIE_DISCORD_GUILD_ID: missing" in discord
    )


def test_problems_name_variables_but_never_print_their_values() -> None:
    leaky = {**PROD, "CREWBIE_ADMIN_TOKEN": "short-secret-value"}
    assert "short-secret-value" not in "".join(startup_problems(leaky))


def test_help_prints_usage_and_exits_cleanly(capsys: pytest.CaptureFixture[str]) -> None:
    assert entrypoint.main(["--help"]) == 0
    assert "python -m crewbie" in capsys.readouterr().out


def test_unknown_arguments_are_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert entrypoint.main(["serve"]) == 2
    assert "usage" in capsys.readouterr().err


def test_production_start_aborts_before_serving_when_misconfigured(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)  # no .env here
    for name in ("CREWBIE_ENVELOPE_KEY", "CREWBIE_PUBLIC_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CREWBIE_ENV", "prod")
    started: list[object] = []
    monkeypatch.setattr(entrypoint.uvicorn, "run", lambda *a, **k: started.append((a, k)))
    assert entrypoint.main([]) == 1
    assert started == [] and "Refusing to start in production" in capsys.readouterr().err


def test_the_server_is_started_single_process_and_proxy_headers_follow_the_setting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CREWBIE_ENV", "dev")
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(entrypoint.uvicorn, "run", lambda *a, **k: calls.append(k))
    monkeypatch.setenv("CREWBIE_TRUST_PROXY", "true")
    assert entrypoint.main([]) == 0
    monkeypatch.setenv("CREWBIE_TRUST_PROXY", "false")
    assert entrypoint.main([]) == 0
    trusted, direct = calls
    assert trusted["workers"] == direct["workers"] == 1
    assert (trusted["proxy_headers"], trusted["forwarded_allow_ips"]) == (True, "*")
    assert (direct["proxy_headers"], direct["forwarded_allow_ips"]) == (False, None)


def test_port_comes_from_the_hosts_port_variable_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CREWBIE_PORT", "8000")
    monkeypatch.setenv("PORT", "10000")
    assert Settings(_env_file=None).port == 10000  # type: ignore[call-arg]


def test_the_module_prints_help_from_the_command_line() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "crewbie", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0 and "usage: python -m crewbie" in result.stdout
