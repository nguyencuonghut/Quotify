from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import QuotifySetting
from app.services.exchange_rate_service import quantize_money

DEFAULT_CONVERSION_COST_VND_PER_KG = Decimal("200.00")


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
            conversion_cost_vnd_per_kg=DEFAULT_CONVERSION_COST_VND_PER_KG,
        )
        self.session.add(setting)
        await self.session.flush()
        return setting

    async def update_conversion_cost(
        self,
        *,
        conversion_cost_vnd_per_kg: Decimal,
        updated_by_id: UUID,
    ) -> QuotifySetting:
        setting = await self.get_or_create_settings()
        setting.conversion_cost_vnd_per_kg = validate_conversion_cost(
            conversion_cost_vnd_per_kg,
        )
        setting.updated_by_id = updated_by_id
        await self.session.flush()
        return setting


def validate_conversion_cost(value: Decimal) -> Decimal:
    if value < 0:
        raise ValueError("Chi phí quy đổi không được âm.")
    return quantize_money(value)
