"""Chạy alembic bằng tiến trình con trên một database tạm và truy vấn trực tiếp bằng SQL."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

BACKEND_DIR = Path(__file__).resolve().parents[2]


def run_alembic(database_url: str, *args: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": database_url},
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"alembic {' '.join(args)} thất bại:\n{result.stdout}\n{result.stderr}"
        )


def sql(database_url: str, statement: str, **params: Any) -> list[tuple[Any, ...]]:
    """Chạy một câu SQL (tự commit) và trả về các dòng kết quả nếu có."""

    async def run() -> list[tuple[Any, ...]]:
        engine = create_async_engine(database_url)
        try:
            async with engine.begin() as connection:
                result = await connection.execute(text(statement), params)
                return [tuple(row) for row in result.fetchall()] if result.returns_rows else []
        finally:
            await engine.dispose()

    return asyncio.run(run())
