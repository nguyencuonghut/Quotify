from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.services.price_alert_formatter import (
    CAPTION_MAX_LENGTH,
    EventView,
    MessageView,
    chart_title,
    format_caption,
    format_details,
    title,
)

BASE_URL = "https://quotify.honghafeed.com.vn"
MOBILE_WIDTH = 34  # số ký tự tối đa mỗi dòng để không xuống dòng trên điện thoại


def _event(**overrides: object) -> EventView:
    """Ví dụ 1 của D2: 7,900 · 7,720 · 7,800 rồi 8,150, kèm CNF."""
    values: dict[str, object] = {
        "delivery_month": date(2026, 12, 1),
        "direction": "up",
        "level": "medium",
        "rule": "R2",
        "percent_change": Decimal("5.5699"),
        "price_new": Decimal("8150"),
        "price_ref": Decimal("7720"),
        "received_date_new": date(2026, 10, 2),
        "received_date_ref": date(2026, 9, 25),
        "window_min": Decimal("7720"),
        "window_max": Decimal("7900"),
        "window_min_date": date(2026, 9, 25),
        "window_max_date": date(2026, 9, 23),
        "secondary_rule": "R1",
        "secondary_percent": Decimal("4.4872"),
        "secondary_price_ref": Decimal("7800"),
        "secondary_date_ref": date(2026, 9, 30),
        "cnf_price_new": Decimal("303.50"),
        "cnf_price_ref": Decimal("287.00"),
        "cnf_date_ref": date(2026, 9, 25),
    }
    values.update(overrides)
    return EventView(**values)  # type: ignore[arg-type]


def _message(*events: EventView, name: str = "Ngô hạt") -> MessageView:
    return MessageView(material_name=name, events=events or (_event(),), quote_id="abc-123")


def _lines(text: str) -> list[str]:
    return text.splitlines()


def test_example_1_caption_shows_from_to_and_the_difference() -> None:
    assert format_caption(_message()) == (
        "<b>🟠 TĂNG TRUNG BÌNH · Ngô hạt</b>\n"
        "7,720 → 8,150 VNĐ/KG (+430)\n"
        "<b>▲5.57%</b> so với thấp nhất 7 ngày"
    )


def test_example_1_details_are_compact_labelled_lines_with_a_short_link() -> None:
    assert format_details(_message(), base_url=BASE_URL) == (
        "<b>Chi tiết kỳ 12/2026</b>\n"
        "So với giá thấp nhất 7 ngày\n"
        "  7,720 (25/09)\n"
        "Giá mới: 8,150 (02/10)\n"
        "Cũng: ▲4.49% so với điểm gần nhất\n"
        "7 ngày qua: 7,720 – 7,900\n"
        "CNF: 303.50 USD/MT\n"
        "  ▲5.75% so với 287.00 (25/09)\n"
        "\n"
        '🔗 <a href="https://quotify.honghafeed.com.vn/quotes/abc-123">Xem phiếu →</a>\n'
        "ℹ️ Điểm giá có thể thuộc nhà cung cấp khác lần trước."
    )


def test_a_vnd_line_has_no_cnf() -> None:
    event = _event(cnf_price_new=None, cnf_price_ref=None, cnf_date_ref=None)

    caption = format_caption(_message(event))
    details = format_details(_message(event), base_url=BASE_URL)

    assert "7,720 → 8,150 VNĐ/KG" in caption
    assert "CNF" not in details


def test_cnf_without_a_usd_reference_prints_only_the_new_price() -> None:
    event = _event(cnf_price_ref=None, cnf_date_ref=None)

    details = format_details(_message(event), base_url=BASE_URL)

    assert "CNF: 303.50 USD/MT\n\n" in details
    assert "so với 287" not in details


def test_cnf_moving_against_the_vnd_direction_is_flagged_as_exchange_rate() -> None:
    event = _event(cnf_price_ref=Decimal("320.00"))

    details = format_details(_message(event), base_url=BASE_URL)

    assert "▼5.16% so với 320.00 (25/09)\n  (chênh lệch do tỷ giá)" in details


def test_a_flat_cnf_with_a_moving_vnd_price_is_flagged_as_exchange_rate() -> None:
    event = _event(cnf_price_ref=Decimal("303.50"))

    assert "0.00% so với 303.50 (25/09)\n  (chênh lệch do tỷ giá)" in format_details(
        _message(event), base_url=BASE_URL
    )


def test_the_other_comparison_is_hidden_when_it_has_the_same_reference_point() -> None:
    event = _event(
        rule="R1",
        level="light",
        percent_change=Decimal("4.0"),
        secondary_rule=None,
        secondary_percent=None,
        secondary_price_ref=None,
        secondary_date_ref=None,
    )

    assert "Cũng:" not in format_details(_message(event), base_url=BASE_URL)


def test_a_fall_uses_the_down_arrow_and_the_highest_reference() -> None:
    event = _event(
        direction="down",
        level="large",
        rule="R3",
        percent_change=Decimal("-10.5769"),
        price_new=Decimal("9300"),
        price_ref=Decimal("10400"),
    )

    caption = format_caption(_message(event))

    assert caption.startswith("<b>🔴 GIẢM LỚN · Ngô hạt</b>")
    assert "10,400 → 9,300 VNĐ/KG (−1,100)" in caption
    assert "<b>▼10.58%</b> so với cao nhất 7 ngày" in caption


@pytest.mark.parametrize(
    ("level", "direction", "expected"),
    [
        ("light", "up", "🟡 TĂNG NHẸ"),
        ("medium", "down", "🟠 GIẢM TRUNG BÌNH"),
        ("large", "up", "🔴 TĂNG LỚN"),
    ],
)
def test_titles_follow_the_level_and_direction_table(
    level: str, direction: str, expected: str
) -> None:
    assert title(level, direction) == expected  # type: ignore[arg-type]


def test_the_chart_title_has_no_emoji_and_uses_triangles() -> None:
    assert chart_title(_message()) == "▲ TĂNG TRUNG BÌNH · Ngô hạt"
    down = _event(direction="down", level="large")
    assert chart_title(_message(down)) == "▼ GIẢM LỚN · Ngô hạt"


def test_markup_characters_in_the_material_name_are_escaped() -> None:
    message = _message(name="Lysine <99%> & Co")

    assert "Lysine &lt;99%&gt; &amp; Co" in format_caption(message)
    details = format_details(message, base_url=BASE_URL)
    assert "<99%>" not in details
    assert "&lt;99%&gt;" in format_caption(message)


def test_the_caption_never_exceeds_telegram_limit_even_with_a_huge_name() -> None:
    caption = format_caption(_message(name="X" * 3000))

    assert len(caption) <= CAPTION_MAX_LENGTH
    assert caption.endswith("…")


def test_several_periods_open_with_a_one_line_per_period_table() -> None:
    medium = _event(delivery_month=date(2027, 1, 1), percent_change=Decimal("19.28"))
    large_a = _event(delivery_month=date(2026, 11, 1), level="large", percent_change=Decimal("20"))
    large_b = _event(delivery_month=date(2026, 12, 1), level="large", percent_change=Decimal("20"))

    details = format_details(_message(medium, large_b, large_a), base_url=BASE_URL)
    caption = format_caption(_message(medium, large_b, large_a))

    lines = _lines(details)
    assert lines[0] == "<b>Các kỳ giao hàng vượt ngưỡng</b>"
    assert lines[1:3] == [
        "🔴 11/2026, 12/2026 · <b>▲20.00%</b>",  # hai kỳ cùng số liệu gộp một dòng
        "🟠 01/2027 · <b>▲19.28%</b>",
    ]
    assert lines[3] == ""  # dòng trống tách bảng khỏi phần chi tiết
    assert "<b>Chi tiết kỳ 11/2026</b> (kỳ trong ảnh)" in details
    assert "mạnh nhất" not in details
    assert details.count("Giá mới") == 1  # chỉ giải thích kỳ đang vẽ trong ảnh
    assert "TĂNG LỚN" in caption.splitlines()[0]
    assert "➕ Kỳ 11/2026 và 2 kỳ khác ↓" in caption


def test_many_identical_periods_collapse_into_a_range_not_a_long_list() -> None:
    events = [
        replace(_event(), delivery_month=date(2026 + index // 12, index % 12 + 1, 1))
        for index in range(6)
    ]

    details = format_details(_message(*events), base_url=BASE_URL)

    assert "🟠 01/2026–06/2026 (6 kỳ) · <b>▲5.57%</b>" in details


def test_periods_with_different_numbers_stay_on_separate_lines() -> None:
    a = _event(delivery_month=date(2026, 12, 1), percent_change=Decimal("39.53"))
    b = _event(delivery_month=date(2027, 1, 1), percent_change=Decimal("28.00"))

    details = format_details(_message(a, b), base_url=BASE_URL)

    assert "🟠 12/2026 · <b>▲39.53%</b>" in details
    assert "🟠 01/2027 · <b>▲28.00%</b>" in details


def test_a_huge_jump_adds_a_check_the_quote_warning() -> None:
    big = _event(percent_change=Decimal("39.53"))
    message = MessageView("Ngô hạt", (big,), "abc", warn_percent=Decimal("30"))

    assert "⚠️ Tăng rất mạnh, nên kiểm tra phiếu" in format_caption(message)
    assert "⚠️" not in format_caption(_message(_event(percent_change=Decimal("29.9"))))
    fall = _event(direction="down", percent_change=Decimal("-35"))
    assert "⚠️ Giảm rất mạnh" in format_caption(
        MessageView("Ngô hạt", (fall,), "abc", warn_percent=Decimal("30"))
    )


def test_mixed_directions_are_visible_in_the_table() -> None:
    up = _event(delivery_month=date(2026, 11, 1))
    down = _event(delivery_month=date(2026, 12, 1), direction="down", percent_change=Decimal("-6"))

    details = format_details(_message(up, down), base_url=BASE_URL)

    assert "🟠 11/2026 · <b>▲5.57%</b>" in details
    assert "🟠 12/2026 · <b>▼6.00%</b>" in details


def test_a_long_table_is_limited_and_points_to_the_web() -> None:
    events = [
        replace(
            _event(),
            delivery_month=date(2026 + index // 12, index % 12 + 1, 1),
            percent_change=Decimal(5 + index) / 10,
        )
        for index in range(60)
    ]

    details = format_details(_message(*events), base_url=BASE_URL)

    assert len(details) <= 4096
    assert "nhóm kỳ nữa, xem trên web." in details
    assert "/quotes/abc-123" in details


def test_every_line_of_a_typical_message_fits_a_phone_without_wrapping() -> None:
    events = [
        _event(delivery_month=date(2026, 11, 1), level="large", percent_change=Decimal("20")),
        _event(delivery_month=date(2026, 12, 1), level="large", percent_change=Decimal("20")),
    ]
    message = _message(*events, name="Lúa mỳ 3")
    text = format_caption(message) + "\n" + format_details(message, base_url=BASE_URL)

    for line in text.splitlines():
        if "http" in line or "ℹ️" in line:
            continue  # liên kết và ghi chú được phép xuống dòng
        plain = line.replace("<b>", "").replace("</b>", "")
        assert len(plain) <= MOBILE_WIDTH, plain


def test_cutting_never_splits_an_html_entity() -> None:
    caption = format_caption(_message(name="&" * 2000))

    assert len(caption) <= CAPTION_MAX_LENGTH
    body = caption.rstrip("…")
    assert body.endswith("&amp;") or "&" not in body[-5:].replace("&amp;", "")


def test_an_oversized_name_is_cut_but_keeps_the_footer_link() -> None:
    details = format_details(_message(name="Y" * 6000), base_url=BASE_URL)

    assert len(details) <= 4096
    assert "/quotes/abc-123" in details
    assert details.endswith("khác lần trước.")


def test_money_and_percent_formatting_edge_cases() -> None:
    event = _event(
        price_new=Decimal("1234567.5"),
        percent_change=Decimal("0.004"),
        secondary_percent=Decimal("-0.5"),
    )

    details = format_details(_message(event), base_url=BASE_URL)

    assert "▼0.50% so với điểm gần nhất" in details
    assert "→ 1,234,568 VNĐ/KG" in format_caption(_message(event))
    assert "." not in format_caption(_message(event)).split("\n")[1]  # VNĐ/KG không có số lẻ


def test_direction_is_written_once_with_a_text_arrow_and_the_dot_only_carries_the_level() -> None:
    up = _event(delivery_month=date(2026, 11, 1))
    down = _event(delivery_month=date(2026, 12, 1), direction="down", percent_change=Decimal("-6"))
    message = _message(up, down)
    text = format_caption(message) + "\n" + format_details(message, base_url=BASE_URL)

    assert "🔺" not in text and "🔻" not in text  # không còn emoji mũi tên đỏ cạnh chấm màu
    assert "🟠 11/2026 · <b>▲5.57%</b>" in text
    assert "🟠 12/2026 · <b>▼6.00%</b>" in text
    assert "+5.57%" not in text and "−6.00%" not in text  # không lặp chiều bằng dấu


def test_a_follow_up_alert_names_the_previous_price_and_the_move_since() -> None:
    event = _event(
        direction="down",
        level="large",
        rule="R1",
        percent_change=Decimal("-29.5"),
        price_new=Decimal(5500),
        price_ref=Decimal(7800),
        prior_alert_price=Decimal(6500),
        prior_alert_date=date(2026, 10, 4),
    )

    caption = format_caption(_message(event))

    assert "↻ Báo tiếp: lần trước 6,500 (▼15.38%)" in caption


def test_a_fallback_reference_says_how_old_it_is_and_drops_the_empty_window_line() -> None:
    event = _event(
        rule="R1",
        secondary_rule=None,
        secondary_percent=None,
        secondary_price_ref=None,
        secondary_date_ref=None,
        reference_age_days=12,
        cnf_price_new=None,
        cnf_price_ref=None,
        cnf_date_ref=None,
    )

    caption = format_caption(_message(event))
    details = format_details(_message(event), base_url=BASE_URL)

    assert "⏳ Gốc cách đây 12 ngày" in caption
    assert "So với điểm gần nhất (cách 12 ngày)" in details
    assert "Không có giá nào trong 7 ngày qua" in details
    assert "7 ngày qua: 7,720" not in details


def test_a_normal_alert_has_neither_follow_up_nor_age_lines() -> None:
    caption = format_caption(_message())

    assert "↻" not in caption and "⏳" not in caption
