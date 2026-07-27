from __future__ import annotations

import io
import typing
from collections.abc import Sequence
from uuid import UUID, uuid4

from minio import Minio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import File


class FileMetadataNotFoundError(Exception):
    """Raised when the target file metadata does not exist in the database."""


class FilePermissionDeniedError(Exception):
    """Raised when the user is not authorized to access or delete the file."""


class FileAdminService:
    def __init__(self, session: AsyncSession, minio_client: Minio | None = None) -> None:
        self.session = session
        self.settings = get_settings()
        if minio_client is not None:
            self.minio_client = minio_client
        else:
            from app.storage.minio import build_minio_client

            self.minio_client = build_minio_client(self.settings)

    async def upload_file(
        self,
        *,
        filename: str,
        content_type: str,
        size_bytes: int,
        data_stream: io.BytesIO | typing.BinaryIO,
        is_public: bool,
        uploaded_by_id: UUID | None,
    ) -> File:
        # Generate a unique path in the bucket: {uuid}/{filename}
        file_uuid = uuid4()
        storage_path = f"{file_uuid}/{filename}"

        # Upload the object to MinIO
        self.minio_client.put_object(
            bucket_name=self.settings.minio_bucket,
            object_name=storage_path,
            data=data_stream,
            length=size_bytes,
            content_type=content_type,
        )

        # Create database metadata record
        db_file = File(
            id=file_uuid,
            filename=filename,
            storage_path=storage_path,
            bucket=self.settings.minio_bucket,
            content_type=content_type,
            size_bytes=size_bytes,
            is_public=is_public,
            uploaded_by_id=uploaded_by_id,
        )
        self.session.add(db_file)
        await self.session.flush()
        return db_file

    async def get_file_by_id(self, file_id: UUID) -> File:
        stmt = select(File).where(File.id == file_id)
        result = await self.session.execute(stmt)
        db_file = result.scalar_one_or_none()
        if db_file is None:
            raise FileMetadataNotFoundError(f"File metadata {file_id} not found.")
        return db_file

    async def list_files(
        self,
        *,
        limit: int = 10,
        offset: int = 0,
        search: str | None = None,
        user_id: UUID | None = None,
        read_all: bool = False,
    ) -> tuple[Sequence[File], int]:
        stmt = select(File)

        # Apply search filter
        if search:
            stmt = stmt.where(File.filename.ilike(f"%{search}%"))

        # Apply visibility filtering: if not read_all, user can only see files they uploaded
        if not read_all:
            if user_id is None:
                # Anonymous or unauthenticated can only view public files
                stmt = stmt.where(File.is_public == True)  # noqa: E712
            else:
                # Logged in users can view their own files or public files
                stmt = stmt.where(
                    (File.uploaded_by_id == user_id) | (File.is_public == True)  # noqa: E712
                )

        # Get total matching count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        # Order by creation date (newest first)
        stmt = stmt.order_by(File.created_at.desc())
        stmt = stmt.offset(offset).limit(limit)

        result = await self.session.execute(stmt)
        files = result.scalars().all()
        return files, total

    async def delete_file(
        self,
        *,
        file_id: UUID,
        user_id: UUID | None,
        can_delete_all: bool = False,
    ) -> None:
        db_file = await self.get_file_by_id(file_id)

        # Permission check: must be owner or have delete-all permissions (admin)
        if not can_delete_all:
            if db_file.uploaded_by_id is None or db_file.uploaded_by_id != user_id:
                raise FilePermissionDeniedError("You are not authorized to delete this file.")

        # Delete the object from MinIO
        try:
            self.minio_client.remove_object(
                bucket_name=db_file.bucket,
                object_name=db_file.storage_path,
            )
        except Exception as e:
            # We can log this warning, but proceed with DB deletion if MinIO object is missing
            import logging

            logging.getLogger("app").warning(
                "Could not delete MinIO object '%s' in bucket '%s': %s",
                db_file.storage_path,
                db_file.bucket,
                e,
            )

        # Delete database metadata record
        await self.session.delete(db_file)
        await self.session.flush()
