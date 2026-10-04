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


def test_example_1_caption_matches_the_plan_character_for_character() -> None:
    assert format_caption(_message()) == (
        "🔺🟠 TĂNG TRUNG BÌNH · Ngô hạt\n"
        "Giá thấp nhất hôm nay: 8,150.00 VNĐ/KG (giá quy đổi, 02/10/2026)\n"
        "Kỳ 12/2026: +5.57% so với giá thấp nhất 7 ngày làm việc"
    )


def test_example_1_details_match_the_plan_character_for_character() -> None:
    assert format_details(_message(), base_url=BASE_URL) == (
        "Ngô hạt · kỳ giao hàng 12/2026\n"
        "Lý do chính: so với giá thấp nhất 7 ngày làm việc\n"
        "  +5.57%  (7,720.00 · 25/09/2026)\n"
        "So sánh khác: so với điểm giá gần nhất\n"
        "  +4.49%  (7,800.00 · 30/09/2026)\n"
        "Vùng tham chiếu 7 ngày làm việc\n"
        "  Thấp nhất: 7,720.00 (25/09) · Cao nhất: 7,900.00 (23/09)\n"
        "CNF (USD/MT): 303.50 (02/10/2026), so với 287.00 (25/09/2026): +5.75%\n"
        "\n"
        "Lưu ý: điểm giá có thể thuộc nhà cung cấp khác với lần trước.\n"
        "🔗 Xem chi tiết: https://quotify.honghafeed.com.vn/quotes/abc-123"
    )


def test_a_vnd_line_has_no_cnf_and_no_converted_price_note() -> None:
    event = _event(cnf_price_new=None, cnf_price_ref=None, cnf_date_ref=None)

    caption = format_caption(_message(event))
    details = format_details(_message(event), base_url=BASE_URL)

    assert "giá quy đổi" not in caption
    assert "(02/10/2026)" in caption
    assert "CNF" not in details


def test_cnf_without_a_usd_reference_prints_only_the_new_price() -> None:
    event = _event(cnf_price_ref=None, cnf_date_ref=None)

    assert "CNF (USD/MT): 303.50 (02/10/2026)\n" in format_details(
        _message(event), base_url=BASE_URL
    )


def test_cnf_moving_against_the_vnd_direction_is_flagged_as_exchange_rate() -> None:
    event = _event(cnf_price_ref=Decimal("320.00"))

    details = format_details(_message(event), base_url=BASE_URL)

    assert "−5.16% (chênh lệch do tỷ giá)" in details


def test_the_other_comparison_is_hidden_when_it_has_the_same_reference_point() -> None:
    event = _event(
        rule="R1",
        percent_change=Decimal("4.0"),
        level="light",
        secondary_rule=None,
        secondary_percent=None,
        secondary_price_ref=None,
        secondary_date_ref=None,
    )

    assert "So sánh khác" not in format_details(_message(event), base_url=BASE_URL)


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

    assert caption.startswith("🔻🔴 GIẢM LỚN · Ngô hạt")
    assert "Kỳ 12/2026: −10.58% so với giá cao nhất 7 ngày làm việc" in caption


@pytest.mark.parametrize(
    ("level", "direction", "expected"),
    [
        ("light", "up", "🔺🟡 TĂNG NHẸ"),
        ("medium", "down", "🔻🟠 GIẢM TRUNG BÌNH"),
        ("large", "up", "🔺🔴 TĂNG LỚN"),
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
    assert "Lysine &lt;99%&gt; &amp; Co · kỳ giao hàng" in format_details(
        message, base_url=BASE_URL
    )
    assert "<99%>" not in format_details(message, base_url=BASE_URL)


def test_the_caption_never_exceeds_telegram_limit_even_with_a_huge_name() -> None:
    caption = format_caption(_message(name="X" * 3000))

    assert len(caption) <= CAPTION_MAX_LENGTH
    assert caption.endswith("…")


def test_the_strongest_period_leads_and_the_rest_are_counted_in_the_caption() -> None:
    medium = _event(delivery_month=date(2026, 11, 1))
    large = _event(delivery_month=date(2026, 12, 1), level="large", percent_change=Decimal("12"))

    caption = format_caption(_message(medium, large))

    assert "TĂNG LỚN" in caption.splitlines()[0]
    assert "Kỳ 12/2026" in caption
    assert "Và 1 kỳ giao hàng khác vượt ngưỡng" in caption


def test_several_periods_get_one_block_each_ordered_by_delivery_month() -> None:
    later = _event(delivery_month=date(2027, 1, 1))
    earlier = _event(delivery_month=date(2026, 11, 1))

    details = format_details(_message(later, earlier), base_url=BASE_URL)

    assert details.index("kỳ giao hàng 11/2026") < details.index("kỳ giao hàng 01/2027")
    assert details.count("Lưu ý:") == 1


def test_mixed_directions_are_marked_per_period() -> None:
    up = _event(delivery_month=date(2026, 11, 1))
    down = _event(delivery_month=date(2026, 12, 1), direction="down", percent_change=Decimal("-6"))

    details = format_details(_message(up, down), base_url=BASE_URL)

    assert "🔺 Ngô hạt · kỳ giao hàng 11/2026" in details
    assert "🔻 Ngô hạt · kỳ giao hàng 12/2026" in details


def test_too_many_periods_are_cut_with_a_note_and_stay_under_the_limit() -> None:
    events = [
        replace(_event(), delivery_month=date(2026 + index // 12, index % 12 + 1, 1))
        for index in range(60)
    ]

    details = format_details(_message(*events), base_url=BASE_URL)

    assert len(details) <= 4096
    assert "kỳ giao hàng nữa, xem trên web." in details
    assert details.rstrip().endswith("/quotes/abc-123")
    assert "kỳ giao hàng 01/2026" in details


def test_a_single_oversized_block_is_hard_cut_to_the_limit() -> None:
    details = format_details(_message(name="Y" * 6000), base_url=BASE_URL)

    assert len(details) <= 4096


def test_money_and_percent_formatting_edge_cases() -> None:
    event = _event(
        price_new=Decimal("1234567.5"),
        percent_change=Decimal("0.004"),
        secondary_percent=Decimal("-0.5"),
    )

    details = format_details(_message(event), base_url=BASE_URL)

    assert "0.00%" in details
    assert "−0.50%" in details
    assert "1,234,567.50" in format_caption(_message(event))


def test_cutting_never_splits_an_html_entity() -> None:
    caption = format_caption(_message(name="&" * 2000))

    assert len(caption) <= CAPTION_MAX_LENGTH
    body = caption.rstrip("…")
    assert body.endswith("&amp;") or "&" not in body[-5:].replace("&amp;", "")


def test_an_oversized_first_block_is_cut_but_keeps_the_footer_link() -> None:
    details = format_details(_message(name="Y" * 6000), base_url=BASE_URL)

    assert len(details) <= 4096
    assert details.endswith("/quotes/abc-123")
    assert "Lưu ý:" in details


def test_a_flat_cnf_with_a_moving_vnd_price_is_flagged_as_exchange_rate() -> None:
    event = _event(cnf_price_ref=Decimal("303.50"))

    assert ": 0.00% (chênh lệch do tỷ giá)" in format_details(_message(event), base_url=BASE_URL)
