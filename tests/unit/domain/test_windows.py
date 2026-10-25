from datetime import datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from crewbie.domain.errors import ValidationFailed
from crewbie.domain.windows import TimeWindow, intersect_all

from .helpers import at, window

windows = st.builds(
    lambda start, length: window(start, start + length),
    st.integers(-500, 500),
    st.integers(1, 500),
)


def test_fr_int_02_start_must_precede_end() -> None:
    with pytest.raises(ValidationFailed):
        window(10, 10)


def test_fr_int_02_naive_datetimes_rejected() -> None:
    with pytest.raises(ValidationFailed):
        TimeWindow(datetime(2026, 1, 1, 1), datetime(2026, 1, 1, 2))


def test_touching_windows_do_not_overlap() -> None:
    assert not window(0, 60).overlaps(window(60, 120))
    assert window(0, 60).intersect(window(60, 120)) is None


def test_intersect_hull_duration_contains() -> None:
    a, b = window(0, 90), window(60, 150)
    assert a.intersect(b) == window(60, 90)
    assert a.hull(b) == window(0, 150)
    assert a.duration.total_seconds() == 90 * 60
    assert a.hull(b).contains(a)
    assert at(0) == a.start


def test_intersect_all_empty_and_disjoint() -> None:
    assert intersect_all([]) is None
    assert intersect_all([window(0, 10), window(20, 30)]) is None
    assert intersect_all([window(0, 100), window(10, 90), window(20, 200)]) == window(20, 90)


@given(windows, windows)
def test_property_intersection_is_commutative_and_inside_both(a: TimeWindow, b: TimeWindow) -> None:
    assert a.intersect(b) == b.intersect(a)
    inter = a.intersect(b)
    assert (inter is not None) == a.overlaps(b)
    if inter:
        assert a.contains(inter) and b.contains(inter)


@given(windows, windows)
def test_property_hull_contains_both_and_is_commutative(a: TimeWindow, b: TimeWindow) -> None:
    assert a.hull(b) == b.hull(a)
    assert a.hull(b).contains(a) and a.hull(b).contains(b)


@given(windows)
def test_property_idempotent(a: TimeWindow) -> None:
    assert a.intersect(a) == a
    assert a.hull(a) == a


@given(st.lists(windows, min_size=1, max_size=6))
def test_property_intersect_all_is_order_independent(items: list[TimeWindow]) -> None:
    assert intersect_all(items) == intersect_all(reversed(items))
