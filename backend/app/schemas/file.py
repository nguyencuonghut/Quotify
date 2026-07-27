from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FileResponse(BaseModel):
    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    is_public: bool
    uploaded_by_id: UUID | None
    created_at: datetime
    url: str


class FileListResponse(BaseModel):
    items: list[FileResponse]
    total: int
