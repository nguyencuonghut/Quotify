from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.integrations.telegram import TELEGRAM_MESSAGE_MAX_LENGTH, escape_html

MAX_DIGEST_LINES = 30
LINE_WIDTH = 34
_ELLIPSIS = "…"


@dataclass(frozen=True, slots=True)
class DigestLine:
    """Một vật tư trong bản tin: kỳ giao hàng có \\|%\\| lớn nhất của ngày hôm đó."""

    material_name: str
    direction: str
    percent: Decimal
    price: Decimal


def format_daily_digest(lines: Sequence[DigestLine], *, day: date, base_url: str) -> str:
    """Bản tin tổng hợp mức Nhẹ (M5): mỗi vật tư một dòng ≤ 34 ký tự, tối đa 30 dòng."""
    if not lines:
        raise ValueError("Bản tin rỗng không được gửi")
    ordered = sorted(lines, key=lambda item: (-abs(item.percent), item.material_name))
    shown = ordered[:MAX_DIGEST_LINES]
    rows = [f"📋 <b>Bản tin giá · {day:%d/%m}</b>", ""]
    rows.extend(_row(item) for item in shown)
    hidden = len(ordered) - len(shown)
    if hidden > 0:
        rows.append(f"và {hidden} vật tư nữa, xem trên web.")
    rows.append("")
    rows.append(f'<a href="{escape_html(base_url.rstrip("/"))}/quotes">Xem trên web →</a>')
    text = "\n".join(rows)
    return text if len(text) <= TELEGRAM_MESSAGE_MAX_LENGTH else text[:TELEGRAM_MESSAGE_MAX_LENGTH]


def _row(item: DigestLine) -> str:
    percent = item.percent.copy_abs().quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    arrow = "" if percent == 0 else "▲" if item.direction == "up" else "▼"
    price = f"{item.price.quantize(Decimal('1'), rounding=ROUND_HALF_UP):,}"
    head, tail = f"{arrow}{percent:.2f}% ", f" · {price}"
    room = max(LINE_WIDTH - len(head) - len(tail), 1)
    name = item.material_name
    if len(name) > room:
        name = name[: room - 1].rstrip() + _ELLIPSIS
    return f"{head}{escape_html(name)}{tail}"
