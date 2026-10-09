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
_CHART_ARROW = {"up": "▲", "down": "▼"}
_DIRECTION_ADVERB = {"up": "Tăng", "down": "Giảm"}

FOOTER_NOTE = "Điểm giá có thể thuộc nhà cung cấp khác lần trước."


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
    prior_alert_price: Decimal | None = None  # báo tiếp: giá của lần báo trước
    prior_alert_date: date | None = None
    reference_age_days: int | None = None  # gốc dự phòng: gốc cách bao nhiêu ngày


@dataclass(frozen=True, slots=True)
class MessageView:
    material_name: str
    events: Sequence[EventView]
    quote_id: str
    reference_working_days: int = 7
    warn_percent: Decimal | None = None  # |%| từ mức này trở lên thì nhắc kiểm tra phiếu


def top_event(message: MessageView) -> EventView:
    """Kỳ có mức cao nhất; hòa thì kỳ giao hàng sớm nhất."""
    return max(
        sorted(message.events, key=lambda e: e.delivery_month),
        key=lambda e: _LEVEL_ORDER[e.level],
    )


def title(level: Level, direction: Direction) -> str:
    """Chấm màu là MỨC, chữ là CHIỀU: mỗi ý chỉ xuất hiện một lần."""
    return f"{_LEVEL_DOT[level]} {_DIRECTION_WORD[direction]} {_LEVEL_LABEL[level]}"


def _headline(event: EventView) -> str:
    """"🔴 ▼18.08% · GIẢM LỚN": chấm màu là mức, mũi tên và phần trăm đứng ngay sau chấm."""
    return (
        f"{_LEVEL_DOT[event.level]} {_percent(event.percent_change)} · "
        f"{_DIRECTION_WORD[event.direction]} {_LEVEL_LABEL[event.level]}"
    )


def chart_title(message: MessageView) -> str:
    """Tiêu đề trong ảnh: không emoji (DejaVu không vẽ được), dùng ▲ ▼."""
    top = top_event(message)
    return (
        f"{_CHART_ARROW[top.direction]} {_DIRECTION_WORD[top.direction]} "
        f"{_LEVEL_LABEL[top.level]} · {message.material_name}"
    )


def format_caption(message: MessageView) -> str:
    """Caption ngắn của ảnh (≤ 1.024 ký tự), mỗi dòng ngắn để không xuống dòng trên điện thoại.

    Tiêu đề mở bằng chấm màu (mức) rồi mũi tên kèm phần trăm, sau đó chiều và mức bằng chữ, rồi
    "gốc → giá mới (chênh lệch)"; gốc so sánh nằm ở tin chi tiết. Có thể thêm dòng nhắc các kỳ
    khác và dòng cảnh báo khi biến động rất lớn (nghi nhập nhầm).
    """
    top = top_event(message)
    delta = top.price_new - top.price_ref
    lines = [
        f"<b>{_headline(top)} · {escape_html(message.material_name)}</b>",
        f"{_money_short(top.price_ref)} → {_money_short(top.price_new)} VNĐ/KG "
        f"({_signed_money(delta)})",
    ]
    if top.prior_alert_price is not None and top.prior_alert_price > 0:
        since_last = (top.price_new - top.prior_alert_price) / top.prior_alert_price * 100
        lines.append(
            f"↻ Báo tiếp: lần trước {_money_short(top.prior_alert_price)} ({_percent(since_last)})",
        )
    if top.reference_age_days is not None:
        lines.append(f"⏳ Gốc cách đây {top.reference_age_days} ngày")
    others = len(message.events) - 1
    if others > 0:
        lines.append(f"➕ Kỳ {_month(top.delivery_month)} và {others} kỳ khác ↓")
    if message.warn_percent is not None and abs(top.percent_change) >= message.warn_percent:
        lines.append(f"⚠️ {_DIRECTION_ADVERB[top.direction]} rất mạnh, nên kiểm tra phiếu")
    return _fit(lines, CAPTION_MAX_LENGTH)


def format_details(message: MessageView, *, base_url: str) -> str:
    """Tin chi tiết (≤ 4.096 ký tự), gọn cho điện thoại và gửi im lặng.

    Nhiều kỳ giao hàng thì mở đầu bằng bảng một dòng mỗi kỳ (các kỳ cùng số liệu được gộp một
    dòng), rồi giải thích chi tiết kỳ đang vẽ trong ảnh.
    """
    top = top_event(message)
    events = sorted(message.events, key=lambda e: e.delivery_month)
    sections = []
    if len(events) > 1:
        sections.append(_summary(events))
    sections.append(_detail(message, top, many=len(events) > 1))
    url = escape_html(f"{base_url.rstrip('/')}/quotes/{message.quote_id}")
    footer = "\n".join(
        [
            f'🔗 <a href="{url}">Xem phiếu →</a>',
            f"ℹ️ {FOOTER_NOTE}",
        ],
    )
    body = "\n\n".join(sections)
    room = TELEGRAM_MESSAGE_MAX_LENGTH - len(footer) - 2
    # Cắt phần thân (không bao giờ cắt chân có liên kết) và không chẻ giữa thực thể HTML.
    return _fit_text(body, room) + "\n\n" + footer


_MAX_SUMMARY_LINES = 12


def _summary(events: list[EventView]) -> str:
    """Một dòng mỗi nhóm kỳ giao hàng; các kỳ cùng chiều, mức, phần trăm và giá thì gộp lại."""
    groups: list[tuple[EventView, list[str]]] = []
    for event in events:
        key = (event.direction, event.level, _percent(event.percent_change), event.price_ref)
        for head, months in groups:
            head_key = (head.direction, head.level, _percent(head.percent_change), head.price_ref)
            if head_key == key:
                months.append(_month(event.delivery_month))
                break
        else:
            groups.append((event, [_month(event.delivery_month)]))
    lines = ["<b>Các kỳ giao hàng vượt ngưỡng</b>"]
    for head, months in groups[:_MAX_SUMMARY_LINES]:
        label = (
            ", ".join(months)
            if len(months) <= 2
            else f"{months[0]}–{months[-1]} ({len(months)} kỳ)"
        )
        lines.append(
            f"{_LEVEL_DOT[head.level]} {label} · <b>{_percent(head.percent_change)}</b>",
        )
    hidden = len(groups) - _MAX_SUMMARY_LINES
    if hidden > 0:
        lines.append(f"… và {hidden} nhóm kỳ nữa, xem trên web.")
    return "\n".join(lines)


def _detail(message: MessageView, event: EventView, *, many: bool) -> str:
    window = message.reference_working_days
    heading = f"<b>Chi tiết kỳ {_month(event.delivery_month)}</b>"
    if many:
        heading += " (kỳ trong ảnh)"
    lines = [
        heading,
        *_cnf_change_lines(event),
        f"So với {_reference_target_short(event.rule, window)}"
        + (f" (cách {event.reference_age_days} ngày)" if event.reference_age_days else ""),
        f"  {_money_short(event.price_ref)} ({_short_day(event.received_date_ref)})",
        f"Giá mới: {_money_short(event.price_new)} ({_short_day(event.received_date_new)})",
    ]
    if (
        event.secondary_rule is not None
        and event.secondary_percent is not None
        and event.secondary_price_ref is not None
    ):
        lines.append(
            f"Cũng: {_percent(event.secondary_percent)} "
            f"{_reference_short(event.secondary_rule, window)}",
        )
    if event.reference_age_days:
        lines.append(f"Không có giá nào trong {window} ngày qua")
    else:
        lines.append(
            f"{window} ngày qua: {_money_short(event.window_min)} – "
            f"{_money_short(event.window_max)}",
        )
    if event.cnf_price_new is not None:
        lines.append(f"CNF: {_money(event.cnf_price_new)} USD/MT")
    return "\n".join(lines)


def _cnf_change_lines(event: EventView) -> list[str]:
    """QĐ-8: dòng 'so với' chỉ khi điểm mới và điểm tham chiếu đều là USD/MT; đứng đầu chi tiết."""
    lines: list[str] = []
    if (
        event.cnf_price_new is not None
        and event.cnf_price_ref is not None
        and event.cnf_date_ref is not None
        and event.cnf_price_ref > 0
    ):
        change = (event.cnf_price_new - event.cnf_price_ref) / event.cnf_price_ref * 100
        lines.append(
            f"  {_percent(change)} so với {_money(event.cnf_price_ref)} "
            f"({_short_day(event.cnf_date_ref)})",
        )
        # CNF đứng yên hoặc ngược chiều VNĐ/KG đều là chênh lệch do tỷ giá (QĐ-8).
        if change == 0 or (change > 0) != (event.direction == "up"):
            lines.append("  (chênh lệch do tỷ giá)")
    return lines


def _reference_target_short(rule: str, working_days: int) -> str:
    return {
        "R1": "điểm gần nhất",
        "R2": f"giá thấp nhất {working_days} ngày",
        "R3": f"giá cao nhất {working_days} ngày",
    }[rule]


def _reference_short(rule: str, working_days: int) -> str:
    """Cụm ngắn cho dòng có số phần trăm (giữ dưới độ rộng một dòng trên điện thoại)."""
    return {
        "R1": "so với điểm gần nhất",
        "R2": f"so với thấp nhất {working_days} ngày",
        "R3": f"so với cao nhất {working_days} ngày",
    }[rule]


def _money_short(value: Decimal) -> str:
    """Giá VNĐ/KG làm tròn nguyên có dấu phẩy nghìn (phần lẻ không có ý nghĩa), ví dụ 13,215."""
    return f"{value.quantize(Decimal('1'), rounding=ROUND_HALF_UP):,}"


def _signed_money(value: Decimal) -> str:
    rounded = value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    sign = "+" if rounded > 0 else _MINUS if rounded < 0 else ""
    return f"{sign}{abs(rounded):,}"


def format_price_short(value: Decimal) -> str:
    """Giá làm tròn nguyên có dấu phẩy nghìn, dùng cho nhãn trên biểu đồ (ví dụ 8,150)."""
    return f"{value.quantize(Decimal('1'), rounding=ROUND_HALF_UP):,}"


def format_percent(value: Decimal) -> str:
    """Phần trăm có dấu (+5.57%, −3.20%), dùng cho nhãn trên biểu đồ."""
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = "+" if rounded > 0 else _MINUS if rounded < 0 else ""
    return f"{sign}{abs(rounded):.2f}%"


def _money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


def _percent(value: Decimal) -> str:
    """Phần trăm trong tin: mũi tên chữ thay cho dấu (▲5.57%, ▼3.20%); chiều chỉ ghi một chỗ."""
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    arrow = "▲" if rounded > 0 else "▼" if rounded < 0 else ""
    return f"{arrow}{abs(rounded):.2f}%"


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
