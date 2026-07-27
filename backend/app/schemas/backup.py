from __future__ import annotations

from datetime import datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class BackupLogResponse(BaseModel):
    id: UUID
    backup_type: str
    status: str
    filename: str | None = None
    file_size: int | None = None
    storage_path: str | None = None
    error_message: str | None = None
    created_by_id: UUID | None = None
    created_by_email: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class BackupLogListResponse(BaseModel):
    items: list[BackupLogResponse]
    total: int


class BackupScheduleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    frequency: Literal["daily", "weekly", "one_off"]
    day_of_week: int | None = Field(default=None, ge=0, le=6, description="0=Monday, 6=Sunday")
    time_of_day: str = Field(description="Time of day in format HH:MM or HH:MM:SS")
    one_off_datetime: datetime | None = Field(
        default=None, description="Datetime for one-off backups"
    )
    is_active: bool = Field(default=True)

    @field_validator("time_of_day")
    @classmethod
    def validate_time_of_day(cls, v: str) -> time:
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                dt = datetime.strptime(v.strip(), fmt)
                return dt.time()
            except ValueError:
                continue
        raise ValueError("Time must be in format HH:MM or HH:MM:SS")


class BackupScheduleUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    frequency: Literal["daily", "weekly", "one_off"]
    day_of_week: int | None = Field(default=None, ge=0, le=6, description="0=Monday, 6=Sunday")
    time_of_day: str = Field(description="Time of day in format HH:MM or HH:MM:SS")
    one_off_datetime: datetime | None = Field(
        default=None, description="Datetime for one-off backups"
    )
    is_active: bool = Field(default=True)

    @field_validator("time_of_day")
    @classmethod
    def validate_time_of_day(cls, v: str) -> time:
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                dt = datetime.strptime(v.strip(), fmt)
                return dt.time()
            except ValueError:
                continue
        raise ValueError("Time must be in format HH:MM or HH:MM:SS")


class BackupScheduleResponse(BaseModel):
    id: UUID
    name: str
    frequency: str
    day_of_week: int | None = None
    time_of_day: time
    one_off_datetime: datetime | None = None
    is_active: bool
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
