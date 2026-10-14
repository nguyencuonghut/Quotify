"""Bước khôi phục khi trả kết nối về pool của engine chỉ đọc (kế hoạch 5.1, S6), không cần DB."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.db.readonly import _RESTORE_STATEMENTS, _restore_session_defaults


class _Cursor:
    def __init__(self, fail_on: str | None = None) -> None:
        self.executed: list[str] = []
        self.closed = False
        self._fail_on = fail_on

    def execute(self, statement: str) -> None:
        if statement == self._fail_on:
            raise RuntimeError("kết nối hỏng")
        self.executed.append(statement)

    def close(self) -> None:
        self.closed = True


class _Connection:
    def __init__(self, cursor: _Cursor) -> None:
        self._cursor = cursor
        self.commits = 0

    def cursor(self) -> _Cursor:
        return self._cursor

    def commit(self) -> None:
        self.commits += 1


def _state(*, terminate_only: bool = False, asyncio_safe: bool = True) -> Any:
    return SimpleNamespace(terminate_only=terminate_only, asyncio_safe=asyncio_safe)


def test_the_restore_runs_every_statement_in_order_then_commits() -> None:
    cursor = _Cursor()
    connection = _Connection(cursor)

    _restore_session_defaults(connection, None, _state())

    assert cursor.executed == list(_RESTORE_STATEMENTS)
    assert connection.commits == 1
    assert cursor.closed is True


@pytest.mark.parametrize(
    "state",
    [_state(terminate_only=True), _state(asyncio_safe=False)],
    ids=["terminate-only", "not-asyncio-safe"],
)
def test_a_connection_that_is_only_being_discarded_is_not_touched(state: Any) -> None:
    cursor = _Cursor()
    connection = _Connection(cursor)

    _restore_session_defaults(connection, None, state)  # thu gom rác: không được chạy I/O

    assert cursor.executed == [] and connection.commits == 0


def test_a_failing_statement_still_closes_the_cursor_and_does_not_commit() -> None:
    cursor = _Cursor(fail_on="RESET ALL")
    connection = _Connection(cursor)

    with pytest.raises(RuntimeError):
        _restore_session_defaults(connection, None, _state())

    assert cursor.closed is True
    assert connection.commits == 0  # không commit dở dang; SQLAlchemy hủy kết nối này


def test_the_restore_never_uses_statements_that_break_the_prepared_statement_cache() -> None:
    forbidden = ("DISCARD ALL", "DEALLOCATE")
    assert not any(part in statement for statement in _RESTORE_STATEMENTS for part in forbidden)
