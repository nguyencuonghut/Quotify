from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.working_days import is_working_day, reference_window, working_days_between

FRIDAY = date(2026, 10, 2)
SATURDAY = date(2026, 10, 3)
SUNDAY = date(2026, 10, 4)
MONDAY = date(2026, 10, 5)


def test_window_for_a_friday_point_is_seven_working_days_back() -> None:
    assert reference_window(FRIDAY, 7) == (date(2026, 9, 23), date(2026, 10, 1))


def test_window_for_a_monday_point_ends_on_sunday_and_spans_the_weekend() -> None:
    # 7 ngày làm việc trước thứ Hai 05/10: 24/09 đến 02/10; cuối tuần ở giữa vẫn nằm trong khoảng.
    assert reference_window(MONDAY, 7) == (date(2026, 9, 24), date(2026, 10, 4))


def test_window_for_a_saturday_point_starts_seven_working_days_back() -> None:
    assert reference_window(SATURDAY, 7) == (date(2026, 9, 24), date(2026, 10, 2))


def test_window_for_a_sunday_point_includes_the_saturday_before() -> None:
    assert reference_window(SUNDAY, 7) == (date(2026, 9, 24), date(2026, 10, 3))


def test_window_of_one_working_day_is_the_previous_working_day() -> None:
    assert reference_window(MONDAY, 1) == (date(2026, 10, 2), date(2026, 10, 4))


def test_window_rejects_a_non_positive_size() -> None:
    with pytest.raises(ValueError):
        reference_window(FRIDAY, 0)


@pytest.mark.parametrize(
    ("day", "expected"),
    [(FRIDAY, True), (SATURDAY, False), (SUNDAY, False), (MONDAY, True)],
)
def test_is_working_day(day: date, expected: bool) -> None:
    assert is_working_day(day) is expected


def test_between_friday_and_monday_is_one() -> None:
    assert working_days_between(FRIDAY, MONDAY) == 1


def test_between_never_counts_weekend_days() -> None:
    assert working_days_between(FRIDAY, SUNDAY) == 0
    assert working_days_between(SATURDAY, SUNDAY) == 0


def test_between_the_same_day_is_zero() -> None:
    assert working_days_between(FRIDAY, FRIDAY) == 0


def test_between_counts_the_end_day_but_not_the_start_day() -> None:
    assert working_days_between(date(2026, 9, 28), date(2026, 10, 2)) == 4


def test_between_a_full_week_is_five() -> None:
    assert working_days_between(date(2026, 9, 25), date(2026, 10, 2)) == 5


def test_between_with_end_before_start_is_zero() -> None:
    assert working_days_between(MONDAY, FRIDAY) == 0


@pytest.mark.parametrize("day", [date(2026, 10, d) for d in range(1, 15)])
def test_window_holds_exactly_the_requested_working_days(day: date) -> None:
    start, end = reference_window(day, 7)

    assert is_working_day(start)
    assert working_days_between(start - timedelta(days=1), end) == 7


def test_window_defaults_to_seven_working_days() -> None:
    assert reference_window(FRIDAY) == reference_window(FRIDAY, 7)
