from __future__ import annotations

from datetime import date, timedelta

# Thứ Hai đến thứ Sáu là ngày làm việc. Ngày lễ và Tết chưa được loại (QĐ-11).
_SATURDAY = 5


def is_working_day(day: date) -> bool:
    return day.weekday() < _SATURDAY


def working_days_between(start: date, end: date) -> int:
    """Số ngày làm việc trong `(start, end]`: không tính `start`, có tính `end`."""
    if end <= start:
        return 0
    count = 0
    current = start
    while current < end:
        current += timedelta(days=1)
        if is_working_day(current):
            count += 1
    return count


def reference_window(day: date, working_days: int = 7) -> tuple[date, date]:
    """Khoảng ngày lịch `[start, end]` chứa `working_days` ngày làm việc ngay trước `day`.

    `end` là ngày liền trước `day`, nên điểm nhận vào cuối tuần nằm giữa khoảng vẫn là điểm
    tham chiếu. `start` là ngày làm việc thứ `working_days` tính lùi từ `day`.
    """
    if working_days < 1:
        raise ValueError("Số ngày làm việc của cửa sổ tham chiếu phải từ 1 trở lên.")
    start = day
    remaining = working_days
    while remaining:
        start -= timedelta(days=1)
        if is_working_day(start):
            remaining -= 1
    return start, day - timedelta(days=1)
