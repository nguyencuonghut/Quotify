"""Vẽ biểu đồ giá 14 ngày (PNG 900x500) cho cảnh báo biến động giá Telegram.

Quyết định (L11, plan Telegram 1B):
- matplotlib API hướng đối tượng (``Figure`` + ``FigureCanvasAgg``), không import pyplot.
- Trục X là chỉ số ngày tự tính, không dùng ``matplotlib.dates``.
- Font DejaVu Sans nhúng theo đường dẫn trong gói matplotlib, không phụ thuộc font hệ thống.
- Không emoji trong ảnh (chỉ dùng các ký tự có trong DejaVu như ▲ ▼).
- ``render_price_chart_sync`` xác định: cùng đầu vào cho cùng PNG (metadata không chứa thời gian).
"""

from __future__ import annotations

import asyncio
import io
import os
import tempfile
import threading
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal

# Thư mục cache font/cấu hình của matplotlib phải ghi được (container chạy user không có HOME).
# Phải đặt TRƯỚC khi import matplotlib; setdefault để không đè giá trị do môi trường cấu hình.
os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "mpl"))

import matplotlib  # noqa: E402
from matplotlib.backends.backend_agg import FigureCanvasAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

ChartLevel = Literal["light", "medium", "large"]

CHART_WIDTH_PX = 900
CHART_HEIGHT_PX = 500
_DPI = 100
_WINDOW_DAYS = 14

_FONT_DIR = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
_FONT = FontProperties(fname=str(_FONT_DIR / "DejaVuSans.ttf"))
_FONT_BOLD = FontProperties(fname=str(_FONT_DIR / "DejaVuSans-Bold.ttf"))

_SURFACE = "#fcfcfb"
_INK = "#0b0b0b"
_INK2 = "#52514e"
_INK3 = "#9a9893"
_GRID = "#e1e0d9"
_SERIES = "#2a78d6"
LEVEL_COLORS: dict[str, str] = {
    "light": "#fab219",  # vàng
    "medium": "#ec835a",  # cam
    "large": "#d03b3b",  # đỏ
}

# Các FT2Font được matplotlib cache dùng chung giữa các luồng (``get_font`` có lru_cache) và
# không an toàn khi vẽ đồng thời, nên mỗi lần vẽ được tuần tự hóa bằng khóa này. Một ảnh
# mất khoảng 0,1 giây nên 5 ảnh liên tiếp vẫn chấp nhận được.
_RENDER_LOCK = threading.Lock()


@dataclass(frozen=True)
class ChartSpec:
    """Đầu vào vẽ biểu đồ; toàn bộ chữ hiển thị do người gọi soạn sẵn."""

    title: str  # ví dụ "▲ TĂNG TRUNG BÌNH · Ngô hạt"
    subtitle: str
    level: ChartLevel  # light -> vàng, medium -> cam, large -> đỏ
    points: Sequence[tuple[date, Decimal | float]]  # daily-min 14 ngày
    new_point_date: date
    window_start: date
    window_end: date
    ref_min: Decimal | float
    ref_max: Decimal | float
    last_label: str  # ví dụ "8,150  (+5.57%)"
    ref_min_label: str
    ref_max_label: str
    unit: str = "VNĐ/KG"
    zone_caption: str = "Vùng tham chiếu 7 ngày làm việc"


def _fit(
    fig: Figure,
    y: float,
    text: str,
    fp: FontProperties,
    size: float,
    max_px: float,
    color: str,
) -> None:
    """Vẽ chữ ở mép trái, cắt bớt và thêm '…' nếu rộng hơn ``max_px``."""
    artist = fig.text(
        0.105, y, text, fontproperties=fp, fontsize=size, color=color, ha="left", va="center"
    )
    renderer = FigureCanvasAgg(fig).get_renderer()  # type: ignore[no-untyped-call]
    shown = text
    while len(shown) > 1 and artist.get_window_extent(renderer).width > max_px:
        shown = shown[:-1]
        artist.set_text(shown.rstrip() + "…")


def _fmt_tick(value: float, step: float) -> str:
    return f"{value:,.0f}" if step >= 1 else f"{value:,.2f}"


def _render(spec: ChartSpec) -> bytes:
    pts = sorted((d, float(v)) for d, v in spec.points)
    ref_min, ref_max = float(spec.ref_min), float(spec.ref_max)
    end = max(spec.new_point_date, pts[-1][0]) if pts else spec.new_point_date
    start = min(end - timedelta(days=_WINDOW_DAYS - 1), pts[0][0]) if pts else end
    span_days = (end - start).days

    def xi(d: date) -> int:
        return (d - start).days

    xs = [xi(d) for d, _ in pts]
    ys = [v for _, v in pts]

    fig = Figure(
        figsize=(CHART_WIDTH_PX / _DPI, CHART_HEIGHT_PX / _DPI), dpi=_DPI, facecolor=_SURFACE
    )
    FigureCanvasAgg(fig)
    ax = fig.add_axes((0.105, 0.10, 0.87, 0.68), facecolor=_SURFACE)

    # Dải màu theo mức ở mép trên ảnh.
    fig.add_artist(
        Rectangle(
            (0, 0.98),
            1,
            0.02,
            transform=fig.transFigure,
            facecolor=LEVEL_COLORS[spec.level],
            edgecolor="none",
        )
    )

    x_lo, x_hi = -0.6, span_days + 0.6
    ax.set_xlim(x_lo, x_hi)

    # Trục Y: đệm để trục không phẳng khi giá bằng nhau / chỉ có một điểm.
    vals = [*ys, ref_min, ref_max]
    v_lo, v_hi = min(vals), max(vals)
    pad = (v_hi - v_lo) * 0.18
    if pad <= 0:
        pad = max(abs(v_hi) * 0.02, 1.0)
    y_lo, y_hi = v_lo - pad, v_hi + pad
    ax.set_ylim(y_lo, y_hi)
    y_ticks = [float(t) for t in MaxNLocator(nbins=6).tick_values(y_lo, y_hi)]
    y_ticks = [t for t in y_ticks if y_lo <= t <= y_hi]
    step = (y_ticks[1] - y_ticks[0]) if len(y_ticks) > 1 else 1.0
    ax.set_yticks(y_ticks)
    ax.set_yticklabels([_fmt_tick(t, step) for t in y_ticks], fontproperties=_FONT, fontsize=8.5)

    # Trục X: mỗi ngày một nhãn DD/MM (thưa bớt nếu cửa sổ dài); cuối tuần nhạt màu hơn.
    every = 1 if span_days <= 20 else 2
    x_ticks = list(range(0, span_days + 1, every))
    ticks_dates = [start + timedelta(days=i) for i in x_ticks]
    ax.set_xticks(x_ticks)
    ax.set_xticklabels(
        [f"{d.day:02d}/{d.month:02d}" for d in ticks_dates], fontproperties=_FONT, fontsize=8.5
    )
    for tick_label, d in zip(ax.get_xticklabels(), ticks_dates, strict=True):
        tick_label.set_color(_INK3 if d.weekday() >= 5 else _INK2)
    ax.tick_params(axis="y", colors=_INK2, length=3)
    ax.tick_params(axis="x", length=3, colors=_INK2)

    # Vùng tham chiếu.
    z0 = max(xi(spec.window_start) - 0.5, x_lo)
    z1 = min(xi(spec.window_end) + 0.5, x_hi)
    ax.axvspan(z0, z1, color=_SERIES, alpha=0.08, linewidth=0, zorder=0)
    ax.text(
        (z0 + z1) / 2,
        1.012,
        spec.zone_caption,
        transform=ax.get_xaxis_transform(),
        ha="center",
        va="bottom",
        fontproperties=_FONT,
        fontsize=9,
        color=_INK2,
    )

    # Hai đường min/max kéo tới điểm mới để thấy bị vượt.
    line_end = min(max(xi(spec.new_point_date), z1) + 0.4, x_hi)
    label_bbox = {
        "boxstyle": "round,pad=0.15",
        "facecolor": _SURFACE,
        "edgecolor": "none",
        "alpha": 0.85,
    }
    for val, label, va, dy in (
        (ref_max, spec.ref_max_label, "bottom", 4),
        (ref_min, spec.ref_min_label, "top", -4),
    ):
        ax.hlines(val, z0, line_end, colors=_INK2, linestyles=(0, (4, 3)), linewidth=1.0, zorder=2)
        ax.annotate(
            label,
            (z0 + 0.25, val),
            xytext=(0, dy),
            textcoords="offset points",
            ha="left",
            va=va,
            fontproperties=_FONT,
            fontsize=9,
            color=_INK,
            bbox=label_bbox,
            zorder=4,
        )

    # Đường giá daily-min (cuối tuần không có điểm nên đường nối qua khoảng trống).
    ax.plot(
        xs,
        ys,
        color=_SERIES,
        linewidth=2.0,
        marker="o",
        markersize=5,
        zorder=3,
        markerfacecolor=_SERIES,
        markeredgecolor=_SURFACE,
        markeredgewidth=1.0,
    )

    # Điểm mới: tô màu theo mức, viền tối.
    new_x = xi(spec.new_point_date)
    new_y = next((v for d, v in pts if d == spec.new_point_date), None)
    if new_y is not None:
        ax.scatter(
            [new_x],
            [new_y],
            s=120,
            color=LEVEL_COLORS[spec.level],
            edgecolors=_INK,
            linewidths=1.2,
            zorder=5,
        )
        on_right = new_x > span_days / 2
        ax.annotate(
            spec.last_label,
            (new_x, new_y),
            xytext=(-12 if on_right else 12, 6),
            textcoords="offset points",
            ha="right" if on_right else "left",
            va="bottom",
            fontproperties=_FONT_BOLD,
            fontsize=11,
            color=_INK,
            bbox=label_bbox,
            zorder=6,
        )

    ax.grid(axis="y", color=_GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(_GRID)
    ax.set_ylabel(spec.unit, fontproperties=_FONT, fontsize=9, color=_INK2)

    _fit(fig, 0.925, spec.title, _FONT_BOLD, 15, CHART_WIDTH_PX * 0.87, _INK)
    _fit(fig, 0.865, spec.subtitle, _FONT, 9.5, CHART_WIDTH_PX * 0.87, _INK2)

    buf = io.BytesIO()
    # Software=None: bỏ chunk metadata chứa phiên bản matplotlib; PNG không có thời gian
    # nên cùng đầu vào cho cùng byte.
    fig.savefig(buf, format="png", dpi=_DPI, facecolor=_SURFACE, metadata={"Software": None})
    return buf.getvalue()


def _escape_math(spec: ChartSpec) -> ChartSpec:
    """`$...$` trong tên vật tư sẽ bị matplotlib hiểu là mathtext; thoát dấu đô la."""

    def plain(text: str) -> str:
        return text.replace("$", "\\$")

    return replace(
        spec,
        title=plain(spec.title),
        subtitle=plain(spec.subtitle),
        last_label=plain(spec.last_label),
        ref_min_label=plain(spec.ref_min_label),
        ref_max_label=plain(spec.ref_max_label),
        unit=plain(spec.unit),
        zone_caption=plain(spec.zone_caption),
    )


def render_price_chart_sync(spec: ChartSpec) -> bytes:
    """Vẽ biểu đồ thành PNG 900x500; hàm đồng bộ, xác định và an toàn đa luồng."""
    with _RENDER_LOCK:
        return _render(_escape_math(spec))


async def render_price_chart(spec: ChartSpec) -> bytes:
    """Vẽ biểu đồ trong luồng phụ để không chặn event loop."""
    return await asyncio.to_thread(render_price_chart_sync, spec)
