from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import require_permission
from app.core.config import Settings, get_settings
from app.core.rate_limit import build_rate_limit_dependency
from app.integrations.vietcombank import (
    VietcombankExchangeRateClient,
    VietcombankHistoricalExchangeRateClient,
)
from app.models import User
from app.schemas import ExchangeRateResponse
from app.services import ExchangeRateService, ExchangeRateUnavailableError

router = APIRouter(prefix="/exchange-rates", tags=["exchange-rates"])

limit_exchange_rates_fetch = build_rate_limit_dependency(
    scope="exchange_rates.usd_sell_today",
    limit_setting="rate_limit_exchange_rates",
)


def get_exchange_rate_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ExchangeRateService:
    client = VietcombankExchangeRateClient(
        url=settings.vietcombank_exchange_rate_url,
        timeout_seconds=settings.vietcombank_exchange_rate_timeout_seconds,
        retry_count=settings.vietcombank_exchange_rate_retry_count,
    )
    historical_client = VietcombankHistoricalExchangeRateClient(
        url=settings.vietcombank_historical_exchange_rate_url,
        timeout_seconds=settings.vietcombank_historical_exchange_rate_timeout_seconds,
        retry_count=settings.vietcombank_historical_exchange_rate_retry_count,
    )
    return ExchangeRateService(client, historical_client)


@router.get(
    "/usd-sell/today",
    response_model=ExchangeRateResponse,
    dependencies=[Depends(limit_exchange_rates_fetch)],
)
async def get_usd_sell_today(
    current_user: Annotated[User, Depends(require_permission("exchange_rates.read"))],
    exchange_rate_service: Annotated[
        ExchangeRateService,
        Depends(get_exchange_rate_service),
    ],
) -> ExchangeRateResponse:
    try:
        result = await exchange_rate_service.get_usd_sell_today()
    except ExchangeRateUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return ExchangeRateResponse(
        currency=result.currency,
        rate=result.rate,
        source=result.source,
        retrieved_at=result.retrieved_at,
    )


@router.get(
    "/usd-sell/by-date/{target_date}",
    response_model=ExchangeRateResponse,
    dependencies=[Depends(limit_exchange_rates_fetch)],
)
async def get_usd_sell_by_date(
    target_date: date,
    current_user: Annotated[User, Depends(require_permission("exchange_rates.read"))],
    exchange_rate_service: Annotated[
        ExchangeRateService,
        Depends(get_exchange_rate_service),
    ],
) -> ExchangeRateResponse:
    try:
        result = await exchange_rate_service.get_usd_sell_for_date(target_date)
    except ExchangeRateUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return ExchangeRateResponse(
        currency=result.currency,
        rate=result.rate,
        source=result.source,
        retrieved_at=result.retrieved_at,
    )
