from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.integrations.telegram import TELEGRAM_MESSAGE_MAX_LENGTH
from app.services.price_alert_digest_formatter import (
    MAX_DIGEST_LINES,
    DigestLine,
    format_daily_digest,
)

BASE_URL = "https://quotify.example"
DAY = date(2054, 3, 4)


def line(name: str, percent: str, price: int, direction: str = "up") -> DigestLine:
    return DigestLine(name, direction, Decimal(percent), Decimal(price))  # type: ignore[arg-type]


def test_a_digest_lists_one_line_per_material_sorted_by_the_biggest_move() -> None:
    text = format_daily_digest(
        [line("Lúa mỳ 3", "2.60", 8400), line("Ngô hạt", "4.10", 7800, "down")],
        day=DAY,
        base_url=BASE_URL,
    )

    rows = text.splitlines()
    assert rows[0] == "📋 <b>Bản tin giá · 04/03</b>"
    assert rows[2] == "▼4.10% Ngô hạt · 7,800"
    assert rows[3] == "▲2.60% Lúa mỳ 3 · 8,400"
    assert text.endswith(f'<a href="{BASE_URL}/quotes">Xem trên web →</a>')


def test_every_material_line_fits_the_phone_width_even_with_a_long_name() -> None:
    text = format_daily_digest(
        [line("Methionine 98% (Sumi/CJ/Evonik) loại đặc biệt", "12.34", 129700)],
        day=DAY,
        base_url=BASE_URL,
    )

    material_line = text.splitlines()[2]
    assert len(material_line) <= 34
    assert material_line.startswith("▲12.34% Methionine")
    assert material_line.endswith("… · 129,700")


def test_names_are_html_escaped() -> None:
    text = format_daily_digest([line("A & B <x>", "2.50", 1000)], day=DAY, base_url=BASE_URL)

    assert "A &amp; B &lt;x&gt;" in text


def test_more_than_the_line_limit_shows_how_many_were_left_out() -> None:
    lines = [
        line(f"Vật tư {i}", f"{2 + i / 100:.2f}", 1000 + i) for i in range(MAX_DIGEST_LINES + 5)
    ]

    text = format_daily_digest(lines, day=DAY, base_url=BASE_URL)

    assert "và 5 vật tư nữa, xem trên web." in text
    assert len(text) <= TELEGRAM_MESSAGE_MAX_LENGTH
    assert sum(1 for row in text.splitlines() if row.startswith(("▲", "▼"))) == MAX_DIGEST_LINES


def test_a_zero_move_has_no_arrow_and_an_empty_digest_is_rejected() -> None:
    text = format_daily_digest([line("Ngô hạt", "0.00", 7800)], day=DAY, base_url=BASE_URL)
    assert "0.00% Ngô hạt" in text
    with pytest.raises(ValueError):
        format_daily_digest([], day=DAY, base_url=BASE_URL)
