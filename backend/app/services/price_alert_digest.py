from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, literal, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    PriceAlertMessage,
    PriceAlertMessageEvent,
    PriceAlertSetting,
    UserAlertPreference,
)
from app.services.price_alert_candidates import BUSINESS_TIMEZONE
from app.services.price_alert_settings_service import PriceAlertSettingsService

DIGEST_ADVISORY_LOCK_KEY = 7_620_261_006
MAX_AGE_DAYS = 3


@dataclass(slots=True)
class DigestResult:
    digests_created: int = 0
    queued_consumed: int = 0
    stale: int = 0
    skipped: str | None = None


class PriceAlertDigestService:
    """Bản tin tổng hợp hằng ngày cho mức Nhẹ (M1 đến M4). Chỉ `flush`; người gọi `commit`.

    Gom các tin `digest_queued/light` của mỗi người thành một tin `kind='digest'` (`daily`),
    rồi chuyển tin nguồn sang `sent/in_digest` để chống lặp và leo thang cùng ngày vẫn đếm đúng.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run_once(self, *, now: datetime, settings: PriceAlertSetting) -> DigestResult:
        local = now.astimezone(BUSINESS_TIMEZONE)
        today = local.date()
        if local.hour < settings.digest_hour_local:
            return DigestResult(skipped="not_due")
        locked = (
            await self.session.execute(
                select(func.pg_try_advisory_xact_lock(DIGEST_ADVISORY_LOCK_KEY))
            )
        ).scalar_one()
        if not locked:
            return DigestResult(skipped="locked")
        state = await PriceAlertSettingsService(self.session).get_or_create_scan_state(
            for_update=True
        )
        if state.last_digest_local_date == today:
            return DigestResult(skipped="already_sent")

        result = DigestResult()
        result.stale = await self._expire_stale(today)
        queued = (
            await self.session.execute(
                select(
                    PriceAlertMessage.id,
                    PriceAlertMessage.user_id,
                    PriceAlertMessage.telegram_account_id,
                )
                .where(
                    PriceAlertMessage.status == "digest_queued",
                    PriceAlertMessage.status_reason == "light",
                    PriceAlertMessage.kind == "change",
                )
                .order_by(PriceAlertMessage.sequence_number)
            )
        ).all()
        by_user: dict[UUID, list[tuple[UUID, UUID | None]]] = defaultdict(list)
        for message_id, user_id, account_id in queued:
            by_user[user_id].append((message_id, account_id))

        opted_out = await self._opted_out(set(by_user))
        for user_id, items in by_user.items():
            ids = [message_id for message_id, _ in items]
            if user_id in opted_out:
                await self._close(ids, status="suppressed", reason="opted_out")
                continue
            account_id = next((a for _, a in reversed(items) if a is not None), None)
            if account_id is None:
                await self._close(ids, status="suppressed", reason="no_account")
                continue
            digest_id = (
                await self.session.execute(
                    pg_insert(PriceAlertMessage)
                    .values(
                        user_id=user_id,
                        telegram_account_id=account_id,
                        material_id=None,
                        local_date=today,
                        scan_run_id=None,
                        kind="digest",
                        digest_kind="daily",
                        status="pending",
                        created_at=now,
                    )
                    .on_conflict_do_nothing(
                        index_elements=["user_id", "local_date"],
                        index_where=PriceAlertMessage.digest_kind == "daily",
                    )
                    .returning(PriceAlertMessage.id)
                )
            ).scalar_one_or_none()
            if digest_id is None:
                continue
            await self.session.execute(
                pg_insert(PriceAlertMessageEvent).from_select(
                    ["message_id", "event_id"],
                    select(
                        literal(digest_id, PriceAlertMessageEvent.message_id.type),
                        PriceAlertMessageEvent.event_id,
                    )
                    .where(PriceAlertMessageEvent.message_id.in_(ids))
                    .distinct(),
                )
            )
            await self._close(ids, status="sent", reason="in_digest")
            result.digests_created += 1
            result.queued_consumed += len(ids)

        state.last_digest_local_date = today
        await self.session.flush()
        return result

    async def _expire_stale(self, today: object) -> int:
        cutoff = today - timedelta(days=MAX_AGE_DAYS)  # type: ignore[operator]
        stale = await self.session.execute(
            update(PriceAlertMessage)
            .where(
                PriceAlertMessage.status == "digest_queued",
                PriceAlertMessage.status_reason == "light",
                PriceAlertMessage.local_date < cutoff,
            )
            .values(status="suppressed", status_reason="stale")
        )
        return int(getattr(stale, "rowcount", 0) or 0)

    async def _opted_out(self, user_ids: set[UUID]) -> set[UUID]:
        if not user_ids:
            return set()
        rows = (
            await self.session.execute(
                select(UserAlertPreference.user_id).where(
                    UserAlertPreference.user_id.in_(user_ids),
                    UserAlertPreference.is_enabled.is_(False),
                )
            )
        ).scalars()
        return set(rows)

    async def _close(self, message_ids: list[UUID], *, status: str, reason: str) -> None:
        await self.session.execute(
            update(PriceAlertMessage)
            .where(PriceAlertMessage.id.in_(message_ids))
            .values(status=status, status_reason=reason)
        )
