from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from app.integrations.telegram import TELEGRAM_MESSAGE_MAX_LENGTH, escape_html

MAX_REMINDER_LINES = 30


@dataclass(frozen=True, slots=True)
class FreshnessLine:
    """Một vật tư quá hạn trong tin nhắc: số ngày chưa có giá, chu kỳ và người nhập gần nhất."""

    material_name: str
    age_days: int
    interval_days: int
    enterer_label: str | None


def format_freshness_reminder(lines: Sequence[FreshnessLine], *, day: date, base_url: str) -> str:
    """Tin nhắc cập nhật giá (F13): vật tư quá hạn nặng nhất trước, tối đa 30 dòng."""
    if not lines:
        raise ValueError("Tin nhắc rỗng không được gửi")
    ordered = sorted(
        lines,
        key=lambda item: (-(item.age_days / item.interval_days), item.material_name),
    )
    header = f"⏰ <b>Vật tư chưa có giá mới ({len(ordered)})</b> · {day:%d/%m}"
    footer = f'<a href="{escape_html(base_url.rstrip("/"))}/">Xem trên web →</a>'
    rendered = [_row(item) for item in ordered[:MAX_REMINDER_LINES]]
    # Bỏ cả dòng (không cắt giữa chừng, tránh làm hỏng thẻ HTML) cho tới khi vừa giới hạn Telegram.
    while True:
        hidden = len(ordered) - len(rendered)
        rows = [header, "", *rendered]
        if hidden > 0:
            rows.append(f"và {hidden} vật tư nữa, xem trên web.")
        rows.extend(["", footer])
        text = "\n".join(rows)
        if len(text) <= TELEGRAM_MESSAGE_MAX_LENGTH or len(rendered) <= 1:
            return text
        rendered.pop()


def _row(item: FreshnessLine) -> str:
    row = (
        f"• {escape_html(item.material_name)} — {item.age_days} ngày (chu kỳ {item.interval_days})"
    )
    if item.enterer_label:
        row += f" · {escape_html(item.enterer_label)}"
    return row
