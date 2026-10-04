from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from app.integrations.telegram import (
    TELEGRAM_MESSAGE_MAX_LENGTH,
    escape_html,
)

CAPTION_MAX_LENGTH = 1024
_ELLIPSIS = "…"
_MINUS = "−"

Level = Literal["light", "medium", "large"]
Direction = Literal["up", "down"]

_LEVEL_LABEL = {"light": "NHẸ", "medium": "TRUNG BÌNH", "large": "LỚN"}
_LEVEL_DOT = {"light": "🟡", "medium": "🟠", "large": "🔴"}
_LEVEL_ORDER = {"light": 1, "medium": 2, "large": 3}
_DIRECTION_WORD = {"up": "TĂNG", "down": "GIẢM"}
_DIRECTION_ARROW = {"up": "🔺", "down": "🔻"}
_CHART_ARROW = {"up": "▲", "down": "▼"}

FOOTER_NOTE = "Lưu ý: điểm giá có thể thuộc nhà cung cấp khác với lần trước."


@dataclass(frozen=True, slots=True)
class EventView:
    """Một sự kiện (một kỳ giao hàng) đã lưu; formatter không tính lại gì từ DB."""

    delivery_month: date
    direction: Direction
    level: Level
    rule: Literal["R1", "R2", "R3"]
    percent_change: Decimal
    price_new: Decimal
    price_ref: Decimal
    received_date_new: date
    received_date_ref: date
    window_min: Decimal
    window_max: Decimal
    window_min_date: date
    window_max_date: date
    secondary_rule: Literal["R1", "R2", "R3"] | None = None
    secondary_percent: Decimal | None = None
    secondary_price_ref: Decimal | None = None
    secondary_date_ref: date | None = None
    cnf_price_new: Decimal | None = None
    cnf_price_ref: Decimal | None = None
    cnf_date_ref: date | None = None


@dataclass(frozen=True, slots=True)
class MessageView:
    material_name: str
    events: Sequence[EventView]
    quote_id: str
    reference_working_days: int = 7


def top_event(message: MessageView) -> EventView:
    """Kỳ có mức cao nhất; hòa thì kỳ giao hàng sớm nhất."""
    return max(
        sorted(message.events, key=lambda e: e.delivery_month),
        key=lambda e: _LEVEL_ORDER[e.level],
    )


def title(level: Level, direction: Direction) -> str:
    arrow, dot = _DIRECTION_ARROW[direction], _LEVEL_DOT[level]
    return f"{arrow}{dot} {_DIRECTION_WORD[direction]} {_LEVEL_LABEL[level]}"


def chart_title(message: MessageView) -> str:
    """Tiêu đề trong ảnh: không emoji (DejaVu không vẽ được), dùng ▲ ▼."""
    top = top_event(message)
    return (
        f"{_CHART_ARROW[top.direction]} {_DIRECTION_WORD[top.direction]} "
        f"{_LEVEL_LABEL[top.level]} · {message.material_name}"
    )


def format_caption(message: MessageView) -> str:
    """Caption ngắn (≤ 1.024 ký tự) của ảnh: tiêu đề, giá mới và lý do chính."""
    top = top_event(message)
    when = _day(top.received_date_new)
    if top.cnf_price_new is not None:
        when = f"giá quy đổi, {when}"
    lines = [
        f"{title(top.level, top.direction)} · {escape_html(message.material_name)}",
        f"Giá thấp nhất hôm nay: {_money(top.price_new)} VNĐ/KG ({when})",
        f"Kỳ {_month(top.delivery_month)}: {_percent(top.percent_change)} "
        f"so với {_reference_target(top.rule, message.reference_working_days)}",
    ]
    others = len(message.events) - 1
    if others > 0:
        lines.append(f"Và {others} kỳ giao hàng khác vượt ngưỡng, xem chi tiết ở tin kế tiếp.")
    return _fit(lines, CAPTION_MAX_LENGTH)


def format_details(message: MessageView, *, base_url: str) -> str:
    """Tin chi tiết (≤ 4.096 ký tự): một khối cho mỗi kỳ giao hàng, cắt có chú thích nếu dài."""
    footer = [
        "",
        FOOTER_NOTE,
        f"🔗 Xem chi tiết: {base_url.rstrip('/')}/quotes/{escape_html(message.quote_id)}",
    ]
    events = sorted(message.events, key=lambda e: e.delivery_month)
    mixed = len({e.direction for e in events}) > 1
    blocks = [_block(message, event, mixed) for event in events]

    footer_text = "\n" + "\n".join(footer)
    kept: list[str] = []
    for index, block in enumerate(blocks):
        remaining = len(blocks) - index - 1
        candidate = [*kept, block]
        note = [f"… còn {remaining} kỳ giao hàng nữa, xem trên web."] if remaining else []
        if len(_join(candidate, note, footer)) > TELEGRAM_MESSAGE_MAX_LENGTH:
            if kept:
                skipped = len(blocks) - len(kept)
                return _join(kept, [f"… còn {skipped} kỳ giao hàng nữa, xem trên web."], footer)
            # Khối đầu tiên một mình đã quá dài: cắt khối, giữ nguyên phần chân có liên kết.
            room = TELEGRAM_MESSAGE_MAX_LENGTH - len(footer_text) - 2
            only = [_fit_text(block, room)]
            return _join(only, [], footer)
        kept = candidate
    return _join(kept, [], footer)


def _block(message: MessageView, event: EventView, mixed: bool) -> str:
    window = message.reference_working_days
    prefix = f"{_DIRECTION_ARROW[event.direction]} " if mixed else ""
    lines = [
        f"{prefix}{escape_html(message.material_name)} · "
        f"kỳ giao hàng {_month(event.delivery_month)}",
        f"Lý do chính: so với {_reference_target(event.rule, window)}",
        f"  {_percent(event.percent_change)}  "
        f"({_money(event.price_ref)} · {_day(event.received_date_ref)})",
    ]
    if (
        event.secondary_rule is not None
        and event.secondary_percent is not None
        and event.secondary_price_ref is not None
        and event.secondary_date_ref is not None
    ):
        lines += [
            f"So sánh khác: so với {_reference_target(event.secondary_rule, window)}",
            f"  {_percent(event.secondary_percent)}  "
            f"({_money(event.secondary_price_ref)} · {_day(event.secondary_date_ref)})",
        ]
    lines += [
        f"Vùng tham chiếu {window} ngày làm việc",
        f"  Thấp nhất: {_money(event.window_min)} ({_short_day(event.window_min_date)}) · "
        f"Cao nhất: {_money(event.window_max)} ({_short_day(event.window_max_date)})",
    ]
    cnf = _cnf_line(event)
    if cnf:
        lines.append(cnf)
    return "\n".join(lines)


def _cnf_line(event: EventView) -> str | None:
    """QĐ-8: chỉ khi điểm mới là USD/MT; dòng 'so với' chỉ khi điểm tham chiếu cũng là USD/MT."""
    if event.cnf_price_new is None:
        return None
    line = f"CNF (USD/MT): {_money(event.cnf_price_new)} ({_day(event.received_date_new)})"
    if (
        event.cnf_price_ref is not None
        and event.cnf_date_ref is not None
        and event.cnf_price_ref > 0
    ):
        change = (event.cnf_price_new - event.cnf_price_ref) / event.cnf_price_ref * 100
        line += (
            f", so với {_money(event.cnf_price_ref)} ({_day(event.cnf_date_ref)}): "
            f"{_percent(change)}"
        )
        # CNF đứng yên hoặc ngược chiều VNĐ/KG đều là chênh lệch do tỷ giá (QĐ-8).
        if change == 0 or (change > 0) != (event.direction == "up"):
            line += " (chênh lệch do tỷ giá)"
    return line


def _reference_target(rule: str, working_days: int) -> str:
    return {
        "R1": "điểm giá gần nhất",
        "R2": f"giá thấp nhất {working_days} ngày làm việc",
        "R3": f"giá cao nhất {working_days} ngày làm việc",
    }[rule]


def format_price_short(value: Decimal) -> str:
    """Giá làm tròn nguyên có dấu phẩy nghìn, dùng cho nhãn trên biểu đồ (ví dụ 8,150)."""
    return f"{value.quantize(Decimal('1'), rounding=ROUND_HALF_UP):,}"


def format_percent(value: Decimal) -> str:
    return _percent(value)


def _money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


def _percent(value: Decimal) -> str:
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = "+" if rounded > 0 else _MINUS if rounded < 0 else ""
    return f"{sign}{abs(rounded):.2f}%"


def _day(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _short_day(value: date) -> str:
    return value.strftime("%d/%m")


def _month(value: date) -> str:
    return value.strftime("%m/%Y")


def _join(blocks: list[str], notes: list[str], footer: list[str]) -> str:
    parts = ["\n\n".join(blocks)]
    if notes:
        parts.append("\n".join(notes))
    text = "\n\n".join(parts)
    return text + "\n" + "\n".join(footer)


def _fit(lines: list[str], limit: int) -> str:
    return _fit_text("\n".join(lines), limit)


def _fit_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    # Không cắt giữa thực thể HTML (ví dụ "&am"), Telegram sẽ báo lỗi parse và bỏ cả tin.
    ampersand = cut.rfind("&")
    if ampersand != -1 and ";" not in cut[ampersand:]:
        cut = cut[:ampersand]
    return cut.rstrip() + _ELLIPSIS
