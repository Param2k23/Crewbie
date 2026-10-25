import base64
from pathlib import Path

from crewbie.config import Settings, check, collect_raw_values, main

VALID_KEY = base64.urlsafe_b64encode(b"k" * 32).decode()


def statuses(values: dict[str, str]) -> dict[str, str]:
    return dict(check(values))


def test_dev_defaults_need_nothing() -> None:
    result = statuses({})
    assert "missing" not in result.values()
    assert "invalid" not in result.values()


def test_prod_requires_envelope_key_and_public_url() -> None:
    result = statuses({"CREWBIE_ENV": "prod"})
    assert result["CREWBIE_ENVELOPE_KEY"] == "missing"
    assert result["CREWBIE_PUBLIC_URL"] == "missing"


def test_envelope_key_format_is_checked() -> None:
    assert statuses({"CREWBIE_ENVELOPE_KEY": VALID_KEY})["CREWBIE_ENVELOPE_KEY"] == "ok"
    assert statuses({"CREWBIE_ENVELOPE_KEY": "nope"})["CREWBIE_ENVELOPE_KEY"] == "invalid"


def test_discord_vars_required_only_when_enabled() -> None:
    assert statuses({})["CREWBIE_DISCORD_TOKEN"] == "unset"
    enabled = statuses({"CREWBIE_DISCORD_ENABLED": "true", "CREWBIE_DISCORD_GUILD_ID": "12"})
    assert enabled["CREWBIE_DISCORD_TOKEN"] == "missing"
    assert enabled["CREWBIE_DISCORD_GUILD_ID"] == "invalid"


def test_llm_vars_required_only_when_on() -> None:
    assert statuses({"CREWBIE_LLM_MODE": "on"})["ANTHROPIC_API_KEY"] == "missing"


def test_check_never_prints_values(tmp_path: Path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    secret = "s3cret-value-that-must-not-leak-0123456789"
    (tmp_path / ".env").write_text(f"CREWBIE_ADMIN_TOKEN={secret}\n")
    monkeypatch.chdir(tmp_path)
    assert main(["check"]) == 0
    out = capsys.readouterr()
    assert secret not in out.out + out.err
    assert "CREWBIE_ADMIN_TOKEN" in out.out


def test_check_exit_code_nonzero_on_invalid(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / ".env").write_text("CREWBIE_ENVELOPE_KEY=bad\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CREWBIE_ENVELOPE_KEY", raising=False)
    assert main(["check"]) == 1


def test_process_environment_overrides_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("CREWBIE_ENV=dev\n")
    assert collect_raw_values(env_file, {"CREWBIE_ENV": "prod"})["CREWBIE_ENV"] == "prod"


def test_settings_defaults_match_env_example() -> None:
    s = Settings(_env_file=None)
    assert (s.env, s.llm_mode, s.max_rounds, s.offer_ttl_minutes) == ("dev", "off", 3, 15)
