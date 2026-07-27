from __future__ import annotations

import logging
import zoneinfo
from datetime import UTC, datetime, time, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.backup_log import BackupLog
from app.models.backup_schedule import BackupSchedule

_create_pool: Any

try:
    from arq import create_pool as _create_pool
    from arq.connections import RedisSettings
except ImportError:
    _create_pool = None

    class RedisSettings:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass


if TYPE_CHECKING:
    from typing import Any

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def calculate_next_run(
    frequency: str,
    time_of_day: time,
    day_of_week: int | None = None,
    one_off_datetime: datetime | None = None,
    current_time: datetime | None = None,
    tz_name: str = "Asia/Ho_Chi_Minh",
) -> datetime | None:
    tz = zoneinfo.ZoneInfo(tz_name)

    if current_time is None:
        current_time = datetime.now(UTC)

    # Convert current time to local timezone
    local_now = current_time.astimezone(tz)

    if frequency == "one_off":
        if one_off_datetime is None:
            return None
        # Ensure it has timezone info, if naive treat it as local
        if one_off_datetime.tzinfo is None:
            one_off_datetime = one_off_datetime.replace(tzinfo=tz)
        # Convert to UTC to store in DB
        return one_off_datetime.astimezone(UTC)

    # For daily and weekly, combine local date with time_of_day
    local_date = local_now.date()
    local_scheduled = datetime.combine(local_date, time_of_day).replace(tzinfo=tz)

    if frequency == "daily":
        # If today's scheduled time has already passed, schedule for tomorrow
        if local_scheduled <= local_now:
            local_scheduled += timedelta(days=1)
        return local_scheduled.astimezone(UTC)

    elif frequency == "weekly":
        if day_of_week is None:
            day_of_week = 0  # default Monday
        # Calculate days until the scheduled day_of_week (0=Monday, ..., 6=Sunday)
        days_ahead = day_of_week - local_now.weekday()
        if days_ahead < 0:
            days_ahead += 7
        elif days_ahead == 0:
            # If it's today, check if the time has already passed
            if local_scheduled <= local_now:
                days_ahead = 7

        local_scheduled = datetime.combine(
            local_date + timedelta(days=days_ahead), time_of_day
        ).replace(tzinfo=tz)
        return local_scheduled.astimezone(UTC)

    return None


class BackupScheduleNotFoundError(Exception):
    pass


class BackupAdminService:
    def __init__(self, session: AsyncSession, redis_pool: Any = None) -> None:
        self.session = session
        self.settings = get_settings()
        self.redis_pool = redis_pool

    async def _get_redis(self) -> Any:
        if self.redis_pool is not None:
            return self.redis_pool
        if _create_pool is None:
            return None
        return await _create_pool(
            RedisSettings(host=self.settings.redis_host, port=self.settings.redis_port)
        )

    async def get_backup_logs(
        self, limit: int = 50, offset: int = 0
    ) -> tuple[list[BackupLog], int]:
        # Count total logs
        total_stmt = select(func.count(BackupLog.id))
        total_result = await self.session.execute(total_stmt)
        total = total_result.scalar() or 0

        # Query paginated list
        stmt = (
            select(BackupLog)
            .options(selectinload(BackupLog.created_by))
            .order_by(BackupLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        logs = list(res.scalars().all())

        return logs, total

    async def get_backup_schedules(self) -> list[BackupSchedule]:
        stmt = select(BackupSchedule).order_by(BackupSchedule.created_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create_backup_schedule(
        self,
        name: str,
        frequency: str,
        time_of_day: time,
        day_of_week: int | None = None,
        one_off_datetime: datetime | None = None,
        is_active: bool = True,
    ) -> BackupSchedule:
        now = datetime.now(UTC)
        next_run_at = calculate_next_run(
            frequency=frequency,
            time_of_day=time_of_day,
            day_of_week=day_of_week,
            one_off_datetime=one_off_datetime,
            current_time=now,
            tz_name=self.settings.app_timezone,
        )

        schedule = BackupSchedule(
            id=uuid4(),
            name=name,
            frequency=frequency,
            day_of_week=day_of_week,
            time_of_day=time_of_day,
            one_off_datetime=one_off_datetime,
            is_active=is_active,
            next_run_at=next_run_at,
            created_at=now,
            updated_at=now,
        )

        self.session.add(schedule)
        await self.session.flush()
        return schedule

    async def update_backup_schedule(
        self,
        schedule_id: UUID,
        name: str,
        frequency: str,
        time_of_day: time,
        day_of_week: int | None = None,
        one_off_datetime: datetime | None = None,
        is_active: bool = True,
    ) -> BackupSchedule:
        stmt = select(BackupSchedule).where(BackupSchedule.id == schedule_id)
        res = await self.session.execute(stmt)
        schedule = res.scalar_one_or_none()
        if not schedule:
            raise BackupScheduleNotFoundError(f"Backup schedule {schedule_id} not found.")

        now = datetime.now(UTC)
        schedule.name = name
        schedule.frequency = frequency
        schedule.time_of_day = time_of_day
        schedule.day_of_week = day_of_week
        schedule.one_off_datetime = one_off_datetime
        schedule.is_active = is_active
        schedule.updated_at = now

        # Recalculate next run time
        schedule.next_run_at = calculate_next_run(
            frequency=frequency,
            time_of_day=time_of_day,
            day_of_week=day_of_week,
            one_off_datetime=one_off_datetime,
            current_time=now,
            tz_name=self.settings.app_timezone,
        )

        await self.session.flush()
        return schedule

    async def delete_backup_schedule(self, schedule_id: UUID) -> BackupSchedule:
        stmt = select(BackupSchedule).where(BackupSchedule.id == schedule_id)
        res = await self.session.execute(stmt)
        schedule = res.scalar_one_or_none()
        if not schedule:
            raise BackupScheduleNotFoundError(f"Backup schedule {schedule_id} not found.")

        await self.session.delete(schedule)
        await self.session.flush()
        return schedule

    async def trigger_manual_backup(self, created_by_id: UUID) -> BackupLog:
        now = datetime.now(UTC)
        log = BackupLog(
            id=uuid4(),
            backup_type="manual",
            status="pending",
            created_by_id=created_by_id,
            started_at=now,
            created_at=now,
        )

        self.session.add(log)
        await self.session.flush()
        return log

    async def enqueue_manual_backup(self, backup_log_id: UUID) -> bool:
        # Enqueue job in Arq Redis
        try:
            redis = await self._get_redis()
            if redis:
                logger.info(f"Enqueuing run_backup_task for backup log {backup_log_id}")
                await redis.enqueue_job("run_backup_task", backup_log_id)
                return True
            else:
                logger.error("Failed to enqueue backup: redis pool not available.")
        except Exception as e:
            logger.exception(f"Failed to enqueue backup to redis: {e}")
        return False
