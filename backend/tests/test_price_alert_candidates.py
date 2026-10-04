from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.services.price_alert_candidates import (
    LineRef,
    is_trigger_source,
    select_candidate_lines,
    trigger_delay_working_days,
)

SEED = uuid4()
HUMAN = uuid4()
MON = date(2026, 10, 5)
M1, M2 = uuid4(), uuid4()
DEC = date(2026, 12, 1)


def _confirmed(day: date, hour: int = 3) -> datetime:
    return datetime(day.year, day.month, day.day, hour, 0, tzinfo=UTC)


def _source(created_by: UUID | None, delay_days: int = 0, max_delay: int = 3) -> bool:
    received = date(2026, 9, 28)  # thứ Hai
    confirmed_day = received + timedelta(days=delay_days)
    return is_trigger_source(
        quote_created_by_id=created_by,
        seed_user_id=SEED,
        received_date=received,
        confirmed_at=_confirmed(confirmed_day),
        max_delay_working_days=max_delay,
    )


def test_a_real_person_confirming_the_same_day_is_a_trigger_source() -> None:
    assert _source(HUMAN) is True


def test_the_seed_account_is_excluded() -> None:
    assert _source(SEED) is False


def test_a_null_creator_is_not_mistaken_for_the_seed_account() -> None:
    assert _source(None) is True


def test_without_a_known_seed_user_nobody_is_excluded() -> None:
    assert is_trigger_source(
        quote_created_by_id=None,
        seed_user_id=None,
        received_date=MON,
        confirmed_at=_confirmed(MON),
        max_delay_working_days=3,
    )


@pytest.mark.parametrize(("delay_days", "expected"), [(0, True), (3, True), (4, False)])
def test_delay_of_zero_and_three_working_days_qualify_but_four_does_not(
    delay_days: int, expected: bool
) -> None:
    assert _source(HUMAN, delay_days) is expected


def test_received_friday_confirmed_monday_is_a_delay_of_one() -> None:
    assert trigger_delay_working_days(date(2026, 10, 2), _confirmed(MON)) == 1


def test_a_late_evening_confirmation_counts_on_the_vietnam_day() -> None:
    # 23:30 giờ VN thứ Hai 05/10 là 16:30 UTC cùng ngày; 00:30 giờ VN thứ Ba là 17:30 UTC thứ Hai.
    monday_evening = datetime(2026, 10, 5, 16, 30, tzinfo=UTC)
    tuesday_after_midnight = datetime(2026, 10, 5, 17, 30, tzinfo=UTC)

    assert trigger_delay_working_days(MON, monday_evening) == 0
    assert trigger_delay_working_days(MON, tuesday_after_midnight) == 1


def test_a_received_date_after_the_confirmation_day_counts_as_zero_delay() -> None:
    assert trigger_delay_working_days(date(2026, 10, 9), _confirmed(MON)) == 0


def _line(material: UUID, price: int, month: date = DEC) -> LineRef:
    return LineRef(uuid4(), material, month, Decimal(price))


def _select(
    new: list[LineRef],
    source: list[LineRef] | None,
    *,
    new_date: date = MON,
    source_date: date | None = MON,
    scanned: bool = True,
) -> list[LineRef]:
    return select_candidate_lines(
        new,
        source,
        new_received_date=new_date,
        source_received_date=source_date,
        source_was_scanned=scanned,
    )


def test_only_changed_and_added_lines_are_candidates() -> None:
    unchanged, changed, added = _line(M1, 100), _line(M2, 120), _line(M2, 90)
    source = [_line(M1, 100), _line(M2, 110)]

    assert _select([unchanged, changed, added], source) == [changed, added]


def test_a_removed_line_creates_no_candidate() -> None:
    kept = _line(M1, 100)

    assert _select([kept], [_line(M1, 100), _line(M2, 110)]) == []


def test_two_equal_lines_in_the_source_and_one_in_the_new_version_is_not_a_candidate() -> None:
    assert _select([_line(M1, 100)], [_line(M1, 100), _line(M1, 100)]) == []


def test_one_equal_line_in_the_source_and_two_in_the_new_version_makes_the_second_a_candidate() -> (
    None
):
    first, second = _line(M1, 100), _line(M1, 100)

    assert _select([first, second], [_line(M1, 100)]) == [second]


def test_the_same_price_in_another_chain_does_not_cancel_a_change() -> None:
    other_month = _line(M1, 100, date(2027, 1, 1))

    assert _select([other_month], [_line(M1, 100, DEC)]) == [other_month]


def test_delivery_months_not_on_the_first_still_share_a_chain() -> None:
    assert _select([_line(M1, 100, date(2026, 12, 20))], [_line(M1, 100, DEC)]) == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"source": None, "source_date": None},
        {"scanned": False},
        {"new_date": date(2026, 10, 6)},
    ],
)
def test_every_line_is_a_candidate_without_a_scanned_source_or_when_the_date_moved(
    kwargs: dict[str, object],
) -> None:
    new = [_line(M1, 100), _line(M2, 120)]
    source = kwargs.pop("source", [_line(M1, 100), _line(M2, 120)])

    assert _select(new, source, **kwargs) == new  # type: ignore[arg-type]


def test_deleting_a_line_and_keeping_the_prices_gives_no_candidates() -> None:
    new = [_line(M1, 100)]
    source = [_line(M1, 100), _line(M2, 120)]

    assert _select(new, source) == []
