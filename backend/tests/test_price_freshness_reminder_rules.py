from __future__ import annotations

from datetime import date

import pytest

from app.services.price_freshness_formatter import (
    MAX_REMINDER_LINES,
    NAME_WIDTH,
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


DAY = date(2026, 10, 7)
BASE = "https://q.example.com/"


def render(lines: list[FreshnessLine]) -> str:
    return format_freshness_reminder(lines, day=DAY, base_url=BASE)


def material_rows(text: str) -> list[str]:
    return [
        row for row in text.split("\n") if row.startswith(("🔴", "🟡")) and row.endswith(" ngày")
    ]


def person_rows(text: str) -> list[str]:
    return [row for row in text.split("\n") if row.startswith("👤")]


SAMPLE = [
    FreshnessLine("Cám mỳ", 21, 7, "Vũ Hoàng Giang"),
    FreshnessLine("Arginin 98%", 8, 7, "Hoàng Thúy Dung"),
    FreshnessLine("Lysine 99%", 8, 7, "Hoàng Thúy Dung"),
    FreshnessLine("VITAMIN A", 15, 14, "Nguyễn Thị Kim Loan"),
]


def test_the_message_leads_with_the_count_and_a_one_line_severity_summary() -> None:
    text = render(SAMPLE)

    first, second = text.split("\n")[:2]
    assert first == "⏰ <b>4 vật tư chưa có giá mới</b> · 07/10"
    assert second == "🔴 1 trễ nhiều · 🟡 3 vừa trễ"


def test_materials_are_grouped_under_the_person_to_chase_with_a_count() -> None:
    text = render(SAMPLE)

    assert person_rows(text) == [
        "👤 <b>Vũ Hoàng Giang</b> · 1",  # có vật tư trễ nhiều nên đứng đầu
        "👤 <b>Hoàng Thúy Dung</b> · 2",
        "👤 <b>Nguyễn Thị Kim Loan</b> · 1",
    ]
    body = text.split("\n")
    giang = body.index("👤 <b>Vũ Hoàng Giang</b> · 1")
    assert body[giang + 1] == "🔴 Cám mỳ · 21 ngày"
    dung = body.index("👤 <b>Hoàng Thúy Dung</b> · 2")
    assert body[dung + 1 : dung + 3] == ["🟡 Arginin 98% · 8 ngày", "🟡 Lysine 99% · 8 ngày"]


def test_a_material_is_severe_from_twice_its_interval_and_only_then() -> None:
    text = render(
        [
            FreshnessLine("Đúng gấp đôi", 14, 7, "A"),
            FreshnessLine("Sát gấp đôi", 13, 7, "A"),
        ]
    )

    assert "🔴 Đúng gấp đôi · 14 ngày" in text
    assert "🟡 Sát gấp đôi · 13 ngày" in text


def test_within_a_person_the_most_overdue_comes_first() -> None:
    lines = [
        FreshnessLine("B nhẹ", 8, 7, "A"),
        FreshnessLine("A nặng", 40, 14, "A"),
        FreshnessLine("C nhẹ", 8, 7, "A"),
    ]

    assert [row.split(" · ")[0] for row in material_rows(render(lines))] == [
        "🔴 A nặng",
        "🟡 B nhẹ",
        "🟡 C nhẹ",
    ]


def test_people_without_severe_items_are_ordered_by_how_many_items_then_name() -> None:
    lines = [
        FreshnessLine("m1", 8, 7, "Bình"),
        FreshnessLine("m2", 8, 7, "An"),
        FreshnessLine("m3", 8, 7, "An"),
        FreshnessLine("m4", 8, 7, "Cường"),
        FreshnessLine("m5", 8, 7, "Cường"),
    ]

    assert [row.split(" · ")[0] for row in person_rows(render(lines))] == [
        "👤 <b>An</b>",
        "👤 <b>Cường</b>",
        "👤 <b>Bình</b>",
    ]


def test_an_unknown_enterer_is_a_group_of_its_own_and_always_last() -> None:
    lines = [
        FreshnessLine("không rõ nặng", 90, 7, None),
        FreshnessLine("có tên", 8, 7, "Lê Thị Hồng"),
    ]

    assert person_rows(render(lines)) == [
        "👤 <b>Lê Thị Hồng</b> · 1",
        "👤 <b>Chưa rõ người nhập</b> · 1",
    ]


def test_every_material_line_is_short_enough_to_stay_on_one_phone_line() -> None:
    lines = [
        FreshnessLine("Methionine 98% (Sumi/CJ/Evonik)", 15, 14, "Hoàng Thúy Dung"),
        FreshnessLine("Fermented Soybean Meal", 123, 7, "Hoàng Thúy Dung"),
        FreshnessLine("Ngô", 9, 7, "Hoàng Thúy Dung"),
    ]

    rows = material_rows(render(lines))

    assert len(rows) == 3
    assert all(len(row) <= 34 for row in rows), rows
    assert any(row.startswith("🟡 Methionine 98% (Sum…") for row in rows)
    assert NAME_WIDTH == 20


def test_html_in_names_and_people_is_escaped() -> None:
    text = render([FreshnessLine("A <b>&</b>", 9, 7, "Tên <i>lạ</i>")])

    assert "🟡 A &lt;b&gt;&amp;&lt;/b&gt; · 9 ngày" in text
    assert "👤 <b>Tên &lt;i&gt;lạ&lt;/i&gt;</b> · 1" in text
    assert "<i>lạ</i>" not in text


def test_the_footer_explains_the_numbers_and_links_to_the_web() -> None:
    text = render(SAMPLE)

    assert "<i>Số ngày tính từ lần nhận giá gần nhất. 🔴 = trễ từ gấp đôi chu kỳ.</i>" in text
    assert text.endswith('<a href="https://q.example.com/">Xem chi tiết trên web →</a>')


def test_long_lists_are_cut_at_the_item_limit_with_a_note() -> None:
    lines = [FreshnessLine(f"Vật tư {i:02d}", 10, 7, "A") for i in range(MAX_REMINDER_LINES + 4)]

    text = render(lines)

    assert len(material_rows(text)) == MAX_REMINDER_LINES
    assert "và 4 vật tư nữa, xem trên web." in text
    assert f"{MAX_REMINDER_LINES + 4} vật tư chưa có giá mới" in text
    assert f"👤 <b>A</b> · {MAX_REMINDER_LINES}" in text
    assert len(text) <= 4096


def test_an_empty_reminder_is_never_built() -> None:
    with pytest.raises(ValueError, match="rỗng"):
        render([])


def test_an_oversized_reminder_drops_whole_lines_instead_of_cutting_the_html() -> None:
    lines = [
        FreshnessLine(f"{'&<' * 30}{i:02d}", 10, 7, f"{'Người nhập & ' * 3}{i:02d}")
        for i in range(MAX_REMINDER_LINES)
    ]

    text = render(lines)

    assert len(text) <= 4096
    assert text.endswith("Xem chi tiết trên web →</a>")
    assert text.count("<b>") == text.count("</b>")
    assert "&lt;" in text and "&amp;" in text
    shown = len(material_rows(text))
    assert 0 < shown <= MAX_REMINDER_LINES
    if shown < MAX_REMINDER_LINES:
        assert f"và {MAX_REMINDER_LINES - shown} vật tư nữa, xem trên web." in text
    assert f"{MAX_REMINDER_LINES} vật tư chưa có giá mới" in text
