from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import has_permission
from app.auth.service import AuthService
from app.integrations.telegram import TELEGRAM_MESSAGE_MAX_LENGTH, escape_html
from app.models import Material, PriceAlertEvent, PriceAlertMessage, TelegramAccount, User
from app.services.audit_log import AuditLogContext, AuditLogService
from app.services.price_alert_anomaly_formatter import (
    AnomalyPointView,
    format_anomaly_card,
    format_anomaly_cluster,
    format_anomaly_expired,
    format_anomaly_resolution,
)
from app.services.price_alert_message_view import load_anomaly_points

REVIEW_PERMISSION = "price_alerts.receive_all"
Action = Literal["ok", "no"]
_STATUS_BY_ACTION = {"ok": "accepted", "no": "rejected"}


class ReviewOutcome(StrEnum):
    REVIEWED = "reviewed"
    ALREADY_REVIEWED = "already_reviewed"
    NOT_FOUND = "not_found"
    FORBIDDEN = "forbidden"


@dataclass(frozen=True, slots=True)
class ReviewResult:
    outcome: ReviewOutcome
    status: str | None = None
    reviewer_name: str | None = None
    reviewed_at: datetime | None = None


class PriceAlertReviewService:
    """Trưởng phòng duyệt một thẻ giá bất thường. Chỉ `flush`; người gọi `commit`.

    Cập nhật nguyên tử (L23): chỉ thẻ còn `pending` mới đổi được, nên hai người bấm cùng lúc
    thì đúng một người thắng. Điểm đã gắn vào thẻ đi theo quyết định của thẻ.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def review(
        self,
        event_id: UUID,
        action: Action,
        *,
        actor_user_id: UUID,
        now: datetime,
        request_id: str | None = None,
    ) -> ReviewResult:
        actor = await AuthService(self.session).get_active_user(user_id=actor_user_id)
        if actor is None or not has_permission(actor, REVIEW_PERMISSION):
            return ReviewResult(ReviewOutcome.FORBIDDEN)

        status = _STATUS_BY_ACTION[action]
        won = (
            await self.session.execute(
                update(PriceAlertEvent)
                .where(
                    PriceAlertEvent.id == event_id,
                    PriceAlertEvent.kind == "anomaly",
                    PriceAlertEvent.review_status == "pending",
                    PriceAlertEvent.attached_to_event_id.is_(None),
                )
                .values(review_status=status, reviewed_by_id=actor.id, reviewed_at=now)
                .returning(PriceAlertEvent.material_id),
            )
        ).scalar_one_or_none()
        if won is None:
            return await self._already(event_id)

        await self.session.execute(
            update(PriceAlertEvent)
            .where(
                PriceAlertEvent.attached_to_event_id == event_id,
                PriceAlertEvent.review_status == "pending",
            )
            .values(review_status=status, reviewed_by_id=actor.id, reviewed_at=now),
        )
        await AuditLogService(self.session).log_event(
            action="price_alerts.anomaly_reviewed",
            entity_type="price_alert_event",
            context=AuditLogContext(
                actor_user_id=actor.id,
                entity_id=str(event_id),
                metadata_json={
                    "status": status,
                    "material_id": str(won),
                    **await self._material_labels(won),
                },
                request_id=request_id,
            ),
        )
        return ReviewResult(ReviewOutcome.REVIEWED, status, actor.full_name, now)

    async def _material_labels(self, material_id: UUID) -> dict[str, str]:
        """Mã và tên vật tư cho nhật ký audit (người đọc cần biết vật tư nào, không chỉ id thẻ)."""
        row = (
            await self.session.execute(
                select(Material.code, Material.name).where(Material.id == material_id)
            )
        ).first()
        return {} if row is None else {"material_code": row[0], "material_name": row[1]}

    async def _already(self, event_id: UUID) -> ReviewResult:
        row = (
            await self.session.execute(
                select(
                    PriceAlertEvent.review_status,
                    PriceAlertEvent.reviewed_at,
                    User.full_name,
                    PriceAlertEvent.attached_to_event_id,
                )
                .outerjoin(User, User.id == PriceAlertEvent.reviewed_by_id)
                .where(PriceAlertEvent.id == event_id, PriceAlertEvent.kind == "anomaly"),
            )
        ).first()
        if row is None:
            return ReviewResult(ReviewOutcome.NOT_FOUND)
        if row[3] is not None:
            # Điểm đã gắn vào thẻ khác: chỉ duyệt được qua thẻ gốc, không có gì để báo "đã xử lý".
            return ReviewResult(ReviewOutcome.NOT_FOUND)
        return ReviewResult(ReviewOutcome.ALREADY_REVIEWED, row[0], row[2], row[1])


async def compose_review_edit(
    session: AsyncSession,
    *,
    chat_id: int,
    message_id: int,
    base_url: str,
) -> tuple[str, dict[str, Any] | None] | None:
    """Nội dung mới của tin chứa nút sau khi duyệt (L24); `None` nếu không tìm thấy tin.

    Điểm đã duyệt thành một dòng kết quả (kèm người duyệt và giờ); điểm còn chờ giữ thẻ và nút.
    """
    message = (
        await session.execute(
            select(PriceAlertMessage)
            .join(TelegramAccount, TelegramAccount.id == PriceAlertMessage.telegram_account_id)
            .where(
                PriceAlertMessage.telegram_message_id == message_id,
                TelegramAccount.chat_id == chat_id,
                PriceAlertMessage.kind.in_(("anomaly", "digest")),
                PriceAlertMessage.audience.is_not(None),
            )
            .order_by(PriceAlertMessage.sequence_number.desc())
            .limit(1),
        )
    ).scalar_one_or_none()
    if message is None:
        return None
    points = await load_anomaly_points(session, message.id)
    if not points:
        return None
    states = {
        str(row[0]): row[1:]
        for row in (
            await session.execute(
                select(
                    PriceAlertEvent.id,
                    PriceAlertEvent.review_status,
                    PriceAlertEvent.reviewed_at,
                    User.full_name,
                )
                .outerjoin(User, User.id == PriceAlertEvent.reviewed_by_id)
                .where(PriceAlertEvent.id.in_([UUID(point.event_id) for _, point in points])),
            )
        ).all()
    }
    resolved: list[str] = []
    pending: list[tuple[str, AnomalyPointView]] = []
    for name, point in points:
        status, reviewed_at, reviewer = states.get(point.event_id, ("pending", None, None))
        if status in ("accepted", "rejected") and reviewed_at is not None:
            resolved.append(
                f"{escape_html(name)} · {point.delivery_month:%m/%Y} · {point.price:,.0f}\n"
                + format_anomaly_resolution(status, reviewer or "người dùng", reviewed_at)
            )
        elif status == "expired":
            resolved.append(
                f"{escape_html(name)} · {point.delivery_month:%m/%Y}\n{format_anomaly_expired()}"
            )
        else:
            pending.append((name, point))
    blocks = list(resolved)
    markup: dict[str, Any] | None = None
    if pending:
        if message.kind == "anomaly":
            text, markup = format_anomaly_card(
                pending[0][0], [p for _, p in pending], base_url=base_url, with_buttons=True
            )
        else:
            text, markup = format_anomaly_cluster(pending, base_url=base_url, with_buttons=True)
        blocks.append(text)
    text = "\n\n".join(blocks)
    if len(text) > TELEGRAM_MESSAGE_MAX_LENGTH:
        text = text[: TELEGRAM_MESSAGE_MAX_LENGTH - 1].rstrip() + "…"
    return text, markup
