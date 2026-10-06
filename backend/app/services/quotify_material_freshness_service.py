"""Độ mới của giá theo vật tư trong một tuần (Telegram 1D).

Một "lần cập nhật" của vật tư là một phiên bản phiếu hợp lệ (đã chốt, `confirmed_at` có giá trị,
phiếu chưa hủy) có dòng của vật tư đó và `received_date` nằm trong tuần. Mọi mốc ngày đều tính
đến `as_of = min(hôm nay, chủ nhật của tuần)` nên xem lại tuần cũ cho đúng trạng thái lúc ấy.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Material,
    MaterialType,
    PriceFreshnessMaterial,
    Quote,
    QuoteLine,
    QuoteVersion,
    User,
)
from app.services.quotify_dashboard_service import BUSINESS_TIMEZONE, normalize_week_start

FreshnessStatus = Literal["updated", "on_time", "overdue", "never"]


def classify_freshness(
    *,
    update_count: int,
    expected_interval_days: int | None,
    age_days: int | None,
) -> FreshnessStatus:
    """`updated`: có cập nhật trong tuần; `never`: chưa từng có giá; `overdue`: quá chu kỳ."""
    if update_count > 0:
        return "updated"
    if age_days is None:
        return "never"
    if expected_interval_days is not None and age_days > expected_interval_days:
        return "overdue"
    return "on_time"


class QuotifyMaterialFreshnessService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_material_freshness(
        self,
        *,
        week_start: date | None = None,
        today: date | None = None,
    ) -> dict[str, Any]:
        today_local = today or datetime.now(BUSINESS_TIMEZONE).date()
        normalized_week_start = normalize_week_start(week_start or today_local)
        week_end = normalized_week_start + timedelta(days=6)
        as_of = min(today_local, week_end)

        config = await self._load_config()
        week_counts = await self._week_counts(normalized_week_start, as_of)
        candidate_ids = {mid for mid, (watched, _) in config.items() if watched} | set(week_counts)

        materials = await self._load_materials(candidate_ids)
        latest = await self._load_latest_received(set(materials), as_of)

        items = [
            self._build_item(material, config.get(material.id), week_counts, latest, as_of)
            for material in materials.values()
        ]
        return {
            "week_start": normalized_week_start,
            "week_end": week_end,
            "as_of_date": as_of,
            "summary": self._summarize(items),
            "items": items,
        }

    def _valid_quote_filters(self) -> list[Any]:
        """Phiếu hợp lệ: cùng bộ điều kiện với các truy vấn Dashboard theo `received_date`."""
        return [
            QuoteVersion.status == "confirmed",
            QuoteVersion.confirmed_at.is_not(None),
            Quote.cancelled_at.is_(None),
        ]

    async def _load_config(self) -> dict[UUID, tuple[bool, int]]:
        rows = await self.db.execute(
            select(
                PriceFreshnessMaterial.material_id,
                PriceFreshnessMaterial.is_watched,
                PriceFreshnessMaterial.expected_interval_days,
            ),
        )
        return {row.material_id: (row.is_watched, row.expected_interval_days) for row in rows}

    async def _week_counts(self, week_start: date, as_of: date) -> dict[UUID, tuple[int, int]]:
        rows = await self.db.execute(
            select(
                QuoteLine.material_id,
                func.count(distinct(QuoteVersion.id)).label("update_count"),
                func.count(distinct(Quote.supplier_id)).label("supplier_count"),
            )
            .select_from(QuoteLine)
            .join(QuoteVersion, QuoteLine.quote_version_id == QuoteVersion.id)
            .join(Quote, QuoteVersion.quote_id == Quote.id)
            .where(
                *self._valid_quote_filters(),
                QuoteVersion.received_date >= week_start,
                QuoteVersion.received_date <= as_of,
            )
            .group_by(QuoteLine.material_id),
        )
        return {row.material_id: (int(row.update_count), int(row.supplier_count)) for row in rows}

    async def _load_materials(self, material_ids: set[UUID]) -> dict[UUID, Any]:
        if not material_ids:
            return {}
        rows = await self.db.execute(
            select(
                Material.id,
                Material.code,
                Material.name,
                Material.material_type_id,
                MaterialType.name.label("material_type_name"),
            )
            .join(MaterialType, Material.material_type_id == MaterialType.id)
            .where(Material.status == "active", Material.id.in_(material_ids))
            .order_by(Material.name.asc(), Material.code.asc()),
        )
        return {row.id: row for row in rows}

    async def _load_latest_received(self, material_ids: set[UUID], as_of: date) -> dict[UUID, Any]:
        """Ngày nhận gần nhất tới `as_of` và người tạo phiếu của phiên bản đó (mỗi vật tư một)."""
        if not material_ids:
            return {}
        rows = await self.db.execute(
            select(
                QuoteLine.material_id,
                QuoteVersion.received_date,
                Quote.created_by_id,
                User.full_name,
                User.email,
            )
            .select_from(QuoteLine)
            .join(QuoteVersion, QuoteLine.quote_version_id == QuoteVersion.id)
            .join(Quote, QuoteVersion.quote_id == Quote.id)
            .outerjoin(User, Quote.created_by_id == User.id)
            .where(
                *self._valid_quote_filters(),
                QuoteLine.material_id.in_(material_ids),
                QuoteVersion.received_date <= as_of,
            )
            .distinct(QuoteLine.material_id)
            .order_by(
                QuoteLine.material_id,
                QuoteVersion.received_date.desc(),
                QuoteVersion.confirmed_at.desc(),
                QuoteVersion.id.desc(),
            ),
        )
        return {row.material_id: row for row in rows}

    def _build_item(
        self,
        material: Any,
        config: tuple[bool, int] | None,
        week_counts: dict[UUID, tuple[int, int]],
        latest: dict[UUID, Any],
        as_of: date,
    ) -> dict[str, Any]:
        is_watched = config is not None and config[0]
        interval = config[1] if is_watched and config is not None else None
        update_count, supplier_count = week_counts.get(material.id, (0, 0))
        last = latest.get(material.id)
        last_received = last.received_date if last is not None else None
        age_days = (as_of - last_received).days if last_received is not None else None
        enterer_label = (last.full_name or last.email) if last is not None else None
        return {
            "material_id": material.id,
            "material_code": material.code,
            "material_name": material.name,
            "material_type_id": material.material_type_id,
            "material_type_name": material.material_type_name,
            "is_watched": is_watched,
            "expected_interval_days": interval,
            "update_count": update_count,
            "supplier_count": supplier_count,
            "last_received_date": last_received,
            "age_days": age_days,
            "status": classify_freshness(
                update_count=update_count,
                expected_interval_days=interval,
                age_days=age_days,
            ),
            "last_enterer_id": last.created_by_id if last is not None else None,
            "last_enterer_label": enterer_label,
        }

    def _summarize(self, items: list[dict[str, Any]]) -> dict[str, int]:
        watched = [item for item in items if item["is_watched"]]
        return {
            "watched_count": len(watched),
            "updated_count": sum(1 for item in watched if item["status"] == "updated"),
            "on_time_count": sum(1 for item in watched if item["status"] == "on_time"),
            "overdue_count": sum(1 for item in watched if item["status"] in ("overdue", "never")),
            "unwatched_updated_count": sum(
                1 for item in items if not item["is_watched"] and item["update_count"] > 0
            ),
        }
