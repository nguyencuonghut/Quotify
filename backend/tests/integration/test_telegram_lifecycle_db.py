"""Vòng đời liên kết Telegram trên PostgreSQL thật: hủy, /stop, bị chặn, giải phóng chỗ, dọn dẹp."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest
from bot_harness import ESCAPED_NAME, Bot, linked_user
from db_helpers import create_user, insert_rows, issue_token, next_telegram_id, next_update_id
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telegram_fakes import make_update

from app.models import UserStatus
from app.models.telegram_link_token import TelegramLinkToken
from app.services.telegram_bot_messages import (
    HELP_TEXT,
    NOT_LINKED_TEXT,
    STOPPED_TEXT,
    TELEGRAM_IN_USE_TEXT,
    USER_INACTIVE_TEXT,
)
from app.services.telegram_link_service import TelegramLinkService

pytestmark = pytest.mark.integration


def chat_member_update(
    tg: int, new_status: str, *, chat_type: str = "private"
) -> dict[str, object]:
    return {
        "update_id": next_update_id(),
        "my_chat_member": {
            "chat": {"id": tg, "type": chat_type},
            "from": {"id": tg, "is_bot": False, "first_name": "An"},
            "date": 0,
            "old_chat_member": {"user": {"id": 1, "is_bot": True}, "status": "member"},
            "new_chat_member": {"user": {"id": 1, "is_bot": True}, "status": new_status},
        },
    }


async def _set_user_status(bot: Bot, user_id: object, status: UserStatus) -> None:
    async with bot.session_factory() as session:
        await session.execute(
            text("update users set status = :s where id = :u"),
            {"s": status.value, "u": user_id},
        )
        await session.commit()


async def _set_account_status(bot: Bot, tg: int, status: str) -> None:
    async with bot.session_factory() as session:
        await session.execute(
            text("update telegram_accounts set status = :s where telegram_user_id = :t"),
            {"s": status, "t": tg},
        )
        await session.commit()


async def _status_of(bot: Bot, user_id: object) -> list[tuple[str, str | None]]:
    async with bot.session_factory() as session:
        rows = await session.execute(
            text(
                "select status, revoked_reason from telegram_accounts "
                "where user_id = :u order by created_at, id"
            ),
            {"u": user_id},
        )
        return [(row.status, row.revoked_reason) for row in rows]


# --- hủy liên kết từ web -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unlinking_from_the_web_then_linking_again_does_not_violate_uniqueness(
    bot: Bot,
) -> None:
    user_id, tg = await linked_user(bot)

    async with bot.session_factory() as session:
        service = TelegramLinkService(session)
        revoked = await service.revoke_user_link(user_id, reason="user_unlink")
        again = await service.revoke_user_link(user_id, reason="user_unlink")
        await session.commit()
    assert revoked is not None
    assert again is None
    assert await _status_of(bot, user_id) == [("revoked", "user_unlink")]

    await bot.send(f"/start {await issue_token(bot.session_factory, user_id)}", tg=tg)

    assert await _status_of(bot, user_id) == [("revoked", "user_unlink"), ("active", None)]


# --- /stop ---------------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("initial", ["active", "blocked"])
async def test_stop_revokes_an_active_or_blocked_link(bot: Bot, initial: str) -> None:
    user_id, tg = await linked_user(bot)
    await _set_account_status(bot, tg, initial)

    update_id = await bot.send("/stop", tg=tg)

    assert bot.outbox.texts_to(tg) == [STOPPED_TEXT]
    assert await _status_of(bot, user_id) == [("revoked", "stop_command")]
    [event] = [e for e in await bot.audit(user_id) if e.action == "telegram.unlinked"]
    assert event.entity_type == "telegram_account"
    assert event.metadata_json["channel"] == "telegram"
    assert event.metadata_json["reason"] == "stop_command"
    assert event.request_id == f"tg-update-{update_id}"
    assert str(tg) not in str(event.metadata_json)


@pytest.mark.asyncio
async def test_stop_when_not_linked_only_says_so(bot: Bot) -> None:
    tg = next_telegram_id()

    await bot.send("/stop", tg=tg)

    assert bot.outbox.texts_to(tg) == [NOT_LINKED_TEXT]


@pytest.mark.asyncio
async def test_stop_after_stop_is_harmless(bot: Bot) -> None:
    user_id, tg = await linked_user(bot)
    await bot.send("/stop", tg=tg)

    await bot.send("/stop", tg=tg)

    assert bot.outbox.texts_to(tg) == [STOPPED_TEXT, NOT_LINKED_TEXT]
    assert await _status_of(bot, user_id) == [("revoked", "stop_command")]


# --- bị chặn -------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blocking_and_unblocking_the_bot_toggles_the_link(bot: Bot) -> None:
    user_id, tg = await linked_user(bot)

    await bot.process_raw(chat_member_update(tg, "kicked"))
    assert await _status_of(bot, user_id) == [("blocked", None)]

    await bot.process_raw(chat_member_update(tg, "member"))
    assert await _status_of(bot, user_id) == [("active", None)]
    assert bot.outbox.sent_messages() == []


@pytest.mark.asyncio
async def test_unblocking_never_resurrects_a_revoked_link(bot: Bot) -> None:
    user_id, tg = await linked_user(bot)
    await bot.send("/stop", tg=tg)

    await bot.process_raw(chat_member_update(tg, "member"))
    await bot.process_raw(chat_member_update(tg, "kicked"))

    assert await _status_of(bot, user_id) == [("revoked", "stop_command")]


@pytest.mark.asyncio
async def test_chat_member_changes_outside_private_chats_are_ignored(bot: Bot) -> None:
    user_id, tg = await linked_user(bot)

    await bot.process_raw(chat_member_update(tg, "kicked", chat_type="supergroup"))

    assert await _status_of(bot, user_id) == [("active", None)]


@pytest.mark.asyncio
async def test_a_forbidden_reply_marks_the_account_as_blocked(bot: Bot) -> None:
    user_id, tg = await linked_user(bot)
    bot.outbox.forbidden_chat_ids.add(tg)

    await bot.send("/help", tg=tg)

    assert await _status_of(bot, user_id) == [("blocked", None)]


@pytest.mark.asyncio
async def test_a_blocked_account_still_holds_the_telegram_for_other_users(bot: Bot) -> None:
    _holder, tg = await linked_user(bot)
    await bot.process_raw(chat_member_update(tg, "kicked"))
    other = await create_user(bot.session_factory)

    await bot.send(f"/start {await issue_token(bot.session_factory, other)}", tg=tg)

    assert bot.outbox.texts_to(tg) == [TELEGRAM_IN_USE_TEXT]
    assert await _status_of(bot, other) == []


@pytest.mark.asyncio
async def test_relinking_the_same_blocked_telegram_reactivates_it(bot: Bot) -> None:
    user_id, tg = await linked_user(bot)
    await bot.process_raw(chat_member_update(tg, "kicked"))

    await bot.send(f"/start {await issue_token(bot.session_factory, user_id)}", tg=tg)

    assert bot.outbox.texts_to(tg) == [f"✅ Đã kích hoạt lại liên kết với <b>{ESCAPED_NAME}</b>."]
    assert await _status_of(bot, user_id) == [("active", None)]
    event = [e for e in await bot.audit(user_id) if e.action == "telegram.linked"][-1]
    assert event.metadata_json["reason"] == "reactivated"


# --- giải phóng chỗ khi chủ cũ không còn hoạt động ------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [UserStatus.LOCKED, UserStatus.INACTIVE])
async def test_a_telegram_held_by_an_inactive_user_is_released_for_a_new_link(
    bot: Bot,
    status: UserStatus,
) -> None:
    old_user, tg = await linked_user(bot)
    await _set_user_status(bot, old_user, status)
    new_user = await create_user(bot.session_factory, full_name="Người Mới")

    await bot.send(f"/start {await issue_token(bot.session_factory, new_user)}", tg=tg)

    assert await _status_of(bot, old_user) == [("revoked", "owner_inactive")]
    assert await _status_of(bot, new_user) == [("active", None)]
    assert bot.outbox.texts_to(tg)[0].startswith("✅ Đã liên kết với tài khoản <b>Người Mới</b>")
    [old_account] = await bot.accounts(old_user)
    [event] = [
        e
        for e in await bot.audit(None)  # hệ thống giải phóng, không có người thao tác
        if e.action == "telegram.unlinked" and e.entity_id == str(old_account.id)
    ]
    assert event.metadata_json == {
        "channel": "telegram",
        "telegram_account_id": str(old_account.id),
        "reason": "owner_inactive",
    }


@pytest.mark.asyncio
async def test_an_active_owner_is_never_released(bot: Bot) -> None:
    holder, tg = await linked_user(bot)
    other = await create_user(bot.session_factory)

    await bot.send(f"/start {await issue_token(bot.session_factory, other)}", tg=tg)

    assert await _status_of(bot, holder) == [("active", None)]
    assert await _status_of(bot, other) == []


# --- duy trì liên kết mỗi tin nhận ------------------------------------------------------------


@pytest.mark.asyncio
async def test_every_message_refreshes_username_and_last_seen(bot: Bot) -> None:
    user_id, tg = await linked_user(bot)
    [before] = await bot.accounts(user_id)
    await asyncio.sleep(0.01)

    await bot.send("/help", tg=tg, username="ten_moi")

    [after] = await bot.accounts(user_id)
    assert after.username == "ten_moi"
    assert after.last_seen_at > before.last_seen_at
    assert bot.outbox.texts_to(tg) == [HELP_TEXT]


@pytest.mark.asyncio
async def test_a_message_from_a_blocked_account_proves_it_can_receive_again(bot: Bot) -> None:
    user_id, tg = await linked_user(bot)
    await bot.process_raw(chat_member_update(tg, "kicked"))

    await bot.send("/help", tg=tg)

    assert await _status_of(bot, user_id) == [("active", None)]


@pytest.mark.asyncio
@pytest.mark.parametrize("command", ["/help", "/stop", "/start", "xin chào"])
async def test_users_who_are_no_longer_active_get_a_notice_and_nothing_else(
    bot: Bot,
    command: str,
) -> None:
    user_id, tg = await linked_user(bot)
    await _set_user_status(bot, user_id, UserStatus.LOCKED)

    await bot.send(command, tg=tg)

    assert bot.outbox.texts_to(tg) == [USER_INACTIVE_TEXT]
    assert await _status_of(bot, user_id) == [("active", None)]


# --- dọn dẹp ----------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_removes_only_link_tokens_stale_for_over_seven_days(
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await create_user(session_factory)
    now = datetime.now(UTC)
    # (hết hạn lúc, dùng lúc) -> có bị dọn không
    cases = {
        "expired_long_ago": (now - timedelta(days=8), None, True),
        "expired_recently": (now - timedelta(days=2), None, False),
        "still_valid": (now + timedelta(minutes=5), None, False),
        "used_long_ago": (now - timedelta(days=8), now - timedelta(days=9), True),
        "used_recently": (now - timedelta(days=8), now - timedelta(days=1), False),
    }
    hashes = {name: sha256(name.encode()).hexdigest() for name in cases}
    await insert_rows(
        session_factory,
        *(
            TelegramLinkToken(
                user_id=user_id,
                token_hash=hashes[name],
                expires_at=expires_at,
                used_at=used_at,
            )
            for name, (expires_at, used_at, _) in cases.items()
        ),
    )

    await bot.send("/help", tg=next_telegram_id())  # lần xử lý đầu tiên kích hoạt dọn dẹp

    async with session_factory() as session:
        remaining = set(
            (
                await session.execute(
                    text("select token_hash from telegram_link_tokens where user_id = :u"),
                    {"u": user_id},
                )
            )
            .scalars()
            .all()
        )
    assert remaining == {hashes[name] for name, (_, _, stale) in cases.items() if not stale}


@pytest.mark.asyncio
async def test_bot_username_suffix_and_unknown_telegram_users_are_handled(bot: Bot) -> None:
    tg = next_telegram_id()
    await bot.process_raw(chat_member_update(tg, "kicked"))  # người lạ, không có liên kết

    await bot.process_raw(make_update(next_update_id(), "/stop@Quotify_Bot", user_id=tg))

    assert bot.outbox.texts_to(tg) == [NOT_LINKED_TEXT]
