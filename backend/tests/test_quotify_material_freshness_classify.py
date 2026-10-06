from __future__ import annotations

import pytest

from app.services.quotify_material_freshness_service import FreshnessStatus, classify_freshness


@pytest.mark.parametrize(
    ("update_count", "interval", "age", "expected"),
    [
        (1, 7, 0, "updated"),
        (3, 7, 40, "updated"),  # có cập nhật trong tuần thì luôn là đã cập nhật
        (1, None, 2, "updated"),  # vật tư không theo dõi
        (0, 7, 7, "on_time"),  # đúng bằng chu kỳ vẫn còn hạn
        (0, 7, 0, "on_time"),
        (0, 7, 8, "overdue"),
        (0, 30, 31, "overdue"),
        (0, 7, None, "never"),
        (0, None, None, "never"),
    ],
)
def test_classify_freshness(
    update_count: int,
    interval: int | None,
    age: int | None,
    expected: FreshnessStatus,
) -> None:
    assert (
        classify_freshness(
            update_count=update_count,
            expected_interval_days=interval,
            age_days=age,
        )
        == expected
    )
