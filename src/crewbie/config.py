"""Runtime settings and the `python -m crewbie.config check` command.

`check` validates raw environment values on its own, so it can report a malformed variable
instead of failing on construction, and it never prints a value.
"""

import base64
import binascii
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    env: Literal["dev", "prod"] = Field("dev", validation_alias="CREWBIE_ENV")
    public_url: str = Field("http://localhost:8000", validation_alias="CREWBIE_PUBLIC_URL")
    database_url: str = Field(
        "sqlite:///./data/crewbie.db", validation_alias="CREWBIE_DATABASE_URL"
    )
    timezone: str = Field("America/Phoenix", validation_alias="CREWBIE_TIMEZONE")
    host: str = Field("127.0.0.1", validation_alias="CREWBIE_HOST")
    port: int = Field(8000, validation_alias=AliasChoices("PORT", "CREWBIE_PORT"), gt=0)
    envelope_key: str = Field("", validation_alias="CREWBIE_ENVELOPE_KEY")
    admin_token: str = Field("", validation_alias="CREWBIE_ADMIN_TOKEN")

    discord_token: str = Field("", validation_alias="CREWBIE_DISCORD_TOKEN")
    discord_app_id: str = Field("", validation_alias="CREWBIE_DISCORD_APP_ID")
    discord_guild_id: str = Field("", validation_alias="CREWBIE_DISCORD_GUILD_ID")
    discord_board_channel_id: str = Field("", validation_alias="CREWBIE_DISCORD_BOARD_CHANNEL_ID")
    discord_crews_channel_id: str = Field("", validation_alias="CREWBIE_DISCORD_CREWS_CHANNEL_ID")
    discord_invite_url: str = Field("", validation_alias="CREWBIE_DISCORD_INVITE_URL")
    discord_test_channel_id: str = Field("", validation_alias="CREWBIE_DISCORD_TEST_CHANNEL_ID")
    discord_enabled: bool = Field(False, validation_alias="CREWBIE_DISCORD_ENABLED")

    llm_mode: Literal["on", "off"] = Field("off", validation_alias="CREWBIE_LLM_MODE")
    llm_model: str = Field("", validation_alias="CREWBIE_LLM_MODEL")
    anthropic_api_key: str = Field(
        "", validation_alias=AliasChoices("ANTHROPIC_API_KEY", "CREWBIE_ANTHROPIC_API_KEY")
    )

    offer_ttl_minutes: int = Field(15, validation_alias="CREWBIE_OFFER_TTL_MINUTES", gt=0)
    match_time_budget_seconds: int = Field(
        10, validation_alias="CREWBIE_MATCH_TIME_BUDGET_SECONDS", gt=0
    )
    max_candidate_rooms: int = Field(3, validation_alias="CREWBIE_MAX_CANDIDATE_ROOMS", gt=0)
    max_rounds: int = Field(3, validation_alias="CREWBIE_MAX_ROUNDS", gt=0)


settings = Settings()


Validator = Callable[[str], bool]


def _is_fernet_key(value: str) -> bool:
    try:
        return len(base64.urlsafe_b64decode(value.encode())) == 32
    except (binascii.Error, ValueError):
        return False


def _is_snowflake(value: str) -> bool:
    return value.isdigit() and 15 <= len(value) <= 20


def _is_http_url(value: str) -> bool:
    return value.startswith(("http://", "https://")) and len(value) > 8


def _is_positive_int(value: str) -> bool:
    return value.isdigit() and int(value) > 0


@dataclass(frozen=True)
class VarSpec:
    name: str
    validator: Validator
    required: Callable[[Mapping[str, str]], bool]


def _never(_: Mapping[str, str]) -> bool:
    return False


def _prod(values: Mapping[str, str]) -> bool:
    return values.get("CREWBIE_ENV") == "prod"


def _discord_on(values: Mapping[str, str]) -> bool:
    return values.get("CREWBIE_DISCORD_ENABLED", "").lower() in {"true", "1", "yes", "on"}


def _llm_on(values: Mapping[str, str]) -> bool:
    return values.get("CREWBIE_LLM_MODE") == "on"


def _non_empty(value: str) -> bool:
    return bool(value.strip())


def _long_token(value: str) -> bool:
    return len(value) >= 32


SPECS: tuple[VarSpec, ...] = (
    VarSpec("CREWBIE_ENV", lambda v: v in {"dev", "prod"}, _never),
    VarSpec("CREWBIE_PUBLIC_URL", _is_http_url, _prod),
    VarSpec("CREWBIE_DATABASE_URL", lambda v: v.startswith("sqlite:///"), _never),
    VarSpec("CREWBIE_TIMEZONE", _non_empty, _never),
    VarSpec("CREWBIE_HOST", _non_empty, _never),
    VarSpec("CREWBIE_PORT", _is_positive_int, _never),
    VarSpec("CREWBIE_ENVELOPE_KEY", _is_fernet_key, _prod),
    VarSpec("CREWBIE_ADMIN_TOKEN", _long_token, _never),
    VarSpec("CREWBIE_DISCORD_TOKEN", _non_empty, _discord_on),
    VarSpec("CREWBIE_DISCORD_APP_ID", _is_snowflake, _discord_on),
    VarSpec("CREWBIE_DISCORD_GUILD_ID", _is_snowflake, _discord_on),
    VarSpec("CREWBIE_DISCORD_BOARD_CHANNEL_ID", _is_snowflake, _discord_on),
    VarSpec("CREWBIE_DISCORD_CREWS_CHANNEL_ID", _is_snowflake, _discord_on),
    VarSpec("CREWBIE_DISCORD_INVITE_URL", _is_http_url, _discord_on),
    VarSpec("CREWBIE_DISCORD_TEST_CHANNEL_ID", _is_snowflake, _never),
    VarSpec("CREWBIE_DISCORD_ENABLED", lambda v: v.lower() in {"true", "false"}, _never),
    VarSpec("CREWBIE_LLM_MODE", lambda v: v in {"on", "off"}, _never),
    VarSpec("CREWBIE_LLM_MODEL", _non_empty, _llm_on),
    VarSpec("ANTHROPIC_API_KEY", _non_empty, _llm_on),
    VarSpec("CREWBIE_OFFER_TTL_MINUTES", _is_positive_int, _never),
    VarSpec("CREWBIE_MATCH_TIME_BUDGET_SECONDS", _is_positive_int, _never),
    VarSpec("CREWBIE_MAX_CANDIDATE_ROOMS", _is_positive_int, _never),
    VarSpec("CREWBIE_MAX_ROUNDS", _is_positive_int, _never),
)


def collect_raw_values(env_file: Path, environ: Mapping[str, str]) -> dict[str, str]:
    """Merge `.env` with the process environment; the process environment wins."""
    merged = {k: v for k, v in dotenv_values(env_file).items() if v is not None}
    merged.update(environ)
    return merged


def check(values: Mapping[str, str]) -> list[tuple[str, str]]:
    """Return (variable, status) rows. Status is ok, missing, invalid or unset (optional)."""
    rows: list[tuple[str, str]] = []
    for spec in SPECS:
        raw = values.get(spec.name, "")
        if not raw:
            rows.append((spec.name, "missing" if spec.required(values) else "unset"))
        else:
            rows.append((spec.name, "ok" if spec.validator(raw) else "invalid"))
    return rows


def main(argv: list[str]) -> int:
    if argv != ["check"]:
        sys.stderr.write("usage: python -m crewbie.config check\n")
        return 2
    rows = check(collect_raw_values(Path(".env"), os.environ))
    for name, status in rows:
        sys.stdout.write(f"{name:<40} {status}\n")
    return 1 if any(status in {"missing", "invalid"} for _, status in rows) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
