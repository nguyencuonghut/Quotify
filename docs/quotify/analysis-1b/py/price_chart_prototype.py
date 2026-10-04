"""Thu nghiem kha thi: ve bieu do gia 14 ngay bang matplotlib OO API (khong pyplot)."""

from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import matplotlib
from matplotlib import dates as mdates
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from matplotlib.ticker import FuncFormatter

# Font DejaVu Sans di kem matplotlib (khong phu thuoc font he thong).
_FONT_DIR = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
FONT = FontProperties(fname=str(_FONT_DIR / "DejaVuSans.ttf"))
FONT_BOLD = FontProperties(fname=str(_FONT_DIR / "DejaVuSans-Bold.ttf"))

# Token mau (lay tu skill dataviz: bang mau trang thai + muc ink)
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e1e0d9"
SERIES = "#2a78d6"
LEVEL_COLORS = {"yellow": "#fab219", "orange": "#ec835a", "red": "#d03b3b"}
ZONE_TINT = "#2a78d6"


@dataclass(frozen=True)
class ChartSpec:
    title: str
    subtitle: str
    points: list[tuple[date, float]]  # daily-min
    window_start: date  # vung tham chieu: ngay dau
    window_end: date  # vung tham chieu: ngay cuoi
    ref_min: float
    ref_max: float
    level: str  # yellow | orange | red
    last_label: str  # vi du "8,150.00  (+5.57%)"
    ref_min_label: str
    ref_max_label: str


def fmt_money(v: float) -> str:
    return f"{v:,.2f}"


def render_png(spec: ChartSpec, width_px: int = 900, height_px: int = 500, dpi: int = 100) -> bytes:
    fig = Figure(figsize=(width_px / dpi, height_px / dpi), dpi=dpi, facecolor=SURFACE)
    FigureCanvasAgg(fig)
    ax = fig.add_axes((0.105, 0.09, 0.87, 0.71), facecolor=SURFACE)

    xs = [mdates.date2num(d) for d, _ in spec.points]
    ys = [p for _, p in spec.points]
    last_d, last_p = spec.points[-1]

    # vung tham chieu to sang (7 ngay lam viec, khong gom diem moi)
    x0 = mdates.date2num(spec.window_start) - 0.5
    x1 = mdates.date2num(spec.window_end) + 0.5
    ax.axvspan(x0, x1, color=ZONE_TINT, alpha=0.08, linewidth=0, zorder=0)
    ax.text(
        (x0 + x1) / 2,
        1.01,
        "Vùng tham chiếu 7 ngày làm việc",
        transform=ax.get_xaxis_transform(),
        ha="center",
        va="bottom",
        fontproperties=FONT,
        fontsize=9,
        color=INK2,
    )

    # hai duong ngang min/max (keo toi diem moi de thay bi vuot)
    xr_end = mdates.date2num(last_d) + 0.4
    for val, lab, va, dy in (
        (spec.ref_max, spec.ref_max_label, "bottom", 0),
        (spec.ref_min, spec.ref_min_label, "top", 0),
    ):
        ax.hlines(val, x0, xr_end, colors=INK2, linestyles=(0, (4, 3)), linewidth=1.0, zorder=2)
        ax.annotate(
            lab,
            (x0 + 3.3, val),
            xytext=(0, 4 if va == "bottom" else -4),
            textcoords="offset points",
            ha="left",
            va=va,
            fontproperties=FONT,
            fontsize=9,
            color=INK,
        )

    # duong daily-min
    ax.plot(xs, ys, color=SERIES, linewidth=2.0, marker="o", markersize=5, zorder=3,
            markerfacecolor=SERIES, markeredgecolor=SURFACE, markeredgewidth=1.0)

    # diem cuoi to mau theo muc, vien toi de doc duoc khi mau vang nhat tren nen sang
    ax.scatter([xs[-1]], [last_p], s=120, color=LEVEL_COLORS[spec.level],
               edgecolors=INK, linewidths=1.2, zorder=5)
    ax.annotate(
        spec.last_label,
        (xs[-1], last_p),
        xytext=(-12, 2),
        textcoords="offset points",
        ha="right",
        va="bottom",
        fontproperties=FONT_BOLD,
        fontsize=11,
        color=INK,
    )

    # truc
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    ax.set_xlim(mdates.date2num(spec.points[-1][0] - timedelta(days=13)) - 0.5, xs[-1] + 0.6)
    lo = min(ys + [spec.ref_min]) - 60
    hi = max(ys + [spec.ref_max]) + 80
    ax.set_ylim(lo, hi)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:,.2f}"))
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8.5, length=3)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_fontproperties(FONT)
        lbl.set_fontsize(8.5)
    ax.set_ylabel("VNĐ/KG", fontproperties=FONT, fontsize=9, color=INK2)

    fig.text(0.105, 0.945, spec.title, fontproperties=FONT_BOLD, fontsize=15, color=INK,
             ha="left", va="center")
    fig.text(0.105, 0.885, spec.subtitle, fontproperties=FONT, fontsize=9.5, color=INK2,
             ha="left", va="center")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor=SURFACE)
    return buf.getvalue()


async def render_png_async(spec: ChartSpec) -> bytes:
    return await asyncio.to_thread(render_png, spec)


def sample_spec(
    material: str = "Ngô hạt",
    level_text: str = "TĂNG TRUNG BÌNH",
    prefix: str = "▲",
    level: str = "orange",
    shift: float = 0.0,
    last: float = 8150.0,
) -> ChartSpec:
    d0 = date(2026, 9, 19)
    # chi co ngay lam viec (T2-T6) co bao gia, cuoi tuan khong co
    raw = {
        date(2026, 9, 21): 7950, date(2026, 9, 22): 7880, date(2026, 9, 23): 7900,
        date(2026, 9, 24): 7790, date(2026, 9, 25): 7720, date(2026, 9, 28): 7760,
        date(2026, 9, 29): 7830, date(2026, 9, 30): 7800, date(2026, 10, 1): 7840,
        date(2026, 10, 2): last,
    }
    pts = sorted((d, v + (shift if d != date(2026, 10, 2) else 0)) for d, v in raw.items())
    assert (pts[-1][0] - d0) == timedelta(days=13)
    in_win = [v for d, v in pts if date(2026, 9, 23) <= d <= date(2026, 10, 1)]
    ref_min, ref_max = min(in_win), max(in_win)
    pct = (last / ref_min - 1) * 100
    title = f"{prefix} {level_text} · {material}".strip()
    return ChartSpec(
        title=title,
        subtitle="Giá thấp nhất hôm nay: 8,150.00 VNĐ/KG · Kỳ giao hàng 12/2026 · "
                 "Đường dẫn ngắn ơ ư ằ ẵ ế ộ",
        points=pts,
        window_start=date(2026, 9, 23),
        window_end=date(2026, 10, 1),
        ref_min=ref_min,
        ref_max=ref_max,
        level=level,
        last_label=f"{fmt_money(last)}  (+{pct:.2f}%)",
        ref_min_label=f"Thấp nhất: {fmt_money(ref_min)}",
        ref_max_label=f"Cao nhất: {fmt_money(ref_max)}",
    )
