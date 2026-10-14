from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings
from app.core.observability import instrument_sqlalchemy_engine

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        instrument_sqlalchemy_engine(_engine)
    return _engine


def create_bot_engine(settings: Settings) -> AsyncEngine:
    """Engine riêng của `bot-worker`: pool nhỏ đặt tường minh (RC-5), không dùng engine toàn cục."""
    engine = create_async_engine(
        settings.database_url,
        pool_size=settings.bot_db_pool_size,
        max_overflow=settings.bot_db_max_overflow,
        pool_pre_ping=True,
    )
    instrument_sqlalchemy_engine(engine)
    return engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _sessionmaker


async def get_db_session() -> AsyncIterator[AsyncSession]:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        yield session
