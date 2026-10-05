from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.services.price_alert_anomaly_formatter import (
    AnomalyPointView,
    format_anomaly_card,
    format_anomaly_cluster,
    format_anomaly_expired,
    format_anomaly_resolution,
)

BASE_URL = "https://quotify.honghafeed.com.vn"
MOBILE_WIDTH = 34


def _point(**overrides: object) -> AnomalyPointView:
    values: dict[str, object] = {
        "event_id": str(uuid4()),
        "delivery_month": date(2026, 11, 1),
        "price": Decimal("970"),
        "median": Decimal("25600"),
        "percent": Decimal("-96.2109"),
        "received_date": date(2026, 9, 15),
        "reference_values": (Decimal("25600"), Decimal("25435"), Decimal("25900")),
        "reference_point_count": 3,
        "quote_id": "q-1",
    }
    values.update(overrides)
    return AnomalyPointView(**values)  # type: ignore[arg-type]


def _plain_lines(text: str) -> list[str]:
    return [re.sub(r"</?b>", "", ln) for ln in text.split("\n") if "<a href" not in ln]


def test_card_matches_threonine_example_for_manager() -> None:
    point = _point(event_id="e-1")
    text, markup = format_anomaly_card("Threonine", [point], base_url=BASE_URL, with_buttons=True)
    assert text == (
        "<b>⚠️ GIÁ BẤT THƯỜNG · Threonine</b>\n"
        "\n"
        "Kỳ giao hàng: 11/2026\n"
        "Giá nhận 15/09: 970\n"
        "Giá hợp lệ gần đây:\n"
        "25,600 · 25,435 · 25,900\n"
        "Trung vị: 25,600\n"
        "Lệch ▼96.21%\n"
        f'🔗 <a href="{BASE_URL}/quotes/q-1">Xem phiếu →</a>\n'
        "\n"
        "Giá này tạm chưa được dùng\n"
        "để tính biến động."
    )
    assert markup == {
        "inline_keyboard": [
            [
                {"text": "✅ Giá đúng", "callback_data": "pa:ok:e-1"},
                {"text": "❌ Nhập sai", "callback_data": "pa:no:e-1"},
            ],
        ],
    }
    assert all(len(line) <= MOBILE_WIDTH for line in _plain_lines(text))


def test_card_for_entering_user_has_no_buttons() -> None:
    text, markup = format_anomaly_card(
        "Threonine", [_point()], base_url=BASE_URL, with_buttons=False
    )
    assert markup is None
    assert text.endswith("Vui lòng kiểm tra và sửa phiếu\nnếu nhập sai.")


def test_low_confidence_line_only_with_single_reference() -> None:
    one = _point(reference_values=(Decimal("25600"),), reference_point_count=1)
    text, _ = format_anomaly_card("Threonine", [one], base_url=BASE_URL, with_buttons=True)
    assert "Độ tin cậy thấp: chỉ có 1 giá tham chiếu" in text
    text, _ = format_anomaly_card("Threonine", [_point()], base_url=BASE_URL, with_buttons=True)
    assert "Độ tin cậy thấp" not in text


def test_reference_values_show_at_most_three_latest() -> None:
    refs = tuple(Decimal(v) for v in (1000, 25600, 25435, 25900))
    text, _ = format_anomaly_card(
        "T", [_point(reference_values=refs)], base_url=BASE_URL, with_buttons=True
    )
    assert "25,600 · 25,435 · 25,900" in text
    assert "1,000" not in text


def test_attached_count_line() -> None:
    text, _ = format_anomaly_card(
        "T", [_point(attached_count=2)], base_url=BASE_URL, with_buttons=True
    )
    assert "đã có 2 điểm xác nhận cùng mức" in text
    text, _ = format_anomaly_card("T", [_point()], base_url=BASE_URL, with_buttons=True)
    assert "xác nhận cùng mức" not in text


def test_two_points_one_card_two_button_rows() -> None:
    first = _point(event_id="e-1")
    second = _point(event_id="e-2", delivery_month=date(2026, 12, 1))
    text, markup = format_anomaly_card(
        "Threonine", [first, second], base_url=BASE_URL, with_buttons=True
    )
    assert "Kỳ giao hàng: 11/2026" in text
    assert "Kỳ giao hàng: 12/2026" in text
    assert markup is not None
    rows = markup["inline_keyboard"]
    assert [[b["text"] for b in row] for row in rows] == [
        ["✅ 11/2026 đúng", "❌ 11/2026 sai"],
        ["✅ 12/2026 đúng", "❌ 12/2026 sai"],
    ]
    assert rows[1][0]["callback_data"] == "pa:ok:e-2"
    assert rows[1][1]["callback_data"] == "pa:no:e-2"


def test_card_rejects_zero_or_three_points() -> None:
    with pytest.raises(ValueError):
        format_anomaly_card("T", [], base_url=BASE_URL, with_buttons=True)
    with pytest.raises(ValueError):
        format_anomaly_card("T", [_point()] * 3, base_url=BASE_URL, with_buttons=True)


def test_callback_data_fits_64_bytes_with_real_uuid() -> None:
    _, markup = format_anomaly_card("T", [_point()], base_url=BASE_URL, with_buttons=True)
    assert markup is not None
    for button in markup["inline_keyboard"][0]:
        assert len(button["callback_data"].encode()) <= 64


def test_callback_data_over_64_bytes_raises() -> None:
    with pytest.raises(ValueError):
        format_anomaly_card("T", [_point(event_id="x" * 80)], base_url=BASE_URL, with_buttons=True)


def test_html_in_material_name_is_escaped() -> None:
    text, _ = format_anomaly_card("A<b> & B", [_point()], base_url=BASE_URL, with_buttons=True)
    assert "A&lt;b&gt; &amp; B" in text
    assert "A<b>" not in text


def test_card_with_very_long_name_stays_within_limit() -> None:
    text, _ = format_anomaly_card("&" * 5000, [_point()], base_url=BASE_URL, with_buttons=True)
    assert len(text) <= 4096
    assert re.search(r"&(?!amp;|lt;|gt;|quot;|#)", text) is None


def _cluster(count: int) -> list[tuple[str, AnomalyPointView]]:
    return [(f"Vật tư {i}", _point(event_id=str(uuid4()))) for i in range(count)]


def test_cluster_of_six_lists_all_with_buttons() -> None:
    text, markup = format_anomaly_cluster(_cluster(6), base_url=BASE_URL, with_buttons=True)
    assert text.startswith("<b>⚠️ 6 GIÁ BẤT THƯỜNG</b>")
    assert "Vật tư 0 · 11/2026 · 970 · ▼96%" in text
    assert "xem trên web" not in text
    assert markup is not None
    assert len(markup["inline_keyboard"]) == 6
    for row in markup["inline_keyboard"]:
        assert len(row) == 2
        assert row[0]["callback_data"].startswith("pa:ok:")
        assert row[1]["callback_data"].startswith("pa:no:")


def test_cluster_of_twelve_cuts_to_ten() -> None:
    text, markup = format_anomaly_cluster(_cluster(12), base_url=BASE_URL, with_buttons=True)
    assert text.startswith("<b>⚠️ 12 GIÁ BẤT THƯỜNG</b>")
    assert "Vật tư 9 ·" in text
    assert "Vật tư 10 ·" not in text
    assert "và 2 điểm nữa, xem trên web." in text
    assert markup is not None
    assert len(markup["inline_keyboard"]) == 10


def test_cluster_for_entering_user_has_no_buttons() -> None:
    text, markup = format_anomaly_cluster(_cluster(3), base_url=BASE_URL, with_buttons=False)
    assert markup is None
    assert "Vui lòng kiểm tra và sửa phiếu\nnếu nhập sai." in text


def test_cluster_truncates_names_escapes_and_respects_limit() -> None:
    items = [("<" * 3000, replace(_point(), event_id=str(uuid4()))) for _ in range(12)]
    text, _ = format_anomaly_cluster(items, base_url=BASE_URL, with_buttons=True)
    assert len(text) <= 4096
    assert "&lt;" in text
    assert "…" in text
    assert "<<" not in text


def test_resolution_texts_use_vietnam_time_and_escape() -> None:
    at = datetime(2026, 10, 5, 3, 7, tzinfo=UTC)  # 10:07 giờ Việt Nam
    assert (
        format_anomaly_resolution("accepted", "Lan <A>", at)
        == "✅ Đã xác nhận giá đúng bởi Lan &lt;A&gt; lúc 10:07 05/10/2026"
    )
    assert (
        format_anomaly_resolution("rejected", "Minh", at)
        == "❌ Đã đánh dấu nhập sai bởi Minh lúc 10:07 05/10/2026"
    )


def test_expired_text() -> None:
    assert format_anomaly_expired() == "Thẻ này đã hết hạn. Điểm giá vẫn bị loại khỏi tính toán."
