from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from app.integrations.telegram import TELEGRAM_MESSAGE_MAX_LENGTH, escape_html

MAX_REMINDER_LINES = 30
# Tên vật tư dài tối đa 20 ký tự (cắt bằng "…") để một dòng "🟡 tên · 15 ngày" gọn trong một
# dòng trên điện thoại, không bị xuống dòng như bản đầu tiên.
NAME_WIDTH = 20
SEVERE_RATIO = 2  # trễ từ gấp đôi chu kỳ trở lên là "trễ nhiều"
UNKNOWN_ENTERER = "Chưa rõ người nhập"
_ELLIPSIS = "…"
_SEVERE = "🔴"
_MILD = "🟡"


@dataclass(frozen=True, slots=True)
class FreshnessLine:
    """Một vật tư quá hạn trong tin nhắc: số ngày chưa có giá, chu kỳ và người nhập gần nhất."""

    material_name: str
    age_days: int
    interval_days: int
    enterer_label: str | None


def format_freshness_reminder(lines: Sequence[FreshnessLine], *, day: date, base_url: str) -> str:
    """Tin nhắc cập nhật giá (F13), dựng cho màn hình điện thoại.

    Đầu tin là số vật tư và tóm tắt mức độ; thân tin gom theo NGƯỜI NHẬP (người cần nhắc), mỗi
    vật tư một dòng ngắn `🔴/🟡 tên · N ngày`. Người có vật tư trễ nhiều đứng đầu, vật tư trễ nhiều
    nhất đứng trước trong từng người, nhóm "chưa rõ người nhập" luôn cuối. Tối đa 30 vật tư; quá
    giới hạn độ dài của Telegram thì bỏ cả dòng cuối cho tới khi vừa (không cắt giữa thẻ HTML).
    """
    if not lines:
        raise ValueError("Tin nhắc rỗng không được gửi")
    ordered = sorted(lines, key=lambda item: (-_ratio(item), item.material_name))
    shown = ordered[:MAX_REMINDER_LINES]
    while True:
        text = _render(ordered, shown, day=day, base_url=base_url)
        if len(text) <= TELEGRAM_MESSAGE_MAX_LENGTH or len(shown) <= 1:
            return text
        shown = shown[:-1]


def _ratio(item: FreshnessLine) -> float:
    return item.age_days / item.interval_days


def _is_severe(item: FreshnessLine) -> bool:
    return item.age_days >= SEVERE_RATIO * item.interval_days


def _render(
    ordered: Sequence[FreshnessLine],
    shown: Sequence[FreshnessLine],
    *,
    day: date,
    base_url: str,
) -> str:
    severe = sum(1 for item in ordered if _is_severe(item))
    summary = []
    if severe:
        summary.append(f"{_SEVERE} {severe} trễ nhiều")
    if len(ordered) - severe:
        summary.append(f"{_MILD} {len(ordered) - severe} vừa trễ")
    rows = [
        f"⏰ <b>{len(ordered)} vật tư chưa có giá mới</b> · {day:%d/%m}",
        " · ".join(summary),
    ]
    for enterer, items in _groups(shown):
        rows.append("")
        rows.append(f"👤 <b>{escape_html(enterer or UNKNOWN_ENTERER)}</b> · {len(items)}")
        rows.extend(_row(item) for item in items)
    hidden = len(ordered) - len(shown)
    rows.append("")
    if hidden > 0:
        rows.append(f"và {hidden} vật tư nữa, xem trên web.")
    rows.append(f"<i>Số ngày tính từ lần nhận giá gần nhất. {_SEVERE} = trễ từ gấp đôi chu kỳ.</i>")
    rows.append(f'<a href="{escape_html(base_url.rstrip("/"))}/">Xem chi tiết trên web →</a>')
    return "\n".join(rows)


def _groups(shown: Sequence[FreshnessLine]) -> list[tuple[str | None, list[FreshnessLine]]]:
    by_person: dict[str | None, list[FreshnessLine]] = {}
    for item in shown:  # `shown` đã sắp theo mức trễ giảm dần nên thứ tự trong nhóm giữ nguyên
        by_person.setdefault(item.enterer_label or None, []).append(item)

    def order(entry: tuple[str | None, list[FreshnessLine]]) -> tuple[int, int, int, str]:
        person, items = entry
        return (
            1 if person is None else 0,  # chưa rõ người nhập luôn cuối
            0 if any(_is_severe(item) for item in items) else 1,
            -len(items),
            person or "",
        )

    return sorted(by_person.items(), key=order)


def _row(item: FreshnessLine) -> str:
    icon = _SEVERE if _is_severe(item) else _MILD
    name = item.material_name
    if len(name) > NAME_WIDTH:
        name = name[: NAME_WIDTH - 1].rstrip() + _ELLIPSIS
    return f"{icon} {escape_html(name)} · {item.age_days} ngày"
