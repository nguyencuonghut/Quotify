"""Nhắc cập nhật giá theo vật tư qua Telegram (Telegram 1D, Slice 5)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PriceAlertMessage, PriceAlertMessageMaterial, PriceAlertSetting
from app.services.price_alert_candidates import BUSINESS_TIMEZONE
from app.services.price_alert_recipients import resolve_freshness_recipients
from app.services.price_alert_settings_service import PriceAlertSettingsService
from app.services.quotify_material_freshness_service import QuotifyMaterialFreshnessService
from app.services.working_days import is_working_day, working_days_between

FRESHNESS_ADVISORY_LOCK_KEY = 7_620_261_007  # khóa quét: ...004, bản tin: ...006

# Nhịp nhắc (F12, Q7 đã chốt): ngày làm việc đầu tiên sau khi quá hạn, rồi mỗi 3 ngày làm việc,
# tối đa 5 lần cho mỗi đợt quá hạn. Đổi nhịp chỉ cần đổi hai hằng số này.
REPEAT_WORKING_DAYS = 3
MAX_REMINDERS = 5


def reminder_working_days(last_received: date, interval_days: int, *, today: date) -> int:
    """Số ngày làm việc đã quá hạn: đếm trong `(hạn, hôm nay]`; 0 nghĩa là chưa quá hạn."""
    due_date = last_received + timedelta(days=interval_days)
    return working_days_between(due_date, today)


def reminder_due(overdue_working_days: int) -> bool:
    """Hôm nay có nhắc không, chỉ dựa vào số ngày làm việc đã quá hạn (không lưu trạng thái)."""
    if overdue_working_days < 1:
        return False
    if overdue_working_days > (MAX_REMINDERS - 1) * REPEAT_WORKING_DAYS + 1:
        return False
    return (overdue_working_days - 1) % REPEAT_WORKING_DAYS == 0


@dataclass(frozen=True, slots=True)
class DueMaterial:
    material_id: UUID
    age_days: int
    interval_days: int
    last_received_date: date
    last_enterer_id: UUID | None


@dataclass(slots=True)
class ReminderResult:
    messages_created: int = 0
    materials_due: int = 0
    skipped: str | None = None


class PriceFreshnessReminderService:
    """Xếp tin nhắc cập nhật giá mỗi ngày làm việc (F12). Chỉ `flush`; người gọi `commit`.

    Mỗi người nhận một tin gom các vật tư của họ đến nhịp nhắc hôm nay. Idempotent bằng khóa
    advisory, `last_freshness_local_date` và chỉ mục duy nhất `(user_id, local_date)`.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run_once(
        self,
        *,
        now: datetime,
        settings: PriceAlertSetting,
        seed_user_id: UUID | None,
        pilot_emails: frozenset[str] = frozenset(),
    ) -> ReminderResult:
        local = now.astimezone(BUSINESS_TIMEZONE)
        today = local.date()
        if not is_working_day(today):
            return ReminderResult(skipped="not_working_day")
        if local.hour < settings.freshness_hour_local:
            return ReminderResult(skipped="not_due")
        locked = (
            await self.session.execute(
                select(func.pg_try_advisory_xact_lock(FRESHNESS_ADVISORY_LOCK_KEY))
            )
        ).scalar_one()
        if not locked:
            return ReminderResult(skipped="locked")
        state = await PriceAlertSettingsService(self.session).get_or_create_scan_state(
            for_update=True
        )
        if state.last_freshness_local_date == today:
            return ReminderResult(skipped="already_sent")

        result = ReminderResult()
        due = await self._due_materials(today)
        result.materials_due = len(due)
        if due:
            by_id = {item.material_id: item for item in due}
            recipients, _ = await resolve_freshness_recipients(
                self.session,
                material_ids=set(by_id),
                now=now,
                seed_user_id=seed_user_id,
                pilot_emails=pilot_emails,
                staff_lookback_days=settings.staff_lookback_days,
            )
            for recipient in recipients:
                message_id = (
                    await self.session.execute(
                        pg_insert(PriceAlertMessage)
                        .values(
                            user_id=recipient.user_id,
                            telegram_account_id=recipient.telegram_account_id,
                            material_id=None,
                            local_date=today,
                            scan_run_id=None,
                            kind="freshness",
                            status="pending",
                            created_at=now,
                        )
                        .on_conflict_do_nothing(
                            index_elements=["user_id", "local_date"],
                            index_where=PriceAlertMessage.kind == "freshness",
                        )
                        .returning(PriceAlertMessage.id)
                    )
                ).scalar_one_or_none()
                if message_id is None:
                    continue
                await self.session.execute(
                    pg_insert(PriceAlertMessageMaterial).values(
                        [
                            {
                                "message_id": message_id,
                                "material_id": material_id,
                                "age_days": by_id[material_id].age_days,
                                "interval_days": by_id[material_id].interval_days,
                                "last_received_date": by_id[material_id].last_received_date,
                                "last_enterer_id": by_id[material_id].last_enterer_id,
                            }
                            for material_id in sorted(recipient.material_ids, key=str)
                        ]
                    )
                )
                result.messages_created += 1

        state.last_freshness_local_date = today
        await self.session.flush()
        return result

    async def _due_materials(self, today: date) -> list[DueMaterial]:
        """Vật tư đang theo dõi, đã quá hạn, hôm nay đúng nhịp nhắc (bỏ vật tư chưa có giá)."""
        table = await QuotifyMaterialFreshnessService(self.session).get_material_freshness(
            week_start=today,
            today=today,
        )
        due: list[DueMaterial] = []
        for item in table["items"]:
            interval = item["expected_interval_days"]
            last = item["last_received_date"]
            age = item["age_days"]
            if not item["is_watched"] or interval is None or last is None or age is None:
                continue
            if age <= interval:
                continue
            if not reminder_due(reminder_working_days(last, interval, today=today)):
                continue
            due.append(
                DueMaterial(item["material_id"], age, interval, last, item["last_enterer_id"])
            )
        return due
