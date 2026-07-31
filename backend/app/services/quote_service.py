from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Quote, QuoteLine, QuoteVersion, Supplier, SupplierMaterial
from app.services.exchange_rate_service import (
    convert_usd_mt_to_vnd_kg,
    get_business_today,
    quantize_money,
)
from app.services.quote_pricing import QuotePricingService


@dataclass(frozen=True)
class DeleteDraftVersionResult:
    deleted_quote: bool
    deleted_quote_id: UUID | None
    deleted_version_id: UUID
    version_number: int
    received_date: date
    correction_reason: str | None
    line_count: int
    file_id: UUID | None
    deleted_scope: str


class QuoteService:
    def __init__(self, session: AsyncSession, pricing_service: QuotePricingService) -> None:
        self.session = session
        self.pricing_service = pricing_service

    def _get_first_day_of_month(self, value: date) -> date:
        return value.replace(day=1)

    def _parse_date_value(self, value: object) -> date:
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))

    def _get_line_snapshot_key(self, line: QuoteLine) -> tuple[UUID, date, str, str]:
        return (
            line.material_id,
            line.delivery_month,
            line.currency.upper(),
            line.unit.upper(),
        )

    def _get_line_input_snapshot_key(
        self,
        *,
        material_id: UUID,
        delivery_month: date,
        currency: str,
        unit: str,
    ) -> tuple[UUID, date, str, str]:
        return (
            material_id,
            delivery_month,
            currency.upper(),
            unit.upper(),
        )

    def _resolve_previous_snapshot_pricing(
        self,
        *,
        source_line: QuoteLine,
        currency: str,
        unit: str,
        price_original: Decimal,
    ) -> dict[str, Any] | None:
        c_upper = currency.upper()
        u_upper = unit.upper()
        if c_upper == "VND" and u_upper == "KG":
            return {
                "exchange_rate": None,
                "exchange_rate_source": None,
                "exchange_rate_source_mode": None,
                "exchange_rate_entered_at": None,
                "exchange_rate_manual_reason": None,
                "exchange_rate_actor_id": None,
                "conversion_cost_vnd_per_kg": None,
                "price_converted_vnd_per_kg": quantize_money(price_original),
            }

        if c_upper != "USD" or u_upper != "MT" or source_line.exchange_rate is None:
            return None

        conversion_cost = source_line.conversion_cost_vnd_per_kg or Decimal("0")
        return {
            "exchange_rate": source_line.exchange_rate,
            "exchange_rate_source": source_line.exchange_rate_source,
            "exchange_rate_source_mode": source_line.exchange_rate_source_mode,
            "exchange_rate_entered_at": source_line.exchange_rate_entered_at,
            "exchange_rate_manual_reason": source_line.exchange_rate_manual_reason,
            "exchange_rate_actor_id": source_line.exchange_rate_actor_id,
            "conversion_cost_vnd_per_kg": conversion_cost,
            "price_converted_vnd_per_kg": convert_usd_mt_to_vnd_kg(
                original_price_usd_per_mt=price_original,
                exchange_rate=source_line.exchange_rate,
                conversion_cost_vnd_per_kg=conversion_cost,
            ),
        }

    def _get_snapshot_pricing_for_line(
        self,
        *,
        source_snapshot_lines: dict[tuple[UUID, date, str, str], QuoteLine],
        material_id: UUID,
        delivery_month: date,
        currency: str,
        unit: str,
        price_original: Decimal,
    ) -> dict[str, Any] | None:
        snapshot_key = self._get_line_input_snapshot_key(
            material_id=material_id,
            delivery_month=delivery_month,
            currency=currency,
            unit=unit,
        )
        source_line = source_snapshot_lines.get(snapshot_key)
        if source_line is None:
            return None
        return self._resolve_previous_snapshot_pricing(
            source_line=source_line,
            currency=currency,
            unit=unit,
            price_original=price_original,
        )

    def _build_source_snapshot_lines(
        self,
        *,
        source_version: QuoteVersion | None,
        received_date: date,
    ) -> dict[tuple[UUID, date, str, str], QuoteLine]:
        if source_version is None or source_version.received_date != received_date:
            return {}
        return {
            self._get_line_snapshot_key(line): line
            for line in sorted(source_version.lines, key=lambda item: item.line_order)
        }

    def _validate_backfill(self, received_date: date, delivery_month: date, is_backfilled: bool, backfill_reason: str | None) -> None:
        today = get_business_today()
        first_day_current_month = today.replace(day=1)
        delivery_first_day = delivery_month.replace(day=1)

        is_backfill_required = (received_date < today) or (delivery_first_day < first_day_current_month)

        if is_backfill_required:
            if not is_backfilled:
                raise ValueError("Báo giá nhập lại bắt buộc phải đánh dấu nhập lùi (is_backfilled=true).")
            if not backfill_reason or not backfill_reason.strip():
                raise ValueError("Báo giá nhập lại bắt buộc phải ghi rõ lý do nhập lùi.")
        else:
            if is_backfilled:
                raise ValueError("Báo giá hiện tại không được đánh dấu nhập lùi.")

    async def _validate_supplier_materials(self, supplier_id: UUID, material_ids: list[UUID]) -> None:
        unique_mids = list(set(material_ids))
        stmt = select(SupplierMaterial.material_id).where(
            SupplierMaterial.supplier_id == supplier_id,
            SupplierMaterial.material_id.in_(unique_mids),
        )
        result = await self.session.execute(stmt)
        allowed_mids = list(result.scalars().all())
        
        missing_mids = [mid for mid in unique_mids if mid not in allowed_mids]
        if missing_mids:
            raise ValueError("Nhà cung cấp không cung cấp một số vật tư được chọn trong danh mục.")

    async def create_quote(
        self,
        *,
        supplier_id: UUID,
        received_date: date,
        is_backfilled: bool,
        backfill_reason: str | None,
        lines_data: list[dict[str, object]],
        created_by_id: UUID,
    ) -> Quote:
        # Check supplier existence
        supplier = await self.session.get(Supplier, supplier_id)
        if not supplier:
            raise ValueError("Nhà cung cấp không tồn tại.")

        # Validate lines quantity
        if not lines_data:
            raise ValueError("Báo giá phải có ít nhất một dòng vật tư.")

        material_ids = [UUID(str(line["material_id"])) for line in lines_data]
        await self._validate_supplier_materials(supplier_id, material_ids)

        # Validate backfill logic for each line
        for line in lines_data:
            delivery_m = self._parse_date_value(line["delivery_month"])
            self._validate_backfill(received_date, delivery_m, is_backfilled, backfill_reason)

        # Create Quote
        quote = Quote(
            supplier_id=supplier_id,
            created_by_id=created_by_id,
        )
        self.session.add(quote)
        await self.session.flush()

        # Create Version 1 (Draft)
        version = QuoteVersion(
            quote_id=quote.id,
            version_number=1,
            received_date=received_date,
            status="draft",
            is_backfilled=is_backfilled,
            backfill_reason=backfill_reason.strip() if backfill_reason else None,
            created_by_id=created_by_id,
        )
        self.session.add(version)
        await self.session.flush()

        # Create lines (preview calculation)
        for line_order, line in enumerate(lines_data):
            material_id = UUID(str(line["material_id"]))
            price_original = Decimal(str(line["price_original"]))
            currency = str(line["currency"])
            unit = str(line["unit"])
            delivery_month = self._parse_date_value(line["delivery_month"])
            
            manual_rate = Decimal(str(line["exchange_rate"])) if line.get("exchange_rate") is not None else None
            manual_reason = str(line["exchange_rate_manual_reason"]) if line.get("exchange_rate_manual_reason") else None

            pricing = await self.pricing_service.resolve_pricing_provenance(
                currency=currency,
                unit=unit,
                received_date=received_date,
                price_original=price_original,
                manual_rate=manual_rate,
                manual_reason=manual_reason,
                actor_id=created_by_id,
            )

            q_line = QuoteLine(
                quote_version_id=version.id,
                material_id=material_id,
                price_original=price_original,
                currency=currency,
                unit=unit,
                delivery_month=delivery_month,
                line_order=line_order,
                exchange_rate=pricing["exchange_rate"],
                exchange_rate_source=pricing["exchange_rate_source"],
                exchange_rate_source_mode=pricing["exchange_rate_source_mode"],
                exchange_rate_entered_at=pricing["exchange_rate_entered_at"],
                exchange_rate_manual_reason=pricing["exchange_rate_manual_reason"],
                exchange_rate_actor_id=pricing["exchange_rate_actor_id"],
                conversion_cost_vnd_per_kg=pricing["conversion_cost_vnd_per_kg"],
                price_converted_vnd_per_kg=pricing["price_converted_vnd_per_kg"],
            )
            self.session.add(q_line)

        await self.session.flush()
        
        # Reload to load relationships
        stmt = select(Quote).options(
            selectinload(Quote.versions).selectinload(QuoteVersion.lines).selectinload(QuoteLine.material),
            selectinload(Quote.supplier)
        ).where(Quote.id == quote.id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def create_version(
        self,
        *,
        quote_id: UUID,
        received_date: date,
        is_backfilled: bool,
        backfill_reason: str | None,
        lines_data: list[dict[str, object]],
        created_by_id: UUID,
        correction_reason: str | None = None,
    ) -> QuoteVersion:
        # Lock Quote
        result = await self.session.execute(
            select(Quote).where(Quote.id == quote_id).with_for_update()
        )
        quote = result.scalar_one_or_none()
        if not quote:
            raise ValueError("Báo giá không tồn tại.")

        # Check existing draft version
        draft_stmt = select(QuoteVersion).where(
            QuoteVersion.quote_id == quote_id,
            QuoteVersion.status == "draft",
        )
        existing_draft = (await self.session.execute(draft_stmt)).scalar_one_or_none()
        if existing_draft:
            raise ValueError("Đã tồn tại một bản nháp cho báo giá này. Vui lòng xác nhận bản nháp cũ trước.")

        confirmed_stmt = select(QuoteVersion).options(
            selectinload(QuoteVersion.lines),
        ).where(
            QuoteVersion.quote_id == quote_id,
            QuoteVersion.status == "confirmed",
        )
        confirmed_versions = (await self.session.execute(confirmed_stmt)).scalars().all()
        if confirmed_versions and not correction_reason:
            raise ValueError("Tạo bản điều chỉnh cho báo giá đã xác nhận bắt buộc phải nhập lý do điều chỉnh.")
        source_version = max(
            confirmed_versions,
            key=lambda item: item.version_number,
            default=None,
        )
        source_snapshot_lines = self._build_source_snapshot_lines(
            source_version=source_version,
            received_date=received_date,
        )

        if not lines_data:
            raise ValueError("Phiên bản báo giá phải có ít nhất một dòng vật tư.")

        material_ids = [UUID(str(line["material_id"])) for line in lines_data]
        await self._validate_supplier_materials(quote.supplier_id, material_ids)

        for line in lines_data:
            delivery_m = self._parse_date_value(line["delivery_month"])
            self._validate_backfill(received_date, delivery_m, is_backfilled, backfill_reason)

        # Get next version number
        v_num_stmt = select(func.max(QuoteVersion.version_number)).where(QuoteVersion.quote_id == quote_id)
        max_v = (await self.session.execute(v_num_stmt)).scalar() or 0
        next_v_num = max_v + 1

        version = QuoteVersion(
            quote_id=quote_id,
            version_number=next_v_num,
            received_date=received_date,
            status="draft",
            is_backfilled=is_backfilled,
            backfill_reason=backfill_reason.strip() if backfill_reason else None,
            correction_reason=correction_reason.strip() if correction_reason else None,
            created_by_id=created_by_id,
        )
        self.session.add(version)
        await self.session.flush()

        for line_order, line in enumerate(lines_data):
            material_id = UUID(str(line["material_id"]))
            price_original = Decimal(str(line["price_original"]))
            currency = str(line["currency"])
            unit = str(line["unit"])
            delivery_month = self._parse_date_value(line["delivery_month"])
            
            manual_rate = Decimal(str(line["exchange_rate"])) if line.get("exchange_rate") is not None else None
            manual_reason = str(line["exchange_rate_manual_reason"]) if line.get("exchange_rate_manual_reason") else None

            pricing = self._get_snapshot_pricing_for_line(
                source_snapshot_lines=source_snapshot_lines,
                material_id=material_id,
                delivery_month=delivery_month,
                currency=currency,
                unit=unit,
                price_original=price_original,
            )
            if pricing is None:
                pricing = await self.pricing_service.resolve_pricing_provenance(
                    currency=currency,
                    unit=unit,
                    received_date=received_date,
                    price_original=price_original,
                    manual_rate=manual_rate,
                    manual_reason=manual_reason,
                    actor_id=created_by_id,
                )

            q_line = QuoteLine(
                quote_version_id=version.id,
                material_id=material_id,
                price_original=price_original,
                currency=currency,
                unit=unit,
                delivery_month=delivery_month,
                line_order=line_order,
                exchange_rate=pricing["exchange_rate"],
                exchange_rate_source=pricing["exchange_rate_source"],
                exchange_rate_source_mode=pricing["exchange_rate_source_mode"],
                exchange_rate_entered_at=pricing["exchange_rate_entered_at"],
                exchange_rate_manual_reason=pricing["exchange_rate_manual_reason"],
                exchange_rate_actor_id=pricing["exchange_rate_actor_id"],
                conversion_cost_vnd_per_kg=pricing["conversion_cost_vnd_per_kg"],
                price_converted_vnd_per_kg=pricing["price_converted_vnd_per_kg"],
            )
            self.session.add(q_line)

        await self.session.flush()

        stmt = select(QuoteVersion).options(
            selectinload(QuoteVersion.lines).selectinload(QuoteLine.material)
        ).where(QuoteVersion.id == version.id)
        return (await self.session.execute(stmt)).scalar_one()

    async def update_draft(
        self,
        *,
        quote_id: UUID,
        version_id: UUID,
        received_date: date,
        is_backfilled: bool,
        backfill_reason: str | None,
        lines_data: list[dict[str, object]],
        updated_by_id: UUID,
        correction_reason: str | None = None,
    ) -> QuoteVersion:
        # Load and lock version
        stmt = select(QuoteVersion).where(
            QuoteVersion.id == version_id,
            QuoteVersion.quote_id == quote_id
        ).with_for_update()
        version = (await self.session.execute(stmt)).scalar_one_or_none()
        
        if not version:
            raise ValueError("Không tìm thấy phiên bản báo giá.")
        if version.status != "draft":
            raise ValueError("Chỉ được sửa đổi phiên bản ở trạng thái bản nháp (draft).")

        if not lines_data:
            raise ValueError("Báo giá phải có ít nhất một dòng vật tư.")

        # Load quote to get supplier_id
        quote = await self.session.get(Quote, quote_id)
        if not quote:
            raise ValueError("Báo giá không tồn tại.")

        material_ids = [UUID(str(line["material_id"])) for line in lines_data]
        await self._validate_supplier_materials(quote.supplier_id, material_ids)

        for line in lines_data:
            delivery_m = self._parse_date_value(line["delivery_month"])
            self._validate_backfill(received_date, delivery_m, is_backfilled, backfill_reason)

        # Update metadata
        version.received_date = received_date
        version.is_backfilled = is_backfilled
        version.backfill_reason = backfill_reason.strip() if backfill_reason else None
        version.correction_reason = correction_reason.strip() if correction_reason else None
        
        # Clear old lines
        del_stmt = delete(QuoteLine).where(QuoteLine.quote_version_id == version_id)
        await self.session.execute(del_stmt)

        # Write new lines
        for line_order, line in enumerate(lines_data):
            material_id = UUID(str(line["material_id"]))
            price_original = Decimal(str(line["price_original"]))
            currency = str(line["currency"])
            unit = str(line["unit"])
            delivery_month = self._parse_date_value(line["delivery_month"])
            
            manual_rate = Decimal(str(line["exchange_rate"])) if line.get("exchange_rate") is not None else None
            manual_reason = str(line["exchange_rate_manual_reason"]) if line.get("exchange_rate_manual_reason") else None

            pricing = await self.pricing_service.resolve_pricing_provenance(
                currency=currency,
                unit=unit,
                received_date=received_date,
                price_original=price_original,
                manual_rate=manual_rate,
                manual_reason=manual_reason,
                actor_id=updated_by_id,
            )

            q_line = QuoteLine(
                quote_version_id=version.id,
                material_id=material_id,
                price_original=price_original,
                currency=currency,
                unit=unit,
                delivery_month=delivery_month,
                line_order=line_order,
                exchange_rate=pricing["exchange_rate"],
                exchange_rate_source=pricing["exchange_rate_source"],
                exchange_rate_source_mode=pricing["exchange_rate_source_mode"],
                exchange_rate_entered_at=pricing["exchange_rate_entered_at"],
                exchange_rate_manual_reason=pricing["exchange_rate_manual_reason"],
                exchange_rate_actor_id=pricing["exchange_rate_actor_id"],
                conversion_cost_vnd_per_kg=pricing["conversion_cost_vnd_per_kg"],
                price_converted_vnd_per_kg=pricing["price_converted_vnd_per_kg"],
            )
            self.session.add(q_line)

        await self.session.flush()

        reload_stmt = select(QuoteVersion).options(
            selectinload(QuoteVersion.lines).selectinload(QuoteLine.material)
        ).where(QuoteVersion.id == version.id)
        return (await self.session.execute(reload_stmt)).scalar_one()

    async def confirm_version(
        self,
        *,
        quote_id: UUID,
        version_id: UUID,
        confirmed_by_id: UUID,
    ) -> QuoteVersion:
        # Load and lock version
        stmt = select(QuoteVersion).where(
            QuoteVersion.id == version_id,
            QuoteVersion.quote_id == quote_id
        ).with_for_update()
        version = (await self.session.execute(stmt)).scalar_one_or_none()
        
        if not version:
            raise ValueError("Không tìm thấy phiên bản báo giá.")
        if version.status == "confirmed":
            # Idempotency: return if already confirmed
            reload_stmt = select(QuoteVersion).options(
                selectinload(QuoteVersion.lines).selectinload(QuoteLine.material)
            ).where(QuoteVersion.id == version.id)
            return (await self.session.execute(reload_stmt)).scalar_one()

        superseded_stmt = select(QuoteVersion).options(
            selectinload(QuoteVersion.lines),
        ).where(
            QuoteVersion.quote_id == quote_id,
            QuoteVersion.status == "confirmed",
            QuoteVersion.id != version.id,
        )
        superseded_versions = (await self.session.execute(superseded_stmt)).scalars().all()
        if superseded_versions and not version.correction_reason:
            raise ValueError("Xác nhận bản điều chỉnh bắt buộc phải có lý do điều chỉnh.")
        source_version = max(
            superseded_versions,
            key=lambda item: item.version_number,
            default=None,
        )
        source_snapshot_lines = self._build_source_snapshot_lines(
            source_version=source_version,
            received_date=version.received_date,
        )

        # Load lines to calculate and freeze pricing
        lines_stmt = (
            select(QuoteLine)
            .where(QuoteLine.quote_version_id == version_id)
            .order_by(QuoteLine.line_order.asc())
        )
        lines = (await self.session.execute(lines_stmt)).scalars().all()

        for line in lines:
            pricing: dict[str, Any] | None = self._get_snapshot_pricing_for_line(
                source_snapshot_lines=source_snapshot_lines,
                material_id=line.material_id,
                delivery_month=line.delivery_month,
                currency=line.currency,
                unit=line.unit,
                price_original=line.price_original,
            )
            if pricing is None:
                pricing = cast(
                    dict[str, Any],
                    await self.pricing_service.resolve_pricing_provenance(
                        currency=line.currency,
                        unit=line.unit,
                        received_date=version.received_date,
                        price_original=line.price_original,
                        manual_rate=line.exchange_rate,
                        manual_reason=line.exchange_rate_manual_reason,
                        actor_id=line.exchange_rate_actor_id or confirmed_by_id,
                    ),
                )
            line.exchange_rate = pricing["exchange_rate"]
            line.exchange_rate_source = pricing["exchange_rate_source"]
            line.exchange_rate_source_mode = pricing["exchange_rate_source_mode"]
            line.exchange_rate_entered_at = pricing["exchange_rate_entered_at"]
            line.exchange_rate_manual_reason = pricing["exchange_rate_manual_reason"]
            line.exchange_rate_actor_id = pricing["exchange_rate_actor_id"]
            line.conversion_cost_vnd_per_kg = pricing["conversion_cost_vnd_per_kg"]
            line.price_converted_vnd_per_kg = pricing["price_converted_vnd_per_kg"]

        confirmed_at = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
        for previous_version in superseded_versions:
            previous_version.status = "superseded"
            previous_version.superseded_at = confirmed_at
            previous_version.superseded_by_id = confirmed_by_id
            previous_version.superseded_by_version_id = version.id

        version.status = "confirmed"
        version.confirmed_at = confirmed_at
        version.confirmed_by_id = confirmed_by_id

        await self.session.flush()

        reload_stmt = select(QuoteVersion).options(
            selectinload(QuoteVersion.lines).selectinload(QuoteLine.material)
        ).where(QuoteVersion.id == version.id)
        return (await self.session.execute(reload_stmt)).scalar_one()

    async def toggle_line_purchase(
        self,
        *,
        line_id: UUID,
        purchase: bool,
        user_id: UUID,
        purchase_date: datetime | None = None,
    ) -> QuoteLine:
        stmt = select(QuoteLine).options(
            selectinload(QuoteLine.version),
            selectinload(QuoteLine.material)
        ).where(QuoteLine.id == line_id)
        line = (await self.session.execute(stmt)).scalar_one_or_none()
        if not line:
            raise ValueError("Không tìm thấy dòng báo giá.")
        if line.version.status != "confirmed":
            raise ValueError("Chỉ được chốt mua trên phiên bản báo giá đã xác nhận.")

        if purchase:
            line.purchase_marked_at = purchase_date or datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
            line.purchase_marked_by_id = user_id
        else:
            line.purchase_marked_at = None
            line.purchase_marked_by_id = None

        await self.session.flush()
        return line

    async def associate_source_file(
        self,
        *,
        quote_id: UUID,
        version_id: UUID,
        file_id: UUID,
    ) -> QuoteVersion:
        stmt = select(QuoteVersion).where(
            QuoteVersion.id == version_id,
            QuoteVersion.quote_id == quote_id
        ).with_for_update()
        version = (await self.session.execute(stmt)).scalar_one_or_none()
        if not version:
            raise ValueError("Không tìm thấy phiên bản báo giá.")
        if version.status != "draft":
            raise ValueError("Chỉ được đính kèm tệp tin cho phiên bản ở trạng thái bản nháp.")

        version.file_id = file_id
        await self.session.flush()

        reload_stmt = select(QuoteVersion).options(
            selectinload(QuoteVersion.lines).selectinload(QuoteLine.material)
        ).where(QuoteVersion.id == version.id)
        return (await self.session.execute(reload_stmt)).scalar_one()

    async def delete_draft_version(
        self,
        *,
        quote_id: UUID,
        version_id: UUID,
    ) -> DeleteDraftVersionResult:
        stmt = (
            select(QuoteVersion)
            .options(selectinload(QuoteVersion.lines))
            .where(
                QuoteVersion.id == version_id,
                QuoteVersion.quote_id == quote_id,
            )
            .with_for_update()
        )
        version = (await self.session.execute(stmt)).scalar_one_or_none()
        if not version:
            raise ValueError("Không tìm thấy phiên bản báo giá.")
        if version.status != "draft":
            raise ValueError("Chỉ được xóa phiên bản ở trạng thái bản nháp.")

        quote = await self.session.get(Quote, quote_id)
        if not quote:
            raise ValueError("Báo giá không tồn tại.")

        versions_stmt = select(QuoteVersion).where(QuoteVersion.quote_id == quote_id)
        versions = list((await self.session.execute(versions_stmt)).scalars().all())
        file_id = version.file_id
        version_number = version.version_number
        received_date = version.received_date
        correction_reason = version.correction_reason
        line_count = len(version.lines or [])
        delete_whole_quote = len(versions) == 1

        if delete_whole_quote:
            await self.session.delete(quote)
        else:
            await self.session.delete(version)

        await self.session.flush()
        return DeleteDraftVersionResult(
            deleted_quote=delete_whole_quote,
            deleted_quote_id=quote_id if delete_whole_quote else None,
            deleted_version_id=version_id,
            version_number=version_number,
            received_date=received_date,
            correction_reason=correction_reason,
            line_count=line_count,
            file_id=file_id,
            deleted_scope="draft_quote" if delete_whole_quote else "draft_version",
        )

    async def get_quote_by_id(self, quote_id: UUID) -> Quote | None:
        stmt = select(Quote).options(
            selectinload(Quote.versions).selectinload(QuoteVersion.lines).selectinload(QuoteLine.material),
            selectinload(Quote.supplier)
        ).where(Quote.id == quote_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
