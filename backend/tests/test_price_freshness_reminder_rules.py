from __future__ import annotations

from datetime import date

import pytest

from app.services.price_freshness_formatter import (
    MAX_REMINDER_LINES,
    FreshnessLine,
    format_freshness_reminder,
)
from app.services.price_freshness_reminder import (
    MAX_REMINDERS,
    REPEAT_WORKING_DAYS,
    reminder_due,
    reminder_working_days,
)


def test_reminder_constants_match_the_agreed_cadence() -> None:
    assert (REPEAT_WORKING_DAYS, MAX_REMINDERS) == (3, 5)


@pytest.mark.parametrize("k", [1, 4, 7, 10, 13])
def test_a_reminder_is_due_on_the_first_overdue_working_day_and_every_third_after(k: int) -> None:
    assert reminder_due(k) is True


@pytest.mark.parametrize("k", [-1, 0, 2, 3, 5, 6, 8, 9, 11, 12, 14, 16, 100])
def test_no_reminder_between_the_cadence_days_before_overdue_or_after_the_cap(k: int) -> None:
    assert reminder_due(k) is False


def test_working_days_overdue_counts_from_the_due_date_and_skips_weekends() -> None:
    # Cập nhật cuối thứ Ba 22/09/2026, chu kỳ 7 ngày: hạn thứ Ba 29/09.
    last = date(2026, 9, 22)
    assert reminder_working_days(last, 7, today=date(2026, 9, 29)) == 0  # đúng hạn
    assert reminder_working_days(last, 7, today=date(2026, 9, 30)) == 1  # thứ Tư: ngày đầu
    assert reminder_working_days(last, 7, today=date(2026, 10, 2)) == 3  # thứ Sáu
    assert reminder_working_days(last, 7, today=date(2026, 10, 5)) == 4  # thứ Hai: bỏ cuối tuần


def test_a_due_date_on_friday_makes_monday_the_first_overdue_day() -> None:
    last = date(2026, 9, 25)  # thứ Sáu; chu kỳ 7 ngày: hạn thứ Sáu 02/10
    assert reminder_working_days(last, 7, today=date(2026, 10, 2)) == 0
    assert reminder_working_days(last, 7, today=date(2026, 10, 5)) == 1


LINE = FreshnessLine("Lysine 99%", 18, 14, "Trần Thị B")


def test_reminder_lists_each_material_with_age_interval_and_last_enterer() -> None:
    text = format_freshness_reminder(
        [LINE], day=date(2026, 10, 7), base_url="https://q.example.com/"
    )

    assert "<b>Vật tư chưa có giá mới (1)</b> · 07/10" in text
    assert "• Lysine 99% — 18 ngày (chu kỳ 14) · Trần Thị B" in text
    assert '<a href="https://q.example.com/">Xem trên web →</a>' in text


def test_a_missing_enterer_is_left_out_and_html_is_escaped() -> None:
    text = format_freshness_reminder(
        [FreshnessLine("A <b>&</b>", 9, 7, None)], day=date(2026, 10, 7), base_url="https://q"
    )

    assert "• A &lt;b&gt;&amp;&lt;/b&gt; — 9 ngày (chu kỳ 7)\n" in text
    assert "·" not in text.split("\n")[2]


def test_most_overdue_first_by_age_over_interval() -> None:
    lines = [
        FreshnessLine("B nhẹ", 8, 7, None),
        FreshnessLine("A nặng", 40, 14, None),
        FreshnessLine("C nhẹ", 8, 7, None),
    ]

    text = format_freshness_reminder(lines, day=date(2026, 10, 7), base_url="https://q")

    body = [row for row in text.split("\n") if row.startswith("•")]
    assert [row.split(" — ")[0] for row in body] == ["• A nặng", "• B nhẹ", "• C nhẹ"]


def test_long_lists_are_cut_at_the_line_limit_with_a_note() -> None:
    lines = [FreshnessLine(f"Vật tư {i:02d}", 10, 7, None) for i in range(MAX_REMINDER_LINES + 4)]

    text = format_freshness_reminder(lines, day=date(2026, 10, 7), base_url="https://q")

    assert sum(row.startswith("•") for row in text.split("\n")) == MAX_REMINDER_LINES
    assert "và 4 vật tư nữa, xem trên web." in text
    assert f"({MAX_REMINDER_LINES + 4})" in text
    assert len(text) <= 4096


def test_an_empty_reminder_is_never_built() -> None:
    with pytest.raises(ValueError, match="rỗng"):
        format_freshness_reminder([], day=date(2026, 10, 7), base_url="https://q")


def test_an_oversized_reminder_drops_whole_lines_instead_of_cutting_the_html() -> None:
    names = [("&<" * 60) + f" {i:02d}" for i in range(MAX_REMINDER_LINES)]  # nở rất dài khi thoát
    lines = [FreshnessLine(name, 10, 7, "Người nhập " * 5) for name in names]

    text = format_freshness_reminder(lines, day=date(2026, 10, 7), base_url="https://q")

    assert len(text) <= 4096
    assert text.endswith("Xem trên web →</a>")
    assert text.count("<b>") == text.count("</b>") == 1
    assert "&lt;" in text and not text.rstrip().endswith("&")
    shown = sum(row.startswith("•") for row in text.split("\n"))
    assert 0 < shown < MAX_REMINDER_LINES
    assert f"và {MAX_REMINDER_LINES - shown} vật tư nữa, xem trên web." in text
    assert f"({MAX_REMINDER_LINES})" in text
