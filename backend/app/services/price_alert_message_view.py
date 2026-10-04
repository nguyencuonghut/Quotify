from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Material,
    PriceAlertEvent,
    PriceAlertMessage,
    PriceAlertMessageEvent,
    PriceAlertSetting,
    QuoteVersion,
)
from app.services.daily_min_series import get_daily_min_series
from app.services.price_alert_chart import ChartSpec
from app.services.price_alert_formatter import (
    EventView,
    MessageView,
    chart_title,
    format_percent,
    format_price_short,
    top_event,
)
from app.services.working_days import reference_window


async def load_message_view(
    session: AsyncSession,
    message_id: UUID,
    settings: PriceAlertSetting,
) -> MessageView | None:
    """Dựng dữ liệu hiển thị của một tin từ các sự kiện đã lưu (không tính lại gì từ giá hiện tại).

    Trả `None` nếu tin không phải tin biến động hoặc không còn sự kiện nào gắn kèm.
    """
    message = await session.get(PriceAlertMessage, message_id)
    if message is None or message.kind != "change" or message.material_id is None:
        return None
    rows = (
        await session.execute(
            select(PriceAlertEvent, QuoteVersion.quote_id)
            .join(PriceAlertMessageEvent, PriceAlertMessageEvent.event_id == PriceAlertEvent.id)
            .join(QuoteVersion, QuoteVersion.id == PriceAlertEvent.quote_version_id)
            .where(PriceAlertMessageEvent.message_id == message_id)
            .order_by(PriceAlertEvent.delivery_month),
        )
    ).all()
    if not rows:
        return None
    material_name = (
        await session.execute(select(Material.name).where(Material.id == message.material_id))
    ).scalar_one()
    events = [_event_view(event) for event, _quote_id in rows]
    view = MessageView(
        material_name=material_name,
        events=events,
        quote_id=str(rows[0][1]),
        reference_working_days=settings.reference_working_days,
        warn_percent=settings.anomaly_percent,
    )
    top = top_event(view)
    top_quote = next(
        str(quote_id) for event, quote_id in rows if event.delivery_month == top.delivery_month
    )
    return MessageView(
        material_name=view.material_name,
        events=view.events,
        quote_id=top_quote,
        reference_working_days=view.reference_working_days,
        warn_percent=view.warn_percent,
    )


def _event_view(event: PriceAlertEvent) -> EventView:
    # Sự kiện `kind='change'` luôn có đủ các trường này; thiếu nghĩa là dữ liệu hỏng.
    if (
        event.level is None
        or event.rule is None
        or event.received_date_ref is None
        or event.window_min is None
        or event.window_max is None
        or event.window_min_date is None
        or event.window_max_date is None
    ):
        raise ValueError(f"Sự kiện {event.id} thiếu trường bắt buộc của tin biến động giá.")
    return EventView(
        delivery_month=event.delivery_month,
        direction=event.direction,  # type: ignore[arg-type]
        level=event.level,  # type: ignore[arg-type]
        rule=event.rule,  # type: ignore[arg-type]
        percent_change=event.percent_change,
        price_new=event.price_new,
        price_ref=event.price_ref,
        received_date_new=event.received_date_new,
        received_date_ref=event.received_date_ref,
        window_min=event.window_min,
        window_max=event.window_max,
        window_min_date=event.window_min_date,
        window_max_date=event.window_max_date,
        secondary_rule=event.secondary_rule,  # type: ignore[arg-type]
        secondary_percent=event.secondary_percent,
        secondary_price_ref=event.secondary_price_ref,
        secondary_date_ref=event.secondary_date_ref,
        cnf_price_new=event.cnf_price_new,
        cnf_price_ref=event.cnf_price_ref,
        cnf_date_ref=event.cnf_date_ref,
        prior_alert_price=event.prior_alert_price,
        prior_alert_date=event.prior_alert_date,
        reference_age_days=event.reference_age_days,
    )


CHART_DAYS = 14


async def load_chart_spec(
    session: AsyncSession,
    message_id: UUID,
    view: MessageView,
) -> ChartSpec | None:
    """Dữ liệu vẽ ảnh của kỳ giao hàng có mức cao nhất: daily-min 14 ngày kết thúc ở điểm mới."""
    message = await session.get(PriceAlertMessage, message_id)
    if message is None or message.material_id is None:
        return None
    top = top_event(view)
    series = await get_daily_min_series(
        session,
        material_id=message.material_id,
        delivery_month=top.delivery_month,
        start=top.received_date_new - timedelta(days=CHART_DAYS - 1),
        end=top.received_date_new,
    )
    if not series:
        return None
    window = view.reference_working_days
    window_start, window_end = reference_window(top.received_date_new, window)
    return ChartSpec(
        title=chart_title(view),
        subtitle=(
            f"Giá thấp nhất hôm nay: {format_price_short(top.price_new)} VNĐ/KG · "
            f"Kỳ giao hàng {top.delivery_month:%m/%Y}"
        ),
        level=top.level,
        points=[(point.received_date, point.price) for point in series],
        new_point_date=top.received_date_new,
        window_start=window_start,
        window_end=window_end,
        ref_min=top.window_min,
        ref_max=top.window_max,
        last_label=f"{format_price_short(top.price_new)}  ({format_percent(top.percent_change)})",
        ref_min_label=f"Thấp nhất: {format_price_short(top.window_min)}",
        ref_max_label=f"Cao nhất: {format_price_short(top.window_max)}",
        zone_caption=f"Vùng tham chiếu {window} ngày làm việc",
    )
