"""Liên kết Telegram qua `/start <mã>` và đổi tài khoản, trên PostgreSQL thật.

Logic này dựa vào khóa dòng, savepoint và ràng buộc unique của PostgreSQL nên fake session
không kiểm được (K18).
"""

from __future__ import annotations

import asyncio

import pytest
from bot_harness import ESCAPED_NAME, FULL_NAME, Bot, linked_user
from db_helpers import (
    build_account,
    create_user,
    insert_rows,
    issue_token,
    next_telegram_id,
    next_update_id,
)
from sqlalchemy import text
from telegram_fakes import make_update

from app.models import UserStatus
from app.services.telegram_bot_messages import (
    INVALID_LINK_TEXT,
    REPLACED_TEXT,
    START_TEXT,
    TELEGRAM_IN_USE_TEXT,
    USER_INACTIVE_TEXT,
)
from app.services.telegram_link_service import TelegramLinkService

pytestmark = pytest.mark.integration

INVALID_TOKEN = "x" * 43


@pytest.mark.asyncio
async def test_opening_the_deep_link_links_the_telegram_account(bot: Bot) -> None:
    user_id = await create_user(bot.session_factory, full_name=FULL_NAME)
    token = await issue_token(bot.session_factory, user_id)
    tg = next_telegram_id()

    update_id = await bot.send(f"/start {token}", tg=tg, username="an_nguyen")

    assert bot.outbox.texts_to(tg) == [
        f"✅ Đã liên kết với tài khoản <b>{ESCAPED_NAME}</b>. "
        "Bạn sẽ nhận thông báo biến động giá tại đây. Gõ /stop để hủy liên kết."
    ]
    [account] = await bot.accounts(user_id)
    assert (account.telegram_user_id, account.status) == (tg, "active")
    assert (account.username, account.first_name) == ("an_nguyen", "Telegram An")
    async with bot.session_factory() as session:
        link_status = await TelegramLinkService(session).get_status(user_id)
        used = (
            await session.execute(
                text("select used_at is not null from telegram_link_tokens where user_id = :u"),
                {"u": user_id},
            )
        ).scalar_one()
    assert link_status.account is not None
    assert link_status.account.status == "active"
    assert link_status.pending_expires_at is None
    assert used is True

    [event] = await bot.audit(user_id)
    assert event.action == "telegram.linked"
    assert event.entity_type == "telegram_account"
    assert event.entity_id == str(account.id)
    assert event.metadata_json == {"channel": "telegram", "telegram_account_id": str(account.id)}
    assert event.request_id == f"tg-update-{update_id}"
    assert str(tg) not in str(event.metadata_json)
    assert "an_nguyen" not in str(event.metadata_json)


@pytest.mark.asyncio
async def test_the_same_link_cannot_be_used_twice(bot: Bot) -> None:
    user_id = await create_user(bot.session_factory)
    token = await issue_token(bot.session_factory, user_id)
    first_tg, second_tg = next_telegram_id(), next_telegram_id()
    await bot.send(f"/start {token}", tg=first_tg)

    await bot.send(f"/start {token}", tg=second_tg)

    assert bot.outbox.texts_to(second_tg) == [INVALID_LINK_TEXT]
    assert [a.telegram_user_id for a in await bot.accounts(user_id)] == [first_tg]


@pytest.mark.asyncio
async def test_expired_and_unknown_links_are_rejected_without_audit(bot: Bot) -> None:
    user_id = await create_user(bot.session_factory)
    token = await issue_token(bot.session_factory, user_id)
    async with bot.session_factory() as session:
        await session.execute(
            text("update telegram_link_tokens set expires_at = now() - interval '1 second'")
        )
        await session.commit()
    tg = next_telegram_id()

    await bot.send(f"/start {token}", tg=tg)
    await bot.send(f"/start {INVALID_TOKEN}", tg=tg)

    assert bot.outbox.texts_to(tg) == [INVALID_LINK_TEXT, INVALID_LINK_TEXT]
    assert await bot.accounts(user_id) == []
    assert await bot.audit(user_id) == []


@pytest.mark.asyncio
async def test_a_telegram_account_held_by_another_user_is_rejected_and_audited(bot: Bot) -> None:
    _holder, tg = await linked_user(bot)
    other = await create_user(bot.session_factory)
    token = await issue_token(bot.session_factory, other)

    await bot.send(f"/start {token}", tg=tg)

    assert bot.outbox.texts_to(tg) == [TELEGRAM_IN_USE_TEXT]
    assert await bot.accounts(other) == []
    [event] = await bot.audit(other)
    assert event.action == "telegram.link_rejected"
    assert event.metadata_json == {"channel": "telegram", "reason": "telegram_in_use"}
    # Từ chối thì không "đốt" mã: người dùng giải phóng Telegram xong có thể dùng lại.
    async with bot.session_factory() as session:
        used = (
            await session.execute(
                text("select used_at from telegram_link_tokens where user_id = :u"),
                {"u": other},
            )
        ).scalar_one()
    assert used is None


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [UserStatus.INACTIVE, UserStatus.LOCKED])
async def test_users_who_are_not_active_cannot_link(bot: Bot, status: UserStatus) -> None:
    user_id = await create_user(bot.session_factory, status=status)
    token = await issue_token(bot.session_factory, user_id)
    tg = next_telegram_id()

    await bot.send(f"/start {token}", tg=tg)

    assert bot.outbox.texts_to(tg) == [USER_INACTIVE_TEXT]
    assert await bot.accounts(user_id) == []
    [event] = await bot.audit(user_id)
    assert event.action == "telegram.link_rejected"
    assert event.metadata_json == {"channel": "telegram", "reason": "user_inactive"}


@pytest.mark.asyncio
async def test_the_same_person_on_the_same_telegram_is_idempotent(bot: Bot) -> None:
    user_id, tg = await linked_user(bot)
    token = await issue_token(bot.session_factory, user_id)

    await bot.send(f"/start {token}", tg=tg)

    assert bot.outbox.texts_to(tg) == [
        f"Tài khoản Telegram này đã liên kết với <b>{ESCAPED_NAME}</b>. Gõ /help để xem hướng dẫn."
    ]
    assert len(await bot.accounts(user_id)) == 1
    assert [e.action for e in await bot.audit(user_id)] == ["telegram.linked"]


@pytest.mark.asyncio
async def test_switching_to_another_telegram_account_replaces_the_old_link(bot: Bot) -> None:
    user_id, old_tg = await linked_user(bot)
    [old] = await bot.accounts(user_id)
    new_tg = next_telegram_id()
    token = await issue_token(bot.session_factory, user_id)

    await bot.send(f"/start {token}", tg=new_tg)

    accounts = await bot.accounts(user_id)
    assert [(a.telegram_user_id, a.status, a.revoked_reason) for a in accounts] == [
        (old_tg, "revoked", "replaced"),
        (new_tg, "active", None),
    ]
    assert bot.outbox.texts_to(new_tg)[0].startswith("✅ Đã liên kết với tài khoản")
    assert bot.outbox.texts_to(old_tg) == [REPLACED_TEXT]
    event = (await bot.audit(user_id))[-1]
    assert event.action == "telegram.linked"
    assert event.metadata_json == {
        "channel": "telegram",
        "telegram_account_id": str(accounts[1].id),
        "replaced_account_id": str(old.id),
    }


@pytest.mark.asyncio
async def test_failing_to_notify_the_old_chat_does_not_undo_the_switch(bot: Bot) -> None:
    user_id, old_tg = await linked_user(bot)
    new_tg = next_telegram_id()
    bot.outbox.forbidden_chat_ids.add(old_tg)
    token = await issue_token(bot.session_factory, user_id)

    await bot.send(f"/start {token}", tg=new_tg)

    assert [(a.telegram_user_id, a.status) for a in await bot.accounts(user_id)] == [
        (old_tg, "revoked"),
        (new_tg, "active"),
    ]
    assert len(bot.outbox.texts_to(new_tg)) == 1


@pytest.mark.asyncio
async def test_a_losing_race_for_the_new_telegram_rolls_back_the_revocation(
    bot: Bot,
) -> None:
    """Chèn tài khoản mới vi phạm unique thì việc thu hồi tài khoản cũ phải bị hoàn tác."""
    user_id, old_tg = await linked_user(bot)
    rival = await create_user(bot.session_factory)
    taken_tg = next_telegram_id()
    await insert_rows(bot.session_factory, build_account(rival, taken_tg))

    async with bot.session_factory() as session:
        service = TelegramLinkService(session)
        existing = await service.find_holding_account(user_id)
        assert existing is not None
        result = await service.attach_account(
            user_id=user_id,
            existing=existing,
            telegram_user_id=taken_tg,
            chat_id=taken_tg,
            username=None,
            first_name=None,
        )
        await session.commit()

    assert result.account is None
    assert result.violated_constraint == "uq_telegram_accounts_holding_telegram_user"
    assert [(a.telegram_user_id, a.status) for a in await bot.accounts(user_id)] == [
        (old_tg, "active")
    ]


@pytest.mark.asyncio
async def test_two_telegram_accounts_opening_the_same_link_only_one_wins(bot: Bot) -> None:
    user_id = await create_user(bot.session_factory)
    token = await issue_token(bot.session_factory, user_id)
    first_tg, second_tg = next_telegram_id(), next_telegram_id()

    await asyncio.gather(
        bot.send(f"/start {token}", tg=first_tg),
        bot.send(f"/start {token}", tg=second_tg),
    )

    accounts = await bot.accounts(user_id)
    assert len(accounts) == 1
    assert accounts[0].status == "active"
    winner = accounts[0].telegram_user_id
    loser = second_tg if winner == first_tg else first_tg
    assert bot.outbox.texts_to(loser) == [INVALID_LINK_TEXT]
    assert bot.outbox.texts_to(winner)[0].startswith("✅ Đã liên kết")


@pytest.mark.asyncio
async def test_start_without_a_code_depends_on_whether_telegram_is_linked(bot: Bot) -> None:
    _user, linked_tg = await linked_user(bot)
    stranger = next_telegram_id()

    await bot.send("/start", tg=stranger)
    await bot.send("/start", tg=linked_tg)

    assert bot.outbox.texts_to(stranger) == [START_TEXT]
    assert bot.outbox.texts_to(linked_tg) == [
        f"Tài khoản Telegram này đã liên kết với <b>{ESCAPED_NAME}</b>. Gõ /help để xem hướng dẫn."
    ]


@pytest.mark.asyncio
async def test_only_private_chats_can_redeem_a_link(bot: Bot) -> None:
    user_id = await create_user(bot.session_factory)
    token = await issue_token(bot.session_factory, user_id)

    await bot.runner.process(
        make_update(
            next_update_id(), f"/start {token}", chat_type="group", user_id=next_telegram_id()
        )
    )

    assert bot.outbox.sent_messages() == []
    assert await bot.accounts(user_id) == []
