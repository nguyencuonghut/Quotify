from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal
from zoneinfo import ZoneInfo

from app.integrations.telegram import (
    TELEGRAM_MESSAGE_MAX_LENGTH,
    escape_html,
)

CALLBACK_DATA_MAX_BYTES = 64
MAX_CLUSTER_POINTS = 10
MAX_REFERENCE_VALUES = 3
_NAME_MAX = 60
_CLUSTER_NAME_MAX = 18
_BUTTON_NAME_MAX = 12
_ELLIPSIS = "…"
_VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# Hai câu cố định, ngắt dòng ở ranh giới từ để mỗi dòng ≤ 34 ký tự trên điện thoại.
CHECK_PROMPT = "Vui lòng kiểm tra và sửa phiếu\nnếu nhập sai."
NOT_USED_NOTE = "Giá này tạm chưa được dùng\nđể tính biến động."
EXPIRED_TEXT = "Thẻ này đã hết hạn. Điểm giá vẫn bị loại khỏi tính toán."


@dataclass(frozen=True, slots=True)
class AnomalyPointView:
    """Một điểm giá bất thường đã lưu; formatter không tính lại gì từ DB."""

    event_id: str
    delivery_month: date
    price: Decimal
    median: Decimal
    percent: Decimal  # độ lệch so với trung vị, có dấu
    received_date: date
    reference_values: tuple[Decimal, ...]  # các giá hợp lệ gần đây, mới nhất ở cuối
    reference_point_count: int
    quote_id: str
    attached_count: int = 0


def format_anomaly_card(
    material_name: str,
    points: Sequence[AnomalyPointView],
    *,
    base_url: str,
    with_buttons: bool,
) -> tuple[str, dict[str, Any] | None]:
    """Thẻ giá bất thường của MỘT vật tư (1 đến 2 điểm) và bàn phím nút (nếu có)."""
    if not 1 <= len(points) <= 2:
        raise ValueError("Thẻ giá bất thường nhận 1 đến 2 điểm")
    name = escape_html(_truncate(material_name, _NAME_MAX))
    blocks = [f"<b>⚠️ GIÁ BẤT THƯỜNG · {name}</b>"]
    for point in points:
        blocks.append(_point_block(point, base_url=base_url))
    blocks.append(NOT_USED_NOTE)
    if not with_buttons:
        blocks.append(CHECK_PROMPT)
    text = _fit_text("\n\n".join(blocks), TELEGRAM_MESSAGE_MAX_LENGTH)
    if not with_buttons:
        return text, None
    many = len(points) > 1
    rows = [
        _button_row(
            point,
            ok_label=f"✅ {_month(point.delivery_month)} đúng" if many else "✅ Giá đúng",
            no_label=f"❌ {_month(point.delivery_month)} sai" if many else "❌ Nhập sai",
        )
        for point in points
    ]
    return text, {"inline_keyboard": rows}


def format_anomaly_cluster(
    points_by_material: Sequence[tuple[str, AnomalyPointView]],
    *,
    base_url: str,
    with_buttons: bool,
) -> tuple[str, dict[str, Any] | None]:
    """Tin tóm tắt khi từ 3 điểm bất thường trở lên trong cùng ngày."""
    shown = points_by_material[:MAX_CLUSTER_POINTS]
    lines = [f"<b>⚠️ {len(points_by_material)} GIÁ BẤT THƯỜNG</b>", ""]
    for name, point in shown:
        lines.append(
            f"{escape_html(_truncate(name, _CLUSTER_NAME_MAX))} · "
            f"{_month(point.delivery_month)} · {_money(point.price)} · "
            f"{_percent(point.percent, 0)}",
        )
    hidden = len(points_by_material) - len(shown)
    if hidden > 0:
        lines.append(f"và {hidden} điểm nữa, xem trên web.")
    lines.append("")
    lines.append(NOT_USED_NOTE)
    if not with_buttons:
        lines.append(CHECK_PROMPT)
    text = _fit_text("\n".join(lines), TELEGRAM_MESSAGE_MAX_LENGTH)
    if not with_buttons:
        return text, None
    rows = []
    for name, point in shown:
        short = _truncate(name, _BUTTON_NAME_MAX)
        label = f"{short} {_month(point.delivery_month)}"
        rows.append(_button_row(point, ok_label=f"✅ {label}", no_label=f"❌ {label}"))
    return text, {"inline_keyboard": rows}


def format_anomaly_resolution(
    kind: Literal["accepted", "rejected"],
    actor_name: str,
    at: datetime,
) -> str:
    """Nội dung thay thế sau khi có người bấm nút (giờ Việt Nam)."""
    local = (at if at.tzinfo else at.replace(tzinfo=UTC)).astimezone(_VN_TZ)
    stamp = local.strftime("%H:%M %d/%m/%Y")
    name = escape_html(actor_name)
    if kind == "accepted":
        return f"✅ Đã xác nhận giá đúng bởi {name} lúc {stamp}"
    return f"❌ Đã đánh dấu nhập sai bởi {name} lúc {stamp}"


def format_anomaly_expired() -> str:
    return EXPIRED_TEXT


def _point_block(point: AnomalyPointView, *, base_url: str) -> str:
    refs = point.reference_values[-MAX_REFERENCE_VALUES:]
    lines = [
        f"Kỳ giao hàng: {_month(point.delivery_month)}",
        f"Giá nhận {_short_day(point.received_date)}: {_money(point.price)}",
        "Giá hợp lệ gần đây:",
        " · ".join(_money(value) for value in refs),
        f"Trung vị: {_money(point.median)}",
        f"Lệch {_percent(point.percent, 2)}",
    ]
    if point.reference_point_count == 1:
        lines.append("Độ tin cậy thấp: chỉ có 1 giá tham chiếu")
    if point.attached_count > 0:
        lines.append(f"đã có {point.attached_count} điểm xác nhận cùng mức")
    url = escape_html(f"{base_url.rstrip('/')}/quotes/{point.quote_id}")
    lines.append(f'🔗 <a href="{url}">Xem phiếu →</a>')
    return "\n".join(lines)


def _button_row(point: AnomalyPointView, *, ok_label: str, no_label: str) -> list[dict[str, str]]:
    return [
        {"text": ok_label, "callback_data": _callback("ok", point.event_id)},
        {"text": no_label, "callback_data": _callback("no", point.event_id)},
    ]


def _callback(action: Literal["ok", "no"], event_id: str) -> str:
    data = f"pa:{action}:{event_id}"
    if len(data.encode("utf-8")) > CALLBACK_DATA_MAX_BYTES:
        raise ValueError("callback_data vượt 64 byte")
    return data


def _money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('1'), rounding=ROUND_HALF_UP):,}"


def _percent(value: Decimal, places: int) -> str:
    rounded = value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    arrow = "▲" if rounded > 0 else "▼" if rounded < 0 else ""
    return f"{arrow}{abs(rounded):.{places}f}%"


def _short_day(value: date) -> str:
    return value.strftime("%d/%m")


def _month(value: date) -> str:
    return value.strftime("%m/%Y")


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + _ELLIPSIS


def _fit_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    # Không cắt giữa thực thể HTML (ví dụ "&am"), Telegram sẽ báo lỗi parse và bỏ cả tin.
    ampersand = cut.rfind("&")
    if ampersand != -1 and ";" not in cut[ampersand:]:
        cut = cut[:ampersand]
    return cut.rstrip() + _ELLIPSIS
