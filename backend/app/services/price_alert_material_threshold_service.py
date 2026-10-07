from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Material, PriceAlertMaterialThreshold, PriceFreshnessMaterial
from app.services.price_alert_settings_service import PriceAlertSettingsService

_PERCENT_QUANTUM = Decimal("0.01")
DEFAULT_LABEL = "mặc định"

THRESHOLD_FIELD_LABELS: tuple[tuple[str, str], ...] = (
    ("light_from_percent", "Ngưỡng Nhẹ từ (%)"),
    ("medium_from_percent", "Ngưỡng Trung bình từ (%)"),
    ("large_over_percent", "Ngưỡng Lớn trên (%)"),
    ("anomaly_percent", "Ngưỡng giá bất thường (%)"),
)


FRESHNESS_NOT_CONFIGURED = "chưa cấu hình"
FRESHNESS_MIN_INTERVAL_DAYS = 1
FRESHNESS_MAX_INTERVAL_DAYS = 365


class MaterialNotFoundError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class ThresholdOverride:
    light_from_percent: Decimal
    medium_from_percent: Decimal
    large_over_percent: Decimal
    anomaly_percent: Decimal | None


@dataclass(frozen=True, slots=True)
class EffectiveThresholds:
    light_from_percent: Decimal
    medium_from_percent: Decimal
    large_over_percent: Decimal
    anomaly_percent: Decimal


@dataclass(frozen=True, slots=True)
class FreshnessConfig:
    is_watched: bool
    expected_interval_days: int


@dataclass(frozen=True, slots=True)
class MaterialThresholdView:
    material_id: UUID
    code: str
    name: str
    override: ThresholdOverride | None
    effective: EffectiveThresholds
    freshness: FreshnessConfig | None = None


@dataclass(frozen=True, slots=True)
class MaterialThresholdPage:
    items: list[MaterialThresholdView]
    total: int


@dataclass(frozen=True, slots=True)
class MaterialThresholdChange:
    view: MaterialThresholdView
    changes: list[dict[str, str]]


@dataclass(frozen=True, slots=True)
class FreshnessChange:
    material_id: UUID
    code: str
    config: FreshnessConfig
    changes: list[dict[str, str]]


class PriceAlertMaterialThresholdService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_materials(
        self,
        *,
        limit: int,
        offset: int,
        search: str | None,
        sort: str = "code",
        descending: bool = False,
    ) -> MaterialThresholdPage:
        defaults = await self._default_thresholds()
        term = (search or "").strip()
        count_statement = select(func.count()).select_from(Material)
        statement = (
            select(Material, PriceAlertMaterialThreshold, PriceFreshnessMaterial)
            .outerjoin(
                PriceAlertMaterialThreshold,
                PriceAlertMaterialThreshold.material_id == Material.id,
            )
            .outerjoin(
                PriceFreshnessMaterial,
                PriceFreshnessMaterial.material_id == Material.id,
            )
            .order_by(*_order_by(sort, descending))
            .limit(limit)
            .offset(offset)
        )
        if term:
            pattern = f"%{_escape_like(term)}%"
            condition = or_(
                Material.code.ilike(pattern, escape="\\"),
                Material.name.ilike(pattern, escape="\\"),
            )
            count_statement = count_statement.where(condition)
            statement = statement.where(condition)

        total = (await self.session.execute(count_statement)).scalar_one()
        rows = (await self.session.execute(statement)).all()
        items = [
            _build_view(material, row, defaults, freshness) for material, row, freshness in rows
        ]
        return MaterialThresholdPage(items=items, total=total)

    async def set_override(
        self,
        *,
        material_id: UUID,
        light: Decimal,
        medium: Decimal,
        large: Decimal,
        anomaly: Decimal | None,
        updated_by_id: UUID,
    ) -> MaterialThresholdChange:
        material = await self._get_material(material_id)
        defaults = await self._default_thresholds()
        new = ThresholdOverride(
            light_from_percent=light.quantize(_PERCENT_QUANTUM),
            medium_from_percent=medium.quantize(_PERCENT_QUANTUM),
            large_over_percent=large.quantize(_PERCENT_QUANTUM),
            anomaly_percent=anomaly.quantize(_PERCENT_QUANTUM) if anomaly is not None else None,
        )
        validate_override(new, default_anomaly=defaults.anomaly_percent)

        old = _to_override(await self._get_row(material_id, for_update=True))
        statement = pg_insert(PriceAlertMaterialThreshold).values(
            material_id=material_id,
            light_from_percent=new.light_from_percent,
            medium_from_percent=new.medium_from_percent,
            large_over_percent=new.large_over_percent,
            anomaly_percent=new.anomaly_percent,
            updated_by_id=updated_by_id,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[PriceAlertMaterialThreshold.material_id],
            set_={
                "light_from_percent": statement.excluded.light_from_percent,
                "medium_from_percent": statement.excluded.medium_from_percent,
                "large_over_percent": statement.excluded.large_over_percent,
                "anomaly_percent": statement.excluded.anomaly_percent,
                "updated_by_id": statement.excluded.updated_by_id,
                "updated_at": func.now(),
            },
        )
        await self.session.execute(statement)
        await self.session.flush()

        view = MaterialThresholdView(
            material_id=material.id,
            code=material.code,
            name=material.name,
            override=new,
            effective=_effective(new, defaults),
        )
        return MaterialThresholdChange(view=view, changes=_diff(old, new))

    async def clear_override(self, *, material_id: UUID) -> list[dict[str, str]]:
        """Bỏ ghi đè; idempotent. Trả về `changes[]` (rỗng nếu vốn không có ghi đè)."""
        old_row = await self._get_row(material_id, for_update=True)
        if old_row is None:
            return []
        old = _to_override(old_row)
        await self.session.execute(
            delete(PriceAlertMaterialThreshold).where(
                PriceAlertMaterialThreshold.material_id == material_id,
            ),
        )
        await self.session.flush()
        return _diff(old, None)

    async def set_freshness(
        self,
        *,
        material_id: UUID,
        is_watched: bool,
        expected_interval_days: int,
        updated_by_id: UUID,
    ) -> FreshnessChange:
        """Đặt theo dõi độ mới của giá cho một vật tư; không đụng tới ngưỡng biến động giá."""
        if not (
            FRESHNESS_MIN_INTERVAL_DAYS <= expected_interval_days <= FRESHNESS_MAX_INTERVAL_DAYS
        ):
            raise ValueError("Chu kỳ kỳ vọng phải từ 1 đến 365 ngày.")
        material = await self._get_material(material_id)
        old = _to_freshness(await self._get_freshness_row(material_id, for_update=True))
        new = FreshnessConfig(is_watched=is_watched, expected_interval_days=expected_interval_days)
        statement = pg_insert(PriceFreshnessMaterial).values(
            material_id=material_id,
            is_watched=new.is_watched,
            expected_interval_days=new.expected_interval_days,
            updated_by_id=updated_by_id,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[PriceFreshnessMaterial.material_id],
            set_={
                "is_watched": statement.excluded.is_watched,
                "expected_interval_days": statement.excluded.expected_interval_days,
                "updated_by_id": statement.excluded.updated_by_id,
                "updated_at": func.now(),
            },
        )
        await self.session.execute(statement)
        await self.session.flush()
        return FreshnessChange(
            material_id=material.id,
            code=material.code,
            config=new,
            changes=_freshness_diff(old, new),
        )

    async def clear_freshness(self, *, material_id: UUID) -> list[dict[str, str]]:
        """Bỏ cấu hình theo dõi; idempotent. Trả về `changes[]` (rỗng nếu vốn không có)."""
        old_row = await self._get_freshness_row(material_id, for_update=True)
        if old_row is None:
            return []
        old = _to_freshness(old_row)
        await self.session.execute(
            delete(PriceFreshnessMaterial).where(
                PriceFreshnessMaterial.material_id == material_id,
            ),
        )
        await self.session.flush()
        return _freshness_diff(old, None)

    async def _get_freshness_row(
        self,
        material_id: UUID,
        *,
        for_update: bool = False,
    ) -> PriceFreshnessMaterial | None:
        statement = select(PriceFreshnessMaterial).where(
            PriceFreshnessMaterial.material_id == material_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def _get_material(self, material_id: UUID) -> Material:
        material = (
            await self.session.execute(select(Material).where(Material.id == material_id))
        ).scalar_one_or_none()
        if material is None:
            raise MaterialNotFoundError(str(material_id))
        return material

    async def _get_row(
        self,
        material_id: UUID,
        *,
        for_update: bool = False,
    ) -> PriceAlertMaterialThreshold | None:
        statement = select(PriceAlertMaterialThreshold).where(
            PriceAlertMaterialThreshold.material_id == material_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def _default_thresholds(self) -> EffectiveThresholds:
        setting = await PriceAlertSettingsService(self.session).get_or_create_settings()
        return EffectiveThresholds(
            light_from_percent=setting.light_from_percent,
            medium_from_percent=setting.medium_from_percent,
            large_over_percent=setting.large_over_percent,
            anomaly_percent=setting.anomaly_percent,
        )


def validate_override(override: ThresholdOverride, *, default_anomaly: Decimal) -> None:
    light = override.light_from_percent
    if not 0 < light < override.medium_from_percent < override.large_over_percent:
        raise ValueError("Ngưỡng phải tăng dần: 0 < Nhẹ < Trung bình < Lớn.")
    anomaly = override.anomaly_percent if override.anomaly_percent is not None else default_anomaly
    if anomaly <= override.large_over_percent:
        raise ValueError("Ngưỡng giá bất thường phải lớn hơn ngưỡng Lớn.")


def _effective(
    override: ThresholdOverride | None,
    defaults: EffectiveThresholds,
) -> EffectiveThresholds:
    if override is None:
        return defaults
    return EffectiveThresholds(
        light_from_percent=override.light_from_percent,
        medium_from_percent=override.medium_from_percent,
        large_over_percent=override.large_over_percent,
        anomaly_percent=(
            override.anomaly_percent
            if override.anomaly_percent is not None
            else defaults.anomaly_percent
        ),
    )


def _to_override(row: PriceAlertMaterialThreshold | None) -> ThresholdOverride | None:
    if (
        row is None
        or row.light_from_percent is None
        or row.medium_from_percent is None
        or row.large_over_percent is None
    ):
        return None
    return ThresholdOverride(
        light_from_percent=row.light_from_percent,
        medium_from_percent=row.medium_from_percent,
        large_over_percent=row.large_over_percent,
        anomaly_percent=row.anomaly_percent,
    )


def _to_freshness(row: PriceFreshnessMaterial | None) -> FreshnessConfig | None:
    if row is None:
        return None
    return FreshnessConfig(
        is_watched=row.is_watched,
        expected_interval_days=row.expected_interval_days,
    )


def _freshness_diff(
    old: FreshnessConfig | None,
    new: FreshnessConfig | None,
) -> list[dict[str, str]]:
    def watched_text(config: FreshnessConfig | None) -> str:
        if config is None:
            return FRESHNESS_NOT_CONFIGURED
        return "có" if config.is_watched else "không"

    def interval_text(config: FreshnessConfig | None) -> str:
        return FRESHNESS_NOT_CONFIGURED if config is None else str(config.expected_interval_days)

    changes: list[dict[str, str]] = []
    for field, label, render in (
        ("is_watched", "Theo dõi độ mới của giá", watched_text),
        ("expected_interval_days", "Chu kỳ kỳ vọng (ngày)", interval_text),
    ):
        old_text, new_text = render(old), render(new)
        if old_text != new_text:
            changes.append(
                {"field": field, "label": label, "old_value": old_text, "new_value": new_text},
            )
    return changes


def _build_view(
    material: Material,
    row: PriceAlertMaterialThreshold | None,
    defaults: EffectiveThresholds,
    freshness_row: PriceFreshnessMaterial | None = None,
) -> MaterialThresholdView:
    override = _to_override(row)
    return MaterialThresholdView(
        material_id=material.id,
        code=material.code,
        name=material.name,
        override=override,
        effective=_effective(override, defaults),
        freshness=_to_freshness(freshness_row),
    )


def _diff(
    old: ThresholdOverride | None,
    new: ThresholdOverride | None,
) -> list[dict[str, str]]:
    changes: list[dict[str, str]] = []
    for field, label in THRESHOLD_FIELD_LABELS:
        old_value = getattr(old, field) if old is not None else None
        new_value = getattr(new, field) if new is not None else None
        if old_value == new_value:
            continue
        changes.append(
            {
                "field": field,
                "label": label,
                "old_value": DEFAULT_LABEL if old_value is None else str(old_value),
                "new_value": DEFAULT_LABEL if new_value is None else str(new_value),
            },
        )
    return changes


def _order_by(sort: str, descending: bool) -> list[Any]:
    """Thứ tự danh sách; luôn kết thúc bằng mã và id để phân trang ổn định khi giá trị trùng."""
    if sort == "code":
        primary: list[Any] = []
    elif sort == "name":
        primary = [Material.name.desc() if descending else Material.name.asc()]
    elif sort == "interval":
        column = PriceFreshnessMaterial.expected_interval_days
        # Vật tư chưa đặt chu kỳ luôn nằm cuối, kể cả khi sắp giảm dần.
        primary = [(column.desc() if descending else column.asc()).nulls_last()]
    else:
        raise ValueError("Khóa sắp xếp không hợp lệ.")
    tail = (
        [Material.code.desc(), Material.id.desc()] if descending else [Material.code, Material.id]
    )
    return [*primary, *tail]


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
