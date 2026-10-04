from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

Direction = Literal["up", "down"]
Level = Literal["light", "medium", "large"]
Rule = Literal["R1", "R2", "R3"]

_HUNDRED = Decimal(100)


@dataclass(frozen=True, slots=True)
class PricePoint:
    received_date: date
    price: Decimal


@dataclass(frozen=True, slots=True)
class Thresholds:
    """Biên phần trăm: Nhẹ khi |%| >= light, Trung bình khi >= medium, Lớn khi > large (D4)."""

    light: Decimal
    medium: Decimal
    large: Decimal


@dataclass(frozen=True, slots=True)
class ChangeEvaluation:
    direction: Direction
    level: Level
    rule: Rule
    percent_change: Decimal
    price_new: Decimal
    price_ref: Decimal
    received_date_new: date
    received_date_ref: date
    window_min: Decimal
    window_max: Decimal
    window_min_date: date
    window_max_date: date
    reference_point_count: int
    secondary_rule: Rule | None
    secondary_percent: Decimal | None
    secondary_price_ref: Decimal | None
    secondary_date_ref: date | None


def evaluate_change(
    new_point: PricePoint,
    prior_points: list[PricePoint],
    thresholds: Thresholds,
) -> ChangeEvaluation | None:
    """Bộ ba quy tắc R1/R2/R3 nhất quán hướng (D2). Hàm thuần: không DB, không thời gian hệ thống.

    Phần trăm là `Decimal` không làm tròn trước khi so với biên (L7). Trả `None` khi không có
    điểm trước dùng được (trước ngày điểm mới, giá dương), giá không dương, giá bằng điểm gần
    nhất, hoặc dưới ngưỡng Nhẹ.
    """
    if new_point.price <= 0:
        return None
    # Chỉ điểm trước ngày điểm mới, giá dương (điểm giá 0 bị bỏ có chủ ý, L7). Mỗi ngày một điểm
    # là giá thấp nhất, để kết quả không phụ thuộc thứ tự đầu vào nếu caller truyền trùng ngày.
    per_day: dict[date, Decimal] = {}
    for point in prior_points:
        if point.price > 0 and point.received_date < new_point.received_date:
            per_day[point.received_date] = min(
                point.price, per_day.get(point.received_date, point.price)
            )
    references = [PricePoint(day, price) for day, price in sorted(per_day.items())]
    if not references:
        return None

    nearest = references[-1]
    # Khi hòa giá, chọn điểm gần nhất để nó trùng với R1 và không in dòng phụ thừa.
    lowest = min(references, key=lambda p: (p.price, -p.received_date.toordinal()))
    highest = max(references, key=lambda p: (p.price, p.received_date.toordinal()))

    r1 = _percent(new_point.price, nearest.price)
    if r1 == 0:
        return None
    direction: Direction = "up" if r1 > 0 else "down"
    other_rule: Rule = "R2" if direction == "up" else "R3"
    other_point = lowest if direction == "up" else highest
    other = _percent(new_point.price, other_point.price)

    main_rule: Rule
    sec_rule: Rule
    # Hòa |%| thì ưu tiên R1.
    if abs(other) > abs(r1):
        main_rule, main_percent, main_point = other_rule, other, other_point
        sec_rule, sec_percent, sec_point = "R1", r1, nearest
    else:
        main_rule, main_percent, main_point = "R1", r1, nearest
        sec_rule, sec_percent, sec_point = other_rule, other, other_point

    level = _level(abs(main_percent), thresholds)
    if level is None:
        return None

    show_secondary = sec_point.price != main_point.price
    return ChangeEvaluation(
        direction=direction,
        level=level,
        rule=main_rule,
        percent_change=main_percent,
        price_new=new_point.price,
        price_ref=main_point.price,
        received_date_new=new_point.received_date,
        received_date_ref=main_point.received_date,
        window_min=lowest.price,
        window_max=highest.price,
        window_min_date=lowest.received_date,
        window_max_date=highest.received_date,
        reference_point_count=len(references),
        secondary_rule=sec_rule if show_secondary else None,
        secondary_percent=sec_percent if show_secondary else None,
        secondary_price_ref=sec_point.price if show_secondary else None,
        secondary_date_ref=sec_point.received_date if show_secondary else None,
    )


def _percent(new_price: Decimal, ref_price: Decimal) -> Decimal:
    return (new_price - ref_price) / ref_price * _HUNDRED


def _level(absolute_percent: Decimal, thresholds: Thresholds) -> Level | None:
    if absolute_percent > thresholds.large:
        return "large"
    if absolute_percent >= thresholds.medium:
        return "medium"
    if absolute_percent >= thresholds.light:
        return "light"
    return None
