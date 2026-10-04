from __future__ import annotations

import ast
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.services.price_alert_rules import ChangeEvaluation, PricePoint, Thresholds, evaluate_change

DEFAULTS = Thresholds(light=Decimal("2.5"), medium=Decimal("5"), large=Decimal("10"))
NEW_DAY = date(2026, 10, 2)


def _points(*pairs: tuple[int, int]) -> list[PricePoint]:
    """(ngày trong tháng 9 hoặc 10, giá) theo thứ tự thời gian."""
    return [
        PricePoint(date(2026, 9 if day > 15 else 10, day), Decimal(price)) for day, price in pairs
    ]


def test_example_1_rise_is_medium_with_r2_as_the_main_reason() -> None:
    prior = _points((23, 7900), (25, 7720), (30, 7800))

    result = evaluate_change(PricePoint(NEW_DAY, Decimal(8150)), prior, DEFAULTS)

    assert result is not None
    assert (result.direction, result.level, result.rule) == ("up", "medium", "R2")
    assert round(result.percent_change, 2) == Decimal("5.57")
    assert result.price_ref == Decimal(7720)
    assert result.received_date_ref == date(2026, 9, 25)
    assert result.secondary_rule == "R1"
    assert result.secondary_percent is not None
    assert round(result.secondary_percent, 2) == Decimal("4.49")
    assert result.secondary_price_ref == Decimal(7800)
    assert (result.window_min, result.window_max) == (Decimal(7720), Decimal(7900))
    assert result.reference_point_count == 3


def test_example_2_fall_is_large_with_r3_as_the_main_reason() -> None:
    prior = _points((24, 10400), (28, 10000), (30, 9800))

    result = evaluate_change(PricePoint(NEW_DAY, Decimal(9300)), prior, DEFAULTS)

    assert result is not None
    assert (result.direction, result.level, result.rule) == ("down", "large", "R3")
    assert round(result.percent_change, 2) == Decimal("-10.58")
    assert result.secondary_rule == "R1"
    assert result.secondary_percent is not None
    assert round(result.secondary_percent, 2) == Decimal("-5.10")


def test_example_3_opposite_direction_skips_r2_and_hides_the_duplicate_r3_line() -> None:
    prior = _points((25, 9000), (30, 10000))

    result = evaluate_change(PricePoint(NEW_DAY, Decimal(9600)), prior, DEFAULTS)

    assert result is not None
    assert (result.direction, result.level, result.rule) == ("down", "light", "R1")
    assert round(result.percent_change, 2) == Decimal("-4.00")
    assert result.secondary_rule is None
    assert result.secondary_percent is None


def _single_prior(new_price: str) -> ChangeEvaluation | None:
    return evaluate_change(
        PricePoint(NEW_DAY, Decimal(new_price)),
        [PricePoint(date(2026, 10, 1), Decimal(100))],
        DEFAULTS,
    )


@pytest.mark.parametrize(
    ("new_price", "level"),
    [
        ("102.5", "light"),
        ("105", "medium"),
        ("110", "medium"),
        ("110.0001", "large"),
        ("104.996", "light"),
        ("97.5", "light"),
        ("95", "medium"),
        ("90", "medium"),
        ("89.9999", "large"),
    ],
)
def test_level_boundaries_use_the_unrounded_percent(new_price: str, level: str) -> None:
    result = _single_prior(new_price)

    assert result is not None
    assert result.level == level


@pytest.mark.parametrize("new_price", ["102.4999", "100", "99", "97.6"])
def test_below_the_light_threshold_or_unchanged_sends_nothing(new_price: str) -> None:
    assert _single_prior(new_price) is None


def test_a_tie_in_percent_makes_r1_the_main_reason() -> None:
    # Điểm gần nhất cũng là đáy: R1 và R2 cùng +10%.
    prior = _points((23, 120), (25, 110), (30, 100))

    result = evaluate_change(PricePoint(NEW_DAY, Decimal(110)), prior, DEFAULTS)

    assert result is not None
    assert result.rule == "R1"
    assert result.secondary_rule is None


def test_a_tied_lowest_price_prefers_the_nearest_point() -> None:
    prior = _points((23, 100), (25, 120), (30, 100))

    result = evaluate_change(PricePoint(NEW_DAY, Decimal(110)), prior, DEFAULTS)

    assert result is not None
    assert result.rule == "R1"
    assert result.window_min_date == date(2026, 9, 30)


def test_a_weak_last_step_can_still_alert_through_the_extreme_point() -> None:
    prior = _points((25, 100), (30, 109))

    result = evaluate_change(PricePoint(NEW_DAY, Decimal(110)), prior, DEFAULTS)

    assert result is not None
    assert (result.rule, result.level) == ("R2", "medium")


def test_needs_at_least_one_prior_point() -> None:
    assert evaluate_change(PricePoint(NEW_DAY, Decimal(100)), [], DEFAULTS) is None


@pytest.mark.parametrize("new_price", ["0", "-5"])
def test_non_positive_new_price_is_ignored(new_price: str) -> None:
    assert _single_prior(new_price) is None


def test_zero_priced_prior_points_are_ignored_instead_of_dividing_by_zero() -> None:
    prior = _points((25, 0), (30, 100))

    result = evaluate_change(PricePoint(NEW_DAY, Decimal(110)), prior, DEFAULTS)

    assert result is not None
    assert result.reference_point_count == 1
    assert evaluate_change(PricePoint(NEW_DAY, Decimal(110)), _points((30, 0)), DEFAULTS) is None


def test_prior_points_may_arrive_unordered() -> None:
    ordered = evaluate_change(
        PricePoint(NEW_DAY, Decimal(8150)), _points((23, 7900), (25, 7720), (30, 7800)), DEFAULTS
    )
    shuffled = evaluate_change(
        PricePoint(NEW_DAY, Decimal(8150)), _points((30, 7800), (23, 7900), (25, 7720)), DEFAULTS
    )

    assert ordered == shuffled


def test_a_per_material_override_changes_the_level() -> None:
    strict = Thresholds(light=Decimal("1"), medium=Decimal("2"), large=Decimal("3"))
    loose = Thresholds(light=Decimal("5"), medium=Decimal("20"), large=Decimal("40"))
    prior = [PricePoint(date(2026, 10, 1), Decimal(100))]
    new = PricePoint(NEW_DAY, Decimal(104))

    strict_result = evaluate_change(new, prior, strict)

    assert strict_result is not None
    assert strict_result.level == "large"
    assert evaluate_change(new, prior, loose) is None


def _reference_level(value: Decimal) -> str | None:
    if value > 10:
        return "large"
    if value >= 5:
        return "medium"
    return "light" if value >= Decimal("2.5") else None


def test_matches_an_independent_implementation_on_seeded_random_series() -> None:
    rng = random.Random(20261004)
    produced = 0
    for _ in range(3000):
        prior = [
            PricePoint(date(2026, 9, 20) + timedelta(days=i), Decimal(rng.randint(80, 120)))
            for i in range(rng.randint(1, 7))
        ]
        new = PricePoint(NEW_DAY, Decimal(rng.randint(70, 130)))
        prices = [p.price for p in prior]
        r1 = (new.price - prices[-1]) / prices[-1] * 100
        wide_ref = min(prices) if r1 > 0 else max(prices)
        wide = (new.price - wide_ref) / wide_ref * 100
        main = wide if abs(wide) > abs(r1) else r1
        expected = None if r1 == 0 else _reference_level(abs(main))

        result = evaluate_change(new, prior, DEFAULTS)

        if expected is None:
            assert result is None
            continue
        produced += 1
        assert result is not None
        assert result.level == expected
        assert result.direction == ("up" if r1 > 0 else "down")
        assert result.percent_change == main
        assert result.rule == ("R1" if abs(wide) <= abs(r1) else ("R2" if r1 > 0 else "R3"))
        assert (result.window_min, result.window_max) == (min(prices), max(prices))
        assert result.price_new == new.price
        assert result.reference_point_count == len(prior)
    assert produced > 500


def test_r2_as_main_reason_hits_the_medium_boundary_through_the_bottom() -> None:
    prior = _points((25, 100), (30, 103))

    result = evaluate_change(PricePoint(NEW_DAY, Decimal(105)), prior, DEFAULTS)

    assert result is not None
    assert (result.rule, result.level, result.price_ref) == ("R2", "medium", Decimal(100))
    assert result.received_date_ref == date(2026, 9, 25)
    assert result.secondary_date_ref == date(2026, 9, 30)
    assert result.received_date_new == NEW_DAY


def test_a_tied_highest_price_prefers_the_nearest_point() -> None:
    prior = _points((23, 120), (25, 100), (30, 120))

    result = evaluate_change(PricePoint(NEW_DAY, Decimal(110)), prior, DEFAULTS)

    assert result is not None
    assert result.rule == "R1"
    assert result.window_max_date == date(2026, 9, 30)


def test_two_points_on_one_day_collapse_to_the_lowest_whatever_the_order() -> None:
    day = date(2026, 10, 1)
    new = PricePoint(NEW_DAY, Decimal(130))

    first = evaluate_change(
        new, [PricePoint(day, Decimal(100)), PricePoint(day, Decimal(120))], DEFAULTS
    )
    second = evaluate_change(
        new, [PricePoint(day, Decimal(120)), PricePoint(day, Decimal(100))], DEFAULTS
    )

    assert first == second
    assert first is not None
    assert first.price_ref == Decimal(100)
    assert first.reference_point_count == 1


def test_points_on_or_after_the_new_day_are_not_references() -> None:
    prior = [PricePoint(NEW_DAY, Decimal(100)), PricePoint(date(2026, 10, 3), Decimal(100))]

    assert evaluate_change(PricePoint(NEW_DAY, Decimal(150)), prior, DEFAULTS) is None


def test_a_zero_priced_latest_point_is_skipped_on_purpose() -> None:
    prior = _points((25, 100), (30, 0))

    result = evaluate_change(PricePoint(NEW_DAY, Decimal(110)), prior, DEFAULTS)

    assert result is not None
    assert result.received_date_ref == date(2026, 9, 25)


def test_the_module_stays_pure() -> None:
    source = (Path(__file__).resolve().parents[1] / "app/services/price_alert_rules.py").read_text()
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
    assert imported <= {"__future__", "dataclasses", "datetime", "decimal", "typing"}
    assert "now(" not in source and "today(" not in source
