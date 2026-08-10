from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import QuotifySetting
from app.services.exchange_rate_service import quantize_money

DEFAULT_IMPORT_TAX_RATE_PERCENT = Decimal("0.00")
DEFAULT_PROCESSING_COST_VND_PER_KG = Decimal("200.00")


class QuotifySettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_settings(self) -> QuotifySetting:
        result = await self.session.execute(
            select(QuotifySetting).where(QuotifySetting.singleton_key == "default"),
        )
        setting = result.scalar_one_or_none()
        if setting is not None:
            return setting

        setting = QuotifySetting(
            singleton_key="default",
            import_tax_rate_percent=DEFAULT_IMPORT_TAX_RATE_PERCENT,
            processing_cost_vnd_per_kg=DEFAULT_PROCESSING_COST_VND_PER_KG,
        )
        self.session.add(setting)
        await self.session.flush()
        return setting

    async def update_quotify_settings(
        self,
        *,
        import_tax_rate_percent: Decimal,
        processing_cost_vnd_per_kg: Decimal,
        updated_by_id: UUID,
    ) -> QuotifySetting:
        setting = await self.get_or_create_settings()
        setting.import_tax_rate_percent = validate_import_tax_rate(
            import_tax_rate_percent,
        )
        setting.processing_cost_vnd_per_kg = validate_processing_cost(
            processing_cost_vnd_per_kg,
        )
        setting.updated_by_id = updated_by_id
        await self.session.flush()
        return setting


def validate_import_tax_rate(value: Decimal) -> Decimal:
    if value < 0:
        raise ValueError("Thuế nhập khẩu không được âm.")
    if value > 100:
        raise ValueError("Thuế nhập khẩu không được vượt quá 100%.")
    return quantize_money(value)


def validate_processing_cost(value: Decimal) -> Decimal:
    if value < 0:
        raise ValueError("Chi phí làm hàng không được âm.")
    return quantize_money(value)
