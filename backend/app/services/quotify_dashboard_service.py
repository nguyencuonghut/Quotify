from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import case, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.material import Material
from app.models.quote import Quote
from app.models.quote_line import QuoteLine
from app.models.quote_version import QuoteVersion
from app.models.supplier import Supplier
from app.models.user import User, UserStatus

BUSINESS_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


class QuotifyDashboardService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_entry_kpis(
        self,
        *,
        material_id: UUID | None = None,
        delivery_month: date | None = None,
        received_date_start: date | None = None,
        received_date_end: date | None = None,
        supplier_type: str | None = None,
    ) -> dict[str, Any]:
        filters = self._build_common_filters(
            material_id=material_id,
            delivery_month=delivery_month,
            received_date_start=received_date_start,
            received_date_end=received_date_end,
            supplier_type=supplier_type,
        )

        total_stmt = (
            select(func.count(distinct(Quote.id)).label("total_quote_count"))
            .select_from(QuoteLine)
            .join(QuoteVersion, QuoteLine.quote_version_id == QuoteVersion.id)
            .join(Quote, QuoteVersion.quote_id == Quote.id)
            .join(Supplier, Quote.supplier_id == Supplier.id)
            .where(*filters)
        )
        total_row = (await self.db.execute(total_stmt)).first()
        total_quote_count = int(total_row.total_quote_count or 0) if total_row else 0

        user_stmt = (
            select(
                Quote.created_by_id.label("user_id"),
                User.email.label("user_email"),
                User.full_name.label("user_full_name"),
                func.count(distinct(Quote.id)).label("quote_count"),
            )
            .select_from(QuoteLine)
            .join(QuoteVersion, QuoteLine.quote_version_id == QuoteVersion.id)
            .join(Quote, QuoteVersion.quote_id == Quote.id)
            .join(Supplier, Quote.supplier_id == Supplier.id)
            .outerjoin(User, Quote.created_by_id == User.id)
            .where(*filters)
            .group_by(Quote.created_by_id, User.email, User.full_name)
            .order_by(
                func.count(distinct(Quote.id)).desc(),
                User.full_name.asc().nullslast(),
                User.email.asc().nullslast(),
            )
        )
        result = await self.db.execute(user_stmt)

        return {
            "total_quote_count": total_quote_count,
            "user_kpis": [
                {
                    "user_id": row.user_id,
                    "user_email": row.user_email,
                    "user_full_name": row.user_full_name,
                    "user_label": self._user_label(row.user_full_name, row.user_email),
                    "quote_count": int(row.quote_count or 0),
                }
                for row in result.all()
            ],
        }

    async def get_price_trends(
        self,
        *,
        material_id: UUID | None = None,
        delivery_month: date | None = None,
        received_date_start: date | None = None,
        received_date_end: date | None = None,
        supplier_type: str | None = None,
        point_limit: int = 500,
    ) -> dict[str, Any]:
        filters = self._build_common_filters(
            material_id=material_id,
            delivery_month=delivery_month,
            received_date_start=received_date_start,
            received_date_end=received_date_end,
            supplier_type=supplier_type,
        )

        summary = await self._get_summary(filters)
        points = await self._get_points(filters, point_limit=point_limit)
        purchase_contexts = [
            await self._build_purchase_context(
                point=point,
                received_date_start=received_date_start,
                received_date_end=received_date_end,
                supplier_type=supplier_type,
            )
            for point in points
            if point["purchased"] and point["purchase_marked_at"] is not None
        ]

        return {
            "summary": summary,
            "points": points,
            "purchase_contexts": purchase_contexts,
        }

    async def get_weekly_entry_activity(
        self,
        *,
        week_start: date | None = None,
        user_id: UUID | None = None,
    ) -> dict[str, Any]:
        normalized_week_start = self._normalize_week_start(
            week_start or datetime.now(BUSINESS_TIMEZONE).date()
        )
        week_end = normalized_week_start + timedelta(days=6)
        start_at = datetime.combine(
            normalized_week_start,
            time.min,
            tzinfo=BUSINESS_TIMEZONE,
        )
        end_exclusive = datetime.combine(
            week_end + timedelta(days=1),
            time.min,
            tzinfo=BUSINESS_TIMEZONE,
        )

        quote_counts = (
            select(
                Quote.created_by_id.label("user_id"),
                func.count(distinct(Quote.id)).label("quote_count"),
                func.max(Quote.created_at).label("last_quote_created_at"),
            )
            .select_from(Quote)
            .join(QuoteVersion, QuoteVersion.quote_id == Quote.id)
            .where(
                QuoteVersion.status == "confirmed",
                Quote.created_at >= start_at,
                Quote.created_at < end_exclusive,
            )
            .group_by(Quote.created_by_id)
            .subquery()
        )

        stmt = (
            select(
                User.id.label("user_id"),
                User.email.label("user_email"),
                User.full_name.label("user_full_name"),
                func.coalesce(quote_counts.c.quote_count, 0).label("quote_count"),
                quote_counts.c.last_quote_created_at.label("last_quote_created_at"),
            )
            .select_from(User)
            .outerjoin(quote_counts, quote_counts.c.user_id == User.id)
            .where(User.status == UserStatus.ACTIVE)
            .order_by(
                func.coalesce(quote_counts.c.quote_count, 0).desc(),
                User.full_name.asc(),
                User.email.asc(),
            )
        )
        if user_id is not None:
            stmt = stmt.where(User.id == user_id)

        result = await self.db.execute(stmt)
        user_activities = [
            {
                "user_id": row.user_id,
                "user_email": row.user_email,
                "user_full_name": row.user_full_name,
                "user_label": self._user_label(row.user_full_name, row.user_email),
                "quote_count": int(row.quote_count or 0),
                "last_quote_created_at": row.last_quote_created_at,
                "has_warning": int(row.quote_count or 0) == 0,
            }
            for row in result.all()
        ]

        total_quote_count = sum(row["quote_count"] for row in user_activities)
        users_with_quotes = sum(1 for row in user_activities if row["quote_count"] > 0)

        return {
            "week_start": normalized_week_start,
            "week_end": week_end,
            "total_quote_count": total_quote_count,
            "active_user_count": len(user_activities),
            "users_with_quotes": users_with_quotes,
            "users_without_quotes": len(user_activities) - users_with_quotes,
            "user_activities": user_activities,
        }

    def _build_common_filters(
        self,
        *,
        material_id: UUID | None,
        delivery_month: date | None,
        received_date_start: date | None,
        received_date_end: date | None,
        supplier_type: str | None,
    ) -> list[Any]:
        filters: list[Any] = [
            QuoteVersion.status == "confirmed",
            QuoteVersion.confirmed_at.is_not(None),
        ]
        if material_id is not None:
            filters.append(QuoteLine.material_id == material_id)
        if delivery_month is not None:
            filters.append(QuoteLine.delivery_month == delivery_month)
        if received_date_start is not None:
            filters.append(QuoteVersion.received_date >= received_date_start)
        if received_date_end is not None:
            filters.append(QuoteVersion.received_date <= received_date_end)
        if supplier_type is not None:
            filters.append(self._supplier_type_contains(supplier_type))
        return filters

    def _supplier_type_contains(self, supplier_type: str) -> Any:
        return func.concat(",", Supplier.supplier_type, ",").like(f"%,{supplier_type},%")

    async def _get_summary(self, filters: list[Any]) -> dict[str, Any]:
        stmt = (
            select(
                func.min(QuoteLine.price_converted_vnd_per_kg).label("min_price"),
                func.max(QuoteLine.price_converted_vnd_per_kg).label("max_price"),
                func.avg(QuoteLine.price_converted_vnd_per_kg).label("avg_price"),
                func.count(QuoteLine.id).label("total_lines"),
                func.count(distinct(Quote.id)).label("total_quotes"),
                func.coalesce(
                    func.sum(case((QuoteLine.purchase_marked_at.is_not(None), 1), else_=0)),
                    0,
                ).label("purchased_lines"),
            )
            .select_from(QuoteLine)
            .join(QuoteVersion, QuoteLine.quote_version_id == QuoteVersion.id)
            .join(Quote, QuoteVersion.quote_id == Quote.id)
            .join(Supplier, Quote.supplier_id == Supplier.id)
            .where(*filters)
        )
        row = (await self.db.execute(stmt)).first()
        return self._summary_from_row(row)

    async def _get_points(self, filters: list[Any], *, point_limit: int) -> list[dict[str, Any]]:
        safe_limit = min(max(point_limit, 1), 1000)
        stmt = (
            select(
                QuoteVersion.received_date,
                QuoteLine.delivery_month,
                QuoteLine.price_converted_vnd_per_kg.label("converted_price_vnd_per_kg"),
                Supplier.id.label("supplier_id"),
                Supplier.name.label("supplier_name"),
                Supplier.code.label("supplier_code"),
                Supplier.supplier_type.label("supplier_type"),
                Material.id.label("material_id"),
                Material.name.label("material_name"),
                Material.code.label("material_code"),
                Quote.id.label("quote_id"),
                QuoteVersion.id.label("quote_version_id"),
                QuoteLine.id.label("line_id"),
                (QuoteLine.purchase_marked_at.is_not(None)).label("purchased"),
                QuoteLine.purchase_marked_at,
                QuoteVersion.confirmed_at,
            )
            .select_from(QuoteLine)
            .join(QuoteVersion, QuoteLine.quote_version_id == QuoteVersion.id)
            .join(Quote, QuoteVersion.quote_id == Quote.id)
            .join(Supplier, Quote.supplier_id == Supplier.id)
            .join(Material, QuoteLine.material_id == Material.id)
            .where(*filters)
            .order_by(
                QuoteVersion.received_date.asc(),
                QuoteLine.delivery_month.asc(),
                Material.name.asc(),
                Supplier.name.asc(),
                QuoteLine.id.asc(),
            )
            .limit(safe_limit)
        )
        result = await self.db.execute(stmt)
        return [self._point_from_row(row) for row in result.all()]

    async def _build_purchase_context(
        self,
        *,
        point: dict[str, Any],
        received_date_start: date | None,
        received_date_end: date | None,
        supplier_type: str | None,
    ) -> dict[str, Any]:
        purchase_marked_at = point["purchase_marked_at"]
        context_filters = self._build_common_filters(
            material_id=point["material_id"],
            delivery_month=point["delivery_month"],
            received_date_start=received_date_start,
            received_date_end=received_date_end,
            supplier_type=supplier_type,
        )
        at_purchase = await self._get_summary(
            [*context_filters, QuoteVersion.confirmed_at <= purchase_marked_at]
        )
        after_purchase = await self._get_summary(
            [*context_filters, QuoteVersion.confirmed_at > purchase_marked_at]
        )

        return {
            "purchased_line_id": point["line_id"],
            "quote_id": point["quote_id"],
            "material_id": point["material_id"],
            "delivery_month": point["delivery_month"],
            "purchase_marked_at": purchase_marked_at,
            "at_purchase": at_purchase,
            "after_purchase": after_purchase,
        }

    def _summary_from_row(self, row: Any | None) -> dict[str, Any]:
        if row is None:
            return {
                "min_price": None,
                "max_price": None,
                "avg_price": None,
                "total_lines": 0,
                "total_quotes": 0,
                "purchased_lines": 0,
            }
        return {
            "min_price": row.min_price,
            "max_price": row.max_price,
            "avg_price": row.avg_price,
            "total_lines": int(row.total_lines or 0),
            "total_quotes": int(row.total_quotes or 0),
            "purchased_lines": int(row.purchased_lines or 0),
        }

    def _point_from_row(self, row: Any) -> dict[str, Any]:
        supplier_label = (
            f"{row.supplier_name} ({row.supplier_code})" if row.supplier_code else row.supplier_name
        )
        return {
            "received_date": row.received_date,
            "delivery_month": row.delivery_month,
            "converted_price_vnd_per_kg": row.converted_price_vnd_per_kg,
            "supplier_id": row.supplier_id,
            "supplier_name": row.supplier_name,
            "supplier_code": row.supplier_code,
            "supplier_type": row.supplier_type,
            "supplier_label": supplier_label,
            "material_id": row.material_id,
            "material_name": row.material_name,
            "material_code": row.material_code,
            "quote_id": row.quote_id,
            "quote_version_id": row.quote_version_id,
            "line_id": row.line_id,
            "purchased": bool(row.purchased),
            "purchase_marked_at": row.purchase_marked_at,
            "confirmed_at": row.confirmed_at,
        }

    def _user_label(self, full_name: str | None, email: str | None) -> str:
        return full_name or email or "Không xác định"

    def _normalize_week_start(self, value: date) -> date:
        return value - timedelta(days=value.weekday())
