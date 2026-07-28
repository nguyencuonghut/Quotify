from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from app.integrations.vietcombank import (
    VietcombankExchangeRateClient,
    VietcombankExchangeRateError,
)

MONEY_QUANTUM = Decimal("0.01")


class ExchangeRateUnavailableError(Exception):
    """Raised when automatic exchange rate cannot be fetched."""


@dataclass(frozen=True, slots=True)
class ExchangeRateResult:
    currency: str
    rate: Decimal
    source: str
    retrieved_at: datetime


class ExchangeRateService:
    def __init__(self, client: VietcombankExchangeRateClient) -> None:
        self.client = client

    async def get_usd_sell_today(self) -> ExchangeRateResult:
        try:
            rate = await self.client.fetch_usd_sell_rate()
        except VietcombankExchangeRateError as exc:
            raise ExchangeRateUnavailableError(
                "Không thể lấy tỷ giá USD bán ra tự động.",
            ) from exc

        return ExchangeRateResult(
            currency=rate.currency,
            rate=quantize_money(rate.rate),
            source=rate.source,
            retrieved_at=rate.retrieved_at,
        )


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def convert_usd_mt_to_vnd_kg(
    *,
    original_price_usd_per_mt: Decimal,
    exchange_rate: Decimal,
    conversion_cost_vnd_per_kg: Decimal,
) -> Decimal:
    converted = (original_price_usd_per_mt / Decimal("1000")) * exchange_rate
    return quantize_money(converted + conversion_cost_vnd_per_kg)


def get_business_today(
    *,
    now: datetime | None = None,
    timezone_name: str = "Asia/Ho_Chi_Minh",
) -> date:
    timezone = ZoneInfo(timezone_name)
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return current.astimezone(timezone).date()


def is_business_today(
    value: str | date,
    *,
    now: datetime | None = None,
    timezone_name: str = "Asia/Ho_Chi_Minh",
) -> bool:
    target = date.fromisoformat(value) if isinstance(value, str) else value
    return target == get_business_today(now=now, timezone_name=timezone_name)
