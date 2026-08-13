from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest

from app.models import (
    Material,
    Quote,
    QuoteLine,
    QuoteVersion,
    QuotifySetting,
    Supplier,
    SupplierMaterial,
)
from app.services import quote_pricing as quote_pricing_module
from app.services import quote_service as quote_service_module
from app.services.exchange_rate_service import (
    ExchangeRateService,
    ExchangeRateUnavailableError,
)
from app.services.quote_pricing import QuotePricingService
from app.services.quote_service import QuoteService


class FakeScalarResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        if isinstance(self._value, list):
            return self._value[0] if self._value else None
        return self._value

    def scalar_one(self) -> object:
        if self._value is None:
            raise AssertionError("Expected scalar value.")
        if isinstance(self._value, list):
            return self._value[0]
        return self._value

    def scalar(self) -> object | None:
        if isinstance(self._value, list):
            return self._value[0] if self._value else None
        return self._value

    def scalars(self) -> FakeScalarResult:
        return self

    def all(self) -> list[object]:
        if isinstance(self._value, list):
            return self._value
        if self._value is None:
            return []
        return [self._value]


class FakeQuoteSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.flushed = False
        self.committed = False
        
        self.suppliers: dict[UUID, Supplier] = {}
        self.materials: dict[UUID, Material] = {}
        self.supplier_materials: list[SupplierMaterial] = []
        self.quotes: dict[UUID, Quote] = {}
        self.quote_versions: dict[UUID, QuoteVersion] = {}
        self.quote_lines: dict[UUID, QuoteLine] = {}

    async def get(self, model_class: type[Any], id: UUID) -> Any:
        if model_class == Supplier:
            return self.suppliers.get(id)
        if model_class == Quote:
            return self.quotes.get(id)
        if model_class == QuoteVersion:
            return self.quote_versions.get(id)
        if model_class == Material:
            return self.materials.get(id)
        return None

    def add(self, obj: Any) -> None:
        self.added.append(obj)
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = uuid4()
        
        if isinstance(obj, Quote):
            self.quotes[obj.id] = obj
            obj.versions = []
        elif isinstance(obj, QuoteVersion):
            self.quote_versions[obj.id] = obj
            obj.lines = []
            quote = self.quotes.get(obj.quote_id)
            if quote:
                quote.versions.append(obj)
        elif isinstance(obj, QuoteLine):
            self.quote_lines[obj.id] = obj
            version = self.quote_versions.get(obj.quote_version_id)
            if version:
                version.lines.append(obj)

    async def flush(self) -> None:
        self.flushed = True

    async def commit(self) -> None:
        self.committed = True

    async def delete(self, obj: Any) -> None:
        self.deleted.append(obj)
        if isinstance(obj, Quote):
            for version in list(obj.versions):
                await self.delete(version)
            self.quotes.pop(obj.id, None)
        elif isinstance(obj, QuoteVersion):
            line_ids = [
                line_id
                for line_id, line in self.quote_lines.items()
                if line.quote_version_id == obj.id
            ]
            for line_id in line_ids:
                self.quote_lines.pop(line_id, None)
            quote = self.quotes.get(obj.quote_id)
            if quote:
                quote.versions = [version for version in quote.versions if version.id != obj.id]
            self.quote_versions.pop(obj.id, None)

    async def execute(self, statement: object) -> FakeScalarResult:
        compiled = str(statement)
        params = statement.compile().params  # type: ignore[attr-defined]

        if "FROM supplier_materials" in compiled:
            supplier_id = params.get("supplier_id_1")
            material_ids = params.get("material_id_1")
            if not isinstance(material_ids, list):
                material_ids = [material_ids]
            
            allowed = [
                sm.material_id
                for sm in self.supplier_materials
                if sm.supplier_id == supplier_id and sm.material_id in material_ids
            ]
            return FakeScalarResult(allowed)

        elif "FROM quote_versions" in compiled and params.get("status_1") == "draft":
            quote_id = params.get("quote_id_1")
            draft = next(
                (v for v in self.quote_versions.values() if v.quote_id == quote_id and v.status == "draft"),
                None,
            )
            return FakeScalarResult(draft)

        elif "FROM quote_versions" in compiled and params.get("status_1") == "confirmed":
            quote_id = params.get("quote_id_1")
            excluded_version_id = params.get("id_1")
            confirmed_versions = [
                v
                for v in self.quote_versions.values()
                if v.quote_id == quote_id
                and v.status == "confirmed"
                and (excluded_version_id is None or v.id != excluded_version_id)
            ]
            return FakeScalarResult(confirmed_versions)

        elif "max(quote_versions.version_number)" in compiled:
            quote_id = params.get("quote_id_1")
            versions = [v.version_number for v in self.quote_versions.values() if v.quote_id == quote_id]
            max_v = max(versions) if versions else 0
            return FakeScalarResult(max_v)

        elif "DELETE FROM quote_lines" in compiled:
            version_id = params.get("quote_version_id_1")
            lines_to_del = [l_id for l_id, l in self.quote_lines.items() if l.quote_version_id == version_id]
            for l_id in lines_to_del:
                del self.quote_lines[l_id]
            version = self.quote_versions.get(version_id)
            if version:
                version.lines = []
            return FakeScalarResult(None)

        elif "FROM quote_lines" in compiled:
            version_id = params.get("quote_version_id_1")
            if version_id:
                lines = [l for l in self.quote_lines.values() if l.quote_version_id == version_id]
                # Populate material relation
                for l in lines:
                    if l.material_id in self.materials:
                        l.material = self.materials[l.material_id]
                return FakeScalarResult(lines)
            
            line_id = params.get("id_1")
            if line_id:
                line = self.quote_lines.get(line_id)
                if line and line.material_id in self.materials:
                    line.material = self.materials[line.material_id]
                return FakeScalarResult(line)

        elif "FROM quotes" in compiled:
            quote_id = params.get("quote_id_1") or params.get("id_1")
            quote = self.quotes.get(quote_id)
            if quote and quote.supplier_id in self.suppliers:
                quote.supplier = self.suppliers[quote.supplier_id]
            return FakeScalarResult(quote)

        elif "FROM quote_versions" in compiled:
            version_id = params.get("id_1")
            quote_id = params.get("quote_id_1")
            if quote_id and not version_id:
                return FakeScalarResult([
                    v for v in self.quote_versions.values() if v.quote_id == quote_id
                ])
            version = self.quote_versions.get(version_id)
            if version:
                version.lines = [l for l in self.quote_lines.values() if l.quote_version_id == version_id]
                for l in version.lines:
                    if l.material_id in self.materials:
                        l.material = self.materials[l.material_id]
            return FakeScalarResult(version)

        return FakeScalarResult(None)


class MockExchangeRateClient:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.rate = Decimal("26000.00")

    async def fetch_usd_sell_rate(self) -> Any:
        if self.should_fail:
            raise ExchangeRateUnavailableError("Vietcombank outage")
        
        class FakeRate:
            currency = "USD"
            rate = self.rate
            source = "Vietcombank USD bán ra"
            retrieved_at = datetime(2026, 7, 28, 8, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        return FakeRate()


class MockQuotifySettingsService:
    async def get_or_create_settings(self) -> QuotifySetting:
        return QuotifySetting(
            import_tax_rate_percent=Decimal("0.00"),
            processing_cost_vnd_per_kg=Decimal("150.00"),
        )


@pytest.fixture
def test_setup(monkeypatch: pytest.MonkeyPatch) -> tuple[FakeQuoteSession, QuoteService, MockExchangeRateClient]:
    business_today = date(2026, 7, 28)
    monkeypatch.setattr(quote_service_module, "get_business_today", lambda *_, **__: business_today)
    monkeypatch.setattr(quote_pricing_module, "get_business_today", lambda *_, **__: business_today)

    session = FakeQuoteSession()
    
    # Seed mock master data
    supplier = Supplier(id=uuid4(), code="SUP-A", name="Supplier A", status="active")
    material1 = Material(id=uuid4(), code="MAT-1", name="Material 1", status="active")
    material2 = Material(id=uuid4(), code="MAT-2", name="Material 2", status="active")
    
    session.suppliers[supplier.id] = supplier
    session.materials[material1.id] = material1
    session.materials[material2.id] = material2
    
    # Associate materials with supplier
    session.supplier_materials.append(SupplierMaterial(supplier_id=supplier.id, material_id=material1.id))
    session.supplier_materials.append(SupplierMaterial(supplier_id=supplier.id, material_id=material2.id))
    
    rate_client = MockExchangeRateClient()
    ex_service = ExchangeRateService(rate_client)  # type: ignore[arg-type]
    settings_service = MockQuotifySettingsService()
    
    pricing_service = QuotePricingService(
        exchange_rate_service=ex_service,
        settings_service=settings_service,  # type: ignore[arg-type]
    )
    quote_service = QuoteService(session, pricing_service)  # type: ignore[arg-type]
    
    return session, quote_service, rate_client


@pytest.mark.asyncio
async def test_create_quote_success_vnd(test_setup: Any) -> None:
    session, quote_service, _ = test_setup
    
    supplier_id = list(session.suppliers.keys())[0]
    material_id = list(session.materials.keys())[0]
    user_id = uuid4()
    
    lines = [{
        "material_id": material_id,
        "price_original": Decimal("15000.00"),
        "currency": "VND",
        "unit": "KG",
        "delivery_month": date(2026, 8, 1),
    }]
    
    quote = await quote_service.create_quote(
        supplier_id=supplier_id,
        received_date=date(2026, 7, 28),
        is_backfilled=False,
        backfill_reason=None,
        lines_data=lines,
        created_by_id=user_id,
    )
    
    assert quote.supplier_id == supplier_id
    assert quote.created_by_id == user_id
    assert len(quote.versions) == 1
    
    version = quote.versions[0]
    assert version.version_number == 1
    assert version.status == "draft"
    assert len(version.lines) == 1
    
    line = version.lines[0]
    assert line.price_original == Decimal("15000.00")
    assert line.currency == "VND"
    assert line.unit == "KG"
    assert line.price_converted_vnd_per_kg == Decimal("15000.00")  # Converted price equals original price for VND/KG
    assert line.exchange_rate is None


@pytest.mark.asyncio
async def test_create_quote_vnd_kg_allows_optional_historical_exchange_rate_for_reference(
    test_setup: Any,
) -> None:
    """VND/KG không cần tỷ giá để quy đổi giá, nhưng nhân viên thu mua có thể
    nhập tỷ giá tại thời điểm báo giá để tra cứu bối cảnh lịch sử (vì sao giá
    cao/thấp) — giá trị này chỉ mang tính tham khảo, không ảnh hưởng
    price_converted_vnd_per_kg."""
    session, quote_service, _ = test_setup

    supplier_id = list(session.suppliers.keys())[0]
    material_id = list(session.materials.keys())[0]
    user_id = uuid4()

    lines = [{
        "material_id": material_id,
        "price_original": Decimal("15000.00"),
        "currency": "VND",
        "unit": "KG",
        "delivery_month": date(2026, 8, 1),
        "exchange_rate": Decimal("26100.00"),
        "exchange_rate_manual_reason": "Tỷ giá tham khảo tại thời điểm báo giá",
    }]

    quote = await quote_service.create_quote(
        supplier_id=supplier_id,
        received_date=date(2026, 7, 28),
        is_backfilled=False,
        backfill_reason=None,
        lines_data=lines,
        created_by_id=user_id,
    )

    line = quote.versions[0].lines[0]
    assert line.price_converted_vnd_per_kg == Decimal("15000.00")  # không bị ảnh hưởng bởi tỷ giá
    assert line.exchange_rate == Decimal("26100.00")
    assert line.exchange_rate_source_mode == "manual_reference"
    assert line.exchange_rate_manual_reason == "Tỷ giá tham khảo tại thời điểm báo giá"
    assert line.import_tax_rate_percent is None
    assert line.processing_cost_vnd_per_kg is None


@pytest.mark.asyncio
async def test_create_quote_success_usd_auto(test_setup: Any) -> None:
    session, quote_service, _ = test_setup
    
    supplier_id = list(session.suppliers.keys())[0]
    material_id = list(session.materials.keys())[0]
    user_id = uuid4()
    
    lines = [{
        "material_id": material_id,
        "price_original": Decimal("600.00"),  # USD/MT
        "currency": "USD",
        "unit": "MT",
        "delivery_month": date(2026, 8, 1),
    }]
    
    quote = await quote_service.create_quote(
        supplier_id=supplier_id,
        received_date=date(2026, 7, 28),  # assumed today
        is_backfilled=False,
        backfill_reason=None,
        lines_data=lines,
        created_by_id=user_id,
    )
    
    version = quote.versions[0]
    line = version.lines[0]
    
    # Formulas: (600 / 1000) * 26000 (rate) + 150 (conversion cost) = 15600 + 150 = 15750
    assert line.price_converted_vnd_per_kg == Decimal("15750.00")
    assert line.exchange_rate == Decimal("26000.00")
    assert line.exchange_rate_source_mode == "auto"
    assert line.import_tax_rate_percent == Decimal("0.00")
    assert line.processing_cost_vnd_per_kg == Decimal("150.00")


@pytest.mark.asyncio
async def test_create_quote_success_usd_auto_with_import_tax_rate(test_setup: Any) -> None:
    session, quote_service, _ = test_setup

    class TaxedSettingsService:
        async def get_or_create_settings(self) -> QuotifySetting:
            return QuotifySetting(
                import_tax_rate_percent=Decimal("8.00"),
                processing_cost_vnd_per_kg=Decimal("150.00"),
            )

    quote_service.pricing_service.settings_service = TaxedSettingsService()  # type: ignore[assignment]

    supplier_id = list(session.suppliers.keys())[0]
    material_id = list(session.materials.keys())[0]
    user_id = uuid4()

    lines = [{
        "material_id": material_id,
        "price_original": Decimal("600.00"),  # USD/MT
        "currency": "USD",
        "unit": "MT",
        "delivery_month": date(2026, 8, 1),
    }]

    quote = await quote_service.create_quote(
        supplier_id=supplier_id,
        received_date=date(2026, 7, 28),  # assumed today
        is_backfilled=False,
        backfill_reason=None,
        lines_data=lines,
        created_by_id=user_id,
    )

    line = quote.versions[0].lines[0]

    # Formulas: (600 / 1000) * (1 + 8%) * 26000 (rate) + 150 (chi phí làm hàng)
    # = 0.648 * 26000 + 150 = 16848 + 150 = 16998.00
    assert line.price_converted_vnd_per_kg == Decimal("16998.00")
    assert line.import_tax_rate_percent == Decimal("8.00")
    assert line.processing_cost_vnd_per_kg == Decimal("150.00")


@pytest.mark.asyncio
async def test_create_quote_backfill_import_uses_historical_override_and_note(
    test_setup: Any,
) -> None:
    """Simulates the historical backfill-import flow: manual rate/tax/cost
    override, a per-line note, immediate confirmation, and skip_reload."""
    session, quote_service, _ = test_setup

    supplier_id = list(session.suppliers.keys())[0]
    material_id = list(session.materials.keys())[0]
    user_id = uuid4()

    lines = [{
        "material_id": material_id,
        "price_original": Decimal("300.00"),
        "currency": "USD",
        "unit": "MT",
        "delivery_month": date(2026, 8, 1),
        "exchange_rate": Decimal("25000.00"),
        "import_tax_rate_percent": Decimal("3.00"),
        "processing_cost_vnd_per_kg": Decimal("180.00"),
        "note": "Nhập lại từ báo giá cũ.",
    }]

    quote = await quote_service.create_quote(
        supplier_id=supplier_id,
        received_date=date(2026, 6, 1),  # past date relative to business_today
        is_backfilled=True,
        backfill_reason=None,
        lines_data=lines,
        created_by_id=user_id,
        confirm_immediately=True,
        skip_reload=True,
    )

    version = quote.versions[0]
    line = version.lines[0]

    assert version.status == "confirmed"
    assert version.confirmed_at is not None
    assert version.confirmed_by_id == user_id
    assert line.note == "Nhập lại từ báo giá cũ."
    assert line.exchange_rate == Decimal("25000.00")
    assert line.import_tax_rate_percent == Decimal("3.00")
    assert line.processing_cost_vnd_per_kg == Decimal("180.00")
    # Formula: (300 / 1000) * (1 + 3%) * 25000 + 180 = 7725 + 180 = 7905.00
    assert line.price_converted_vnd_per_kg == Decimal("7905.00")


@pytest.mark.asyncio
async def test_create_quote_defaults_to_draft_without_confirm_immediately(
    test_setup: Any,
) -> None:
    session, quote_service, _ = test_setup

    supplier_id = list(session.suppliers.keys())[0]
    material_id = list(session.materials.keys())[0]
    user_id = uuid4()

    lines = [{
        "material_id": material_id,
        "price_original": Decimal("15000.00"),
        "currency": "VND",
        "unit": "KG",
        "delivery_month": date(2026, 8, 1),
    }]

    quote = await quote_service.create_quote(
        supplier_id=supplier_id,
        received_date=date(2026, 7, 28),
        is_backfilled=False,
        backfill_reason=None,
        lines_data=lines,
        created_by_id=user_id,
    )

    version = quote.versions[0]
    assert version.status == "draft"
    assert version.confirmed_at is None
    assert version.confirmed_by_id is None
    assert version.lines[0].note is None


@pytest.mark.asyncio
async def test_create_quote_preserves_input_line_order(test_setup: Any) -> None:
    session, quote_service, _ = test_setup

    supplier_id = list(session.suppliers.keys())[0]
    material_ids = list(session.materials.keys())
    user_id = uuid4()

    lines = [
        {
            "material_id": material_ids[0],
            "price_original": Decimal("15100.00"),
            "currency": "VND",
            "unit": "KG",
            "delivery_month": date(2026, 9, 1),
        },
        {
            "material_id": material_ids[0],
            "price_original": Decimal("15000.00"),
            "currency": "VND",
            "unit": "KG",
            "delivery_month": date(2026, 8, 1),
        },
        {
            "material_id": material_ids[1],
            "price_original": Decimal("12000.00"),
            "currency": "VND",
            "unit": "KG",
            "delivery_month": date(2026, 8, 1),
        },
    ]

    quote = await quote_service.create_quote(
        supplier_id=supplier_id,
        received_date=date(2026, 7, 28),
        is_backfilled=False,
        backfill_reason=None,
        lines_data=lines,
        created_by_id=user_id,
    )

    version_lines = quote.versions[0].lines
    assert [line.line_order for line in version_lines] == [0, 1, 2]
    assert [(line.material_id, line.delivery_month) for line in version_lines] == [
        (material_ids[0], date(2026, 9, 1)),
        (material_ids[0], date(2026, 8, 1)),
        (material_ids[1], date(2026, 8, 1)),
    ]


@pytest.mark.asyncio
async def test_create_quote_fail_future_date(test_setup: Any) -> None:
    session, quote_service, _ = test_setup
    
    supplier_id = list(session.suppliers.keys())[0]
    material_id = list(session.materials.keys())[0]
    
    lines = [{
        "material_id": material_id,
        "price_original": Decimal("600.00"),
        "currency": "USD",
        "unit": "MT",
        "delivery_month": date(2026, 8, 1),
    }]
    
    with pytest.raises(ValueError, match="Ngày nhận báo giá không được ở tương lai"):
        await quote_service.create_quote(
            supplier_id=supplier_id,
            received_date=date(2026, 12, 31),  # future
            is_backfilled=False,
            backfill_reason=None,
            lines_data=lines,
            created_by_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_create_quote_backfill_required(test_setup: Any) -> None:
    session, quote_service, _ = test_setup
    
    supplier_id = list(session.suppliers.keys())[0]
    material_id = list(session.materials.keys())[0]
    
    lines = [{
        "material_id": material_id,
        "price_original": Decimal("15000.00"),
        "currency": "VND",
        "unit": "KG",
        "delivery_month": date(2026, 8, 1),
    }]
    
    # received_date is yesterday, should require backfilled info
    with pytest.raises(ValueError, match="Báo giá nhập lại bắt buộc phải đánh dấu nhập lùi"):
        await quote_service.create_quote(
            supplier_id=supplier_id,
            received_date=date(2026, 7, 27),  # past
            is_backfilled=False,
            backfill_reason=None,
            lines_data=lines,
            created_by_id=uuid4(),
        )

    # Success with backfill flag; reason is optional in the simplified workflow.
    quote = await quote_service.create_quote(
        supplier_id=supplier_id,
        received_date=date(2026, 7, 27),
        is_backfilled=True,
        backfill_reason=None,
        lines_data=[{
            "material_id": material_id,
            "price_original": Decimal("15000.00"),
            "currency": "VND",
            "unit": "KG",
            "delivery_month": date(2026, 8, 1),
            "exchange_rate": Decimal("26000.00"),  # manual rate for past is required
        }],
        created_by_id=uuid4(),
    )
    assert quote.versions[0].is_backfilled is True
    assert quote.versions[0].backfill_reason is None


@pytest.mark.asyncio
async def test_create_version_and_concurrency(test_setup: Any) -> None:
    session, quote_service, _ = test_setup
    
    supplier_id = list(session.suppliers.keys())[0]
    material_id = list(session.materials.keys())[0]
    user_id = uuid4()
    
    # Create initial quote (version 1, draft)
    quote = await quote_service.create_quote(
        supplier_id=supplier_id,
        received_date=date(2026, 7, 28),
        is_backfilled=False,
        backfill_reason=None,
        lines_data=[{
            "material_id": material_id,
            "price_original": Decimal("15000.00"),
            "currency": "VND",
            "unit": "KG",
            "delivery_month": date(2026, 8, 1),
        }],
        created_by_id=user_id,
    )
    
    # Try to create version 2 while version 1 is still draft -> should fail
    with pytest.raises(ValueError, match="Đã tồn tại một bản nháp cho báo giá này"):
        await quote_service.create_version(
            quote_id=quote.id,
            received_date=date(2026, 7, 28),
            is_backfilled=False,
            backfill_reason=None,
            lines_data=[{
                "material_id": material_id,
                "price_original": Decimal("16000.00"),
                "currency": "VND",
                "unit": "KG",
                "delivery_month": date(2026, 8, 1),
            }],
            created_by_id=user_id,
        )

    # Confirm version 1
    version1 = await quote_service.confirm_version(
        quote_id=quote.id,
        version_id=quote.versions[0].id,
        confirmed_by_id=user_id,
    )
    assert version1.status == "confirmed"

    # Now create version 2 -> should succeed
    version2 = await quote_service.create_version(
        quote_id=quote.id,
        received_date=date(2026, 7, 28),
        is_backfilled=False,
        backfill_reason=None,
        lines_data=[{
            "material_id": material_id,
            "price_original": Decimal("16000.00"),
            "currency": "VND",
            "unit": "KG",
            "delivery_month": date(2026, 8, 1),
        }],
        created_by_id=user_id,
        correction_reason="Cập nhật báo giá mới từ nhà cung cấp.",
    )
    assert version2.version_number == 2
    assert version2.status == "draft"
    assert version2.lines[0].price_original == Decimal("16000.00")


@pytest.mark.asyncio
async def test_delete_draft_version_removes_only_draft_when_quote_has_confirmed_version(test_setup: Any) -> None:
    session, quote_service, _ = test_setup

    supplier_id = list(session.suppliers.keys())[0]
    material_id = list(session.materials.keys())[0]
    user_id = uuid4()

    quote = await quote_service.create_quote(
        supplier_id=supplier_id,
        received_date=date(2026, 7, 28),
        is_backfilled=False,
        backfill_reason=None,
        lines_data=[{
            "material_id": material_id,
            "price_original": Decimal("15000.00"),
            "currency": "VND",
            "unit": "KG",
            "delivery_month": date(2026, 8, 1),
        }],
        created_by_id=user_id,
    )
    confirmed_version = await quote_service.confirm_version(
        quote_id=quote.id,
        version_id=quote.versions[0].id,
        confirmed_by_id=user_id,
    )
    draft_version = await quote_service.create_version(
        quote_id=quote.id,
        received_date=date(2026, 7, 28),
        is_backfilled=False,
        backfill_reason=None,
        lines_data=[{
            "material_id": material_id,
            "price_original": Decimal("16000.00"),
            "currency": "VND",
            "unit": "KG",
            "delivery_month": date(2026, 8, 1),
        }],
        created_by_id=user_id,
        correction_reason="Sửa nhầm giá.",
    )

    result = await quote_service.delete_draft_version(
        quote_id=quote.id,
        version_id=draft_version.id,
    )

    assert result.deleted_quote is False
    assert result.deleted_version_id == draft_version.id
    assert result.version_number == 2
    assert result.received_date == date(2026, 7, 28)
    assert result.correction_reason == "Sửa nhầm giá."
    assert result.line_count == 1
    assert result.deleted_scope == "draft_version"
    assert confirmed_version.id in session.quote_versions
    assert draft_version.id not in session.quote_versions
    assert quote.id in session.quotes


@pytest.mark.asyncio
async def test_delete_only_draft_version_removes_whole_draft_quote(test_setup: Any) -> None:
    session, quote_service, _ = test_setup

    supplier_id = list(session.suppliers.keys())[0]
    material_id = list(session.materials.keys())[0]
    user_id = uuid4()

    quote = await quote_service.create_quote(
        supplier_id=supplier_id,
        received_date=date(2026, 7, 28),
        is_backfilled=False,
        backfill_reason=None,
        lines_data=[{
            "material_id": material_id,
            "price_original": Decimal("15000.00"),
            "currency": "VND",
            "unit": "KG",
            "delivery_month": date(2026, 8, 1),
        }],
        created_by_id=user_id,
    )
    version_id = quote.versions[0].id

    result = await quote_service.delete_draft_version(
        quote_id=quote.id,
        version_id=version_id,
    )

    assert result.deleted_quote is True
    assert result.deleted_quote_id == quote.id
    assert result.version_number == 1
    assert result.received_date == date(2026, 7, 28)
    assert result.correction_reason is None
    assert result.line_count == 1
    assert result.deleted_scope == "draft_quote"
    assert quote.id not in session.quotes
    assert version_id not in session.quote_versions


@pytest.mark.asyncio
async def test_delete_confirmed_version_is_rejected(test_setup: Any) -> None:
    session, quote_service, _ = test_setup

    supplier_id = list(session.suppliers.keys())[0]
    material_id = list(session.materials.keys())[0]
    user_id = uuid4()

    quote = await quote_service.create_quote(
        supplier_id=supplier_id,
        received_date=date(2026, 7, 28),
        is_backfilled=False,
        backfill_reason=None,
        lines_data=[{
            "material_id": material_id,
            "price_original": Decimal("15000.00"),
            "currency": "VND",
            "unit": "KG",
            "delivery_month": date(2026, 8, 1),
        }],
        created_by_id=user_id,
    )
    version = await quote_service.confirm_version(
        quote_id=quote.id,
        version_id=quote.versions[0].id,
        confirmed_by_id=user_id,
    )

    with pytest.raises(ValueError, match="Chỉ được xóa phiên bản ở trạng thái bản nháp"):
        await quote_service.delete_draft_version(
            quote_id=quote.id,
            version_id=version.id,
        )


@pytest.mark.asyncio
async def test_correcting_confirmed_quote_requires_reason_and_supersedes_previous_version(
    test_setup: Any,
) -> None:
    session, quote_service, _ = test_setup

    supplier_id = list(session.suppliers.keys())[0]
    material_id = list(session.materials.keys())[0]
    user_id = uuid4()

    quote = await quote_service.create_quote(
        supplier_id=supplier_id,
        received_date=date(2026, 7, 28),
        is_backfilled=False,
        backfill_reason=None,
        lines_data=[
            {
                "material_id": material_id,
                "price_original": Decimal("15000.00"),
                "currency": "VND",
                "unit": "KG",
                "delivery_month": date(2026, 8, 1),
            }
        ],
        created_by_id=user_id,
    )
    version1 = await quote_service.confirm_version(
        quote_id=quote.id,
        version_id=quote.versions[0].id,
        confirmed_by_id=user_id,
    )

    with pytest.raises(ValueError, match="bắt buộc phải nhập lý do điều chỉnh"):
        await quote_service.create_version(
            quote_id=quote.id,
            received_date=date(2026, 7, 28),
            is_backfilled=False,
            backfill_reason=None,
            lines_data=[
                {
                    "material_id": material_id,
                    "price_original": Decimal("15100.00"),
                    "currency": "VND",
                    "unit": "KG",
                    "delivery_month": date(2026, 8, 1),
                }
            ],
            created_by_id=user_id,
        )

    version2 = await quote_service.create_version(
        quote_id=quote.id,
        received_date=date(2026, 7, 28),
        is_backfilled=False,
        backfill_reason=None,
        lines_data=[
            {
                "material_id": material_id,
                "price_original": Decimal("15100.00"),
                "currency": "VND",
                "unit": "KG",
                "delivery_month": date(2026, 8, 1),
            }
        ],
        created_by_id=user_id,
        correction_reason="Sửa giá nhập nhầm từ báo giá nhà cung cấp.",
    )
    confirmed_version2 = await quote_service.confirm_version(
        quote_id=quote.id,
        version_id=version2.id,
        confirmed_by_id=user_id,
    )

    assert confirmed_version2.status == "confirmed"
    assert confirmed_version2.correction_reason == "Sửa giá nhập nhầm từ báo giá nhà cung cấp."
    assert version1.status == "superseded"
    assert version1.superseded_at == confirmed_version2.confirmed_at
    assert version1.superseded_by_id == user_id
    assert version1.superseded_by_version_id == confirmed_version2.id


@pytest.mark.asyncio
async def test_correction_with_same_received_date_uses_previous_rate_snapshot(
    test_setup: Any,
) -> None:
    session, quote_service, rate_client = test_setup

    supplier_id = list(session.suppliers.keys())[0]
    material_id = list(session.materials.keys())[0]
    user_id = uuid4()

    quote = await quote_service.create_quote(
        supplier_id=supplier_id,
        received_date=date(2026, 7, 28),
        is_backfilled=False,
        backfill_reason=None,
        lines_data=[
            {
                "material_id": material_id,
                "price_original": Decimal("600.00"),
                "currency": "USD",
                "unit": "MT",
                "delivery_month": date(2026, 8, 1),
            }
        ],
        created_by_id=user_id,
    )
    await quote_service.confirm_version(
        quote_id=quote.id,
        version_id=quote.versions[0].id,
        confirmed_by_id=user_id,
    )

    rate_client.rate = Decimal("27000.00")
    version2 = await quote_service.create_version(
        quote_id=quote.id,
        received_date=date(2026, 7, 28),
        is_backfilled=False,
        backfill_reason=None,
        lines_data=[
            {
                "material_id": material_id,
                "price_original": Decimal("700.00"),
                "currency": "USD",
                "unit": "MT",
                "delivery_month": date(2026, 8, 1),
            }
        ],
        created_by_id=user_id,
        correction_reason="Sửa giá nhập nhầm từ báo giá nhà cung cấp.",
    )
    confirmed_version2 = await quote_service.confirm_version(
        quote_id=quote.id,
        version_id=version2.id,
        confirmed_by_id=user_id,
    )

    line = confirmed_version2.lines[0]
    assert line.exchange_rate == Decimal("26000.00")
    assert line.exchange_rate_source_mode == "auto"
    assert line.import_tax_rate_percent == Decimal("0.00")
    assert line.processing_cost_vnd_per_kg == Decimal("150.00")
    assert line.price_converted_vnd_per_kg == Decimal("18350.00")


@pytest.mark.asyncio
async def test_correction_with_today_received_date_fetches_current_vietcombank_rate(
    test_setup: Any,
) -> None:
    session, quote_service, rate_client = test_setup

    supplier_id = list(session.suppliers.keys())[0]
    material_id = list(session.materials.keys())[0]
    user_id = uuid4()

    quote = await quote_service.create_quote(
        supplier_id=supplier_id,
        received_date=date(2026, 7, 27),
        is_backfilled=True,
        backfill_reason="Nhập lại báo giá hôm qua.",
        lines_data=[
            {
                "material_id": material_id,
                "price_original": Decimal("600.00"),
                "currency": "USD",
                "unit": "MT",
                "delivery_month": date(2026, 8, 1),
                "exchange_rate": Decimal("25000.00"),
                "exchange_rate_manual_reason": "Tỷ giá bán ra tại ngày nhận báo giá.",
            }
        ],
        created_by_id=user_id,
    )
    await quote_service.confirm_version(
        quote_id=quote.id,
        version_id=quote.versions[0].id,
        confirmed_by_id=user_id,
    )

    rate_client.rate = Decimal("27000.00")
    version2 = await quote_service.create_version(
        quote_id=quote.id,
        received_date=date(2026, 7, 28),
        is_backfilled=False,
        backfill_reason=None,
        lines_data=[
            {
                "material_id": material_id,
                "price_original": Decimal("700.00"),
                "currency": "USD",
                "unit": "MT",
                "delivery_month": date(2026, 8, 1),
            }
        ],
        created_by_id=user_id,
        correction_reason="Sửa giá nhập nhầm từ báo giá nhà cung cấp.",
    )

    line = version2.lines[0]
    assert line.exchange_rate == Decimal("27000.00")
    assert line.exchange_rate_source_mode == "auto"
    assert line.price_converted_vnd_per_kg == Decimal("19050.00")


@pytest.mark.asyncio
async def test_confirm_version_freezes_values(test_setup: Any) -> None:
    session, quote_service, _ = test_setup
    
    supplier_id = list(session.suppliers.keys())[0]
    material_id = list(session.materials.keys())[0]
    user_id = uuid4()
    
    quote = await quote_service.create_quote(
        supplier_id=supplier_id,
        received_date=date(2026, 7, 28),
        is_backfilled=False,
        backfill_reason=None,
        lines_data=[{
            "material_id": material_id,
            "price_original": Decimal("600.00"),
            "currency": "USD",
            "unit": "MT",
            "delivery_month": date(2026, 8, 1),
        }],
        created_by_id=user_id,
    )
    
    # Confirm
    version = await quote_service.confirm_version(
        quote_id=quote.id,
        version_id=quote.versions[0].id,
        confirmed_by_id=user_id,
    )
    
    assert version.status == "confirmed"
    assert version.confirmed_at is not None
    assert version.confirmed_by_id == user_id
    
    line = version.lines[0]
    assert line.price_converted_vnd_per_kg == Decimal("15750.00")
    assert line.exchange_rate == Decimal("26000.00")


@pytest.mark.asyncio
async def test_toggle_line_purchase_validation(test_setup: Any) -> None:
    session, quote_service, _ = test_setup
    
    supplier_id = list(session.suppliers.keys())[0]
    material_id = list(session.materials.keys())[0]
    user_id = uuid4()
    
    quote = await quote_service.create_quote(
        supplier_id=supplier_id,
        received_date=date(2026, 7, 28),
        is_backfilled=False,
        backfill_reason=None,
        lines_data=[{
            "material_id": material_id,
            "price_original": Decimal("15000.00"),
            "currency": "VND",
            "unit": "KG",
            "delivery_month": date(2026, 8, 1),
        }],
        created_by_id=user_id,
    )
    
    line_id = quote.versions[0].lines[0].id
    
    # Cannot purchase toggle draft lines
    with pytest.raises(ValueError, match="Chỉ được chốt mua trên phiên bản báo giá đã xác nhận"):
        await quote_service.toggle_line_purchase(
            line_id=line_id,
            purchase=True,
            user_id=user_id,
        )

    # Confirm version
    await quote_service.confirm_version(
        quote_id=quote.id,
        version_id=quote.versions[0].id,
        confirmed_by_id=user_id,
    )

    # Success toggle on
    line = await quote_service.toggle_line_purchase(
        line_id=line_id,
        purchase=True,
        user_id=user_id,
    )
    assert line.purchase_marked_at is not None
    assert line.purchase_marked_by_id == user_id

    # Success toggle off
    line = await quote_service.toggle_line_purchase(
        line_id=line_id,
        purchase=False,
        user_id=user_id,
    )
    assert line.purchase_marked_at is None
    assert line.purchase_marked_by_id is None
