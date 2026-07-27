from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.schemas.file import FileResponse


class ImportJobResponse(BaseModel):
    id: UUID
    file_id: UUID
    status: str
    total_rows: int
    processed_rows: int
    failed_rows: int
    error_summary: str | None = None
    errors_json: list[Any] | None = None
    created_by_id: UUID | None
    created_at: datetime
    updated_at: datetime
    file: FileResponse | None = None


class ImportJobListResponse(BaseModel):
    items: list[ImportJobResponse]
    total: int


class ExportJobResponse(BaseModel):
    id: UUID
    status: str
    file_id: UUID | None = None
    filters: dict[str, Any] | None = None
    error_summary: str | None = None
    created_by_id: UUID | None
    created_at: datetime
    updated_at: datetime
    file: FileResponse | None = None


class ExportJobListResponse(BaseModel):
    items: list[ExportJobResponse]
    total: int
