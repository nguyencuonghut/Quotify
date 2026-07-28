from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class QuoteNoteRevisionResponse(BaseModel):
    id: UUID
    revision_number: int
    content: str
    author_id: UUID | None = None
    author_name: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class QuoteNoteResponse(BaseModel):
    id: UUID
    quote_id: UUID
    created_at: datetime
    updated_at: datetime
    revisions: list[QuoteNoteRevisionResponse]

    class Config:
        from_attributes = True


class QuoteNoteUpdateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20480)
