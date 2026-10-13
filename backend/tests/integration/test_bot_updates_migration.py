"""Migration của hộp thư chatbot chạy từng bước trên database tạm (kế hoạch 5.1, S1)."""

from __future__ import annotations

import pytest
from migration_helpers import run_alembic, sql

pytestmark = pytest.mark.integration

BEFORE = "20261007_0900"
REVISION = "20261013_1000"
EXPECTED_INDEXES = {
    "bot_updates_pkey",
    "ix_bot_updates_chat_open",
    "ix_bot_updates_status_received",
    "ix_bot_updates_user_received",
}


def _table_exists(database_url: str) -> bool:
    return sql(database_url, "SELECT to_regclass('public.bot_updates')")[0][0] is not None


def _indexes(database_url: str) -> dict[str, str]:
    rows = sql(
        database_url,
        "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'bot_updates'",
    )
    return {name: definition for name, definition in rows}


def test_bot_updates_is_created_with_its_indexes_and_dropped_on_downgrade(
    empty_database_url: str,
) -> None:
    run_alembic(empty_database_url, "upgrade", BEFORE)
    assert not _table_exists(empty_database_url)

    run_alembic(empty_database_url, "upgrade", REVISION)
    assert _table_exists(empty_database_url)
    indexes = _indexes(empty_database_url)
    assert set(indexes) == EXPECTED_INDEXES
    # Claim chỉ nhìn các dòng còn mở: chỉ mục từng phần.
    assert "WHERE" in indexes["ix_bot_updates_chat_open"]
    assert "queued" in indexes["ix_bot_updates_chat_open"]

    run_alembic(empty_database_url, "downgrade", BEFORE)
    assert not _table_exists(empty_database_url)

    run_alembic(empty_database_url, "upgrade", REVISION)  # up, down, up
    assert _table_exists(empty_database_url)


def test_bot_updates_rejects_unknown_status_and_kind_and_cascades_on_user_delete(
    empty_database_url: str,
) -> None:
    run_alembic(empty_database_url, "upgrade", REVISION)

    constraints = dict(
        sql(
            empty_database_url,
            "SELECT conname, contype::text FROM pg_constraint "
            "WHERE conrelid = 'bot_updates'::regclass",
        ),
    )
    assert constraints["ck_bot_updates_status"] == "c"
    assert constraints["ck_bot_updates_kind"] == "c"
    # Xóa người dùng thì xóa luôn dữ liệu hội thoại tạm của họ (RR-7: ghi rõ ON DELETE).
    (delete_rule,) = sql(
        empty_database_url,
        "SELECT confdeltype::text FROM pg_constraint "
        "WHERE conrelid = 'bot_updates'::regclass AND contype = 'f'",
    )[0]
    assert delete_rule == "c"
