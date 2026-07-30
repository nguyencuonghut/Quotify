from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.material import Material
from app.models.material_type import MaterialType
from app.models.quote import Quote
from app.models.quote_line import QuoteLine
from app.models.quote_version import QuoteVersion
from app.models.supplier import Supplier
from app.models.user import User


class QuoteQueryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _apply_filters(
        self,
        stmt: Any,
        *,
        global_search: str | None = None,
        material_type_id: UUID | None = None,
        material_id: UUID | None = None,
        supplier_id: UUID | None = None,
        created_by_id: UUID | None = None,
        received_date_start: date | None = None,
        received_date_end: date | None = None,
        delivery_month: date | None = None,
        currency: str | None = None,
        purchased: bool | None = None,
    ) -> Any:
        filters = []

        if global_search:
            search_pattern = f"%{global_search}%"
            filters.append(
                or_(
                    Supplier.name.ilike(search_pattern),
                    Supplier.code.ilike(search_pattern),
                    Material.name.ilike(search_pattern),
                    Material.code.ilike(search_pattern),
                )
            )

        if material_type_id:
            filters.append(Material.material_type_id == material_type_id)

        if material_id:
            filters.append(QuoteLine.material_id == material_id)

        if supplier_id:
            filters.append(Quote.supplier_id == supplier_id)

        if created_by_id:
            filters.append(QuoteVersion.created_by_id == created_by_id)

        if received_date_start:
            filters.append(QuoteVersion.received_date >= received_date_start)

        if received_date_end:
            filters.append(QuoteVersion.received_date <= received_date_end)

        if delivery_month:
            filters.append(QuoteLine.delivery_month == delivery_month)

        if currency:
            filters.append(QuoteLine.currency == currency)

        if purchased is not None:
            if purchased:
                filters.append(QuoteLine.purchase_marked_at.is_not(None))
            else:
                filters.append(QuoteLine.purchase_marked_at.is_(None))

        if filters:
            stmt = stmt.where(*filters)

        stmt = stmt.where(QuoteVersion.status != "superseded")
        return stmt

    async def query_flattened_quotes(
        self,
        *,
        global_search: str | None = None,
        material_type_id: UUID | None = None,
        material_id: UUID | None = None,
        supplier_id: UUID | None = None,
        created_by_id: UUID | None = None,
        received_date_start: date | None = None,
        received_date_end: date | None = None,
        delivery_month: date | None = None,
        currency: str | None = None,
        purchased: bool | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        limit = max(1, min(limit, 100))
        offset = max(0, offset)

        # base query selecting fields to build QuoteFlattenedResponse
        stmt = (
            select(
                QuoteLine.id,
                Quote.id.label("quote_id"),
                QuoteVersion.id.label("quote_version_id"),
                Supplier.id.label("supplier_id"),
                Supplier.name.label("supplier_name"),
                Supplier.code.label("supplier_code"),
                Material.id.label("material_id"),
                Material.name.label("material_name"),
                Material.code.label("material_code"),
                MaterialType.name.label("material_type_name"),
                MaterialType.code.label("material_type_code"),
                QuoteVersion.received_date,
                QuoteLine.delivery_month,
                QuoteLine.price_original,
                QuoteLine.currency,
                QuoteLine.unit,
                QuoteLine.exchange_rate,
                QuoteLine.exchange_rate_source,
                QuoteLine.conversion_cost_vnd_per_kg,
                QuoteLine.price_converted_vnd_per_kg,
                QuoteLine.purchase_marked_at,
                QuoteVersion.version_number,
                QuoteVersion.status.label("version_status"),
                User.full_name.label("created_by_name"),
                QuoteLine.created_at,
            )
            .join(QuoteVersion, QuoteLine.quote_version_id == QuoteVersion.id)
            .join(Quote, QuoteVersion.quote_id == Quote.id)
            .join(Supplier, Quote.supplier_id == Supplier.id)
            .join(Material, QuoteLine.material_id == Material.id)
            .join(MaterialType, Material.material_type_id == MaterialType.id)
            .outerjoin(User, QuoteVersion.created_by_id == User.id)
        )

        stmt = self._apply_filters(
            stmt,
            global_search=global_search,
            material_type_id=material_type_id,
            material_id=material_id,
            supplier_id=supplier_id,
            created_by_id=created_by_id,
            received_date_start=received_date_start,
            received_date_end=received_date_end,
            delivery_month=delivery_month,
            currency=currency,
            purchased=purchased,
        )

        count_stmt = (
            select(func.count(QuoteLine.id))
            .join(QuoteVersion, QuoteLine.quote_version_id == QuoteVersion.id)
            .join(Quote, QuoteVersion.quote_id == Quote.id)
            .join(Supplier, Quote.supplier_id == Supplier.id)
            .join(Material, QuoteLine.material_id == Material.id)
            .join(MaterialType, Material.material_type_id == MaterialType.id)
        )
        count_stmt = self._apply_filters(
            count_stmt,
            global_search=global_search,
            material_type_id=material_type_id,
            material_id=material_id,
            supplier_id=supplier_id,
            created_by_id=created_by_id,
            received_date_start=received_date_start,
            received_date_end=received_date_end,
            delivery_month=delivery_month,
            currency=currency,
            purchased=purchased,
        )
        total = (await self.db.execute(count_stmt)).scalar() or 0

        # Apply sorting
        sort_by_map = {
            "received_date": QuoteVersion.received_date,
            "delivery_month": QuoteLine.delivery_month,
            "supplier_name": Supplier.name,
            "material_name": Material.name,
            "price_original": QuoteLine.price_original,
            "price_converted_vnd_per_kg": QuoteLine.price_converted_vnd_per_kg,
            "version_number": QuoteVersion.version_number,
            "created_at": QuoteLine.created_at,
        }

        sort_col = sort_by_map.get(sort_by, QuoteLine.created_at)
        if sort_order == "desc":
            stmt = stmt.order_by(desc(sort_col), desc(QuoteLine.id))
        else:
            stmt = stmt.order_by(asc(sort_col), asc(QuoteLine.id))

        # Apply pagination
        stmt = stmt.offset(offset).limit(limit)

        result = await self.db.execute(stmt)
        # Parse result into list of dicts for schema validation
        items = []
        for row in result.all():
            items.append({
                "id": row.id,
                "quote_id": row.quote_id,
                "quote_version_id": row.quote_version_id,
                "supplier_id": row.supplier_id,
                "supplier_name": row.supplier_name,
                "supplier_code": row.supplier_code,
                "material_id": row.material_id,
                "material_name": row.material_name,
                "material_code": row.material_code,
                "material_type_name": row.material_type_name,
                "material_type_code": row.material_type_code,
                "received_date": row.received_date,
                "delivery_month": row.delivery_month,
                "price_original": row.price_original,
                "currency": row.currency,
                "unit": row.unit,
                "exchange_rate": row.exchange_rate,
                "exchange_rate_source": row.exchange_rate_source,
                "conversion_cost_vnd_per_kg": row.conversion_cost_vnd_per_kg,
                "price_converted_vnd_per_kg": row.price_converted_vnd_per_kg,
                "purchased": row.purchase_marked_at is not None,
                "version_number": row.version_number,
                "version_status": row.version_status,
                "created_by_name": row.created_by_name,
                "created_at": row.created_at,
            })

        return items, total
