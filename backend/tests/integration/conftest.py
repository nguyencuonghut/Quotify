"""Hạ tầng test tích hợp trên PostgreSQL thật.

Mỗi phiên test tạo MỘT database tạm (`it_<ngẫu nhiên>`) trên cùng máy chủ với URL được cấu hình,
chạy `alembic upgrade head` rồi xóa khi xong. Không bao giờ chạm vào database gốc.

Cách chạy trên máy dev (Postgres dev publish cổng 55432):
    INTEGRATION_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:55432/app \\
        uv run pytest -m integration

Trong compose test (`backend-test`), `DATABASE_URL` đã trỏ tới `postgres-test` nên tự chạy.
Không có URL hoặc không kết nối được thì bỏ qua (skip), không làm hỏng bộ test.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

BACKEND_DIR = Path(__file__).resolve().parents[2]

if TYPE_CHECKING:
    from bot_harness import Bot


def _configured_url() -> str | None:
    return os.environ.get("INTEGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")


@pytest.fixture(scope="session")
def integration_database_url() -> Iterator[str]:
    base_url = _configured_url()
    if not base_url:
        pytest.skip("Không có INTEGRATION_DATABASE_URL hoặc DATABASE_URL: bỏ qua test tích hợp.")

    import asyncio

    parsed = make_url(base_url)
    database_name = f"it_{uuid.uuid4().hex[:12]}"
    admin_url = parsed.set(database="postgres")
    temp_url = parsed.set(database=database_name)

    async def run_admin(statement: str) -> None:
        engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as connection:
                await connection.execute(text(statement))
        finally:
            await engine.dispose()

    try:
        asyncio.run(run_admin(f'CREATE DATABASE "{database_name}"'))
    except Exception as exc:  # không kết nối được máy chủ: không phải lỗi của test
        pytest.skip(f"Không kết nối được PostgreSQL để chạy test tích hợp: {type(exc).__name__}")

    rendered_url = temp_url.render_as_string(hide_password=False)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": rendered_url},
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        asyncio.run(run_admin(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))
        pytest.fail(f"alembic upgrade head thất bại:\n{result.stdout}\n{result.stderr}")

    try:
        yield rendered_url
    finally:
        asyncio.run(run_admin(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))


@pytest.fixture
def empty_database_url() -> Iterator[str]:
    """Database tạm TRỐNG (chưa chạy migration) cho test upgrade/downgrade từng bước."""
    import asyncio

    base_url = _configured_url()
    if not base_url:
        pytest.skip("Không có INTEGRATION_DATABASE_URL hoặc DATABASE_URL: bỏ qua test tích hợp.")

    parsed = make_url(base_url)
    database_name = f"mig_{uuid.uuid4().hex[:12]}"
    admin_url = parsed.set(database="postgres")

    async def run_admin(statement: str) -> None:
        engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as connection:
                await connection.execute(text(statement))
        finally:
            await engine.dispose()

    try:
        asyncio.run(run_admin(f'CREATE DATABASE "{database_name}"'))
    except Exception as exc:  # không kết nối được máy chủ: không phải lỗi của test
        pytest.skip(f"Không kết nối được PostgreSQL để chạy test tích hợp: {type(exc).__name__}")

    try:
        yield parsed.set(database=database_name).render_as_string(hide_password=False)
    finally:
        asyncio.run(run_admin(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))


@pytest.fixture
async def db_engine(integration_database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(integration_database_url)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=db_engine, expire_on_commit=False)


@pytest.fixture
async def bot(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[Bot]:
    from bot_harness import Bot
    from telegram_fakes import Outbox, make_client

    from app.services.telegram_update_runner import TelegramUpdateRunner

    outbox = Outbox()
    client, http_client = make_client(outbox)
    runner = TelegramUpdateRunner(session_factory=session_factory, client=client)
    yield Bot(session_factory, runner, outbox)
    await http_client.aclose()
