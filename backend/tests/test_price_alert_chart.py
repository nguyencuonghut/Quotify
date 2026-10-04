from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import warnings
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from PIL import Image

from app.services.price_alert_chart import (
    LEVEL_COLORS,
    ChartLevel,
    ChartSpec,
    render_price_chart,
    render_price_chart_sync,
)

# 21/09 la thu Hai; 02/10 la thu Sau.
_RAW: dict[date, int] = {
    date(2026, 9, 21): 7950,
    date(2026, 9, 22): 7880,
    date(2026, 9, 23): 7900,
    date(2026, 9, 24): 7790,
    date(2026, 9, 25): 7720,
    date(2026, 9, 28): 7760,
    date(2026, 9, 29): 7830,
    date(2026, 9, 30): 7800,
    date(2026, 10, 1): 7840,
    date(2026, 10, 2): 8150,
}


def _spec(
    material: str = "Ngô hạt",
    head: str = "▲ TĂNG TRUNG BÌNH",
    level: ChartLevel = "medium",
    last: int = 8150,
) -> ChartSpec:
    raw = {**_RAW, date(2026, 10, 2): last}
    points = sorted(raw.items())
    window = [v for d, v in points if date(2026, 9, 23) <= d <= date(2026, 10, 1)]
    ref_min, ref_max = min(window), max(window)
    pct = (last / ref_min - 1) * 100
    return ChartSpec(
        title=f"{head} · {material}",
        subtitle="Giá thấp nhất hôm nay: 8,150 VNĐ/KG · Kỳ giao hàng 12/2026 · ơ ư ằ ẵ ế ộ",
        level=level,
        points=points,
        new_point_date=date(2026, 10, 2),
        window_start=date(2026, 9, 23),
        window_end=date(2026, 10, 1),
        ref_min=ref_min,
        ref_max=ref_max,
        last_label=f"{last:,}  ({pct:+.2f}%)",
        ref_min_label=f"Thấp nhất: {ref_min:,}",
        ref_max_label=f"Cao nhất: {ref_max:,}",
    )


def _decode(png: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(png))
    img.load()
    return img


def test_png_decodes_at_900x500() -> None:
    img = _decode(render_price_chart_sync(_spec()))
    assert img.format == "PNG"
    assert img.size == (900, 500)


def test_no_missing_glyph_warning(caplog: pytest.LogCaptureFixture) -> None:
    long_name = "Bột cá Peru Ơ Ư Ằ Ẵ Ế Ộ Ợ Ữ Ỷ Ỵ Đ đ " * 2
    with caplog.at_level(logging.DEBUG), warnings.catch_warnings():
        warnings.simplefilter("error")
        render_price_chart_sync(_spec(material=long_name))
        render_price_chart_sync(_spec(head="▼ GIẢM LỚN", level="large"))
    missing = [r.getMessage() for r in caplog.records if "missing" in r.getMessage().lower()]
    assert missing == []


def test_same_input_same_hash() -> None:
    a = hashlib.sha256(render_price_chart_sync(_spec())).hexdigest()
    b = hashlib.sha256(render_price_chart_sync(_spec())).hexdigest()
    assert a == b


def test_png_has_no_timestamp_metadata() -> None:
    info = _decode(render_price_chart_sync(_spec())).info
    assert "Software" not in info
    assert "Creation Time" not in info


async def test_five_concurrent_renders() -> None:
    specs = [_spec(material=f"Vật tư {i}", last=8000 + i * 10) for i in range(5)]
    results = await asyncio.gather(*(render_price_chart(s) for s in specs))
    assert len(results) == 5
    assert all(_decode(r).size == (900, 500) for r in results)
    assert results[0] == render_price_chart_sync(specs[0])
    assert len({hashlib.sha256(r).hexdigest() for r in results}) == 5


def test_decimal_values_are_accepted() -> None:
    spec = replace(
        _spec(),
        points=[(d, Decimal(v)) for d, v in _spec().points],
        ref_min=Decimal("7720.50"),
        ref_max=Decimal("7900"),
    )
    assert _decode(render_price_chart_sync(spec)).size == (900, 500)


def test_single_point() -> None:
    spec = replace(
        _spec(),
        points=[(date(2026, 10, 2), 8150)],
        ref_min=8150,
        ref_max=8150,
    )
    assert _decode(render_price_chart_sync(spec)).size == (900, 500)


def test_all_prices_equal_flat_axis() -> None:
    spec = replace(
        _spec(),
        points=[(d, 8000) for d, _ in _spec().points],
        ref_min=8000,
        ref_max=8000,
    )
    assert _decode(render_price_chart_sync(spec)).size == (900, 500)


def test_zero_prices_do_not_fail() -> None:
    spec = replace(_spec(), points=[(d, 0) for d, _ in _spec().points], ref_min=0, ref_max=0)
    assert _decode(render_price_chart_sync(spec)).size == (900, 500)


def test_very_long_material_name_is_truncated_with_ellipsis() -> None:
    short = render_price_chart_sync(_spec())
    long_png = render_price_chart_sync(_spec(material="Vật tư tên rất dài " * 20))
    img = _decode(long_png)
    assert img.size == (900, 500)
    assert short != long_png
    # Tieu de khong tran ra mep phai: cot pixel sat mep phai (vung tieu de) van la nen.
    rgb = img.convert("RGB")
    assert all(rgb.getpixel((895, y)) == (252, 252, 251) for y in range(20, 60))


def test_new_point_on_weekend_and_first_day() -> None:
    sat = date(2026, 10, 3)
    spec = replace(
        _spec(),
        points=[*_spec().points, (sat, 8200)],
        new_point_date=sat,
    )
    assert _decode(render_price_chart_sync(spec)).size == (900, 500)


def test_new_point_not_last_point() -> None:
    spec = replace(_spec(), new_point_date=date(2026, 9, 28))
    assert _decode(render_price_chart_sync(spec)).size == (900, 500)


def test_level_band_color_differs_per_level() -> None:
    pixels: dict[str, tuple[int, int, int]] = {}
    hashes: set[str] = set()
    for level in ("light", "medium", "large"):
        png = render_price_chart_sync(_spec(level=level))
        hashes.add(hashlib.sha256(png).hexdigest())
        px = _decode(png).convert("RGB").getpixel((450, 3))
        assert isinstance(px, tuple)
        pixels[level] = (px[0], px[1], px[2])
    assert len(set(pixels.values())) == 3
    assert len(hashes) == 3
    for level, rgb in pixels.items():
        expected = LEVEL_COLORS[level].lstrip("#")
        assert rgb == tuple(int(expected[i : i + 2], 16) for i in (0, 2, 4))


def test_export_sample_images_for_eyeballing(tmp_path: Path) -> None:
    weekend_points = [(d, v) for d, v in _spec().points if d != date(2026, 9, 28)]
    cases: dict[str, ChartSpec] = {
        "1_tang_trung_binh": _spec(),
        "2_giam_lon": replace(
            _spec(head="▼ GIẢM LỚN", level="large", last=7200),
            points=[*_spec().points[:-1], (date(2026, 10, 2), 7200)],
            last_label="7,200  (-6.74%)",
        ),
        "3_nhe": _spec(head="▲ TĂNG NHẸ", level="light", last=7950),
        "4_cuoi_tuan": replace(
            _spec(),
            points=[*weekend_points, (date(2026, 10, 3), 8200)],
            new_point_date=date(2026, 10, 3),
            last_label="8,200  (+6.22%)",
        ),
        "5_ten_dai": _spec(
            material="Bột cá Peru nhập khẩu loại 1 đạt chuẩn protein 65% đóng bao 50kg Ơ Ư"
        ),
    }
    for name, spec in cases.items():
        path = tmp_path / f"{name}.png"
        path.write_bytes(render_price_chart_sync(spec))
        assert _decode(path.read_bytes()).size == (900, 500)
    assert len(list(tmp_path.glob("*.png"))) == 5
