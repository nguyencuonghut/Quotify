"""Bấm nút Giá đúng / Nhập sai qua runner Telegram trên PostgreSQL thật (Slice 13, L22 đến L24)."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import date

import pytest
from price_alert_scene import Scene
from sqlalchemy import select, update
from telegram_fakes import Outbox, make_client
from test_price_alert_anomaly_messages_db import build, flag, new_run, scene  # noqa: F401

import app.services.telegram_update_runner as runner_module
from app.models import PriceAlertEvent, PriceAlertMessage, TelegramAccount
from app.services.price_alert_review_service import PriceAlertReviewService
from app.services.telegram_update_runner import TelegramUpdateRunner, TelegramUserRateLimiter

pytestmark = pytest.mark.integration

_ids = iter(range(900_000, 999_999))


class Setup:
    def __init__(self, scene: Scene, runner: TelegramUpdateRunner, outbox: Outbox) -> None:  # noqa: F811
        self.scene = scene
        self.runner = runner
        self.outbox = outbox

    async def person_ids(self, user_id: uuid.UUID) -> tuple[int, int]:
        async with self.scene.sf() as session:
            row = (
                await session.execute(
                    select(TelegramAccount.telegram_user_id, TelegramAccount.chat_id).where(
                        TelegramAccount.user_id == user_id
                    )
                )
            ).one()
        return row[0], row[1]

    async def press(
        self, user_id: uuid.UUID, data: str, message_id: int = 555, *, chat: int | None = None
    ) -> None:
        telegram_id, chat_id = await self.person_ids(user_id)
        await self.runner.process(
            {
                "update_id": next(_ids),
                "callback_query": {
                    "id": f"cb{next(_ids)}",
                    "from": {"id": telegram_id, "is_bot": False, "first_name": "Q"},
                    "message": {
                        "message_id": message_id,
                        "chat": {"id": chat if chat is not None else chat_id, "type": "private"},
                    },
                    "data": data,
                },
            }
        )

    async def card(
        self, manager: uuid.UUID, *, months: int = 1, message_id: int = 555
    ) -> list[uuid.UUID]:
        """Thẻ đã gửi cho `manager` với `months` điểm; trả các event_id."""
        run = await new_run(self.scene.sf)
        events = [
            await flag(
                self.scene.sf,
                run,
                self.scene.material,
                None,
                month=date(2052 + index // 12, index % 12 + 1, 1),
                with_line=True,
            )
            for index in range(months)
        ]
        await build(self.scene.sf, run)
        async with self.scene.sf() as session:
            await session.execute(
                update(PriceAlertMessage)
                .where(PriceAlertMessage.user_id == manager)
                .values(status="sent", telegram_message_id=message_id)
            )
            await session.commit()
        return events

    async def status(self, event_id: uuid.UUID) -> str | None:
        async with self.scene.sf() as session:
            event = await session.get(PriceAlertEvent, event_id)
            assert event is not None
            return event.review_status


@pytest.fixture
async def setup(scene: Scene) -> AsyncIterator[Setup]:  # noqa: F811
    outbox = Outbox()
    client, http = make_client(outbox)
    runner = TelegramUpdateRunner(
        session_factory=scene.sf,
        client=client,
        rate_limiter=TelegramUserRateLimiter(limit=1000),
        callback_rate_limiter=TelegramUserRateLimiter(limit=1000),
    )
    yield Setup(scene, runner, outbox)
    await http.aclose()


def methods(outbox: Outbox) -> list[str]:
    return [request.url.path.rsplit("/", 1)[-1] for request in outbox.requests]


async def test_a_manager_pressing_price_ok_confirms_the_card_answers_first_and_edits_the_message(
    setup: Setup,
) -> None:
    manager = await setup.scene.person("it-manager")
    (event,) = await setup.card(manager)

    await setup.press(manager, f"pa:ok:{event}")

    assert await setup.status(event) == "accepted"
    assert methods(setup.outbox) == ["answerCallbackQuery", "editMessageText"]
    (answer,) = setup.outbox.callback_answers()
    assert answer["text"] == "Đã xác nhận giá đúng."
    (edit,) = setup.outbox.edits()
    assert edit["message_id"] == 555 and "Đã xác nhận giá đúng bởi" in edit["text"]
    assert "reply_markup" not in edit  # bàn phím bị bỏ


async def test_marking_the_price_wrong_is_recorded_and_the_card_is_closed(setup: Setup) -> None:
    manager = await setup.scene.person("it-manager")
    (event,) = await setup.card(manager)

    await setup.press(manager, f"pa:no:{event}")

    assert await setup.status(event) == "rejected"
    assert "Đã đánh dấu nhập sai bởi" in setup.outbox.edits()[0]["text"]


async def test_someone_without_permission_is_refused_and_nothing_changes(setup: Setup) -> None:
    manager = await setup.scene.person("it-manager")
    staff = await setup.scene.person()
    (event,) = await setup.card(manager)

    await setup.press(staff, f"pa:ok:{event}")

    assert await setup.status(event) == "pending"
    (answer,) = setup.outbox.callback_answers()
    assert answer["show_alert"] is True and "không có quyền" in answer["text"]
    assert setup.outbox.edits() == []


async def test_a_second_press_is_told_who_handled_it_and_the_message_is_not_broken(
    setup: Setup,
) -> None:
    first = await setup.scene.person("it-manager")
    second = await setup.scene.person("it-manager")
    (event,) = await setup.card(first)

    await setup.press(first, f"pa:ok:{event}")
    await setup.press(second, f"pa:no:{event}", message_id=555)

    assert await setup.status(event) == "accepted"
    answers = setup.outbox.callback_answers()
    assert answers[1]["text"].startswith("Đã được xử lý bởi")


async def test_bad_or_unknown_callback_data_is_still_answered(setup: Setup) -> None:
    manager = await setup.scene.person("it-manager")
    await setup.card(manager)

    for data in (
        "garbage",
        "pa:ok:not-a-uuid",
        "pa:zz:" + str(uuid.uuid4()),
        f"pa:ok:{uuid.uuid4()}",
    ):
        await setup.press(manager, data)

    answers = setup.outbox.callback_answers()
    assert len(answers) == 4 and all("không còn hợp lệ" in a["text"] for a in answers)
    assert setup.outbox.edits() == []


async def test_a_card_with_two_points_keeps_the_buttons_of_the_one_still_pending(
    setup: Setup,
) -> None:
    manager = await setup.scene.person("it-manager")
    first, second = await setup.card(manager, months=2)

    await setup.press(manager, f"pa:ok:{first}")

    assert await setup.status(second) == "pending"
    (edit,) = setup.outbox.edits()
    rows = edit["reply_markup"]["inline_keyboard"]
    assert [b["callback_data"] for b in rows[0]] == [f"pa:ok:{second}", f"pa:no:{second}"]
    assert "Đã xác nhận giá đúng bởi" in edit["text"]


async def test_pressing_too_fast_is_still_answered(setup: Setup) -> None:
    manager = await setup.scene.person("it-manager")
    (event,) = await setup.card(manager)
    setup.runner._callback_rate_limiter = TelegramUserRateLimiter(limit=0)

    await setup.press(manager, f"pa:ok:{event}")

    assert await setup.status(event) == "pending"
    assert "quá nhanh" in setup.outbox.callback_answers()[0]["text"]


async def test_a_failing_review_still_answers_the_callback(
    setup: Setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = await setup.scene.person("it-manager")
    (event,) = await setup.card(manager)

    async def boom(self: object, *args: object, **kwargs: object) -> None:
        raise RuntimeError("lỗi bất ngờ")

    monkeypatch.setattr(PriceAlertReviewService, "review", boom)

    await setup.press(manager, f"pa:ok:{event}")

    assert await setup.status(event) == "pending"
    assert len(setup.outbox.callback_answers()) == 1


async def test_a_slow_review_is_cut_off_so_the_callback_is_answered_in_time(
    setup: Setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = await setup.scene.person("it-manager")
    (event,) = await setup.card(manager)
    original = PriceAlertReviewService.review

    async def slow(self: PriceAlertReviewService, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        await asyncio.sleep(5)
        return await original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(PriceAlertReviewService, "review", slow)
    setup.runner._callback_deadline = 0.2

    await asyncio.wait_for(setup.press(manager, f"pa:ok:{event}"), timeout=3)

    assert await setup.status(event) == "pending"
    assert "bận" in setup.outbox.callback_answers()[0]["text"]
    assert runner_module.CALLBACK_DEADLINE_SECONDS < 5


async def test_a_manager_whose_telegram_link_was_revoked_cannot_press_old_buttons(
    setup: Setup,
) -> None:
    manager = await setup.scene.person("it-manager")
    (event,) = await setup.card(manager)
    async with setup.scene.sf() as session:
        await session.execute(
            update(TelegramAccount)
            .where(TelegramAccount.user_id == manager)
            .values(status="revoked")
        )
        await session.commit()

    await setup.press(manager, f"pa:ok:{event}")

    assert await setup.status(event) == "pending"
    assert "không có quyền" in setup.outbox.callback_answers()[0]["text"]


async def test_a_redelivered_update_is_still_answered_so_the_button_stops_spinning(
    setup: Setup,
) -> None:
    manager = await setup.scene.person("it-manager")
    (event,) = await setup.card(manager)
    telegram_id, chat_id = await setup.person_ids(manager)
    payload = {
        "update_id": next(_ids),
        "callback_query": {
            "id": "dup",
            "from": {"id": telegram_id},
            "message": {"message_id": 555, "chat": {"id": chat_id, "type": "private"}},
            "data": f"pa:ok:{event}",
        },
    }

    await setup.runner.process(payload)
    await setup.runner.process(payload)

    assert len(setup.outbox.callback_answers()) == 2
