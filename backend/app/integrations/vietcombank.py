from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

import httpx


class VietcombankExchangeRateError(Exception):
    """Raised when Vietcombank exchange rate data cannot be fetched."""


class VietcombankExchangeRateParseError(VietcombankExchangeRateError):
    """Raised when Vietcombank exchange rate payload cannot be parsed."""


@dataclass(frozen=True, slots=True)
class VietcombankExchangeRate:
    currency: str
    rate: Decimal
    source: str
    retrieved_at: datetime


class VietcombankExchangeRateClient:
    SOURCE_LABEL = "Vietcombank USD bán ra"
    BUSINESS_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")

    def __init__(
        self,
        *,
        url: str,
        timeout_seconds: float,
        retry_count: int = 1,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.retry_count = max(0, retry_count)
        self._http_client = http_client

    async def fetch_usd_sell_rate(self) -> VietcombankExchangeRate:
        last_error: Exception | None = None
        for attempt in range(self.retry_count + 1):
            try:
                response = await self._get_http_client().get(
                    self.url,
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                return self.parse_xml(response.content)
            except (httpx.HTTPError, VietcombankExchangeRateParseError) as exc:
                last_error = exc
                if attempt < self.retry_count:
                    await asyncio.sleep(0.1 * (attempt + 1))

        raise VietcombankExchangeRateError("Không thể lấy tỷ giá từ Vietcombank.") from last_error

    def parse_xml(self, content: bytes) -> VietcombankExchangeRate:
        try:
            root = ElementTree.fromstring(content)
        except ElementTree.ParseError as exc:
            raise VietcombankExchangeRateParseError(
                "Response tỷ giá Vietcombank không đúng định dạng XML.",
            ) from exc

        retrieved_at = self._parse_retrieved_at(root.attrib.get("DateTime"))
        for item in root.iter():
            if item.attrib.get("CurrencyCode", "").upper() != "USD":
                continue
            sell_value = item.attrib.get("Sell")
            if not sell_value:
                break
            return VietcombankExchangeRate(
                currency="USD",
                rate=self._parse_decimal(sell_value),
                source=self.SOURCE_LABEL,
                retrieved_at=retrieved_at,
            )

        raise VietcombankExchangeRateParseError(
            "Response tỷ giá Vietcombank không có USD bán ra.",
        )

    def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is not None:
            return self._http_client
        self._http_client = httpx.AsyncClient()
        return self._http_client

    def _parse_retrieved_at(self, raw_value: str | None) -> datetime:
        if not raw_value:
            return datetime.now(self.BUSINESS_TIMEZONE)
        for pattern in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
            try:
                parsed = datetime.strptime(raw_value.strip(), pattern)
                return parsed.replace(tzinfo=self.BUSINESS_TIMEZONE)
            except ValueError:
                continue
        raise VietcombankExchangeRateParseError(
            "Thời điểm cập nhật tỷ giá Vietcombank không hợp lệ.",
        )

    def _parse_decimal(self, raw_value: str) -> Decimal:
        try:
            return Decimal(raw_value.replace(",", "").strip())
        except InvalidOperation as exc:
            raise VietcombankExchangeRateParseError(
                "Giá trị tỷ giá Vietcombank không hợp lệ.",
            ) from exc
