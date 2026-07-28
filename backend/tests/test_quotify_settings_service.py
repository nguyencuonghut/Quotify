from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.models import QuotifySetting
from app.services.quotify_settings_service import (
    QuotifySettingsService,
    validate_conversion_cost,
)


class FakeScalarResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class FakeSettingsSession:
    def __init__(self, setting: QuotifySetting | None = None) -> None:
        self.setting = setting
        self.added: list[object] = []
        self.flush_count = 0

    async def execute(self, statement: object) -> FakeScalarResult:
        return FakeScalarResult(self.setting)

    def add(self, instance: object) -> None:
        self.added.append(instance)
        if isinstance(instance, QuotifySetting):
            self.setting = instance

    async def flush(self) -> None:
        self.flush_count += 1


@pytest.mark.asyncio
async def test_get_settings_creates_default_conversion_cost_when_missing() -> None:
    session = FakeSettingsSession()
    service = QuotifySettingsService(session)  # type: ignore[arg-type]

    setting = await service.get_or_create_settings()

    assert setting.conversion_cost_vnd_per_kg == Decimal("200.00")
    assert setting.singleton_key == "default"
    assert session.flush_count == 1


@pytest.mark.asyncio
async def test_update_conversion_cost_tracks_updater() -> None:
    setting = QuotifySetting(conversion_cost_vnd_per_kg=Decimal("200.00"))
    session = FakeSettingsSession(setting)
    service = QuotifySettingsService(session)  # type: ignore[arg-type]
    user_id = uuid4()

    updated = await service.update_conversion_cost(
        conversion_cost_vnd_per_kg=Decimal("250.456"),
        updated_by_id=user_id,
    )

    assert updated.conversion_cost_vnd_per_kg == Decimal("250.46")
    assert updated.updated_by_id == user_id
    assert session.flush_count == 1


def test_validate_conversion_cost_rejects_negative_value() -> None:
    with pytest.raises(ValueError, match="không được âm"):
        validate_conversion_cost(Decimal("-1"))
