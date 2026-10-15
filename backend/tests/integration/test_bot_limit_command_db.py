"""Lệnh `/limit` của chatbot (kế hoạch 5.1, S10): xem lượt đã dùng và còn lại trong ngày."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from bot_harness import Bot
from db_helpers import create_user, issue_token, next_telegram_id
from quota_helpers import gate, tomorrow_text, use_turns
from sqlalchemy import text

from app.services.bot_policy import ChatbotPolicy
from app.services.telegram_bot_messages import HELP_TEXT, UNKNOWN_TEXT


async def _linked(bot: Bot) -> tuple[uuid.UUID, int]:
    user_id = await create_user(bot.session_factory)
    tg = next_telegram_id()
    await bot.send(f"/start {await issue_token(bot.session_factory, user_id)}", tg=tg)
    bot.outbox.requests.clear()
    return user_id, tg


def _policy(**overrides: Any) -> ChatbotPolicy:
    values: dict[str, Any] = {"enabled": True, "usage_gate": gate()}
    values.update(overrides)
    return ChatbotPolicy(**values)


async def test_limit_shows_the_turns_used_left_and_when_they_come_back(
    chatbot_bot_factory: Callable[..., Bot],
) -> None:
    bot = chatbot_bot_factory(_policy())
    user_id, tg = await _linked(bot)
    await use_turns(bot, user_id, tg, 3)

    await bot.send("/limit", tg=tg)

    [reply] = bot.outbox.texts_to(tg)
    assert "đã dùng 3/20, còn 17" in reply  # lượt hỏi
    assert "đã dùng 0/5, còn 5" in reply  # lượt gửi ảnh hoặc PDF
    assert tomorrow_text() in reply
    assert "token" not in reply.lower()


async def test_limit_costs_nothing_and_still_works_when_the_allowance_is_used_up(
    chatbot_bot_factory: Callable[..., Bot],
) -> None:
    bot = chatbot_bot_factory(_policy())
    user_id, tg = await _linked(bot)
    await use_turns(bot, user_id, tg, 20)

    await bot.send("/limit", tg=tg)
    await bot.send("/limit", tg=tg)

    replies = bot.outbox.texts_to(tg)
    assert len(replies) == 2 and all("đã dùng 20/20, còn 0" in reply for reply in replies)
    async with bot.session_factory() as session:
        used = (
            await session.execute(
                text("select count(*) from bot_updates where chat_id = :c"), {"c": tg}
            )
        ).scalar_one()
    assert used == 20  # lệnh không tạo dòng hộp thư, không tốn lượt


async def test_the_other_inline_commands_are_not_blocked_by_the_allowance(
    chatbot_bot_factory: Callable[..., Bot],
) -> None:
    bot = chatbot_bot_factory(_policy())
    user_id, tg = await _linked(bot)
    await use_turns(bot, user_id, tg, 20)

    await bot.send("/help", tg=tg)
    await bot.send("/start", tg=tg)

    help_reply, start_reply = bot.outbox.texts_to(tg)
    assert help_reply == HELP_TEXT
    assert "đã liên kết" in start_reply.lower()


@pytest.mark.parametrize("command", ["/limit", "/limit@quotify_bot", "/LIMIT"])
async def test_limit_is_recognised_however_telegram_spells_it(
    chatbot_bot_factory: Callable[..., Bot], command: str
) -> None:
    bot = chatbot_bot_factory(_policy())
    _, tg = await _linked(bot)

    await bot.send(command, tg=tg)

    assert "Hạn mức hôm nay" in bot.outbox.texts_to(tg)[0]


async def test_limit_is_an_unknown_command_for_someone_who_is_not_linked(
    chatbot_bot_factory: Callable[..., Bot],
) -> None:
    bot = chatbot_bot_factory(_policy())

    await bot.send("/limit", tg=next_telegram_id())

    assert bot.outbox.sent_messages()[0]["text"] == UNKNOWN_TEXT


@pytest.mark.parametrize(
    "policy",
    [
        ChatbotPolicy(enabled=False, usage_gate=gate()),  # chatbot đang tắt
        ChatbotPolicy(
            enabled=True,
            pilot_emails=frozenset({"nguoi.khac@example.com"}),  # ngoài danh sách thử
            usage_gate=gate(),
        ),
        ChatbotPolicy(enabled=True),  # chưa có cổng hạn mức
    ],
    ids=["chatbot-off", "outside-the-pilot-list", "no-gate"],
)
async def test_limit_is_an_unknown_command_when_the_chatbot_is_not_open_to_this_person(
    chatbot_bot_factory: Callable[..., Bot], policy: ChatbotPolicy
) -> None:
    bot = chatbot_bot_factory(policy)
    _, tg = await _linked(bot)

    await bot.send("/limit", tg=tg)

    assert bot.outbox.texts_to(tg) == [UNKNOWN_TEXT]


async def test_limit_counts_today_only_as_of_the_moment_it_is_asked(
    chatbot_bot_factory: Callable[..., Bot],
) -> None:
    bot = chatbot_bot_factory(_policy())
    user_id, tg = await _linked(bot)
    yesterday = datetime.now(UTC).replace(year=2020)
    await use_turns(bot, user_id, tg, 5, received_at=yesterday)

    await bot.send("/limit", tg=tg)

    assert "đã dùng 0/20, còn 20" in bot.outbox.texts_to(tg)[0]
