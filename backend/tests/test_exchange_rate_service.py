from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from app.integrations.vietcombank import (
    VietcombankExchangeRateClient,
    VietcombankExchangeRateParseError,
)
from app.services.exchange_rate_service import (
    ExchangeRateService,
    ExchangeRateUnavailableError,
    convert_usd_mt_to_vnd_kg,
    is_business_today,
)

VCB_XML_FIXTURE = b"""
<ExrateList DateTime="28/07/2026 08:06:00">
  <Exrate CurrencyCode="EUR" Sell="31,100.00" />
  <Exrate CurrencyCode="USD" Sell="26,100.00" />
</ExrateList>
"""


def test_vietcombank_parser_extracts_usd_sell_rate() -> None:
    client = VietcombankExchangeRateClient(
        url="https://portal.vietcombank.com.vn/Usercontrols/TVPortal.TyGia/pXML.aspx",
        timeout_seconds=2,
        retry_count=0,
    )

    result = client.parse_xml(VCB_XML_FIXTURE)

    assert result.currency == "USD"
    assert result.rate == Decimal("26100.00")
    assert result.source == "Vietcombank USD bán ra"
    assert result.retrieved_at.isoformat() == "2026-07-28T08:06:00+07:00"


def test_vietcombank_parser_rejects_response_without_usd_sell() -> None:
    client = VietcombankExchangeRateClient(url="https://example.test", timeout_seconds=2)

    with pytest.raises(VietcombankExchangeRateParseError):
        client.parse_xml(
            b"<ExrateList><Exrate CurrencyCode=\"EUR\" Sell=\"31,100.00\" /></ExrateList>",
        )


@pytest.mark.asyncio
async def test_exchange_rate_service_maps_http_timeout_to_error_contract() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout", request=request)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    vcb_client = VietcombankExchangeRateClient(
        url="https://example.test/vcb.xml",
        timeout_seconds=1,
        retry_count=0,
        http_client=http_client,
    )
    service = ExchangeRateService(vcb_client)

    with pytest.raises(ExchangeRateUnavailableError):
        await service.get_usd_sell_today()

    await http_client.aclose()


def test_convert_usd_mt_to_vnd_kg_uses_decimal_and_rounds_once() -> None:
    result = convert_usd_mt_to_vnd_kg(
        original_price_usd_per_mt=Decimal("310.123"),
        exchange_rate=Decimal("26100.00"),
        conversion_cost_vnd_per_kg=Decimal("200"),
    )

    assert result == Decimal("8294.21")


def test_is_business_today_uses_asia_ho_chi_minh_boundary() -> None:
    now_utc = datetime(2026, 7, 27, 17, 30, tzinfo=UTC)

    assert is_business_today("2026-07-28", now=now_utc, timezone_name="Asia/Ho_Chi_Minh")
    assert not is_business_today(
        "2026-07-27",
        now=now_utc,
        timezone_name="Asia/Ho_Chi_Minh",
    )
