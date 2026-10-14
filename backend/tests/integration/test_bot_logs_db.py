"""Log có cấu trúc và chuỗi mồi của chatbot (kế hoạch 5.1, mục 4.9, S7).

Mọi dòng log `bot.*` chỉ được chứa các trường đã liệt kê, với giá trị thuộc một tập cố định
(định danh, đếm, tên lớp ngoại lệ, danh mục cố định): không bao giờ nội dung tin, câu trả lời hay
thông điệp ngoại lệ nguyên văn. Mỗi nhánh lỗi chạy với một chuỗi mồi 10 chữ số (tiền lệ ở
`bugPatterns.md`) nhét vào tin hỏi, câu trả lời và thông điệp của ngoại lệ; chuỗi đó không được xuất
hiện trong log, audit, chuỗi ngoại lệ nào, và nội dung không được nằm lại ở dòng đã kết thúc.
"""

from __future__ import annotations

import asyncio
import logging
import re
import traceback
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import pytest
from bot_fakes import GateEngine, RecordingClient, ScriptedEngine
from bot_harness import Bot, linked_user
from db_helpers import next_update_id
from sqlalchemy import text

from app import bot_worker
from app.bot_worker import BotWorkerConfig
from app.core.bot_metrics import BotMetrics
from app.core.config import Settings
from app.integrations.telegram import (
    TelegramApiError,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRateLimitError,
)
from app.services.bot_dispatcher import ArqBotDispatcher, build_chatbot_runtime
from app.services.bot_inbox import BotInbox
from app.services.chat_engine import ChatEngineError, ChatEngineTemporaryError, ChatReply, ChatTurn
from app.services.telegram_link_service import TelegramLinkService

DECOY = "7400100555"

CATEGORIES = (
    "engine_error|engine_timeout|send_failed|send_rejected|send_timeout|lease_exhausted|"
    "expired|forbidden|unlinked|user_inactive"
)
# Các trường được phép trong log `bot.*` và dạng giá trị của từng trường.
FIELD_VALUES = {
    "update_id": r"\d+",
    "attempts": r"\d+",
    "duration_ms": r"\d+",
    "rang": r"\d+",
    "deleted": r"\d+",
    "status": r"replied|lost",
    "category": CATEGORIES,
    "error": r"[A-Za-z_][A-Za-z0-9_]*",  # chỉ tên lớp ngoại lệ
    "kind": r"apology|expired",
    "reason": r"unlinked|forbidden|user_inactive",
    "target": r"readonly_session_factory|db_engine|dispatcher|telegram_client",
    "enabled": r"True|False",
    "pilot": r"all|\d+",  # `bot.policy`: số người trong danh sách thử, không bao giờ là email
}
_EVENT = re.compile(r"^bot\.([a-z_]+)((?: [a-z_]+=\S+)*)$")


def contract_violations(messages: list[str]) -> list[str]:
    """Các dòng log `bot.*` vi phạm hợp đồng (trường lạ hay giá trị ngoài tập cho phép)."""
    problems: list[str] = []
    for message in messages:
        match = _EVENT.match(message)
        if match is None:
            problems.append(f"không đúng dạng sự kiện: {message!r}")
            continue
        for pair in match.group(2).split():
            name, _, value = pair.partition("=")
            allowed = FIELD_VALUES.get(name)
            if allowed is None:
                problems.append(f"trường lạ {name!r}: {message!r}")
            elif re.fullmatch(allowed, value) is None:
                problems.append(f"giá trị lạ cho {name!r}: {message!r}")
    return problems


def test_the_contract_rejects_free_text_and_unknown_fields() -> None:
    assert contract_violations(["bot.row_done update_id=5 status=replied duration_ms=12"]) == []
    assert contract_violations(["bot.engine_failed update_id=5 error=RuntimeError"]) == []
    assert contract_violations(["bot.sweep rang=3"]) == []
    assert contract_violations(["bot.row_done update_id=5 text=xin"])  # trường lạ
    assert contract_violations(
        ["bot.engine_failed update_id=5 error=Boom: bí mật"]
    )  # văn bản tự do
    assert contract_violations(
        ["bot.engine_failed update_id=5 error=Bad Name"]
    )  # giá trị có khoảng trắng
    assert contract_violations(["bot.row_dropped update_id=5 category=câu_hỏi"])  # danh mục lạ
    assert contract_violations(
        ["bot.row_done update_id=abc status=replied"]
    )  # định danh không phải số
    assert contract_violations(["bot.free text here"])


async def _drain_raising(bot: Bot, tg: int, **kwargs: object) -> BaseException | None:
    try:
        await bot.drain(tg, **kwargs)  # type: ignore[arg-type]
    except Exception as exc:
        return exc
    return None


class _SlowEngine:
    async def reply(self, turn: ChatTurn) -> ChatReply:
        await asyncio.sleep(5)
        return ChatReply(f"muộn {DECOY}")


class _Scene:
    """Một người dùng đã liên kết có một tin hỏi chứa chuỗi mồi đang chờ."""

    def __init__(self, bot: Bot, user_id: object, tg: int, monkeypatch: pytest.MonkeyPatch) -> None:
        self.bot = bot
        self.user_id = user_id
        self.tg = tg
        self.monkeypatch = monkeypatch
        self.escaped: list[BaseException] = []

    async def ask(self) -> int:
        return await self.bot.send(f"câu hỏi {DECOY}", tg=self.tg)

    async def drain(self, **kwargs: object) -> None:
        error = await _drain_raising(self.bot, self.tg, **kwargs)
        if error is not None:
            self.escaped.append(error)


Scenario = Callable[[_Scene], Awaitable[None]]


async def _success(scene: _Scene) -> None:
    await scene.ask()
    await scene.drain(engine=ScriptedEngine(f"đáp {DECOY}"))


async def _engine_final_error(scene: _Scene) -> None:
    await scene.ask()
    await scene.drain(engine=ScriptedEngine(ChatEngineError(f"cấu hình sai {DECOY}")))


async def _engine_temporary_error(scene: _Scene) -> None:
    await scene.ask()
    await scene.drain(engine=ScriptedEngine(ChatEngineTemporaryError(f"503 {DECOY}")))


async def _engine_unexpected_error_until_failed(scene: _Scene) -> None:
    await scene.ask()
    await scene.drain(
        engine=ScriptedEngine(RuntimeError(f"lỗi lạ {DECOY}")),
        config=BotWorkerConfig(max_attempts=1),
    )


async def _engine_timeout(scene: _Scene) -> None:
    await scene.ask()
    await scene.drain(
        engine=_SlowEngine(), config=BotWorkerConfig(row_timeout_seconds=0.05, max_attempts=1)
    )


async def _engine_empty_reply(scene: _Scene) -> None:
    await scene.ask()
    await scene.drain(engine=ScriptedEngine("   "))


async def _send_network_error(scene: _Scene) -> None:
    await scene.ask()
    await scene.drain(
        engine=ScriptedEngine(f"đáp {DECOY}"),
        client=RecordingClient(TelegramNetworkError(f"mạng {DECOY}")),
    )


async def _send_forbidden(scene: _Scene) -> None:
    await scene.ask()
    await scene.drain(
        engine=ScriptedEngine(f"đáp {DECOY}"),
        client=RecordingClient(TelegramForbiddenError(f"Forbidden {DECOY}", error_code=403)),
    )


async def _send_rejected(scene: _Scene) -> None:
    await scene.ask()
    await scene.drain(
        engine=ScriptedEngine(f"đáp {DECOY}"),
        client=RecordingClient(TelegramApiError(f"Bad Request {DECOY}", error_code=400), None),
    )


async def _send_unexpected_error_and_apology_error(scene: _Scene) -> None:
    await scene.ask()
    boom = RuntimeError(f"lỗi gửi {DECOY}")
    await scene.drain(
        engine=ScriptedEngine(f"đáp {DECOY}"),
        client=RecordingClient(boom, boom),
        config=BotWorkerConfig(max_attempts=1),
    )


async def _send_rate_limited_beyond_the_budget(scene: _Scene) -> None:
    await scene.ask()
    limited = TelegramRateLimitError(f"Too Many Requests {DECOY}", error_code=429, retry_after=300)
    await scene.drain(
        engine=ScriptedEngine(f"đáp {DECOY}"),
        client=RecordingClient(limited),
        config=BotWorkerConfig(send_budget_seconds=1),
    )


async def _saving_the_reply_fails_in_the_database(scene: _Scene) -> None:
    await scene.ask()
    # NUL làm Postgres từ chối lệnh lưu; SQLAlchemy kèm tham số (nội dung) vào lỗi nếu không bọc.
    await scene.drain(engine=ScriptedEngine(f"đáp {DECOY}\x00"))
    # Kịch bản này chỉ có ý nghĩa nếu lỗi DB thật sự xảy ra và thoát ra ngoài.
    assert [type(error).__name__ for error in scene.escaped] == ["BotInboxError"]


async def _link_revoked_while_waiting(scene: _Scene) -> None:
    await scene.ask()
    async with scene.bot.session_factory() as session:
        await session.execute(
            text("update telegram_accounts set status = 'revoked' where telegram_user_id = :t"),
            {"t": scene.tg},
        )
        await session.commit()
    await scene.drain(engine=ScriptedEngine(f"đáp {DECOY}"))


async def _user_locked_while_waiting(scene: _Scene) -> None:
    await scene.ask()
    async with scene.bot.session_factory() as session:
        await session.execute(
            text("update users set status = 'locked' where id = :u"), {"u": scene.user_id}
        )
        await session.commit()
    await scene.drain(engine=ScriptedEngine(f"đáp {DECOY}"))


async def _message_too_old(scene: _Scene) -> None:
    await scene.bot.insert_row(
        scene.tg,
        scene.user_id,  # type: ignore[arg-type]
        next_update_id(),
        text_=f"cũ {DECOY}",
        received_at=datetime.now(UTC) - timedelta(hours=2),
    )
    await scene.drain(engine=ScriptedEngine(f"đáp {DECOY}"))


async def _out_of_attempts_with_a_notice_that_fails(scene: _Scene) -> None:
    await scene.bot.insert_row(
        scene.tg,
        scene.user_id,  # type: ignore[arg-type]
        next_update_id(),
        status="processing",
        attempts=3,
        lease_until=datetime.now(UTC) - timedelta(seconds=1),
        text_=f"hết lượt {DECOY}",
    )
    await scene.drain(client=RecordingClient(RuntimeError(f"không gửi được {DECOY}")))


async def _out_of_attempts_for_a_chat_that_is_gone(scene: _Scene) -> None:
    await _link_revoked_while_waiting(scene)  # dòng bị loại, rồi chèn dòng hết lượt cho chat đã hủy
    await scene.bot.insert_row(
        scene.tg,
        scene.user_id,  # type: ignore[arg-type]
        next_update_id(),
        status="processing",
        attempts=3,
        lease_until=datetime.now(UTC) - timedelta(seconds=1),
        text_=f"hết lượt {DECOY}",
    )
    await scene.drain(client=RecordingClient())


async def _a_stale_worker_loses_its_row(scene: _Scene) -> None:
    update_id = await scene.ask()
    gate = GateEngine(f"của worker cũ {DECOY}")
    old = asyncio.create_task(scene.bot.drain(scene.tg, engine=gate))
    await asyncio.wait_for(gate.started.wait(), timeout=5)
    await scene.bot.set_lease(update_id, datetime.now(UTC) - timedelta(seconds=1))
    await scene.bot.drain(scene.tg, engine=ScriptedEngine(f"của worker mới {DECOY}"))
    gate.release.set()
    await asyncio.wait_for(old, timeout=5)


async def _sweep_and_cleanup(scene: _Scene) -> None:
    await scene.ask()  # một dòng `queued` để cron quét có việc
    await scene.bot.sweep(config=BotWorkerConfig(sweep_stale_seconds=0))
    await scene.bot.insert_row(
        scene.tg,
        scene.user_id,  # type: ignore[arg-type]
        next_update_id(),
        status="replied",
        finished_at=datetime.now(UTC) - timedelta(days=90),
        text_=f"cũ {DECOY}",
    )
    await scene.bot.cleanup()


async def _shutdown_with_a_failing_close(scene: _Scene) -> None:
    class _Closer:
        async def aclose(self) -> None:
            raise RuntimeError(f"không đóng được {DECOY}")

    await bot_worker.shutdown({"readonly_session_factory": _Closer(), "dispatcher": _Closer()})


async def _metrics_cannot_reach_the_database(scene: _Scene) -> None:
    def broken() -> object:
        raise ConnectionError(f"mất kết nối {DECOY}")

    await BotMetrics(broken, ttl_seconds=0, chatbot_enabled=lambda: True).refresh()  # type: ignore[arg-type]


async def _marking_the_link_blocked_fails(scene: _Scene) -> None:
    async def broken(self: TelegramLinkService, telegram_user_id: int) -> bool:
        raise RuntimeError(f"không đánh dấu được {DECOY}")

    scene.monkeypatch.setattr(TelegramLinkService, "mark_blocked", broken)
    await scene.ask()
    await scene.drain(
        engine=ScriptedEngine(f"đáp {DECOY}"),
        client=RecordingClient(TelegramForbiddenError(f"Forbidden {DECOY}", error_code=403)),
    )


async def _releasing_the_lease_fails_on_cancel(scene: _Scene) -> None:
    async def broken(self: BotInbox, *args: object, **kwargs: object) -> bool:
        raise RuntimeError(f"không nhả được lease {DECOY}")

    scene.monkeypatch.setattr(BotInbox, "release_lease", broken)
    await scene.ask()
    gate = GateEngine(f"đáp {DECOY}")
    worker = asyncio.create_task(scene.bot.drain(scene.tg, engine=gate))
    await asyncio.wait_for(gate.started.wait(), timeout=5)
    worker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await worker


class _ClientWithBrokenTyping(RecordingClient):
    async def send_chat_action(self, chat_id: int, action: str = "typing") -> bool:
        raise RuntimeError(f"không báo gõ được {DECOY}")


class _PausingEngine:
    async def reply(self, turn: ChatTurn) -> ChatReply:
        await asyncio.sleep(0.15)  # đủ lâu để tác vụ "đang gõ" chạy ít nhất một lần
        return ChatReply(f"đáp {DECOY}")


async def _typing_indicator_fails(scene: _Scene) -> None:
    await scene.ask()
    await scene.drain(
        engine=_PausingEngine(),
        client=_ClientWithBrokenTyping(),
        config=BotWorkerConfig(typing_interval_seconds=0.02),
    )


async def _out_of_attempts_and_the_chat_blocked_the_bot(scene: _Scene) -> None:
    await scene.bot.insert_row(
        scene.tg,
        scene.user_id,  # type: ignore[arg-type]
        next_update_id(),
        status="processing",
        attempts=3,
        lease_until=datetime.now(UTC) - timedelta(seconds=1),
        text_=f"hết lượt {DECOY}",
    )
    await scene.drain(
        client=RecordingClient(TelegramForbiddenError(f"Forbidden {DECOY}", error_code=403))
    )


class _PoolThatFailsToClose:
    async def enqueue_job(self, *args: object, **kwargs: object) -> None:
        return None

    async def aclose(self) -> None:
        raise RuntimeError(f"không đóng được pool {DECOY}")


async def _awaitable(value: object) -> object:
    return value


async def _the_bell_cannot_be_rung_and_the_pool_cannot_be_closed(scene: _Scene) -> None:
    async def no_redis() -> object:
        raise ConnectionError(f"mất Redis {DECOY}")

    await ArqBotDispatcher(host="x", port=1, queue_name="q", pool_factory=no_redis).notify(
        scene.tg, next_update_id()
    )
    ringing = ArqBotDispatcher(
        host="x",
        port=1,
        queue_name="q",
        pool_factory=lambda: _awaitable(_PoolThatFailsToClose()),
    )
    await ringing.notify(scene.tg, next_update_id())
    await ringing.aclose()


async def _the_policy_is_logged_without_any_email(scene: _Scene) -> None:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        CHATBOT_ENABLED=True,
        TELEGRAM_ENABLED=True,
        CHATBOT_PILOT_USER_EMAILS=f"thu{DECOY}@honghafeed.vn,khac@honghafeed.vn",
    )
    build_chatbot_runtime(settings)


class _ClientTakenOverAfterTheFirstPart(RecordingClient):
    """Gửi xong phần đầu thì một worker khác tiếp quản (attempts tăng) ngay trong DB."""

    def __init__(self, bot: Bot, update_id: int) -> None:
        super().__init__()
        self._bot = bot
        self._update_id = update_id

    async def send_message(self, chat_id: int, text_: str, **kwargs: object) -> int:
        result = await super().send_message(chat_id, text_, **kwargs)
        if len(self.sent) == 1:
            async with self._bot.session_factory() as session:
                await session.execute(
                    text("update bot_updates set attempts = attempts + 1 where update_id = :i"),
                    {"i": self._update_id},
                )
                await session.commit()
        return result


async def _taken_over_between_the_parts_of_a_reply(scene: _Scene) -> None:
    update_id = await scene.ask()
    two_parts = "\n\n".join([f"đoạn một {DECOY} " + "x" * 3000, f"đoạn hai {DECOY} " + "y" * 3000])
    await scene.drain(
        engine=ScriptedEngine(two_parts),
        client=_ClientTakenOverAfterTheFirstPart(scene.bot, update_id),
    )


async def _ownership_is_lost_right_before_sending(scene: _Scene) -> None:
    async def lost(self: BotInbox, update_id: int, attempts: int) -> bool:
        return False

    scene.monkeypatch.setattr(BotInbox, "owns", lost)
    await scene.ask()
    await scene.drain(engine=ScriptedEngine(f"đáp {DECOY}"))


SCENARIOS: dict[str, Scenario] = {
    "success": _success,
    "engine-final-error": _engine_final_error,
    "engine-temporary-error": _engine_temporary_error,
    "engine-unexpected-error-until-failed": _engine_unexpected_error_until_failed,
    "engine-timeout": _engine_timeout,
    "engine-empty-reply": _engine_empty_reply,
    "send-network-error": _send_network_error,
    "send-forbidden": _send_forbidden,
    "send-rejected": _send_rejected,
    "send-unexpected-error-and-apology-error": _send_unexpected_error_and_apology_error,
    "send-rate-limited-beyond-the-budget": _send_rate_limited_beyond_the_budget,
    "saving-the-reply-fails": _saving_the_reply_fails_in_the_database,
    "link-revoked": _link_revoked_while_waiting,
    "user-locked": _user_locked_while_waiting,
    "message-too-old": _message_too_old,
    "out-of-attempts-notice-fails": _out_of_attempts_with_a_notice_that_fails,
    "out-of-attempts-chat-gone": _out_of_attempts_for_a_chat_that_is_gone,
    "stale-worker": _a_stale_worker_loses_its_row,
    "sweep-and-cleanup": _sweep_and_cleanup,
    "shutdown-failure": _shutdown_with_a_failing_close,
    "metrics-failure": _metrics_cannot_reach_the_database,
    "marking-blocked-fails": _marking_the_link_blocked_fails,
    "release-lease-fails": _releasing_the_lease_fails_on_cancel,
    "typing-fails": _typing_indicator_fails,
    "notice-forbidden": _out_of_attempts_and_the_chat_blocked_the_bot,
    "dispatcher-failures": _the_bell_cannot_be_rung_and_the_pool_cannot_be_closed,
    "policy-log": _the_policy_is_logged_without_any_email,
    "taken-over-between-parts": _taken_over_between_the_parts_of_a_reply,
    "ownership-lost-before-sending": _ownership_is_lost_right_before_sending,
}

# Các sự kiện log mà bộ kịch bản trên phải kích hoạt hết, để hợp đồng không xanh vì "không có gì".
EXPECTED_EVENTS = {
    "engine_failed",
    "engine_timeout",
    "engine_empty_reply",
    "row_requeued",
    "row_failed",
    "row_dropped",
    "row_lost",
    "row_done",
    "send_failed",
    "notice_skipped",
    "notice_failed",
    "sweep",
    "cleanup",
    "shutdown_failed",
    "metrics_failed",
    "mark_blocked_failed",
    "release_failed",
    "typing_failed",
    "notify_failed",
    "dispatcher_close_failed",
    "policy",
}


async def test_no_branch_logs_free_text_and_no_decoy_ever_leaves_the_database(
    chatbot_bot: Bot,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caplog.set_level(logging.DEBUG)
    bot = chatbot_bot
    events: set[str] = set()
    for name, scenario in SCENARIOS.items():
        caplog.clear()
        user_id, tg = await linked_user(bot)
        scene = _Scene(bot, user_id, tg, monkeypatch)

        await scenario(scene)

        messages = [record.getMessage() for record in caplog.records]
        bot_messages = [message for message in messages if message.startswith("bot.")]
        assert contract_violations(bot_messages) == [], name
        events |= {match.group(1) for m in bot_messages if (match := _EVENT.match(m))}
        assert DECOY not in caplog.text, f"{name}: chuỗi mồi lọt vào log"
        for escaped in scene.escaped:  # lỗi thoát khỏi worker cũng không được mang nội dung
            assert DECOY not in "".join(traceback.format_exception(escaped)), f"{name}: ngoại lệ"
        async with bot.session_factory() as session:
            # Quét MỌI cột (không chỉ nội dung): chuỗi mồi ở `error_category` hay metadata là rò.
            leaked_audit = (
                await session.execute(
                    text(
                        "select count(*) from audit_logs a "
                        "where cast(row_to_json(a) as text) like :p"
                    ),
                    {"p": f"%{DECOY}%"},
                )
            ).scalar_one()
            leaked_row = (
                await session.execute(
                    text(
                        "select count(*) from bot_updates b where b.chat_id = :c "
                        "and b.status in ('replied','failed','dropped') "
                        "and cast(row_to_json(b) as text) like :p"
                    ),
                    {"c": tg, "p": f"%{DECOY}%"},
                )
            ).scalar_one()
            lingering = (
                await session.execute(
                    text(
                        "select count(*) from bot_updates where chat_id = :c "
                        "and status in ('replied','failed','dropped') "
                        "and (payload_text is not null or reply_text is not null)"
                    ),
                    {"c": tg},
                )
            ).scalar_one()
        assert leaked_audit == 0, f"{name}: chuỗi mồi lọt vào audit"
        assert leaked_row == 0, f"{name}: chuỗi mồi nằm lại ở một cột của dòng đã kết thúc"
        assert lingering == 0, f"{name}: dòng đã kết thúc còn nội dung"

    assert EXPECTED_EVENTS <= events, f"kịch bản chưa kích hoạt: {EXPECTED_EVENTS - events}"
