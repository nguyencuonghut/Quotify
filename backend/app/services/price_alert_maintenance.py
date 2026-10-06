from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.integrations.telegram import TelegramClient
from app.models import (
    PriceAlertEvent,
    PriceAlertMessage,
    PriceAlertMessageEvent,
    PriceAlertScannedVersion,
    PriceAlertScanRun,
    PriceAlertSetting,
    Quote,
    QuoteVersion,
    TelegramAccount,
)
from app.services.price_alert_anomaly_messages import AnomalyFlag, build_messages_for_flags
from app.services.price_alert_candidates import BUSINESS_TIMEZONE
from app.services.price_alert_review_service import compose_review_edit
from app.services.working_days import is_working_day, working_days_between

logger = logging.getLogger(__name__)

REMIND_AFTER_WORKING_DAYS = 2
EXPIRE_AFTER_WORKING_DAYS = 7
RETENTION = timedelta(days=180)


@dataclass(slots=True)
class MaintenanceResult:
    reminded: int = 0
    reminder_messages: int = 0
    expired_event_ids: list[UUID] = field(default_factory=list)


class PriceAlertMaintenanceService:
    """Nhắc, hết hạn thẻ giá bất thường và dọn dữ liệu cũ. Chỉ `flush`; người gọi `commit`."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        seed_user_id: UUID | None,
        pilot_emails: frozenset[str] = frozenset(),
    ) -> None:
        self.session = session
        self.seed_user_id = seed_user_id
        self.pilot_emails = pilot_emails

    async def remind_and_expire(
        self,
        *,
        now: datetime,
        settings: PriceAlertSetting,
    ) -> MaintenanceResult:
        """Thẻ `pending` quá 2 ngày làm việc được nhắc một lần; quá 7 ngày làm việc thì hết hạn.

        Hết hạn không mở lại điểm: dòng vẫn bị loại khỏi tính toán (`expired` không phải
        `accepted`). Phiếu đã hủy không được nhắc nhưng vẫn hết hạn để thẻ không treo mãi.
        """
        today = now.astimezone(BUSINESS_TIMEZONE).date()
        rows = (
            await self.session.execute(
                select(
                    PriceAlertEvent.id,
                    PriceAlertEvent.material_id,
                    PriceAlertEvent.direction,
                    PriceAlertEvent.created_at,
                    PriceAlertEvent.reminded_at,
                    Quote.cancelled_at,
                )
                .join(QuoteVersion, QuoteVersion.id == PriceAlertEvent.quote_version_id)
                .join(Quote, Quote.id == QuoteVersion.quote_id)
                .where(
                    PriceAlertEvent.kind == "anomaly",
                    PriceAlertEvent.review_status == "pending",
                    PriceAlertEvent.attached_to_event_id.is_(None),
                )
                .order_by(PriceAlertEvent.material_id, PriceAlertEvent.sequence_number),
            )
        ).all()

        result = MaintenanceResult()
        to_remind: list[AnomalyFlag] = []
        for event_id, material_id, direction, created_at, reminded_at, cancelled_at in rows:
            age = working_days_between(created_at.astimezone(BUSINESS_TIMEZONE).date(), today)
            if age >= EXPIRE_AFTER_WORKING_DAYS:
                result.expired_event_ids.append(event_id)
            elif (
                age >= REMIND_AFTER_WORKING_DAYS
                and reminded_at is None
                and cancelled_at is None
                and is_working_day(today)
            ):
                to_remind.append(AnomalyFlag(event_id, material_id, direction, None))

        if result.expired_event_ids:
            await self._expire(result.expired_event_ids)
        if to_remind:
            await self.session.execute(
                update(PriceAlertEvent)
                .where(
                    PriceAlertEvent.id.in_([f.event_id for f in to_remind]),
                    PriceAlertEvent.reminded_at.is_(None),
                )
                .values(reminded_at=now),
            )
            result.reminded = len(to_remind)
            result.reminder_messages, _ = await build_messages_for_flags(
                self.session,
                to_remind,
                scan_run_id=None,
                now=now,
                settings=settings,
                seed_user_id=self.seed_user_id,
                pilot_emails=self.pilot_emails,
            )
        return result

    async def _expire(self, event_ids: Sequence[UUID]) -> None:
        await self.session.execute(
            update(PriceAlertEvent)
            .where(
                (PriceAlertEvent.id.in_(event_ids))
                | (PriceAlertEvent.attached_to_event_id.in_(event_ids)),
                PriceAlertEvent.review_status == "pending",
            )
            .values(review_status="expired"),
        )

    async def cleanup(self, *, now: datetime) -> dict[str, int]:
        """L19: xóa sự kiện, tin, lần quét, version đã quét cũ hơn 180 ngày.

        Không bao giờ xóa thẻ còn `pending` hay tin chưa gửi xong (`pending`, `sending`).
        """
        cutoff = now - RETENTION
        deleted: dict[str, int] = {}
        deleted["messages"] = await self._delete(
            delete(PriceAlertMessage).where(
                PriceAlertMessage.created_at < cutoff,
                PriceAlertMessage.status.not_in(("pending", "sending")),
            )
        )
        deleted["events"] = await self._delete(
            delete(PriceAlertEvent).where(
                PriceAlertEvent.created_at < cutoff,
                (PriceAlertEvent.review_status.is_(None))
                | (PriceAlertEvent.review_status != "pending"),
                PriceAlertEvent.id.not_in(
                    select(PriceAlertMessageEvent.event_id)
                    .join(
                        PriceAlertMessage,
                        PriceAlertMessage.id == PriceAlertMessageEvent.message_id,
                    )
                    .where(PriceAlertMessage.status.in_(("pending", "sending")))
                ),
            )
        )
        deleted["scanned_versions"] = await self._delete(
            delete(PriceAlertScannedVersion).where(PriceAlertScannedVersion.scanned_at < cutoff)
        )
        deleted["scan_runs"] = await self._delete(
            delete(PriceAlertScanRun).where(PriceAlertScanRun.started_at < cutoff)
        )
        return deleted

    async def _delete(self, statement: object) -> int:
        result = await self.session.execute(statement)  # type: ignore[call-overload]
        return int(getattr(result, "rowcount", 0) or 0)


async def edit_expired_cards(
    session_factory: async_sessionmaker[AsyncSession],
    client: TelegramClient,
    event_ids: Sequence[UUID],
    *,
    base_url: str,
) -> int:
    """Sửa các tin đã gửi của thẻ vừa hết hạn để bỏ nút (L24). Lỗi sửa chỉ được ghi nhận."""
    if not event_ids:
        return 0
    async with session_factory() as session:
        targets = (
            await session.execute(
                select(TelegramAccount.chat_id, PriceAlertMessage.telegram_message_id)
                .join(TelegramAccount, TelegramAccount.id == PriceAlertMessage.telegram_account_id)
                .join(
                    PriceAlertMessageEvent,
                    PriceAlertMessageEvent.message_id == PriceAlertMessage.id,
                )
                .where(
                    PriceAlertMessageEvent.event_id.in_(event_ids),
                    PriceAlertMessage.status == "sent",
                    PriceAlertMessage.audience.in_(("manager", "admin")),
                    PriceAlertMessage.telegram_message_id.is_not(None),
                )
                .distinct()
            )
        ).all()
        edits = []
        for chat_id, message_id in targets:
            composed = await compose_review_edit(
                session, chat_id=chat_id, message_id=message_id, base_url=base_url
            )
            if composed is not None:
                edits.append((chat_id, message_id, composed))
    edited = 0
    for chat_id, message_id, (text, markup) in edits:
        try:
            await client.edit_message_text(chat_id, message_id, text, reply_markup=markup)
            edited += 1
        except Exception as exc:
            logger.warning("price_alert.expire_edit_failed error=%s", type(exc).__name__)
    return edited
