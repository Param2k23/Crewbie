"""NFR-PRV-01: private envelope values must not appear anywhere except encrypted `envelopes` rows.

Sentinel values are pushed through every flow, then every surface is scanned: HTTP responses,
captured JSON logs, and every database table other than `envelopes` (which covers updates, outbox
payloads and public events).
"""

import logging
from collections.abc import Iterator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from crewbie.domain.intent import PrivateEnvelope
from crewbie.logging import JsonFormatter, RedactionFilter
from crewbie.services.context import ServiceContext
from tests.api.test_room_flow import join, start_room
from tests.conftest import ADMIN_TOKEN
from tests.support import ScriptedMatcher, Student, at

FLEX_EARLIEST = at(5 * 60 + 37).replace(second=41)  # 20:37:41 UTC
FLEX_LATEST = at(8 * 60 + 43).replace(second=19)  # 23:43:19 UTC
CAP = 913.37
NEEDLES = [
    "2026-11-06T20:37:41",
    "2026-11-06 20:37:41",
    "2026-11-06T23:43:19",
    "2026-11-06 23:43:19",
    "913.37",
]
SENTINEL = dict(  # the shared window sits inside the flex range: 21:00-23:00 UTC
    start=6 * 60,
    end=8 * 60,
    flex_earliest=FLEX_EARLIEST,
    flex_latest=FLEX_LATEST,
    cap=CAP,
)


def leaked(text_value: str) -> list[str]:
    return [needle for needle in NEEDLES if needle in text_value]


@pytest.fixture
def surfaces(client: TestClient) -> Iterator[dict[str, list[str]]]:
    """Record every HTTP response and every formatted log line produced during a test."""
    seen: dict[str, list[str]] = {"http": [], "logs": []}
    original = client.request

    def recording(*args, **kwargs):  # type: ignore[no-untyped-def]
        response = original(*args, **kwargs)
        seen["http"].append(f"{response.status_code} {dict(response.headers)} {response.text}")
        return response

    client.request = recording  # type: ignore[method-assign]

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            seen["logs"].append(JsonFormatter().format(record))

    handler = Capture(level=logging.DEBUG)
    handler.addFilter(RedactionFilter())
    root = logging.getLogger()
    previous = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    yield seen
    root.removeHandler(handler)
    root.setLevel(previous)


def database_dump(client: TestClient) -> dict[str, str]:
    engine = client.app.state.crewbie.engine  # type: ignore[attr-defined]
    dump: dict[str, str] = {}
    with engine.connect() as connection:
        tables = [
            row[0]
            for row in connection.execute(text("select name from sqlite_master where type='table'"))
        ]
        for table in tables:
            rows = connection.execute(text(f'select * from "{table}"')).fetchall()
            dump[table] = "\n".join(repr(tuple(row)) for row in rows)
    return dump


def exercise_everything(
    client: TestClient, ctx: ServiceContext, matcher: ScriptedMatcher, students: list[Student]
) -> None:
    a, b, c = students
    admin = {"X-Admin-Token": ADMIN_TOKEN}

    a_intent, room_id = start_room(
        ctx, a, **SENTINEL
    )  # submit, 409 LINK_REQUIRED is separate below
    b_joined = join(ctx, matcher, b, room_id, (6 * 60 + 30, 8 * 60), **SENTINEL)
    # Error paths that receive sentinel input.
    from tests.support import intent_body

    for bad in (
        intent_body(**{**SENTINEL, "start": 8 * 60, "end": 6 * 60}),
        intent_body(**{**SENTINEL, "flex_earliest": at(9 * 60)}),
        intent_body(**{**SENTINEL, "title": ""}),
    ):
        assert c.post("/v1/intents", bad).status_code == 422
    c_offer = c.submit(**SENTINEL)["offer"]["offer_id"]
    c.post(f"/v1/offers/{c_offer}/accept")  # LINK_REQUIRED
    c.post(f"/v1/offers/{c_offer}/accept")
    c.post(f"/v1/offers/{c_offer}/decline")
    c.get(f"/v1/offers/{c_offer}")  # 404/405 path

    for student in (a, b, c):
        student.get("/v1/updates")
        student.get("/v1/installs/me")
    a.get(f"/v1/intents/{a_intent}")
    a.get("/v1/rooms", params={"event_key": "0" * 16})
    for path in ("/v1/admin/rooms", "/v1/admin/outbox?state=pending", "/v1/admin/outbox"):
        client.get(path, headers=admin)
    client.get("/healthz")
    b.post(f"/v1/intents/{b_joined['intent_id']}/withdraw")
    a.client.delete("/v1/installs/me", headers=a.headers)
    client.post(f"/v1/admin/rooms/{room_id}/close", headers=admin)


def test_nfr_prv_01_sentinel_values_never_leave_the_encrypted_envelope(
    client: TestClient,
    ctx: ServiceContext,
    matcher: ScriptedMatcher,
    make_student,  # type: ignore[no-untyped-def]
    surfaces: dict[str, list[str]],
) -> None:
    students = [make_student(), make_student(), make_student()]
    exercise_everything(client, ctx, matcher, students)

    assert len(surfaces["http"]) > 25 and len(surfaces["logs"]) > 25  # the scan saw real traffic
    assert [n for line in surfaces["http"] for n in leaked(line)] == []
    assert [n for line in surfaces["logs"] for n in leaked(line)] == []
    dump = database_dump(client)
    assert "envelopes" in dump
    assert {table: leaked(rows) for table, rows in dump.items() if table != "envelopes"} == {
        table: [] for table in dump if table != "envelopes"
    }
    assert leaked(dump["envelopes"]) == []  # ciphertext only


def test_nfr_prv_01_envelope_is_stored_and_decryptable_so_the_scan_is_meaningful(
    client: TestClient,
    ctx: ServiceContext,
    make_student,  # type: ignore[no-untyped-def]
) -> None:
    student = make_student()
    intent_id = student.submit(**SENTINEL)["intent_id"]
    with ctx.uow_factory() as uow:
        envelope = uow.intents.load_envelope(intent_id)
    assert isinstance(envelope, PrivateEnvelope)
    assert envelope.flex_earliest == FLEX_EARLIEST and envelope.budget_cap_usd == CAP
    # Positive control: the scanner does flag the values when they are present.
    assert leaked(f"{FLEX_EARLIEST.isoformat()} {CAP}") == ["2026-11-06T20:37:41", "913.37"]
    assert isinstance(FLEX_LATEST, datetime)


def test_nfr_prv_01_exception_text_and_repr_never_carry_envelope_values() -> None:
    envelope = PrivateEnvelope(FLEX_EARLIEST, FLEX_LATEST, CAP)
    assert leaked(repr(envelope) + str(envelope) + f"{envelope!r:>80}") == []
    record = logging.LogRecord("t", logging.ERROR, __file__, 1, "failed for %s", (envelope,), None)
    assert leaked(JsonFormatter().format(record)) == []
