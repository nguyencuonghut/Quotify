from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PriceAlertScanState, PriceAlertSetting

_PERCENT_QUANTUM = Decimal("0.01")

# (tên cột, nhãn hiển thị trong audit). Thứ tự này là thứ tự các dòng `changes[]`.
SETTINGS_FIELD_LABELS: tuple[tuple[str, str], ...] = (
    ("is_enabled", "Bật thông báo biến động giá"),
    ("anomaly_enabled", "Bật thông báo giá bất thường"),
    ("reference_working_days", "Số ngày làm việc tham chiếu"),
    ("light_from_percent", "Ngưỡng Nhẹ từ (%)"),
    ("medium_from_percent", "Ngưỡng Trung bình từ (%)"),
    ("large_over_percent", "Ngưỡng Lớn trên (%)"),
    ("anomaly_percent", "Ngưỡng giá bất thường (%)"),
    ("anomaly_lookback_days", "Số ngày xét giá bất thường"),
    ("max_trigger_delay_working_days", "Trễ tối đa của nguồn kích hoạt (ngày làm việc)"),
    ("staff_lookback_days", "Số ngày nhân viên được xem là đã nhập vật tư"),
    ("dedupe_window_days", "Cửa sổ chống lặp (ngày)"),
    ("immediate_cap_per_scan", "Trần tin gửi ngay mỗi lần quét"),
    ("digest_hour_local", "Giờ bản tin tổng hợp"),
    ("reference_fallback_days", "Số ngày tối đa của gốc dự phòng"),
)

_PERCENT_FIELDS = frozenset(
    {
        "light_from_percent",
        "medium_from_percent",
        "large_over_percent",
        "anomaly_percent",
    },
)


@dataclass(frozen=True, slots=True)
class PriceAlertSettingsValues:
    is_enabled: bool
    reference_working_days: int
    light_from_percent: Decimal
    medium_from_percent: Decimal
    large_over_percent: Decimal
    anomaly_percent: Decimal
    anomaly_lookback_days: int
    max_trigger_delay_working_days: int
    staff_lookback_days: int
    dedupe_window_days: int
    immediate_cap_per_scan: int
    digest_hour_local: int
    reference_fallback_days: int = 30
    anomaly_enabled: bool = False


@dataclass(frozen=True, slots=True)
class PriceAlertSettingsUpdate:
    setting: PriceAlertSetting
    scan_state: PriceAlertScanState
    changes: list[dict[str, str]]


class PriceAlertSettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_settings(self, *, for_update: bool = False) -> PriceAlertSetting:
        statement = select(PriceAlertSetting).where(PriceAlertSetting.singleton_key == "default")
        if for_update:
            statement = statement.with_for_update()
        setting = (await self.session.execute(statement)).scalar_one_or_none()
        if setting is not None:
            return setting

        setting = PriceAlertSetting(singleton_key="default")
        self.session.add(setting)
        await self.session.flush()
        return setting

    async def get_or_create_scan_state(self, *, for_update: bool = False) -> PriceAlertScanState:
        statement = select(PriceAlertScanState).where(
            PriceAlertScanState.singleton_key == "default",
        )
        if for_update:
            statement = statement.with_for_update()
        scan_state = (await self.session.execute(statement)).scalar_one_or_none()
        if scan_state is not None:
            return scan_state

        scan_state = PriceAlertScanState(singleton_key="default")
        self.session.add(scan_state)
        await self.session.flush()
        return scan_state

    async def update_settings(
        self,
        *,
        values: PriceAlertSettingsValues,
        updated_by_id: UUID,
        now: datetime | None = None,
    ) -> PriceAlertSettingsUpdate:
        validate_threshold_order(
            light=values.light_from_percent,
            medium=values.medium_from_percent,
            large=values.large_over_percent,
            anomaly=values.anomaly_percent,
        )
        moment = now or datetime.now(UTC)

        # Khóa dòng cấu hình để hai lần bật/tắt đồng thời không đặt watermark chồng nhau.
        setting = await self.get_or_create_settings(for_update=True)
        scan_state = await self.get_or_create_scan_state()
        was_enabled = setting.is_enabled

        changes: list[dict[str, str]] = []
        for field, label in SETTINGS_FIELD_LABELS:
            old_value = getattr(setting, field)
            new_value = _normalize(field, getattr(values, field))
            if old_value == new_value:
                continue
            changes.append(
                {
                    "field": field,
                    "label": label,
                    "old_value": _render(old_value),
                    "new_value": _render(new_value),
                },
            )
            setattr(setting, field, new_value)

        if changes:
            setting.updated_by_id = updated_by_id

        if not was_enabled and setting.is_enabled:
            # Mỗi lần bật đặt lại mốc để dữ liệu cũ không sinh tin (L13).
            scan_state = await self.get_or_create_scan_state(for_update=True)
            scan_state.watermark_confirmed_at = moment
            scan_state.enabled_since = moment

        await self.session.flush()
        return PriceAlertSettingsUpdate(setting=setting, scan_state=scan_state, changes=changes)


def validate_threshold_order(
    *,
    light: Decimal,
    medium: Decimal,
    large: Decimal,
    anomaly: Decimal,
) -> None:
    if not 0 < light < medium < large < anomaly:
        raise ValueError(
            "Ngưỡng phải tăng dần: 0 < Nhẹ < Trung bình < Lớn < Giá bất thường.",
        )


def _normalize(field: str, value: object) -> object:
    if field in _PERCENT_FIELDS and isinstance(value, Decimal):
        return value.quantize(_PERCENT_QUANTUM)
    return value


def _render(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
