"""Cubbie-assisted event matching: different searches for the same event find each other."""

from datetime import timedelta

from fastapi.testclient import TestClient

from crewbie.services.context import ServiceContext
from tests.api.test_matching import create_room
from tests.support import FakeClock

LINK_A = "https://www.majesticphx.com/movie-theater/majestictempe7/movies"
PLACE_A = "Majestic Tempe 7, 1140 E Baseline Rd"
DATE = "2026-11-06"
PUBLIC_KEYS = {
    "event_key", "title", "location_label", "date", "start_time",
    "source_url", "going", "match", "rooms",
}  # fmt: skip


def clayface(**overrides):  # type: ignore[no-untyped-def]
    values = {
        "title": "Clayface",
        "url": LINK_A,
        "date": DATE,
        "start_time": "19:10",
        "place": PLACE_A,
    }
    values.update(overrides)
    return values


def search(student, **body):  # type: ignore[no-untyped-def]
    payload = {"title": "Clayface", "date": DATE, **body}
    response = student.post("/v1/events/search", payload)
    assert response.status_code == 200, response.text
    return response.json()["events"]


def test_a_different_wording_and_no_link_still_finds_the_crew_and_its_link_joins_it(
    real_ctx: ServiceContext,
    make_real_student,  # type: ignore[no-untyped-def]
) -> None:
    host, joiner = make_real_student(), make_real_student()
    create_room(real_ctx, host, start=60, end=180, **clayface())
    found = search(
        joiner, title="Clayface (2026) - PG-13", start_time="19:15",
        location_label="Majestic Tempe Movie Theater",
    )  # fmt: skip
    (candidate,) = found
    assert candidate["source_url"] == LINK_A and candidate["going"] == 1
    assert candidate["title"] == "Clayface" and candidate["match"] >= 0.65
    assert candidate["rooms"][0]["size"] == 1 and candidate["rooms"][0]["status"] == "open"

    # The student confirms it is the same event; using its link puts both in the same crew.
    offer = joiner.submit(
        start=60, end=180, **clayface(title="Clayface at Majestic", url=candidate["source_url"],
                                      date=candidate["date"], start_time=candidate["start_time"])
    )["offer"]  # fmt: skip
    assert offer["type"] == "join" and offer["room"]["size"] == 1


def test_without_the_confirmed_link_the_same_search_would_not_have_matched(
    real_ctx: ServiceContext,
    make_real_student,  # type: ignore[no-untyped-def]
) -> None:
    host, joiner = make_real_student(), make_real_student()
    create_room(real_ctx, host, start=60, end=180, **clayface())
    other_page = clayface(
        url="https://www.fandango.com/clayface-2026/movie-overview", start_time="19:15"
    )
    assert joiner.submit(start=60, end=180, **other_page)["offer"]["type"] == "new_room"


def test_the_exact_link_always_matches(real_ctx: ServiceContext, make_real_student) -> None:  # type: ignore[no-untyped-def]
    host, joiner = make_real_student(), make_real_student()
    create_room(real_ctx, host, start=60, end=180, **clayface())
    (candidate,) = search(
        joiner, title="Totally different words", start_time="19:10", source_url=LINK_A
    )
    assert candidate["match"] == 1.0


def test_different_events_are_not_suggested(real_ctx: ServiceContext, make_real_student) -> None:  # type: ignore[no-untyped-def]
    host, joiner = make_real_student(), make_real_student()
    create_room(real_ctx, host, start=60, end=180, **clayface())
    assert search(joiner, date="2026-11-07") == []  # another day
    assert search(joiner, start_time="21:30") == []  # another showing
    assert search(joiner, location_label="Harkins Tempe Marketplace 16") == []  # another cinema
    assert search(joiner, title="Wicked") == []  # another film
    assert search(joiner, title="Movie night") == []  # too vague


def test_only_events_with_a_live_crew_are_suggested(
    real_client: TestClient,
    real_ctx: ServiceContext,
    clock: FakeClock,
    make_real_student,  # type: ignore[no-untyped-def]
) -> None:
    host, joiner, spare = make_real_student(), make_real_student(), make_real_student()
    # An event nobody confirmed (an offer only) has no room, so it is not suggested.
    spare.submit(start=60, end=180, **clayface())
    assert search(joiner) == []
    create_room(real_ctx, host, start=60, end=180, **clayface(url="https://example.test/other"))
    assert len(search(joiner)) == 1
    clock.advance(hours=4)  # the crew's window has ended
    assert search(joiner) == []


def test_at_most_three_candidates_best_first(real_ctx: ServiceContext, make_real_student) -> None:  # type: ignore[no-untyped-def]
    joiner = make_real_student()
    for start in ("19:00", "19:05", "19:10", "19:20"):
        create_room(
            real_ctx, make_real_student(), start=60, end=180,
            **clayface(url=f"https://example.test/{start}", start_time=start),
        )  # fmt: skip
    found = search(joiner, start_time="19:10", location_label=PLACE_A)
    assert found[0]["start_time"] == "19:10" and len(found) == 3
    assert [c["match"] for c in found] == sorted((c["match"] for c in found), reverse=True)


def test_results_carry_only_public_event_and_room_fields(
    real_ctx: ServiceContext,
    make_real_student,  # type: ignore[no-untyped-def]
) -> None:
    host, joiner = make_real_student(), make_real_student()
    create_room(real_ctx, host, start=60, end=180, cap=913.37, **clayface())
    response = joiner.post("/v1/events/search", {"title": "Clayface", "date": DATE})
    (candidate,) = response.json()["events"]
    assert set(candidate) == PUBLIC_KEYS
    for needle in (host.install_id, joiner.install_id, "913", "member-", "discord"):
        assert needle not in response.text


def test_search_needs_a_token_and_valid_input(client: TestClient, make_student) -> None:  # type: ignore[no-untyped-def]
    assert client.post("/v1/events/search", json={"title": "x", "date": DATE}).status_code == 401
    student = make_student()
    for body in (
        {"title": "x"},
        {"title": "", "date": DATE},
        {"title": "x", "date": "11/06/2026"},
        {"title": "x", "date": DATE, "source_url": "http://insecure.test"},
        {"title": "x", "date": DATE, "extra": 1},
    ):
        assert student.post("/v1/events/search", body).status_code == 422, body


def test_the_matching_window_for_the_start_time_is_thirty_minutes(
    real_ctx: ServiceContext,
    make_real_student,  # type: ignore[no-untyped-def]
) -> None:
    host, joiner = make_real_student(), make_real_student()
    create_room(real_ctx, host, start=60, end=180, **clayface())
    assert len(search(joiner, start_time="19:40")) == 1
    assert search(joiner, start_time="19:41") == []
    assert len(search(joiner)) == 1  # an unknown start time can still be confirmed by the student
    assert timedelta(minutes=30).total_seconds() == 1800
