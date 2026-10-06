from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.dependencies import require_permission
from app.core.config import Settings, get_settings
from app.core.request_id import request_id_context
from app.db.session import get_db_session
from app.integrations.telegram import TelegramClient, TelegramConfigurationError
from app.models import User
from app.schemas.price_alert_anomalies import (
    AnomalyConflictDetail,
    AnomalyItemResponse,
    AnomalyListResponse,
    AnomalyReviewRequest,
    AnomalyReviewResponse,
)
from app.services.price_alert_anomaly_query import list_anomalies
from app.services.price_alert_maintenance import edit_cards_for_events
from app.services.price_alert_review_service import (
    PriceAlertReviewService,
    ReviewOutcome,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/price-alerts/anomalies", tags=["price-alerts"])

_ACTIONS: dict[str, Literal["ok", "no"]] = {"accepted": "ok", "rejected": "no"}


async def get_telegram_client_for_review(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[TelegramClient | None]:
    """Client để sửa tin Telegram sau khi duyệt trên web; `None` khi Telegram chưa cấu hình.

    Dùng lại client của runner webhook nếu đã có; nếu không thì tạo một client riêng cho yêu cầu
    này và đóng khi xong (tránh rò kết nối httpx).
    """
    if not settings.telegram_enabled:
        yield None
        return
    runner = getattr(request.app.state, "telegram_runner", None)
    if runner is not None:
        shared: TelegramClient = runner.client
        yield shared
        return
    try:
        own = TelegramClient.from_settings(settings)
    except TelegramConfigurationError:
        yield None
        return
    try:
        yield own
    finally:
        await own.aclose()


@router.get("", response_model=AnomalyListResponse)
async def list_price_alert_anomalies(
    current_user: Annotated[User, Depends(require_permission("price_alerts.receive_all"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    status_filter: Annotated[
        Literal["pending", "resolved", "all"], Query(alias="status")
    ] = "pending",
    material_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AnomalyListResponse:
    rows, total = await list_anomalies(
        session,
        status=status_filter,
        material_id=material_id,
        limit=limit,
        offset=offset,
        now=datetime.now(UTC),
    )
    return AnomalyListResponse(
        items=[AnomalyItemResponse(**asdict(row)) for row in rows],
        total=total,
    )


@router.post("/{event_id}/review", response_model=AnomalyReviewResponse)
async def review_price_alert_anomaly(
    event_id: UUID,
    payload: AnomalyReviewRequest,
    current_user: Annotated[User, Depends(require_permission("price_alerts.receive_all"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    client: Annotated[TelegramClient | None, Depends(get_telegram_client_for_review)],
) -> AnomalyReviewResponse:
    now = datetime.now(UTC)
    result = await PriceAlertReviewService(session).review(
        event_id,
        _ACTIONS[payload.decision],
        actor_user_id=current_user.id,
        now=now,
        request_id=request_id_context.get() or None,
    )
    match result.outcome:
        case ReviewOutcome.FORBIDDEN:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Bạn không có quyền duyệt giá bất thường."
            )
        case ReviewOutcome.NOT_FOUND:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy điểm giá bất thường.")
        case ReviewOutcome.ALREADY_REVIEWED:
            await session.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=AnomalyConflictDetail(
                    message="Điểm giá này đã được xử lý.",
                    review_status=result.status,
                    reviewed_by_name=result.reviewer_name,
                    reviewed_at=result.reviewed_at,
                ).model_dump(mode="json"),
            )
        case ReviewOutcome.REVIEWED:
            await session.commit()

    if client is not None and session.bind is not None:
        # Cùng engine với yêu cầu này; lỗi sửa tin chỉ được ghi nhận, không làm hỏng việc duyệt.
        try:
            await edit_cards_for_events(
                async_sessionmaker(session.bind, expire_on_commit=False),
                client,
                [event_id],
                base_url=settings.app_public_url,
            )
        except Exception as exc:
            logger.warning("price_alert.review_edit_failed error=%s", type(exc).__name__)
    return AnomalyReviewResponse(
        id=event_id,
        review_status=result.status or payload.decision,
        reviewed_by_name=result.reviewer_name,
        reviewed_at=result.reviewed_at,
    )
