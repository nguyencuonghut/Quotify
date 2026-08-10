from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, cast
from uuid import uuid4

import pytest

from app.services.quote_query_service import QuoteQueryService


class FakeResultRow:
    def __init__(self, data: dict[str, Any]) -> None:
        self.__dict__.update(data)

    def __getattr__(self, name: str) -> Any:
        return self.__dict__.get(name)


class FakeResult:
    def __init__(self, rows: list[FakeResultRow]) -> None:
        self._rows = rows

    def all(self) -> list[FakeResultRow]:
        return self._rows

    def scalar(self) -> Any:
        # Return total count if count query
        return len(self._rows)


class FakeDbSession:
    def __init__(self, rows: list[FakeResultRow]) -> None:
        self.rows = rows
        self.queries: list[Any] = []

    async def execute(self, statement: Any) -> FakeResult:
        self.queries.append(statement)
        # Check if statement is count query
        stmt_str = str(statement).lower()
        if "count" in stmt_str:
            return FakeResult(self.rows)  # Scalar count will read length
        return FakeResult(self.rows)


@pytest.fixture
def mock_rows() -> list[FakeResultRow]:
    quote_id = uuid4()
    version_id = uuid4()
    line_id = uuid4()
    supplier_id = uuid4()
    material_id = uuid4()

    row_data = {
        "id": line_id,
        "quote_id": quote_id,
        "quote_version_id": version_id,
        "supplier_id": supplier_id,
        "supplier_name": "Supplier ABC",
        "supplier_code": "S_ABC",
        "material_id": material_id,
        "material_name": "Corn",
        "material_code": "M_CORN",
        "material_type_name": "Nguyên liệu",
        "material_type_code": "NL",
        "received_date": date(2026, 7, 29),
        "delivery_month": date(2026, 8, 1),
        "price_original": 250.50,
        "currency": "USD",
        "unit": "MT",
        "exchange_rate": 25450.00,
        "exchange_rate_source": "Vietcombank",
        "import_tax_rate_percent": 0.00,
        "processing_cost_vnd_per_kg": 150.00,
        "price_converted_vnd_per_kg": 6525.23,
        "purchase_marked_at": datetime.now(UTC),
        "version_number": 1,
        "version_status": "confirmed",
        "created_by_name": "Admin User",
        "created_at": datetime.now(UTC),
    }
    return [FakeResultRow(row_data)]


@pytest.mark.asyncio
async def test_query_flattened_quotes_returns_items_and_count(
    mock_rows: list[FakeResultRow],
) -> None:
    fake_db = FakeDbSession(mock_rows)
    service = QuoteQueryService(cast(Any, fake_db))

    items, total = await service.query_flattened_quotes(
        global_search="Supplier",
        limit=10,
        offset=0,
    )

    assert total == 1
    assert len(items) == 1
    assert items[0]["supplier_name"] == "Supplier ABC"
    assert items[0]["material_name"] == "Corn"
    assert items[0]["price_converted_vnd_per_kg"] == 6525.23
    assert items[0]["purchased"] is True
    assert len(fake_db.queries) == 2  # one count, one select


@pytest.mark.asyncio
async def test_query_flattened_quotes_uses_lightweight_count(
    mock_rows: list[FakeResultRow],
) -> None:
    fake_db = FakeDbSession(mock_rows)
    service = QuoteQueryService(cast(Any, fake_db))

    await service.query_flattened_quotes(limit=500, offset=-100)

    count_sql = str(fake_db.queries[0]).lower()
    select_sql = str(fake_db.queries[1]).lower()

    assert "count(quote_lines.id)" in count_sql
    assert "anon_1" not in count_sql
    assert "supplier_name" not in count_sql
    assert "quote_versions.status != :status_1" in count_sql
    assert "limit" in select_sql
    assert "offset" in select_sql
