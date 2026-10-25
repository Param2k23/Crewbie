import json
import logging

import pytest
from fastapi.testclient import TestClient

from crewbie.logging import JsonFormatter, RedactionFilter, install_ref, redact, request_id_var


def render(**extra: object) -> dict[str, object]:
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "hello", None, None)
    for key, value in extra.items():
        setattr(record, key, value)
    RedactionFilter().filter(record)
    return json.loads(JsonFormatter().format(record))  # type: ignore[no-any-return]


def test_nfr_obs_01_log_lines_carry_the_standard_fields() -> None:
    token = request_id_var.set("req-12345678")
    try:
        line = render(room_id="r_1", job_id="j_1", event_type="x")
    finally:
        request_id_var.reset(token)
    assert {"ts", "level", "msg", "request_id", "install_ref", "room_id", "job_id"} <= set(line)
    assert line["request_id"] == "req-12345678" and line["msg"] == "hello"


def test_install_ref_is_the_first_eight_hex_of_the_sha256() -> None:
    assert install_ref("abc") == "ba7816bf"


def test_redaction_drops_private_keys_at_any_depth() -> None:
    line = render(
        token="secret-token",
        Authorization="Bearer abc",
        payload={
            "flex": {"earliest": "17:37"},
            "budget_cap_usd": 913,
            "ok": [{"envelope": 1, "a": 2}],
        },
    )
    text = json.dumps(line)
    for leaked in ("secret-token", "Bearer abc", "17:37", "913", '"envelope"'):
        assert leaked not in text
    assert line["payload"] == {"ok": [{"a": 2}]}


def test_redact_leaves_other_values_alone() -> None:
    assert redact({"a": (1, 2), "b": "x"}) == {"a": [1, 2], "b": "x"}


def test_one_info_line_per_request_without_query_string(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="crewbie.api"):
        client.get("/healthz?secret=abc")
    lines = [r for r in caplog.records if r.name == "crewbie.api" and r.getMessage() == "request"]
    assert len(lines) == 1
    record = lines[0]
    assert (record.path, record.status, record.method) == ("/healthz", 200, "GET")  # type: ignore[attr-defined]
    assert "secret" not in JsonFormatter().format(record)


def test_unhandled_errors_return_internal_with_the_request_id(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    app = client.app

    @app.get("/boom")  # type: ignore[attr-defined]
    def boom() -> None:
        raise RuntimeError("kaboom with 913 inside")

    with caplog.at_level(logging.ERROR, logger="crewbie.api"):
        response = client.get("/boom", headers={"X-Request-Id": "trace-abcdef12"})
    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "INTERNAL" and error["details"] == {"request_id": "trace-abcdef12"}
    assert response.headers["X-Request-Id"] == "trace-abcdef12"
    assert "kaboom" not in response.text
