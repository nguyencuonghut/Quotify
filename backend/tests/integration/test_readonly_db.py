"""Engine DB chỉ đọc của công cụ chatbot (kế hoạch 5.1, S6).

Postgres thật. Đây là **rào chắn**, không phải ranh giới bảo mật (RC-27): một phiên cố tình vẫn có
thể tắt chế độ chỉ đọc, nên mỗi lần trả kết nối về pool phải khôi phục cài đặt, và ranh giới cứng
là role chỉ-`SELECT` ở 2D.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator

import pytest
from bot_harness import Bot, linked_user
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.bot_worker import BotWorkerConfig
from app.core.config import Settings
from app.db.readonly import ReadonlySessionFactory
from app.services.chat_engine import ChatReply, ChatTurn


@pytest.fixture
async def readonly_factory(integration_database_url: str) -> AsyncIterator[ReadonlySessionFactory]:
    factory = ReadonlySessionFactory(integration_database_url)
    try:
        yield factory
    finally:
        await factory.aclose()


def _sqlstate(error: DBAPIError) -> str | None:
    # asyncpg đặt mã SQLSTATE ở lỗi gốc; SQLAlchemy bọc nó vài lớp tùy phiên bản.
    cause: BaseException | None = error.orig
    while cause is not None:
        code = getattr(cause, "sqlstate", None)
        if code:
            return str(code)
        cause = cause.__cause__
    return None


async def test_the_readonly_factory_reads_but_rejects_a_write(
    readonly_factory: ReadonlySessionFactory,
) -> None:
    async with readonly_factory() as session:
        assert (await session.execute(text("select 1"))).scalar_one() == 1

        with pytest.raises(DBAPIError) as rejected:
            await session.execute(text("delete from bot_updates where false"))

    assert _sqlstate(rejected.value) == "25006"  # read_only_sql_transaction


@pytest.mark.parametrize(
    "statement",
    [
        "insert into telegram_processed_updates (update_id) values (1)",
        "update users set status = status where false",
        "delete from bot_updates where false",
        "create table s6_forbidden (a int)",
        "create temp table s6_forbidden (a int)",
        "select id from users for update",
        "select id from users for share",
    ],
)
async def test_every_kind_of_write_is_rejected_with_read_only_sql_transaction(
    readonly_factory: ReadonlySessionFactory,
    statement: str,
) -> None:
    async with readonly_factory() as session:
        with pytest.raises(DBAPIError) as rejected:
            await session.execute(text(statement))

    assert _sqlstate(rejected.value) == "25006"


async def test_a_slow_query_is_cancelled_when_the_statement_timeout_is_over(
    integration_database_url: str,
) -> None:
    factory = ReadonlySessionFactory(integration_database_url, statement_timeout_ms=300)
    try:
        started = time.monotonic()
        async with factory() as session:
            with pytest.raises(DBAPIError) as cancelled:
                await session.execute(text("select pg_sleep(5)"))
        elapsed = time.monotonic() - started

        assert _sqlstate(cancelled.value) == "57014"  # query_canceled
        assert 0.25 <= elapsed < 2.0  # bị hủy ở khoảng 0,3 giây, không phải đợi hết 5 giây
    finally:
        await factory.aclose()


async def test_exhausting_the_readonly_pool_does_not_block_the_main_engine(
    integration_database_url: str,
    db_engine: AsyncEngine,
) -> None:
    factory = ReadonlySessionFactory(
        integration_database_url, pool_size=1, max_overflow=0, pool_timeout_seconds=0.3
    )
    try:
        async with factory() as holder:
            await holder.execute(text("select 1"))  # giữ kết nối duy nhất của pool chỉ đọc

            started = time.monotonic()
            async with factory() as waiting:
                with pytest.raises(PoolTimeoutError):
                    await waiting.execute(text("select 1"))
            assert time.monotonic() - started < 2.0  # pool chỉ đọc hết kết nối thì báo lỗi nhanh

            started = time.monotonic()
            async with db_engine.connect() as connection:  # engine chính (API) vẫn phục vụ ngay
                assert (await connection.execute(text("select 1"))).scalar_one() == 1
            assert time.monotonic() - started < 1.0
    finally:
        await factory.aclose()


async def test_a_session_idle_in_a_transaction_is_cut_and_the_next_one_gets_a_fresh_connection(
    integration_database_url: str,
) -> None:
    factory = ReadonlySessionFactory(integration_database_url, idle_in_transaction_timeout_ms=300)
    try:
        async with factory() as session:
            await session.execute(text("select 1"))  # mở giao dịch rồi để rảnh
            await asyncio.sleep(0.9)
            with pytest.raises(DBAPIError):
                await session.execute(text("select 1"))

        async with factory() as fresh:
            assert (await fresh.execute(text("select 1"))).scalar_one() == 1
    finally:
        await factory.aclose()


async def test_the_engine_is_only_built_on_first_use_and_can_be_closed_and_rebuilt(
    integration_database_url: str,
) -> None:
    factory = ReadonlySessionFactory(integration_database_url)
    assert factory.engine_created is False
    await factory.aclose()  # đóng khi chưa tạo gì thì không lỗi

    async with factory() as session:
        assert (await session.execute(text("select 1"))).scalar_one() == 1
    assert factory.engine_created is True

    await factory.aclose()
    assert factory.engine_created is False
    async with factory() as session:  # dùng lại được sau khi đóng
        assert (await session.execute(text("select 1"))).scalar_one() == 1
    await factory.aclose()


async def test_the_readonly_engine_pings_connections_before_use(
    integration_database_url: str,
) -> None:
    factory = ReadonlySessionFactory(integration_database_url)
    try:
        async with factory() as session:
            await session.execute(text("select 1"))
        assert factory._engine is not None
        assert factory._engine.pool._pre_ping is True  # type: ignore[attr-defined]
    finally:
        await factory.aclose()


async def _readonly_backends(engine: AsyncEngine) -> int:
    async with engine.connect() as connection:
        return int(
            (
                await connection.execute(
                    text(
                        "select count(*) from pg_stat_activity "
                        "where application_name = 'quotify-bot-readonly' "
                        "and datname = current_database()"
                    )
                )
            ).scalar_one()
        )


async def test_the_readonly_connections_are_labelled_and_really_closed_by_aclose(
    integration_database_url: str,
    db_engine: AsyncEngine,
) -> None:
    factory = ReadonlySessionFactory(integration_database_url)
    async with factory() as session:
        await session.execute(text("select 1"))
    labelled_while_open = await _readonly_backends(db_engine)

    await factory.aclose()

    assert labelled_while_open == 1  # nhận diện được trong pg_stat_activity
    assert (
        await _readonly_backends(db_engine) == 0
    )  # aclose đóng thật kết nối, không chỉ quên con trỏ


async def test_closing_the_factory_forgets_the_engine_at_once_so_a_late_call_cannot_orphan_it(
    integration_database_url: str,
) -> None:
    factory = ReadonlySessionFactory(integration_database_url)
    async with factory() as session:
        await session.execute(text("select 1"))  # engine đã có một kết nối rảnh trong pool

    closing = asyncio.create_task(factory.aclose())
    await asyncio.sleep(0)  # `aclose` đã bắt đầu đóng kết nối nhưng chưa xong
    forgot_engine_at_once = factory.engine_created is False
    await closing

    # Nếu con trỏ chỉ bị xóa SAU khi đóng xong thì một lần gọi chen vào giữa dùng engine sắp
    # đóng rồi để nó mồ côi (một backend mở mãi trên server).
    assert forgot_engine_at_once


# --- một phiên cố tình tắt rào chắn không để lại dấu vết cho phiên kế tiếp (RC-27) ---------------


async def _tamper(factory: ReadonlySessionFactory) -> None:
    """Một phiên tắt chế độ chỉ đọc, bỏ timeout, tạo bảng tạm, khóa advisory, rồi commit.

    Làm trong MỘT giao dịch (`SET TRANSACTION READ WRITE` phải là câu đầu): commit trả kết nối về
    pool, nên đây đúng là lúc cài đặt của kẻ tấn công có thể rò sang phiên kế tiếp.
    """
    async with factory() as session:
        await session.execute(text("set transaction read write"))
        await session.execute(text("set default_transaction_read_only = off"))
        await session.execute(text("set statement_timeout = 0"))
        await session.execute(text("set idle_in_transaction_session_timeout = 0"))
        await session.execute(text("create temp table s6_tamper (a int)"))
        await session.execute(text("select pg_advisory_lock(424242)"))
        await session.commit()


async def test_a_session_that_switches_read_only_off_does_not_affect_the_next_one(
    integration_database_url: str,
) -> None:
    factory = ReadonlySessionFactory(
        integration_database_url, statement_timeout_ms=4321, pool_size=1, max_overflow=0
    )
    try:
        await _tamper(factory)

        async with factory() as next_session:  # cùng kết nối (pool chỉ có một)
            row = (
                await next_session.execute(
                    text(
                        "select current_setting('default_transaction_read_only'), "
                        "current_setting('statement_timeout'), "
                        "current_setting('idle_in_transaction_session_timeout')"
                    )
                )
            ).one()
            with pytest.raises(DBAPIError) as rejected:
                await next_session.execute(text("delete from bot_updates where false"))

        assert tuple(row) == (
            "on",
            "4321ms",
            "10s",
        )  # đúng giá trị khởi tạo, không phải của kẻ trước
        assert _sqlstate(rejected.value) == "25006"
    finally:
        await factory.aclose()


async def test_temp_tables_and_advisory_locks_of_a_session_do_not_survive_its_return_to_the_pool(
    integration_database_url: str,
) -> None:
    factory = ReadonlySessionFactory(integration_database_url, pool_size=1, max_overflow=0)
    try:
        await _tamper(factory)

        async with factory() as next_session:
            temp_table = (
                await next_session.execute(text("select to_regclass('pg_temp.s6_tamper')"))
            ).scalar_one()
            advisory_locks = (
                await next_session.execute(
                    text(
                        "select count(*) from pg_locks "
                        "where locktype = 'advisory' and pid = pg_backend_pid()"
                    )
                )
            ).scalar_one()

        assert temp_table is None
        assert advisory_locks == 0
    finally:
        await factory.aclose()


# --- nối vào đường ống: ChatTurn mang factory chỉ đọc, chatbot tắt thì không mở gì ---------------


class _ProbingEngine:
    """Engine giả thử một lệnh đọc và một lệnh ghi qua factory chỉ đọc trong `ChatTurn`."""

    def __init__(self) -> None:
        self.read: int | None = None
        self.write_sqlstate: str | None = None
        self.received_factory = False

    async def reply(self, turn: ChatTurn) -> ChatReply:
        factory = turn.readonly_session_factory
        self.received_factory = factory is not None
        assert factory is not None
        async with factory() as session:
            self.read = (await session.execute(text("select 1"))).scalar_one()
            with pytest.raises(DBAPIError) as rejected:
                await session.execute(text("delete from bot_updates where false"))
            self.write_sqlstate = _sqlstate(rejected.value)
        return ChatReply("ok")


async def test_the_engine_gets_the_readonly_factory_in_its_turn_and_can_read_but_not_write(
    chatbot_bot: Bot,
    readonly_factory: ReadonlySessionFactory,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    await bot.send("xin chào", tg=tg)
    engine = _ProbingEngine()

    await bot.drain(tg, engine=engine, readonly_session_factory=readonly_factory)

    assert engine.received_factory is True
    assert engine.read == 1
    assert engine.write_sqlstate == "25006"  # ghi bị từ chối


async def test_a_turn_without_a_readonly_factory_in_the_context_still_works(
    chatbot_bot: Bot,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    update_id = await bot.send("xin chào", tg=tg)

    await bot.drain(tg)  # ngữ cảnh không có factory chỉ đọc (vd test cũ)

    assert (await bot.row(update_id)).status == "replied"


async def test_the_readonly_engine_is_never_opened_by_a_turn_that_does_not_use_it(
    chatbot_bot: Bot,
    readonly_factory: ReadonlySessionFactory,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    await bot.send("xin chào", tg=tg)

    await bot.drain(
        tg, readonly_session_factory=readonly_factory
    )  # engine giả cố định, không đọc DB

    assert readonly_factory.engine_created is False  # chỉ khi công cụ thật sự gọi mới có engine


async def test_with_the_chatbot_off_the_worker_never_opens_the_readonly_engine(
    chatbot_bot: Bot,
    readonly_factory: ReadonlySessionFactory,
) -> None:
    bot = chatbot_bot
    _, tg = await linked_user(bot)
    await bot.send("xin chào", tg=tg)
    off = BotWorkerConfig(enabled=False, sweep_stale_seconds=0)

    await bot.drain(
        tg, engine=_ProbingEngine(), config=off, readonly_session_factory=readonly_factory
    )
    await bot.sweep(config=off)

    assert readonly_factory.engine_created is False
    assert (await bot.inbox_rows(tg))[0].status == "queued"  # tin vẫn chờ, không bị mất


async def test_the_factory_built_from_settings_uses_the_configured_limits(
    integration_database_url: str,
) -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        DATABASE_URL=integration_database_url,
        BOT_READONLY_STATEMENT_TIMEOUT_MS=300,
        BOT_READONLY_IDLE_IN_TRANSACTION_TIMEOUT_MS=7000,
        BOT_READONLY_POOL_SIZE=1,
        BOT_READONLY_MAX_OVERFLOW=0,
        BOT_READONLY_POOL_TIMEOUT_SECONDS=0.3,
    )
    factory = ReadonlySessionFactory.from_settings(settings)
    try:
        async with factory() as probe:  # ánh xạ từng tham số vào đúng cài đặt phiên
            limits = (
                await probe.execute(
                    text(
                        "select current_setting('statement_timeout'), "
                        "current_setting('idle_in_transaction_session_timeout')"
                    )
                )
            ).one()
        assert tuple(limits) == ("300ms", "7s")

        async with factory() as holder:
            with pytest.raises(DBAPIError) as cancelled:
                await holder.execute(text("select pg_sleep(5)"))  # timeout 300 ms từ cấu hình
            assert _sqlstate(cancelled.value) == "57014"

        async with factory() as busy:
            await busy.execute(text("select 1"))  # giữ kết nối duy nhất (pool 1, không tràn)
            async with factory() as waiting:
                with pytest.raises(PoolTimeoutError):  # pool 1 và hạn chờ 0,3 giây từ cấu hình
                    await waiting.execute(text("select 1"))
    finally:
        await factory.aclose()


@pytest.fixture
async def spare_role(db_engine: AsyncEngine) -> AsyncIterator[str]:
    """Một role Postgres tạm để thử `SET ROLE` (role thuộc cả cụm, nên phải xóa sau test)."""
    name = f"it_s6_{uuid.uuid4().hex[:10]}"
    admin = db_engine.execution_options(isolation_level="AUTOCOMMIT")
    async with admin.connect() as connection:
        await connection.execute(text(f"create role {name} nologin"))
    try:
        yield name
    finally:
        async with admin.connect() as connection:
            await connection.execute(text(f"drop role if exists {name}"))


@pytest.mark.parametrize("command", ["set role {role}", "set session authorization {role}"])
async def test_a_changed_role_does_not_survive_the_return_to_the_pool(
    integration_database_url: str,
    spare_role: str,
    command: str,
) -> None:
    factory = ReadonlySessionFactory(integration_database_url, pool_size=1, max_overflow=0)
    try:
        async with factory() as before:
            original = (await before.execute(text("select current_user, session_user"))).one()
        async with factory() as attacker:
            await attacker.execute(text(command.format(role=spare_role)))
            await attacker.commit()

        async with factory() as next_session:
            after = (await next_session.execute(text("select current_user, session_user"))).one()

        assert tuple(after) == tuple(original)  # không phải role của phiên trước
    finally:
        await factory.aclose()


async def test_listen_channels_and_held_cursors_do_not_survive_the_return_to_the_pool(
    integration_database_url: str,
) -> None:
    factory = ReadonlySessionFactory(integration_database_url, pool_size=1, max_overflow=0)
    try:
        async with factory() as attacker:
            await attacker.execute(text("listen s6chan"))
            await attacker.execute(text("declare s6cur cursor with hold for select 1"))
            await attacker.commit()

        async with factory() as next_session:
            channels = (
                await next_session.execute(text("select count(*) from pg_listening_channels()"))
            ).scalar_one()
            cursors = (
                await next_session.execute(
                    text("select count(*) from pg_cursors where name = 's6cur'")
                )
            ).scalar_one()

        assert (channels, cursors) == (0, 0)
    finally:
        await factory.aclose()
