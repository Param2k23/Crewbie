import pytest
from hypothesis import given
from hypothesis import strategies as st

from crewbie.domain.event_match import EventDescriptor, match_score, title_score

CLAYFACE = EventDescriptor(
    "Clayface", "2026-10-25", "19:10", "Majestic Tempe 7, 1140 E Baseline Rd"
)


def event(
    title: str, date: str = "2026-10-25", start: str | None = "19:10", place: str | None = None
):  # type: ignore[no-untyped-def]
    return EventDescriptor(title, date, start, place)


def test_the_same_showing_found_through_different_pages_matches() -> None:
    variants = [
        event("Clayface", place="Majestic Tempe 7"),
        event("Clayface (2026)", place="Majestic Tempe Movie Theater"),
        event("CLAYFACE - PG-13", "2026-10-25", "19:15", "Majestic Tempe 7 Cinemas"),
        event("Clayface in IMAX", start=None, place=None),
    ]
    for variant in variants:
        score = match_score(variant, CLAYFACE)
        assert score is not None and score >= 0.65, variant


def test_the_score_is_symmetric_and_highest_for_identical_descriptions() -> None:
    other = event("Clayface (2026)", start="19:20", place="Majestic Tempe 7")
    assert match_score(other, CLAYFACE) == match_score(CLAYFACE, other)
    assert match_score(CLAYFACE, CLAYFACE) == pytest.approx(0.6 + 0.25 + 0.15)


@pytest.mark.parametrize(
    "different",
    [
        event("Clayface", date="2026-10-26", place="Majestic Tempe 7"),  # another day
        event("Clayface", start="21:30", place="Majestic Tempe 7"),  # another showing
        event("Clayface", place="Harkins Tempe Marketplace 16"),  # another cinema
        event("Wicked", place="Majestic Tempe 7"),  # another film
        event("Movie night", place="Majestic Tempe 7"),  # too vague a title
    ],
)
def test_different_events_do_not_match(different: EventDescriptor) -> None:
    assert match_score(different, CLAYFACE) is None


def test_the_same_title_at_a_nearby_but_different_place_is_not_merged() -> None:
    a = event("Board game night", place="Hayden Library, Tempe")
    b = event("Board game night", place="Noble Library")
    assert match_score(a, b) is None
    assert match_score(a, event("Board game night", place=None)) is not None


def test_titles_ignore_case_punctuation_years_ratings_and_filler_words() -> None:
    assert title_score("The Clayface Screening (2026) PG-13", "clayface") == pytest.approx(0.9)
    assert title_score("Clayface", "Clayface") == 1.0
    assert title_score("", "Clayface") == 0.0


def test_bad_times_do_not_crash() -> None:
    assert match_score(event("Clayface", start="soon"), CLAYFACE) is not None


words = st.text(alphabet="abcdefghij ", min_size=0, max_size=30)
descriptors = st.builds(
    EventDescriptor, words, st.sampled_from(["2026-10-25", "2026-10-26"]),
    st.one_of(st.none(), st.sampled_from(["18:00", "19:10", "20:00"])), st.one_of(st.none(), words),
)  # fmt: skip


@given(descriptors, descriptors)
def test_property_matching_is_symmetric_and_bounded(a: EventDescriptor, b: EventDescriptor) -> None:
    forward, backward = match_score(a, b), match_score(b, a)
    assert forward == backward
    assert forward is None or 0.65 <= forward <= 1.0 + 1e-9
    if a.date != b.date:
        assert forward is None
