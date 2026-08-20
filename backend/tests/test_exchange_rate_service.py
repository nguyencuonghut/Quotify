from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pytest

from app.integrations.vietcombank import (
    VietcombankExchangeRateClient,
    VietcombankExchangeRateParseError,
    VietcombankHistoricalExchangeRateClient,
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


def test_historical_client_parses_usd_sell_rate_for_requested_date() -> None:
    client = VietcombankHistoricalExchangeRateClient(
        url="https://www.vietcombank.com.vn/api/exchangerates",
        timeout_seconds=2,
        retry_count=0,
    )
    payload = {
        "Count": 2,
        "Date": "2026-08-15T00:00:00",
        "UpdatedDate": "2026-08-15T23:00:00+07:00",
        "Data": [
            {"currencyCode": "EUR", "sell": "30,975.53"},
            {"currencyCode": "USD", "sell": "26,330.00"},
        ],
    }

    result = client.parse_json(payload, date(2026, 8, 15))

    assert result.currency == "USD"
    assert result.rate == Decimal("26330.00")
    assert result.source == "Vietcombank USD bán ra"
    assert result.retrieved_at.date() == date(2026, 8, 15)


def test_historical_client_rejects_when_returned_date_does_not_match_requested() -> None:
    # API bên thứ 3 âm thầm trả về ngày hiện tại nếu tham số `date` sai định
    # dạng — phải phát hiện lệch ngày thay vì tin nhầm giá trị trả về.
    client = VietcombankHistoricalExchangeRateClient(
        url="https://www.vietcombank.com.vn/api/exchangerates",
        timeout_seconds=2,
        retry_count=0,
    )
    payload = {
        "Date": "2026-08-20T00:00:00",
        "Data": [{"currencyCode": "USD", "sell": "26,340.00"}],
    }

    with pytest.raises(VietcombankExchangeRateParseError):
        client.parse_json(payload, date(2026, 8, 15))


def test_historical_client_rejects_empty_data_for_date_with_no_rates() -> None:
    client = VietcombankHistoricalExchangeRateClient(
        url="https://www.vietcombank.com.vn/api/exchangerates",
        timeout_seconds=2,
        retry_count=0,
    )
    payload = {"Date": "2099-01-01T00:00:00", "Data": []}

    with pytest.raises(VietcombankExchangeRateParseError):
        client.parse_json(payload, date(2099, 1, 1))


@pytest.mark.asyncio
async def test_exchange_rate_service_get_usd_sell_for_date_success() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=json.dumps(
                {
                    "Date": "2026-08-15T00:00:00",
                    "Data": [{"currencyCode": "USD", "sell": "26,330.00"}],
                },
            ),
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    historical_client = VietcombankHistoricalExchangeRateClient(
        url="https://example.test/exchangerates",
        timeout_seconds=1,
        retry_count=0,
        http_client=http_client,
    )
    service = ExchangeRateService(
        VietcombankExchangeRateClient(url="https://example.test/vcb.xml", timeout_seconds=1),
        historical_client,
    )

    result = await service.get_usd_sell_for_date(date(2026, 8, 15))

    assert result.rate == Decimal("26330.00")
    await http_client.aclose()


@pytest.mark.asyncio
async def test_exchange_rate_service_get_usd_sell_for_date_without_historical_client() -> None:
    service = ExchangeRateService(
        VietcombankExchangeRateClient(url="https://example.test/vcb.xml", timeout_seconds=1),
    )

    with pytest.raises(ExchangeRateUnavailableError):
        await service.get_usd_sell_for_date(date(2026, 8, 15))


def test_convert_usd_mt_to_vnd_kg_with_zero_tax_matches_legacy_formula() -> None:
    result = convert_usd_mt_to_vnd_kg(
        original_price_usd_per_mt=Decimal("310.123"),
        exchange_rate=Decimal("26100.00"),
        import_tax_rate_percent=Decimal("0"),
        processing_cost_vnd_per_kg=Decimal("200"),
    )

    assert result == Decimal("8294.21")


def test_convert_usd_mt_to_vnd_kg_applies_import_tax_rate() -> None:
    result = convert_usd_mt_to_vnd_kg(
        original_price_usd_per_mt=Decimal("310.123"),
        exchange_rate=Decimal("26100.00"),
        import_tax_rate_percent=Decimal("5"),
        processing_cost_vnd_per_kg=Decimal("200"),
    )

    assert result == Decimal("8698.92")


def test_is_business_today_uses_asia_ho_chi_minh_boundary() -> None:
    now_utc = datetime(2026, 7, 27, 17, 30, tzinfo=UTC)

    assert is_business_today("2026-07-28", now=now_utc, timezone_name="Asia/Ho_Chi_Minh")
    assert not is_business_today(
        "2026-07-27",
        now=now_utc,
        timezone_name="Asia/Ho_Chi_Minh",
    )
