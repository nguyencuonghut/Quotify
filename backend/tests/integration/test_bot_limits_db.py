"""Chặn lũ và tin không phải văn bản của đường ống chatbot (kế hoạch 5.1, S5).

Tin không phải văn bản (ảnh, tài liệu, giọng nói, sticker) của người dùng đủ điều kiện nhận một câu
cố định, không vào hộp thư. Tin vượt trần số tin đang chờ của chat được từ chối lịch sự và không ghi
hộp thư. Chat nhóm và tin bị sửa không bao giờ vào đường ống.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from bot_harness import Bot, linked_user
from db_helpers import next_telegram_id, next_update_id
from sqlalchemy import text
from telegram_fakes import make_media_update, make_update

from app.services.bot_policy import ChatbotPolicy
from app.services.telegram_bot_messages import NON_TEXT_TEXT, PENDING_LIMIT_TEXT, UNKNOWN_TEXT
from app.services.telegram_update_runner import TelegramUserRateLimiter


@pytest.mark.parametrize("kind", ["photo", "document", "voice", "sticker", "animation"])
async def test_a_non_text_message_gets_a_fixed_reply_and_never_reaches_the_inbox(
    chatbot_bot: Bot,
    kind: str,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)

    await bot.process_raw(make_media_update(next_update_id(), kind, user_id=tg))

    assert bot.outbox.texts_to(tg) == [NON_TEXT_TEXT]
    assert await bot.inbox_rows(tg) == []
    assert bot.dispatcher.notified == []


async def test_a_photo_caption_is_not_handed_to_the_chatbot_as_a_question(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)

    await bot.process_raw(
        make_media_update(next_update_id(), "photo", user_id=tg, caption="báo giá này đúng không?")
    )

    assert bot.outbox.texts_to(tg) == [NON_TEXT_TEXT]
    assert await bot.inbox_rows(tg) == []


async def test_a_message_that_is_neither_text_nor_a_known_attachment_gets_the_same_reply(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update = make_media_update(next_update_id(), "photo", user_id=tg)
    del update["message"]["photo"]
    update["message"]["location"] = {"latitude": 10.8, "longitude": 106.7}

    await bot.process_raw(update)

    assert bot.outbox.texts_to(tg) == [NON_TEXT_TEXT]
    assert await bot.inbox_rows(tg) == []


@pytest.mark.parametrize(
    "extra",
    [
        {"contact": {"phone_number": "0900000000", "first_name": "An"}},
        {"poll": {"id": "1", "question": "?"}},
        {"dice": {"emoji": "🎲", "value": 3}},
    ],
)
async def test_other_content_a_user_can_send_gets_the_same_fixed_reply(
    chatbot_bot: Bot,
    extra: dict[str, object],
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update = make_media_update(next_update_id(), "photo", user_id=tg)
    del update["message"]["photo"]
    update["message"].update(extra)

    await bot.process_raw(update)

    assert bot.outbox.texts_to(tg) == [NON_TEXT_TEXT]
    assert await bot.inbox_rows(tg) == []


async def test_a_service_message_keeps_the_old_answer_instead_of_text_only_notice(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update = make_media_update(next_update_id(), "photo", user_id=tg)
    del update["message"]["photo"]
    update["message"]["pinned_message"] = {"message_id": 1}  # người dùng ghim một tin trong chat

    await bot.process_raw(update)

    assert bot.outbox.texts_to(tg) == [UNKNOWN_TEXT]
    assert await bot.inbox_rows(tg) == []


async def test_a_text_of_only_whitespace_is_not_handed_to_the_chatbot(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)

    await bot.send("   \n  ", tg=tg)

    assert bot.outbox.texts_to(tg) == [UNKNOWN_TEXT]
    assert await bot.inbox_rows(tg) == []


async def test_with_the_chatbot_off_a_photo_keeps_the_old_answer(bot: Bot) -> None:
    _, tg = await linked_user(bot)

    await bot.process_raw(make_media_update(next_update_id(), "photo", user_id=tg))

    assert bot.outbox.texts_to(tg) == [UNKNOWN_TEXT]


async def test_a_photo_from_a_user_outside_the_pilot_list_keeps_the_old_answer(
    chatbot_bot_factory: Callable[..., Bot],
) -> None:
    bot = chatbot_bot_factory(ChatbotPolicy(enabled=True, pilot_emails=frozenset({"khac@x.vn"})))
    _, tg = await linked_user(bot)

    await bot.process_raw(make_media_update(next_update_id(), "photo", user_id=tg))

    assert bot.outbox.texts_to(tg) == [UNKNOWN_TEXT]


async def test_a_photo_from_an_unlinked_telegram_account_keeps_the_old_answer(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    tg = next_telegram_id()

    await bot.process_raw(make_media_update(next_update_id(), "photo", user_id=tg))

    assert bot.outbox.texts_to(tg) == [UNKNOWN_TEXT]


# --- trần số tin đang chờ mỗi chat ---------------------------------------------------------------


def _capped(limit: int) -> ChatbotPolicy:
    return ChatbotPolicy(enabled=True, max_pending_per_chat=limit)


async def test_a_message_beyond_the_pending_cap_is_declined_politely_and_not_queued(
    chatbot_bot_factory: Callable[..., Bot],
) -> None:
    bot = chatbot_bot_factory(_capped(3))
    _, tg = await linked_user(bot)
    accepted = [await bot.send(f"câu {number}", tg=tg) for number in range(1, 4)]

    declined = await bot.send("câu 4", tg=tg)

    assert [
        r.update_id for r in await bot.inbox_rows(tg)
    ] == accepted  # đúng 3 dòng, không có dòng 4
    assert bot.dispatcher.notified == [
        (tg, update_id) for update_id in accepted
    ]  # không rung chuông
    assert bot.outbox.texts_to(tg) == [PENDING_LIMIT_TEXT]
    assert declined not in {r.update_id for r in await bot.inbox_rows(tg)}


async def test_finished_rows_do_not_count_towards_the_pending_cap(
    chatbot_bot_factory: Callable[..., Bot],
) -> None:
    bot = chatbot_bot_factory(_capped(2))
    user_id, tg = await linked_user(bot)
    for status in ("replied", "failed", "dropped", "replied"):
        await bot.insert_row(
            tg, user_id, next_update_id(), status=status, finished_at=datetime.now(UTC)
        )

    update_id = await bot.send("câu mới", tg=tg)

    assert update_id in {r.update_id for r in await bot.inbox_rows(tg)}  # vẫn được nhận
    assert bot.outbox.texts_to(tg) == []


async def test_both_queued_and_processing_rows_count_towards_the_pending_cap(
    chatbot_bot_factory: Callable[..., Bot],
) -> None:
    bot = chatbot_bot_factory(_capped(2))
    user_id, tg = await linked_user(bot)
    await bot.insert_row(
        tg,
        user_id,
        next_update_id(),
        status="processing",
        attempts=1,
        lease_until=datetime.now(UTC) + timedelta(seconds=60),
    )
    await bot.insert_row(tg, user_id, next_update_id())  # queued

    await bot.send("quá trần", tg=tg)

    assert bot.outbox.texts_to(tg) == [PENDING_LIMIT_TEXT]
    assert len(await bot.inbox_rows(tg)) == 2


async def test_the_pending_cap_is_per_chat_and_frees_up_once_the_worker_answers(
    chatbot_bot_factory: Callable[..., Bot],
) -> None:
    bot = chatbot_bot_factory(_capped(2))
    _, busy_chat = await linked_user(bot)
    _, other_chat = await linked_user(bot)
    for number in range(2):
        await bot.send(f"câu {number}", tg=busy_chat)

    other_update = await bot.send("chat khác", tg=other_chat)  # chat khác không bị ảnh hưởng
    await bot.send("quá trần", tg=busy_chat)
    await bot.drain(busy_chat)  # worker trả lời xong hai câu
    after = await bot.send("hỏi tiếp", tg=busy_chat)

    assert [r.update_id for r in await bot.inbox_rows(other_chat)] == [other_update]
    assert bot.outbox.texts_to(other_chat) == []
    assert after in {r.update_id for r in await bot.inbox_rows(busy_chat)}  # được nhận lại
    assert bot.outbox.texts_to(busy_chat).count(PENDING_LIMIT_TEXT) == 1


async def test_a_replayed_update_that_was_declined_is_declined_only_once(
    chatbot_bot_factory: Callable[..., Bot],
) -> None:
    bot = chatbot_bot_factory(_capped(1))
    _, tg = await linked_user(bot)
    await bot.send("câu đầu", tg=tg)
    declined = make_update(next_update_id(), "quá trần", user_id=tg)

    await bot.process_raw(declined)
    await bot.process_raw(declined)  # Telegram gửi lại cùng update

    assert bot.outbox.texts_to(tg) == [PENDING_LIMIT_TEXT]
    assert len(await bot.inbox_rows(tg)) == 1


async def test_concurrent_messages_of_one_user_never_exceed_the_pending_cap(
    chatbot_bot_factory: Callable[..., Bot],
) -> None:
    """Trần chính xác kể cả khi các update của cùng một người xử lý đồng thời.

    Nó dựa vào khóa dòng của `telegram_accounts`: `touch_linked_identity` luôn ghi `last_seen_at`
    nên các giao dịch của cùng một người xếp hàng ở đó, và phép đếm của giao dịch sau thấy dòng
    của giao dịch trước. Nếu ai đó bỏ lần ghi này thì test này đỏ.
    """
    bot = chatbot_bot_factory(_capped(2))
    _, tg = await linked_user(bot)

    await asyncio.gather(*(bot.send(f"câu {number}", tg=tg) for number in range(6)))

    assert len(await bot.inbox_rows(tg)) == 2  # không vượt trần dù 6 update chạy cùng lúc


# --- album ảnh và lũ tin: một thông báo, không ăn suất của tin văn bản ----------------------------


class _Clock:
    """Đồng hồ giả của runner: thông báo giới hạn chỉ gửi một lần mỗi 10 giây mỗi chat."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


async def test_an_album_gets_one_fixed_reply_and_the_question_after_it_is_still_answered(
    chatbot_bot_factory: Callable[..., Bot],
) -> None:
    # Bộ giới hạn tin văn bản chỉ còn 3 suất: nếu 10 ảnh của album ăn hết thì câu hỏi bị bỏ im lặng.
    bot = chatbot_bot_factory(
        ChatbotPolicy(enabled=True), rate_limiter=TelegramUserRateLimiter(limit=3)
    )
    _, tg = await linked_user(bot)  # `/start` ăn một suất
    for _ in range(10):
        update = make_media_update(next_update_id(), "photo", user_id=tg, media_group_id="album-1")
        await bot.process_raw(update)

    question = await bot.send("báo giá này đúng không?", tg=tg)

    assert bot.outbox.texts_to(tg) == [NON_TEXT_TEXT]  # đúng một thông báo cho cả album
    assert [r.update_id for r in await bot.inbox_rows(tg)] == [question]  # câu hỏi vẫn được nhận


async def test_the_fixed_reply_is_sent_again_once_the_quiet_period_is_over(
    chatbot_bot_factory: Callable[..., Bot],
) -> None:
    clock = _Clock()
    bot = chatbot_bot_factory(ChatbotPolicy(enabled=True), clock=clock)
    _, tg = await linked_user(bot)

    await bot.process_raw(make_media_update(next_update_id(), "photo", user_id=tg))
    await bot.process_raw(make_media_update(next_update_id(), "photo", user_id=tg))
    clock.now += 9
    await bot.process_raw(make_media_update(next_update_id(), "photo", user_id=tg))
    assert bot.outbox.texts_to(tg) == [NON_TEXT_TEXT]  # chưa đủ 10 giây

    clock.now += 2
    await bot.process_raw(make_media_update(next_update_id(), "photo", user_id=tg))

    assert bot.outbox.texts_to(tg) == [NON_TEXT_TEXT, NON_TEXT_TEXT]


async def test_the_quiet_period_is_kept_per_chat_not_shared_between_chats(
    chatbot_bot_factory: Callable[..., Bot],
) -> None:
    bot = chatbot_bot_factory(ChatbotPolicy(enabled=True))
    _, first_chat = await linked_user(bot)
    _, second_chat = await linked_user(bot)

    await bot.process_raw(make_media_update(next_update_id(), "photo", user_id=first_chat))
    await bot.process_raw(make_media_update(next_update_id(), "photo", user_id=second_chat))

    assert bot.outbox.texts_to(first_chat) == [NON_TEXT_TEXT]
    assert bot.outbox.texts_to(second_chat) == [NON_TEXT_TEXT]  # chat kia không bị im lặng oan


async def test_a_flood_of_text_gets_one_pending_notice_per_quiet_period(
    chatbot_bot_factory: Callable[..., Bot],
) -> None:
    clock = _Clock()
    bot = chatbot_bot_factory(_capped(1), clock=clock)
    _, tg = await linked_user(bot)
    await bot.send("câu đầu", tg=tg)

    for number in range(4):
        await bot.send(f"dồn dập {number}", tg=tg)
    assert bot.outbox.texts_to(tg) == [PENDING_LIMIT_TEXT]  # một thông báo, không phải bốn

    clock.now += 11
    await bot.send("lại dồn dập", tg=tg)

    assert bot.outbox.texts_to(tg) == [PENDING_LIMIT_TEXT, PENDING_LIMIT_TEXT]
    assert len(await bot.inbox_rows(tg)) == 1  # các tin bị từ chối không bao giờ vào hộp thư


async def test_non_text_messages_have_their_own_rate_limit_that_still_bounds_a_flood(
    chatbot_bot_factory: Callable[..., Bot],
) -> None:
    bot = chatbot_bot_factory(
        ChatbotPolicy(enabled=True), media_rate_limiter=TelegramUserRateLimiter(limit=2)
    )
    _, tg = await linked_user(bot)
    ids = [next_update_id() for _ in range(5)]

    for update_id in ids:
        await bot.process_raw(make_media_update(update_id, "photo", user_id=tg))

    async with bot.session_factory() as session:
        recorded = (
            await session.execute(
                text("select count(*) from telegram_processed_updates where update_id = any(:ids)"),
                {"ids": ids},
            )
        ).scalar_one()
    assert recorded == 2  # từ ảnh thứ ba, bộ giới hạn bỏ tin trước cả khi chạm DB


# --- chat nhóm và tin bị sửa không vào đường ống ------------------------------------------------


@pytest.mark.parametrize("chat_type", ["group", "supergroup", "channel"])
async def test_messages_in_group_chats_are_ignored_even_from_a_linked_user(
    chatbot_bot: Bot,
    chat_type: str,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    text_update = make_update(next_update_id(), "xin chào", user_id=tg, chat_type=chat_type)
    photo_update = make_media_update(next_update_id(), "photo", user_id=tg, chat_type=chat_type)

    await bot.process_raw(text_update)
    await bot.process_raw(photo_update)

    assert bot.outbox.texts_to(tg) == []
    assert await bot.inbox_rows(tg) == []


async def test_an_edited_message_is_not_handed_to_the_chatbot(chatbot_bot: Bot) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    edited = make_update(next_update_id(), "câu đã sửa", user_id=tg)
    edited["edited_message"] = edited.pop("message")

    await bot.process_raw(edited)

    assert bot.outbox.texts_to(tg) == []
    assert await bot.inbox_rows(tg) == []
