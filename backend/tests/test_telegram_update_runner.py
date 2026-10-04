from __future__ import annotations

import logging

import pytest
from telegram_fakes import FakeStore, Outbox, make_client, make_session_factory, make_update

from app.services.telegram_update_runner import (
    TelegramTemporaryError,
    TelegramUpdateRunner,
    TelegramUserRateLimiter,
)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def build_runner(
    store: FakeStore,
    outbox: Outbox,
    *,
    clock: Clock | None = None,
    limit: int = 10,
) -> TelegramUpdateRunner:
    fake_clock = clock or Clock()
    client, _http = make_client(outbox)
    return TelegramUpdateRunner(
        session_factory=make_session_factory(store),
        client=client,
        rate_limiter=TelegramUserRateLimiter(limit=limit, window_seconds=60, clock=fake_clock),
        clock=fake_clock,
    )


@pytest.mark.asyncio
async def test_updates_over_the_per_user_limit_are_dropped_before_touching_the_database() -> None:
    store, outbox = FakeStore(), Outbox()
    runner = build_runner(store, outbox, limit=2)

    for update_id in (1, 2, 3):
        await runner.process(make_update(update_id, "/help", user_id=111))

    assert store.processed == {1, 2}
    assert len(outbox.sent_messages()) == 2


@pytest.mark.asyncio
async def test_limit_is_per_user_and_resets_after_the_window() -> None:
    store, outbox, clock = FakeStore(), Outbox(), Clock()
    runner = build_runner(store, outbox, clock=clock, limit=1)

    await runner.process(make_update(1, "/help", user_id=111))
    await runner.process(make_update(2, "/help", user_id=222))
    await runner.process(make_update(3, "/help", user_id=111))
    assert store.processed == {1, 2}

    clock.now += 61
    await runner.process(make_update(4, "/help", user_id=111))
    assert store.processed == {1, 2, 4}


@pytest.mark.asyncio
async def test_cleanup_of_old_processed_updates_runs_at_most_once_per_hour() -> None:
    store, outbox, clock = FakeStore(), Outbox(), Clock()
    runner = build_runner(store, outbox, clock=clock)

    def deletes() -> int:
        return sum(1 for sql in store.executed if sql.startswith("DELETE FROM telegram_processed"))

    await runner.process(make_update(1, user_id=1))
    assert deletes() == 1
    await runner.process(make_update(2, user_id=2))
    assert deletes() == 1

    clock.now += 3601
    await runner.process(make_update(3, user_id=3))
    assert deletes() == 2


@pytest.mark.asyncio
async def test_cleanup_also_removes_stale_link_tokens_at_most_once_per_hour() -> None:
    store, outbox, clock = FakeStore(), Outbox(), Clock()
    runner = build_runner(store, outbox, clock=clock)

    def token_deletes() -> int:
        return sum(
            1 for sql in store.executed if sql.startswith("DELETE FROM telegram_link_tokens")
        )

    await runner.process(make_update(1, user_id=1))
    await runner.process(make_update(2, user_id=2))
    assert token_deletes() == 1

    clock.now += 3601
    await runner.process(make_update(3, user_id=3))
    assert token_deletes() == 2


@pytest.mark.asyncio
async def test_a_forbidden_reply_marks_the_chat_as_blocked_without_failing() -> None:
    store, outbox = FakeStore(), Outbox()
    outbox.forbidden_chat_ids.add(111)
    runner = build_runner(store, outbox)

    await runner.process(make_update(1, "/help", user_id=111))

    assert store.processed == {1}
    assert any(sql.startswith("UPDATE telegram_accounts") for sql in store.executed)


@pytest.mark.asyncio
async def test_failing_to_mark_blocked_never_breaks_update_processing() -> None:
    store, outbox = FakeStore(), Outbox()
    store.fail_on_update = RuntimeError("db hiccup")
    outbox.forbidden_chat_ids.add(111)
    runner = build_runner(store, outbox)

    await runner.process(make_update(1, "/help", user_id=111))

    assert store.processed == {1}
    assert len(outbox.sent_messages()) == 1


@pytest.mark.asyncio
async def test_cleanup_failure_never_breaks_update_processing() -> None:
    store, outbox = FakeStore(), Outbox()
    store.fail_on_delete = RuntimeError("db hiccup")
    runner = build_runner(store, outbox)

    await runner.process(make_update(1, "/help"))

    assert store.processed == {1}
    assert len(outbox.sent_messages()) == 1


@pytest.mark.asyncio
async def test_failing_to_record_a_poison_update_is_a_temporary_failure() -> None:
    store, outbox = FakeStore(), Outbox()
    runner = build_runner(store, outbox)
    store.fail_next = [ValueError("boom"), RuntimeError("db down")]

    with pytest.raises(TelegramTemporaryError):
        await runner.process(make_update(5, "/help"))

    assert store.processed == set()
    assert outbox.sent_messages() == []


@pytest.mark.asyncio
async def test_update_content_is_never_logged(caplog: pytest.LogCaptureFixture) -> None:
    store, outbox = FakeStore(), Outbox()
    outbox.status_code = 400
    runner = build_runner(store, outbox)

    with caplog.at_level(logging.DEBUG):
        await runner.process(make_update(6, "/start SECRET_LINK_CODE_123"))

    assert "SECRET_LINK_CODE_123" not in caplog.text
    assert "telegram.send_failed" in caplog.text
