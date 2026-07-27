from __future__ import annotations

import asyncio
import codecs
import csv
import io
import logging
from collections.abc import Iterator
from typing import Any, BinaryIO
from uuid import UUID, uuid4

try:
    from arq.connections import RedisSettings
except ImportError:

    class RedisSettings:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass


from datetime import UTC, datetime

from arq import cron
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.session import get_sessionmaker
from app.models import ExportJob, ImportJob, User, UserStatus
from app.models.backup_log import BackupLog
from app.models.backup_schedule import BackupSchedule
from app.services.audit_log import AuditLogContext, AuditLogService
from app.services.backup_admin import calculate_next_run
from app.services.email import EmailService
from app.services.file_admin import FileAdminService
from app.services.user_admin import RoleNotFoundError, UserAdminService
from app.storage.minio import build_minio_client

logger = logging.getLogger("arq.worker")
TERMINAL_STATUSES = {"completed", "failed"}
CSV_STREAM_CHUNK_SIZE = 64 * 1024


def _iter_decoded_csv_lines(
    binary_stream: BinaryIO,
    *,
    chunk_size: int = CSV_STREAM_CHUNK_SIZE,
) -> Iterator[str]:
    decoder = codecs.getincrementaldecoder("utf-8-sig")()
    pending = ""

    while True:
        chunk = binary_stream.read(chunk_size)
        if not chunk:
            break

        pending += decoder.decode(chunk)
        lines = pending.splitlines(keepends=True)
        if lines and not lines[-1].endswith(("\n", "\r")):
            pending = lines.pop()
        else:
            pending = ""
        yield from lines

    pending += decoder.decode(b"", final=True)
    if pending:
        yield pending


async def _log_worker_audit_event(
    session: Any,
    *,
    action: str,
    entity_type: str,
    entity_id: UUID,
    actor_user_id: UUID | None,
    metadata_json: dict[str, object],
) -> None:
    audit_service = AuditLogService(session)
    await audit_service.log_event(
        action=action,
        entity_type=entity_type,
        context=AuditLogContext(
            actor_user_id=actor_user_id,
            entity_id=str(entity_id),
            metadata_json=metadata_json,
        ),
    )


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    ctx["session_factory"] = get_sessionmaker()
    ctx["minio_client"] = build_minio_client(settings)
    logger.info("Arq background worker started up successfully.")


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("Arq background worker shutting down.")


async def import_users_task(ctx: dict[str, Any], job_id: UUID) -> None:
    session_factory = ctx["session_factory"]
    minio_client = ctx["minio_client"]

    async with session_factory() as session:
        # 1. Fetch import job
        stmt = select(ImportJob).where(ImportJob.id == job_id).options(selectinload(ImportJob.file))
        result = await session.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            logger.error(f"Import job {job_id} not found.")
            return

        job_entity_type = job.entity_type or "users"
        if job_entity_type != "users":
            logger.error(
                "Import job %s has entity_type=%s but import_users_task only handles users.",
                job_id,
                job_entity_type,
            )
            return

        if job.status in TERMINAL_STATUSES:
            logger.warning(f"Import job {job_id} is already in state {job.status}.")
            return

        if job.status == "pending":
            job.status = "processing"
            await session.commit()

        # 2. Get file stream from MinIO
        try:
            minio_response = minio_client.get_object(
                bucket_name=job.file.bucket,
                object_name=job.file.storage_path,
            )
            try:
                reader = csv.DictReader(_iter_decoded_csv_lines(minio_response))
                if reader.fieldnames is None:
                    raise ValueError("CSV header is missing.")

                user_service = UserAdminService(session)
                processed_rows = 0
                failed_rows = 0
                errors_list = []

                # 3. Process each row
                for idx, row in enumerate(reader, start=1):
                    job.total_rows = idx
                    email = (row.get("email") or "").strip()
                    password = row.get("password") or ""
                    status_str = (row.get("status") or "").strip().lower()
                    roles_str = row.get("roles") or ""
                    full_name = (row.get("full_name") or row.get("fullName") or "").strip()

                    # Standard defaults
                    status = UserStatus.ACTIVE
                    if status_str:
                        try:
                            status = UserStatus(status_str)
                        except ValueError:
                            errors_list.append(
                                {
                                    "row": idx,
                                    "email": email,
                                    "errors": [f"Invalid status '{status_str}'."],
                                }
                            )
                            failed_rows += 1
                            continue

                    # Default roles list
                    role_names = [r.strip() for r in roles_str.split(",") if r.strip()]
                    if not role_names:
                        role_names = ["user"]

                    # Validation checks before database call
                    row_errors = []
                    if not email:
                        row_errors.append("Email is required.")
                    if not password or len(password) < 8:
                        row_errors.append("Password must be at least 8 characters long.")
                    if not full_name:
                        row_errors.append("Full name is required.")

                    if row_errors:
                        errors_list.append({"row": idx, "email": email, "errors": row_errors})
                        failed_rows += 1
                        continue

                    # Database creation inside nested sub-transaction
                    try:
                        async with session.begin_nested():
                            await user_service.create_user(
                                email=email,
                                password=password,
                                status=status,
                                role_names=role_names,
                                full_name=full_name,
                            )
                        processed_rows += 1
                    except RoleNotFoundError as e:
                        errors_list.append({"row": idx, "email": email, "errors": [str(e)]})
                        failed_rows += 1
                    except Exception as e:
                        # Catch duplicates or other database constraints
                        # If email already exists or similar database constraint raised
                        # Check for standard unique email constraint error message
                        msg = str(e)
                        if "already exists" in msg or "unique constraint" in msg.lower():
                            msg = f"User with email {email} already exists."
                        errors_list.append({"row": idx, "email": email, "errors": [msg]})
                        failed_rows += 1

                    # Update job progress periodically
                    if idx % 10 == 0:
                        job.processed_rows = processed_rows
                        job.failed_rows = failed_rows
                        job.errors_json = errors_list
                        await session.commit()
            finally:
                minio_response.close()
                minio_response.release_conn()
        except Exception:
            logger.exception(f"Failed to read/parse CSV file for import job {job_id}")
            job.status = "failed"
            job.error_summary = "Failed to read or parse import CSV."
            await _log_worker_audit_event(
                session,
                action="users.import_failed",
                entity_type="import_job",
                entity_id=job.id,
                actor_user_id=job.created_by_id,
                metadata_json={
                    "import_job_id": str(job.id),
                    "file_id": str(job.file_id),
                    "status": job.status,
                    "outcome": "failed",
                    "error_category": "csv_read_parse_failed",
                    "error_summary": "Failed to read or parse import CSV.",
                },
            )
            await session.commit()
            return

        # 4. Finish import job
        job.status = (
            "completed" if job.total_rows > 0 and failed_rows < job.total_rows else "failed"
        )
        if job.total_rows == 0:
            job.error_summary = "No import rows found."
        elif failed_rows == job.total_rows:
            job.error_summary = "All rows failed to import."
        job.processed_rows = processed_rows
        job.failed_rows = failed_rows
        job.errors_json = errors_list
        await _log_worker_audit_event(
            session,
            action=(
                "users.import_completed" if job.status == "completed" else "users.import_failed"
            ),
            entity_type="import_job",
            entity_id=job.id,
            actor_user_id=job.created_by_id,
            metadata_json={
                "import_job_id": str(job.id),
                "file_id": str(job.file_id),
                "status": job.status,
                "outcome": "completed" if job.status == "completed" else "failed",
                "total_rows": job.total_rows,
                "processed_rows": job.processed_rows,
                "failed_rows": job.failed_rows,
                **(
                    {
                        "error_category": "all_rows_failed",
                        "error_summary": "All rows failed to import.",
                    }
                    if job.status == "failed"
                    else {}
                ),
            },
        )
        await session.commit()


async def export_users_task(ctx: dict[str, Any], job_id: UUID) -> None:
    session_factory = ctx["session_factory"]
    minio_client = ctx["minio_client"]

    async with session_factory() as session:
        # 1. Fetch export job
        stmt = select(ExportJob).where(ExportJob.id == job_id)
        result = await session.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            logger.error(f"Export job {job_id} not found.")
            return

        if job.status in TERMINAL_STATUSES:
            logger.warning(f"Export job {job_id} is already in state {job.status}.")
            return

        if job.status == "pending":
            job.status = "processing"
            await session.commit()

        try:
            filters = job.filters or {}

            # 2. Query matching users
            query = select(User).options(selectinload(User.roles))
            if search := filters.get("search"):
                query = query.where(User.email.ilike(f"%{search}%"))
            if status_str := filters.get("status"):
                query = query.where(User.status == UserStatus(status_str))

            query = query.order_by(User.created_at.desc())
            users_result = await session.execute(query)
            users = users_result.scalars().all()

            # 3. Generate CSV in-memory
            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerow(["email", "status", "roles", "created_at"])

            for user in users:
                roles_str = ",".join([r.name for r in user.roles])
                writer.writerow(
                    [user.email, user.status.value, roles_str, user.created_at.isoformat()]
                )

            csv_bytes = csv_buffer.getvalue().encode("utf-8")
            csv_stream = io.BytesIO(csv_bytes)

            # 4. Upload file to MinIO (marked as private)
            file_admin = FileAdminService(session, minio_client)
            db_file = await file_admin.upload_file(
                filename=f"users_export_{job_id}.csv",
                content_type="text/csv",
                size_bytes=len(csv_bytes),
                data_stream=csv_stream,
                is_public=False,
                uploaded_by_id=job.created_by_id,
            )

            # 5. Link file to export job
            job.file_id = db_file.id
            job.status = "completed"
            await _log_worker_audit_event(
                session,
                action="users.export_completed",
                entity_type="export_job",
                entity_id=job.id,
                actor_user_id=job.created_by_id,
                metadata_json={
                    "export_job_id": str(job.id),
                    "file_id": str(db_file.id),
                    "status": job.status,
                    "outcome": "completed",
                    "total_rows": len(users),
                    "size_bytes": len(csv_bytes),
                },
            )
            await session.commit()
        except Exception as e:
            logger.exception(f"Failed to export users for job {job_id}")
            job.status = "failed"
            job.error_summary = str(e)
            await _log_worker_audit_event(
                session,
                action="users.export_failed",
                entity_type="export_job",
                entity_id=job.id,
                actor_user_id=job.created_by_id,
                metadata_json={
                    "export_job_id": str(job.id),
                    "status": job.status,
                    "outcome": "failed",
                    "error_category": "export_failed",
                    "error_summary": "Failed to export users.",
                },
            )
            await session.commit()


async def run_backup_task(ctx: dict[str, Any], backup_log_id: UUID) -> None:
    session_factory = ctx["session_factory"]
    minio_client = ctx["minio_client"]
    settings = get_settings()
    email_service = EmailService(settings)

    async with session_factory() as session:
        # Fetch backup log
        stmt = select(BackupLog).where(BackupLog.id == backup_log_id)
        result = await session.execute(stmt)
        log = result.scalar_one_or_none()

        if not log:
            logger.error(f"Backup log {backup_log_id} not found.")
            return

        if log.status in TERMINAL_STATUSES:
            logger.warning(f"Backup log {backup_log_id} is already in state {log.status}.")
            return

        if log.status == "pending":
            log.status = "running"
            await session.commit()

        started_at = log.started_at
        try:
            # 1. Parse DB URL
            from sqlalchemy.engine.url import make_url

            url = make_url(settings.database_url)
            db_host = url.host or "postgres"
            db_port = url.port or 5432
            db_user = url.username or "postgres"
            db_password = url.password or "postgres"
            db_name = url.database or "app"

            # 2. Formulate filename
            timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
            filename = f"postgres_{timestamp}.sql.gz"

            # Ensure local backups folder exists
            backups_dir = "/app/backups"  # mounted volume
            import os

            os.makedirs(backups_dir, exist_ok=True)
            output_file = os.path.join(backups_dir, filename)

            # 3. Run pg_dump
            env = os.environ.copy()
            env["PGPASSWORD"] = db_password

            logger.info(f"Running pg_dump for database {db_name} on {db_host}:{db_port}")
            process = await asyncio.create_subprocess_exec(
                "pg_dump",
                "-h",
                db_host,
                "-p",
                str(db_port),
                "-U",
                db_user,
                "-d",
                db_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise Exception(
                    f"pg_dump failed with exit code {process.returncode}: {stderr.decode()}"
                )

            # 4. Compress via gzip
            import gzip

            logger.info(f"Writing compressed backup to {output_file}")
            with gzip.open(output_file, "wb") as f:
                f.write(stdout)

            file_size = os.path.getsize(output_file)  # noqa: ASYNC240

            # 5. Upload to MinIO
            storage_path = f"backups/{filename}"
            logger.info(
                f"Uploading backup {filename} to MinIO bucket "
                f"{settings.minio_bucket} at path {storage_path}"
            )

            # Ensure bucket exists
            if not minio_client.bucket_exists(settings.minio_bucket):
                minio_client.make_bucket(settings.minio_bucket)

            # Use fput_object
            minio_client.fput_object(
                bucket_name=settings.minio_bucket,
                object_name=storage_path,
                file_path=output_file,
            )

            # 6. Update log
            completed_at = datetime.now(UTC)
            log.status = "completed"
            log.filename = filename
            log.file_size = file_size
            log.storage_path = storage_path
            log.completed_at = completed_at
            await _log_worker_audit_event(
                session,
                action="backups.run_completed",
                entity_type="backup_log",
                entity_id=log.id,
                actor_user_id=log.created_by_id,
                metadata_json={
                    "backup_log_id": str(log.id),
                    "backup_type": log.backup_type,
                    "filename": filename,
                    "size_bytes": file_size,
                    "status": log.status,
                    "outcome": "completed",
                },
            )
            await session.commit()

            # 7. Send notification
            try:
                await email_service.send_backup_notification(
                    status="success",
                    backup_type=log.backup_type,
                    filename=filename,
                    file_size_bytes=file_size,
                    started_at=started_at,
                    completed_at=completed_at,
                )
            except Exception:
                logger.exception("Failed to send success notification email")

        except Exception as e:
            logger.exception(f"Backup task failed for log {backup_log_id}")
            completed_at = datetime.now(UTC)
            log.status = "failed"
            log.error_message = str(e)
            log.completed_at = completed_at
            await _log_worker_audit_event(
                session,
                action="backups.run_failed",
                entity_type="backup_log",
                entity_id=log.id,
                actor_user_id=log.created_by_id,
                metadata_json={
                    "backup_log_id": str(log.id),
                    "backup_type": log.backup_type,
                    "status": log.status,
                    "outcome": "failed",
                    "error_category": "backup_failed",
                    "error_summary": "Backup task failed.",
                },
            )
            await session.commit()

            # Send failure notification
            try:
                await email_service.send_backup_notification(
                    status="failed",
                    backup_type=log.backup_type,
                    filename=None,
                    file_size_bytes=None,
                    started_at=started_at,
                    completed_at=completed_at,
                    error_message=str(e),
                )
            except Exception:
                logger.exception("Failed to send failure notification email")


async def poll_and_run_scheduled_backups(ctx: dict[str, Any]) -> None:
    session_factory = ctx["session_factory"]
    settings = get_settings()

    redis = ctx.get("redis")
    if not redis:
        logger.error("Arq redis client not found in context.")
        return

    async with session_factory() as session:
        now = datetime.now(UTC)

        # Select active schedules that are due (next_run_at <= now)
        stmt = (
            select(BackupSchedule)
            .where(BackupSchedule.is_active)
            .where(BackupSchedule.next_run_at <= now)
            .with_for_update(skip_locked=True)
        )
        res = await session.execute(stmt)
        due_schedules = res.scalars().all()

        for schedule in due_schedules:
            logger.info(
                f"Triggering scheduled backup for schedule: {schedule.name} ({schedule.id})"
            )

            # Create a pending backup log
            log = BackupLog(
                id=uuid4(),
                backup_type="scheduled",
                status="pending",
                started_at=now,
                created_at=now,
            )
            session.add(log)
            await session.commit()

            # Enqueue the actual backup task
            await redis.enqueue_job("run_backup_task", log.id)

            # Update schedule run metrics and next_run_at
            schedule.last_run_at = now
            next_run = calculate_next_run(
                frequency=schedule.frequency,
                time_of_day=schedule.time_of_day,
                day_of_week=schedule.day_of_week,
                one_off_datetime=schedule.one_off_datetime,
                current_time=now,
                tz_name=settings.app_timezone,
            )

            schedule.next_run_at = next_run
            if schedule.frequency == "one_off":
                schedule.is_active = False

            await session.commit()
            logger.info(f"Schedule {schedule.name} updated. Next run: {next_run}")


settings = get_settings()


class WorkerSettings:
    redis_settings = RedisSettings(host=settings.redis_host, port=settings.redis_port)
    functions = [
        import_users_task,
        export_users_task,
        run_backup_task,
        poll_and_run_scheduled_backups,
    ]
    cron_jobs = [cron(poll_and_run_scheduled_backups, second=0)]
    on_startup = startup
    on_shutdown = shutdown
