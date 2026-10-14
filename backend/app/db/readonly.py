"""Engine DB chỉ đọc riêng cho công cụ của chatbot (kế hoạch 5.1, mục 4.6, KT10 và RC-27).

Dùng `server_settings` (chế độ chỉ đọc, `statement_timeout`, `idle_in_transaction_session_timeout`)
vì chúng có hiệu lực suốt phiên, kể cả sau commit, rollback và khi kết nối được lấy lại từ pool;
pool nhỏ riêng để một đợt hỏi đáp không làm cạn pool của API.

Đây là **rào chắn, không phải ranh giới bảo mật**: một phiên cố tình vẫn có thể tắt chế độ chỉ đọc.
An toàn thật dựa vào việc không công cụ nào nhận SQL từ model, và role chỉ-`SELECT` ở 2D.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from app.core.config import Settings


# Mọi trạng thái phiên mà một phiên cố tình có thể để lại (kiểm bằng thực nghiệm ở S6): cài đặt
# (`RESET ALL` trả `server_settings` về giá trị lúc khởi tạo kết nối), vai trò, kênh LISTEN, cursor
# WITH HOLD, khóa advisory mức phiên, bảng tạm. KHÔNG dùng `DISCARD ALL` hay `DEALLOCATE ALL`: chúng
# xóa cả prepared statement mà asyncpg đang cache và làm lần truy vấn kế tiếp hỏng. `PREPARE` do
# người dùng tạo chỉ gọi được khi biết tên nên chấp nhận để sót (rào chắn, không phải ranh giới).
APPLICATION_NAME = "quotify-bot-readonly"
_RESTORE_STATEMENTS = (
    "RESET SESSION AUTHORIZATION",  # cũng đưa vai trò (SET ROLE) về mặc định
    "RESET ALL",
    "UNLISTEN *",
    "CLOSE ALL",
    "SELECT pg_advisory_unlock_all()",
    "DISCARD TEMP",
)


def _restore_session_defaults(
    dbapi_connection: Any, connection_record: Any, reset_state: Any
) -> None:
    """Khi trả kết nối về pool: đưa trạng thái phiên về như lúc khởi tạo kết nối.

    Đo ở S0(a): một phiên chạy `SET default_transaction_read_only=off` (hay `SET
    statement_timeout=0`) rồi commit thì cài đặt rò sang kết nối được lấy lại từ pool; S6 đo thêm
    vai trò, LISTEN và cursor. Chạy SAU rollback của phiên nên không commit hộ việc dở của ai.
    Lỗi ở đây làm SQLAlchemy hủy kết nối thay vì đưa lại một kết nối chưa sạch vào pool.
    """
    if reset_state.terminate_only or not reset_state.asyncio_safe:
        return  # kết nối bị thu gom rác hay đang bị hủy: không được chạy I/O
    cursor = dbapi_connection.cursor()
    try:
        for statement in _RESTORE_STATEMENTS:
            cursor.execute(statement)
        dbapi_connection.commit()
    finally:
        cursor.close()


class ReadonlySessionFactory:
    """Gọi như `async_sessionmaker`: mở một `AsyncSession` chỉ đọc. Engine tạo lười ở lần gọi đầu.

    Chưa ai gọi thì không có engine, không có kết nối nào: chatbot tắt không tốn gì.
    """

    def __init__(
        self,
        database_url: str,
        *,
        statement_timeout_ms: int = 5000,
        idle_in_transaction_timeout_ms: int = 10000,
        pool_size: int = 2,
        max_overflow: int = 1,
        pool_timeout_seconds: float = 3.0,
    ) -> None:
        self._database_url = database_url
        self._statement_timeout_ms = statement_timeout_ms
        self._idle_in_transaction_timeout_ms = idle_in_transaction_timeout_ms
        self._pool_size = pool_size
        self._max_overflow = max_overflow
        self._pool_timeout_seconds = pool_timeout_seconds
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker[AsyncSession] | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> ReadonlySessionFactory:
        return cls(
            settings.database_url,
            statement_timeout_ms=settings.bot_readonly_statement_timeout_ms,
            idle_in_transaction_timeout_ms=settings.bot_readonly_idle_in_transaction_timeout_ms,
            pool_size=settings.bot_readonly_pool_size,
            max_overflow=settings.bot_readonly_max_overflow,
            pool_timeout_seconds=settings.bot_readonly_pool_timeout_seconds,
        )

    @property
    def engine_created(self) -> bool:
        return self._engine is not None

    def __call__(self) -> AsyncSession:
        if self._sessionmaker is None:
            self._engine = create_async_engine(
                self._database_url,
                pool_size=self._pool_size,
                max_overflow=self._max_overflow,
                pool_timeout=self._pool_timeout_seconds,
                pool_pre_ping=True,
                connect_args={
                    "server_settings": {
                        # Nhãn để nhận diện kết nối chỉ đọc trong `pg_stat_activity`.
                        "application_name": APPLICATION_NAME,
                        "default_transaction_read_only": "on",
                        "statement_timeout": str(self._statement_timeout_ms),
                        "idle_in_transaction_session_timeout": str(
                            self._idle_in_transaction_timeout_ms
                        ),
                    }
                },
            )
            event.listen(self._engine.sync_engine, "reset", _restore_session_defaults)
            self._sessionmaker = async_sessionmaker(bind=self._engine, expire_on_commit=False)
        return self._sessionmaker()

    async def aclose(self) -> None:
        """Đóng mọi kết nối (nếu engine đã được tạo)."""
        # Quên engine NGAY, trước khi đóng: một lần gọi chen vào giữa sẽ tạo engine mới thay vì dùng
        # engine sắp đóng rồi để nó mồ côi.
        engine, self._engine = self._engine, None
        self._sessionmaker = None
        if engine is not None:
            await engine.dispose()
