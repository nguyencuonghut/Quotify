from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.services.quotify_dashboard_service import QuotifyDashboardService


class FakeResultRow:
    def __init__(self, data: dict) -> None:
        self.__dict__.update(data)


class FakeResult:
    def __init__(
        self,
        rows: list[FakeResultRow] | None = None,
        scalar_value: object | None = None,
    ) -> None:
        self._rows = rows or []
        self._scalar_value = scalar_value

    def all(self) -> list[FakeResultRow]:
        return self._rows

    def first(self) -> FakeResultRow | None:
        return self._rows[0] if self._rows else None

    def scalar(self) -> object | None:
        return self._scalar_value


class FakeDbSession:
    def __init__(self, results: list[FakeResult]) -> None:
        self.results = results
        self.queries: list[object] = []

    async def execute(self, statement: object) -> FakeResult:
        self.queries.append(statement)
        return self.results.pop(0)


@pytest.mark.asyncio
async def test_get_entry_kpis_counts_quotes_by_original_creator_only() -> None:
    user_id = uuid4()
    fake_db = FakeDbSession(
        [
            FakeResult([FakeResultRow({"total_quote_count": 3})]),
            FakeResult(
                [
                    FakeResultRow(
                        {
                            "user_id": user_id,
                            "user_email": "buyer@example.com",
                            "user_full_name": "Buyer One",
                            "quote_count": 2,
                        }
                    ),
                    FakeResultRow(
                        {
                            "user_id": None,
                            "user_email": None,
                            "user_full_name": None,
                            "quote_count": 1,
                        }
                    ),
                ]
            ),
        ]
    )

    service = QuotifyDashboardService(fake_db)
    response = await service.get_entry_kpis(supplier_type="domestic")

    assert response["total_quote_count"] == 3
    assert response["user_kpis"][0]["user_id"] == user_id
    assert response["user_kpis"][0]["user_label"] == "Buyer One"
    assert response["user_kpis"][0]["quote_count"] == 2
    assert response["user_kpis"][1]["user_label"] == "Không xác định"
    assert len(fake_db.queries) == 2
    assert "quote_versions.status = :status_1" in str(fake_db.queries[0])
    assert "suppliers.supplier_type = :supplier_type_1" in str(fake_db.queries[0])


@pytest.mark.asyncio
async def test_get_price_trends_maps_summary_points_and_purchase_contexts() -> None:
    material_id = uuid4()
    delivery_month = date(2026, 8, 1)
    purchased_line_id = uuid4()
    confirmed_at = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)
    purchase_marked_at = datetime(2026, 7, 21, 9, 0, tzinfo=UTC)

    point_row = FakeResultRow(
        {
            "received_date": date(2026, 7, 20),
            "delivery_month": delivery_month,
            "converted_price_vnd_per_kg": Decimal("6500.00"),
            "supplier_id": uuid4(),
            "supplier_name": "Supplier ABC",
            "supplier_code": "ABC",
            "supplier_type": "international",
            "material_id": material_id,
            "material_name": "Bắp hạt",
            "material_code": "CORN",
            "quote_id": uuid4(),
            "quote_version_id": uuid4(),
            "line_id": purchased_line_id,
            "purchased": True,
            "purchase_marked_at": purchase_marked_at,
            "confirmed_at": confirmed_at,
        }
    )
    fake_db = FakeDbSession(
        [
            FakeResult(
                [
                    FakeResultRow(
                        {
                            "min_price": Decimal("6400.00"),
                            "max_price": Decimal("6600.00"),
                            "avg_price": Decimal("6500.00"),
                            "total_lines": 2,
                            "total_quotes": 2,
                            "purchased_lines": 1,
                        }
                    )
                ]
            ),
            FakeResult([point_row]),
            FakeResult(
                [
                    FakeResultRow(
                        {
                            "min_price": Decimal("6500.00"),
                            "max_price": Decimal("6500.00"),
                            "avg_price": Decimal("6500.00"),
                            "total_lines": 1,
                            "total_quotes": 1,
                            "purchased_lines": 1,
                        }
                    )
                ]
            ),
            FakeResult(
                [
                    FakeResultRow(
                        {
                            "min_price": Decimal("6700.00"),
                            "max_price": Decimal("6700.00"),
                            "avg_price": Decimal("6700.00"),
                            "total_lines": 1,
                            "total_quotes": 1,
                            "purchased_lines": 0,
                        }
                    )
                ]
            ),
        ]
    )

    service = QuotifyDashboardService(fake_db)
    response = await service.get_price_trends(
        material_id=material_id,
        delivery_month=delivery_month,
        supplier_type="international",
    )

    assert response["summary"]["min_price"] == Decimal("6400.00")
    assert response["summary"]["avg_price"] == Decimal("6500.00")
    assert response["points"][0]["line_id"] == purchased_line_id
    assert response["points"][0]["supplier_type"] == "international"
    assert response["points"][0]["purchased"] is True
    assert response["purchase_contexts"][0]["purchased_line_id"] == purchased_line_id
    assert response["purchase_contexts"][0]["at_purchase"]["total_lines"] == 1
    assert response["purchase_contexts"][0]["after_purchase"]["min_price"] == Decimal("6700.00")
    assert len(fake_db.queries) == 4
    assert "quote_versions.status = :status_1" in str(fake_db.queries[0])
    assert "suppliers.supplier_type = :supplier_type_1" in str(fake_db.queries[0])
