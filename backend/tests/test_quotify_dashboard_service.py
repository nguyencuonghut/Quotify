from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.services.quotify_dashboard_service import QuotifyDashboardService


class FakeResultRow:
    def __init__(self, data: dict[str, object]) -> None:
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

    service = QuotifyDashboardService(fake_db)  # type: ignore[arg-type]
    response = await service.get_entry_kpis(supplier_type="domestic")

    assert response["total_quote_count"] == 3
    assert response["user_kpis"][0]["user_id"] == user_id
    assert response["user_kpis"][0]["user_label"] == "Buyer One"
    assert response["user_kpis"][0]["quote_count"] == 2
    assert response["user_kpis"][1]["user_label"] == "Không xác định"
    assert len(fake_db.queries) == 2
    assert "quote_versions.status = :status_1" in str(fake_db.queries[0])
    assert "suppliers.supplier_type" in str(fake_db.queries[0])
    assert "LIKE" in str(fake_db.queries[0])


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

    service = QuotifyDashboardService(fake_db)  # type: ignore[arg-type]
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
    assert "suppliers.supplier_type" in str(fake_db.queries[0])
    assert "LIKE" in str(fake_db.queries[0])


def _price_trend_point_row(*, received_date: date, line_id: object) -> FakeResultRow:
    return FakeResultRow(
        {
            "received_date": received_date,
            "delivery_month": date(2026, 8, 1),
            "converted_price_vnd_per_kg": Decimal("6500.00"),
            "supplier_id": uuid4(),
            "supplier_name": "Supplier ABC",
            "supplier_code": "ABC",
            "supplier_type": "international",
            "material_id": uuid4(),
            "material_name": "Bắp hạt",
            "material_code": "CORN",
            "quote_id": uuid4(),
            "quote_version_id": uuid4(),
            "line_id": line_id,
            "purchased": False,
            "purchase_marked_at": None,
            "confirmed_at": datetime(2026, 7, 20, 8, 0, tzinfo=UTC),
        }
    )


@pytest.mark.asyncio
async def test_get_price_trends_prefers_most_recent_points_when_over_the_limit() -> None:
    """Khi tổng số dòng lịch sử vượt point_limit, chart phải ưu tiên giữ lại
    các báo giá GẦN NHẤT (không phải cũ nhất) — bug thật đã gặp: dashboard mặc
    định không lọc received_date, DB có >16k dòng từ 2023, nên trước khi sửa,
    LIMIT luôn lấy đúng 500 dòng cũ nhất và chart không bao giờ hiện dữ liệu
    gần hiện tại."""
    newest_line_id = uuid4()
    oldest_line_id = uuid4()

    # DB thật với ORDER BY received_date DESC + LIMIT sẽ trả về dòng mới nhất
    # trước — FakeResult mô phỏng đúng thứ tự đó để kiểm tra _get_points có
    # đảo lại đúng thành tăng dần (cũ -> mới) hay không.
    newest_row = _price_trend_point_row(received_date=date(2026, 8, 1), line_id=newest_line_id)
    oldest_row = _price_trend_point_row(received_date=date(2023, 10, 10), line_id=oldest_line_id)

    fake_db = FakeDbSession(
        [
            FakeResult(
                [
                    FakeResultRow(
                        {
                            "min_price": Decimal("6500.00"),
                            "max_price": Decimal("6500.00"),
                            "avg_price": Decimal("6500.00"),
                            "total_lines": 2,
                            "total_quotes": 2,
                            "purchased_lines": 0,
                        }
                    )
                ]
            ),
            FakeResult([newest_row, oldest_row]),
        ]
    )

    service = QuotifyDashboardService(fake_db)  # type: ignore[arg-type]
    response = await service.get_price_trends(point_limit=1)

    points_query = str(fake_db.queries[1])
    assert "received_date DESC" in points_query

    # Kết quả trả về vẫn phải theo thứ tự tăng dần (cũ -> mới) để không phá
    # giả định của phần build chart ở tầng trên, dù DB đã trả về DESC.
    assert [point["line_id"] for point in response["points"]] == [oldest_line_id, newest_line_id]


@pytest.mark.asyncio
async def test_get_weekly_entry_activity_includes_active_users_without_quotes() -> None:
    user_with_quotes_id = uuid4()
    user_without_quotes_id = uuid4()
    fake_db = FakeDbSession(
        [
            FakeResult(
                [
                    FakeResultRow(
                        {
                            "user_id": user_with_quotes_id,
                            "user_email": "buyer@example.com",
                            "user_full_name": "Buyer One",
                            "quote_count": 3,
                            "last_quote_created_at": datetime(2026, 7, 28, 9, 0, tzinfo=UTC),
                        }
                    ),
                    FakeResultRow(
                        {
                            "user_id": user_without_quotes_id,
                            "user_email": "quiet@example.com",
                            "user_full_name": "Quiet User",
                            "quote_count": 0,
                            "last_quote_created_at": None,
                        }
                    ),
                ]
            )
        ]
    )

    service = QuotifyDashboardService(fake_db)  # type: ignore[arg-type]
    response = await service.get_weekly_entry_activity(week_start=date(2026, 7, 29))

    assert response["week_start"] == date(2026, 7, 27)
    assert response["week_end"] == date(2026, 8, 2)
    assert response["total_quote_count"] == 3
    assert response["active_user_count"] == 2
    assert response["users_with_quotes"] == 1
    assert response["users_without_quotes"] == 1
    assert response["user_activities"][0]["has_warning"] is False
    assert response["user_activities"][1]["user_id"] == user_without_quotes_id
    assert response["user_activities"][1]["has_warning"] is True
    assert "quotes.created_at >= :created_at_1" in str(fake_db.queries[0])
    assert "quote_versions.status = :status_1" in str(fake_db.queries[0])
