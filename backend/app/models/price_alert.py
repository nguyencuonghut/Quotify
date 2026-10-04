from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class PriceAlertSetting(Base):
    """Cấu hình chung của thông báo biến động giá (singleton, tách khỏi `quotify_settings`)."""

    __tablename__ = "price_alert_settings"
    __table_args__ = (
        CheckConstraint(
            "singleton_key = 'default'",
            name="ck_price_alert_settings_singleton_key",
        ),
        CheckConstraint(
            "0 < light_from_percent AND light_from_percent < medium_from_percent "
            "AND medium_from_percent < large_over_percent "
            "AND large_over_percent < anomaly_percent",
            name="ck_price_alert_settings_thresholds_ordered",
        ),
        CheckConstraint(
            "reference_working_days BETWEEN 1 AND 30",
            name="ck_price_alert_settings_reference_working_days",
        ),
        CheckConstraint(
            "anomaly_lookback_days BETWEEN 1 AND 365",
            name="ck_price_alert_settings_anomaly_lookback_days",
        ),
        CheckConstraint(
            "max_trigger_delay_working_days BETWEEN 0 AND 30",
            name="ck_price_alert_settings_max_trigger_delay",
        ),
        CheckConstraint(
            "staff_lookback_days BETWEEN 1 AND 365",
            name="ck_price_alert_settings_staff_lookback_days",
        ),
        CheckConstraint(
            "dedupe_window_days BETWEEN 0 AND 90",
            name="ck_price_alert_settings_dedupe_window_days",
        ),
        CheckConstraint(
            "immediate_cap_per_scan BETWEEN 1 AND 500",
            name="ck_price_alert_settings_immediate_cap",
        ),
        CheckConstraint(
            "digest_hour_local BETWEEN 0 AND 23",
            name="ck_price_alert_settings_digest_hour",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    singleton_key: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        default="default",
        server_default="default",
    )
    reference_working_days: Mapped[int] = mapped_column(
        Integer,
        default=7,
        server_default="7",
    )
    light_from_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("2.50"),
        server_default="2.50",
    )
    medium_from_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("5.00"),
        server_default="5.00",
    )
    large_over_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("10.00"),
        server_default="10.00",
    )
    anomaly_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("30.00"),
        server_default="30.00",
    )
    anomaly_lookback_days: Mapped[int] = mapped_column(
        Integer,
        default=30,
        server_default="30",
    )
    max_trigger_delay_working_days: Mapped[int] = mapped_column(
        Integer,
        default=3,
        server_default="3",
    )
    staff_lookback_days: Mapped[int] = mapped_column(
        Integer,
        default=90,
        server_default="90",
    )
    dedupe_window_days: Mapped[int] = mapped_column(
        Integer,
        default=14,
        server_default="14",
    )
    immediate_cap_per_scan: Mapped[int] = mapped_column(
        Integer,
        default=30,
        server_default="30",
    )
    digest_hour_local: Mapped[int] = mapped_column(
        SmallInteger,
        default=8,
        server_default="8",
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
    )
    updated_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    updated_by: Mapped[User | None] = relationship()


class PriceAlertScanState(Base):
    """Trạng thái cron quét (singleton). Tách khỏi cấu hình để cron không khóa dòng cấu hình."""

    __tablename__ = "price_alert_scan_state"
    __table_args__ = (
        CheckConstraint(
            "singleton_key = 'default'",
            name="ck_price_alert_scan_state_singleton_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    singleton_key: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        default="default",
        server_default="default",
    )
    watermark_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    enabled_since: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_digest_local_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class PriceAlertScanRun(Base):
    """Một lần quét có việc hoặc có lỗi (lần quét rỗng không ghi dòng, xem L27)."""

    __tablename__ = "price_alert_scan_runs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    versions_scanned: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    events_created: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    messages_created: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    messages_sent: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)


class PriceAlertScannedVersion(Base):
    """Mỗi version đã quét một dòng, kể cả khi không sinh sự kiện (L2)."""

    __tablename__ = "price_alert_scanned_versions"

    version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("quote_versions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )
    is_trigger_source: Mapped[bool] = mapped_column(Boolean)
    trigger_delay_working_days: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    scan_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("price_alert_scan_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


class PriceAlertMaterialThreshold(Base):
    """Ghi đè ngưỡng theo vật tư (D4). NULL ở cả ba cột ngưỡng nghĩa là dùng mặc định."""

    __tablename__ = "price_alert_material_thresholds"
    __table_args__ = (
        CheckConstraint(
            "(light_from_percent IS NULL) = (medium_from_percent IS NULL) "
            "AND (medium_from_percent IS NULL) = (large_over_percent IS NULL)",
            name="ck_price_alert_material_thresholds_all_or_none",
        ),
        CheckConstraint(
            "light_from_percent IS NULL OR "
            "(0 < light_from_percent AND light_from_percent < medium_from_percent "
            "AND medium_from_percent < large_over_percent)",
            name="ck_price_alert_material_thresholds_ordered",
        ),
        CheckConstraint(
            "anomaly_percent IS NULL OR large_over_percent IS NULL "
            "OR anomaly_percent > large_over_percent",
            name="ck_price_alert_material_thresholds_anomaly_above_large",
        ),
    )

    material_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("materials.id", ondelete="CASCADE"),
        primary_key=True,
    )
    light_from_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    medium_from_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    large_over_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    anomaly_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    updated_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class UserAlertPreference(Base):
    """Tùy chọn nhận thông báo của từng người (D9, D10)."""

    __tablename__ = "user_alert_preferences"
    __table_args__ = (
        CheckConstraint(
            "min_level IS NULL OR min_level IN ('light','medium','large')",
            name="ck_user_alert_preferences_min_level",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    min_level: Mapped[str | None] = mapped_column(String(10), nullable=True)
    admin_receive_all: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
