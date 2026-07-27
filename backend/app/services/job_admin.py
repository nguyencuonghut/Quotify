from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models import ExportJob, File, ImportJob

_create_pool: Any

try:
    from arq import create_pool as _create_pool
    from arq.connections import RedisSettings
except ImportError:
    _create_pool = None

    class RedisSettings:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass


class JobQueue(Protocol):
    async def enqueue_job(self, *args: Any, **kwargs: Any) -> Any: ...


class DummyJobQueue:
    async def enqueue_job(self, *args: Any, **kwargs: Any) -> None:
        return None


async def create_job_queue(*, host: str, port: int) -> JobQueue:
    if _create_pool is None:
        return DummyJobQueue()

    return cast(JobQueue, await _create_pool(RedisSettings(host=host, port=port)))


class JobNotFoundError(Exception):
    """Raised when a requested job does not exist."""


class JobAdminService:
    def __init__(self, session: AsyncSession, redis_pool: Any = None) -> None:
        self.session = session
        self.settings = get_settings()
        self.redis_pool = redis_pool

    async def _get_redis(self) -> Any:
        if self.redis_pool is not None:
            return self.redis_pool
        return await create_job_queue(
            host=self.settings.redis_host,
            port=self.settings.redis_port,
        )

    async def create_import_job(self, *, file_id: UUID, user_id: UUID) -> ImportJob:
        # Verify file exists
        stmt = select(File).where(File.id == file_id)
        result = await self.session.execute(stmt)
        db_file = result.scalar_one_or_none()
        if db_file is None:
            raise ValueError(f"File {file_id} not found.")

        job = ImportJob(
            file_id=file_id,
            status="pending",
            created_by_id=user_id,
        )
        self.session.add(job)
        await self.session.flush()

        # Enqueue arq background task
        try:
            redis = await self._get_redis()
            await redis.enqueue_job("import_users_task", job.id)
        except Exception as e:
            # We can log this, but set to pending so it can be retried or debugged
            import logging

            logging.getLogger("app").error(f"Failed to enqueue import job {job.id} to redis: {e}")

        return job

    async def create_export_job(
        self, *, filters: dict[str, Any] | None, user_id: UUID
    ) -> ExportJob:
        job = ExportJob(
            status="pending",
            filters=filters,
            created_by_id=user_id,
        )
        self.session.add(job)
        await self.session.flush()

        # Enqueue arq background task
        try:
            redis = await self._get_redis()
            await redis.enqueue_job("export_users_task", job.id)
        except Exception as e:
            import logging

            logging.getLogger("app").error(f"Failed to enqueue export job {job.id} to redis: {e}")

        return job

    async def get_import_job_by_id(self, job_id: UUID) -> ImportJob:
        stmt = select(ImportJob).options(selectinload(ImportJob.file)).where(ImportJob.id == job_id)
        result = await self.session.execute(stmt)
        job = result.scalar_one_or_none()
        if job is None:
            raise JobNotFoundError(f"Import job {job_id} not found.")
        return job

    async def get_export_job_by_id(self, job_id: UUID) -> ExportJob:
        stmt = select(ExportJob).options(selectinload(ExportJob.file)).where(ExportJob.id == job_id)
        result = await self.session.execute(stmt)
        job = result.scalar_one_or_none()
        if job is None:
            raise JobNotFoundError(f"Export job {job_id} not found.")
        return job

    async def list_import_jobs(
        self,
        *,
        limit: int = 10,
        offset: int = 0,
        user_id: UUID | None = None,
        is_admin: bool = False,
    ) -> tuple[Sequence[ImportJob], int]:
        stmt = select(ImportJob).options(selectinload(ImportJob.file))

        if not is_admin and user_id is not None:
            stmt = stmt.where(ImportJob.created_by_id == user_id)

        # Get count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        # Order by created_at desc
        stmt = stmt.order_by(ImportJob.created_at.desc())
        stmt = stmt.offset(offset).limit(limit)

        result = await self.session.execute(stmt)
        jobs = result.scalars().all()
        return jobs, total

    async def list_export_jobs(
        self,
        *,
        limit: int = 10,
        offset: int = 0,
        user_id: UUID | None = None,
        is_admin: bool = False,
    ) -> tuple[Sequence[ExportJob], int]:
        stmt = select(ExportJob).options(selectinload(ExportJob.file))

        if not is_admin and user_id is not None:
            stmt = stmt.where(ExportJob.created_by_id == user_id)

        # Get count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        # Order by created_at desc
        stmt = stmt.order_by(ExportJob.created_at.desc())
        stmt = stmt.offset(offset).limit(limit)

        result = await self.session.execute(stmt)
        jobs = result.scalars().all()
        return jobs, total
