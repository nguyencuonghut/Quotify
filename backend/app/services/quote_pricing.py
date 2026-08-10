from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
from uuid import UUID

from app.services.exchange_rate_service import (
    ExchangeRateService,
    ExchangeRateUnavailableError,
    convert_usd_mt_to_vnd_kg,
    get_business_today,
    quantize_money,
)
from app.services.quotify_settings_service import QuotifySettingsService


class QuotePricingService:
    def __init__(
        self,
        *,
        exchange_rate_service: ExchangeRateService,
        settings_service: QuotifySettingsService,
    ) -> None:
        self.exchange_rate_service = exchange_rate_service
        self.settings_service = settings_service

    def validate_currency_unit(self, currency: str, unit: str) -> None:
        c_upper = currency.upper()
        u_upper = unit.upper()
        
        valid_pairs = {("VND", "KG"), ("USD", "MT")}
        if (c_upper, u_upper) not in valid_pairs:
            raise ValueError(
                f"Cặp tiền tệ/đơn vị '{currency}/{unit}' không hợp lệ. Chỉ hỗ trợ VND/KG hoặc USD/MT."
            )

    async def resolve_pricing_provenance(
        self,
        *,
        currency: str,
        unit: str,
        received_date: date,
        price_original: Decimal,
        manual_rate: Decimal | None = None,
        manual_reason: str | None = None,
        actor_id: UUID | None = None,
        now: datetime | None = None,
    ) -> dict[str, object]:
        """Calculates exchange rate and conversion cost for a quote line."""
        self.validate_currency_unit(currency, unit)
        
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
                "import_tax_rate_percent": None,
                "processing_cost_vnd_per_kg": None,
                "price_converted_vnd_per_kg": quantize_money(price_original),
            }

        # Handle USD/MT conversion
        today = get_business_today(now=now)

        if received_date > today:
            raise ValueError("Ngày nhận báo giá không được ở tương lai.")

        settings = await self.settings_service.get_or_create_settings()
        import_tax_rate_percent = settings.import_tax_rate_percent
        processing_cost = settings.processing_cost_vnd_per_kg

        rate: Decimal
        source: str
        source_mode: str
        entered_at: datetime
        resolved_reason: str | None = None
        resolved_actor_id: UUID | None = None

        if received_date == today:
            # Check automatic fetch
            auto_rate_success = False
            auto_rate_result = None
            try:
                auto_rate_result = await self.exchange_rate_service.get_usd_sell_today()
                auto_rate_success = True
            except ExchangeRateUnavailableError:
                pass

            if auto_rate_success and auto_rate_result is not None:
                # If auto rate is working, reject manual fallback unless it matches the auto rate
                if manual_rate is not None and quantize_money(manual_rate) != quantize_money(auto_rate_result.rate):
                    raise ValueError(
                        "Hệ thống lấy được tỷ giá tự động từ Vietcombank. Bạn không được phép tự nhập tỷ giá."
                    )
                rate = auto_rate_result.rate
                source = auto_rate_result.source
                source_mode = "auto"
                entered_at = auto_rate_result.retrieved_at
            else:
                # Auto rate failed, fallback to manual input
                if manual_rate is None or not manual_reason or not manual_reason.strip():
                    raise ValueError(
                        "Không thể lấy tỷ giá tự động từ Vietcombank. Vui lòng nhập tỷ giá và lý do nhập tay."
                    )
                rate = quantize_money(manual_rate)
                source = "Nhập tay do không lấy được tỷ giá tự động"
                source_mode = "manual_fallback"
                entered_at = now or datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
                resolved_reason = manual_reason.strip()
                resolved_actor_id = actor_id
        else:
            # Past date: manual past input required
            if manual_rate is None:
                raise ValueError("Báo giá quá khứ bắt buộc phải nhập tỷ giá.")
            rate = quantize_money(manual_rate)
            source = "Nhập tay"
            source_mode = "manual_past"
            entered_at = now or datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
            resolved_reason = manual_reason.strip() if manual_reason else None
            resolved_actor_id = actor_id

        # Calculate converted price
        price_converted = convert_usd_mt_to_vnd_kg(
            original_price_usd_per_mt=price_original,
            exchange_rate=rate,
            import_tax_rate_percent=import_tax_rate_percent,
            processing_cost_vnd_per_kg=processing_cost,
        )

        return {
            "exchange_rate": rate,
            "exchange_rate_source": source,
            "exchange_rate_source_mode": source_mode,
            "exchange_rate_entered_at": entered_at,
            "exchange_rate_manual_reason": resolved_reason,
            "exchange_rate_actor_id": resolved_actor_id,
            "import_tax_rate_percent": import_tax_rate_percent,
            "processing_cost_vnd_per_kg": processing_cost,
            "price_converted_vnd_per_kg": price_converted,
        }
