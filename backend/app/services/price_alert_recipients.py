from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Permission,
    Quote,
    QuoteLine,
    QuoteVersion,
    Role,
    TelegramAccount,
    User,
    UserAlertPreference,
    UserStatus,
    role_permissions,
    user_roles,
)
from app.services.price_alert_candidates import BUSINESS_TIMEZONE

RECEIVE_ALL_PERMISSION = "price_alerts.receive_all"
ADMIN_ROLE_NAME = "admin"
LEVEL_ORDER = {"light": 1, "medium": 2, "large": 3}

Audience = Literal["manager", "staff", "admin", "enterer"]
EventKind = Literal["change", "anomaly"]


@dataclass(frozen=True, slots=True)
class Recipient:
    user_id: UUID
    telegram_account_id: UUID
    chat_id: int
    audience: Audience


@dataclass(frozen=True, slots=True)
class SkippedRecipient:
    user_id: UUID
    reason: Literal["pilot"]


@dataclass(frozen=True, slots=True)
class RecipientDecision:
    recipients: list[Recipient]
    skipped: list[SkippedRecipient]


async def resolve_recipients(
    session: AsyncSession,
    *,
    material_id: UUID,
    event_level: str | None,
    kind: EventKind,
    now: datetime,
    seed_user_id: UUID | None,
    pilot_emails: frozenset[str] = frozenset(),
    staff_lookback_days: int = 90,
    entered_by_id: UUID | None = None,
) -> RecipientDecision:
    """Ai nhận tin của một sự kiện (D7 đến D10, L12, L16).

    - Trưởng phòng (quyền `price_alerts.receive_all`, không phải admin): mọi vật tư, mặc định từ
      Trung bình. Nhân viên: vật tư mình là `quotes.created_by_id` trong `staff_lookback_days`
      ngày, mặc định từ Nhẹ. Admin: chỉ khi bật `admin_receive_all`, mặc định từ Trung bình.
    - Chỉ người dùng `ACTIVE` có liên kết Telegram `active` (không `blocked`); tài khoản seed bị
      loại (NULL-safe). Cờ cá nhân tắt thì không nhận. `kind='anomaly'` bỏ qua mức tối thiểu và
      thêm `entered_by_id` (người nhập, nhận thẻ không nút).
    - `pilot_emails` khác rỗng: người ngoài danh sách được ghi nhận `skipped` (lý do `pilot`).
    """
    accounts = await _active_accounts(session)
    if not accounts:
        return RecipientDecision([], [])

    audiences = await _audiences(
        session,
        material_id=material_id,
        today=now.astimezone(BUSINESS_TIMEZONE).date(),
        staff_lookback_days=staff_lookback_days,
        entered_by_id=entered_by_id if kind == "anomaly" else None,
        include_staff=kind == "change",
        candidate_ids=set(accounts),
    )
    if seed_user_id is not None:
        audiences.pop(seed_user_id, None)

    users = await _users(session, set(audiences) & set(accounts))
    preferences = await _preferences(session, set(users))

    recipients: list[Recipient] = []
    skipped: list[SkippedRecipient] = []
    for user_id in sorted(users, key=str):
        user = users[user_id]
        preference = preferences.get(user_id)
        audience = audiences[user_id]
        if audience == "admin" and not (preference and preference.admin_receive_all):
            continue
        if preference is not None and not preference.is_enabled:
            continue
        if kind == "change" and not _meets_minimum(event_level, audience, preference):
            continue
        if pilot_emails and user.email.lower() not in pilot_emails:
            skipped.append(SkippedRecipient(user_id, "pilot"))
            continue
        account_id, chat_id = accounts[user_id]
        recipients.append(Recipient(user_id, account_id, chat_id, audience))
    return RecipientDecision(recipients, skipped)


def _meets_minimum(
    event_level: str | None,
    audience: Audience,
    preference: UserAlertPreference | None,
) -> bool:
    if event_level not in LEVEL_ORDER:
        return False
    chosen = preference.min_level if preference is not None else None
    minimum = chosen or ("light" if audience == "staff" else "medium")
    return LEVEL_ORDER[event_level] >= LEVEL_ORDER[minimum]


async def _active_accounts(session: AsyncSession) -> dict[UUID, tuple[UUID, int]]:
    rows = (
        await session.execute(
            select(TelegramAccount.user_id, TelegramAccount.id, TelegramAccount.chat_id).where(
                TelegramAccount.status == "active",
            ),
        )
    ).all()
    return {row[0]: (row[1], row[2]) for row in rows}


async def _audiences(
    session: AsyncSession,
    *,
    material_id: UUID,
    today: date,
    staff_lookback_days: int,
    entered_by_id: UUID | None,
    include_staff: bool,
    candidate_ids: set[UUID],
) -> dict[UUID, Audience]:
    admins = set(
        (
            await session.execute(
                select(user_roles.c.user_id)
                .join(Role, Role.id == user_roles.c.role_id)
                .where(Role.name == ADMIN_ROLE_NAME),
            )
        ).scalars(),
    )
    managers = set(
        (
            await session.execute(
                select(user_roles.c.user_id)
                .join(role_permissions, role_permissions.c.role_id == user_roles.c.role_id)
                .join(Permission, Permission.id == role_permissions.c.permission_id)
                .where(Permission.code == RECEIVE_ALL_PERMISSION),
            )
        ).scalars(),
    )
    staff: set[UUID] = set()
    if include_staff:
        staff = await _staff_ids(session, material_id, today, staff_lookback_days)
    audiences: dict[UUID, Audience] = {}
    for user_id in candidate_ids:
        # Admin trước: admin cũng có `receive_all` (migration) nhưng chỉ nhận khi bật tùy chọn.
        if user_id in admins:
            audiences[user_id] = "admin"
        elif user_id in managers:
            audiences[user_id] = "manager"
        elif user_id in staff:
            audiences[user_id] = "staff"
        elif user_id == entered_by_id:
            audiences[user_id] = "enterer"
    return audiences


async def _staff_ids(
    session: AsyncSession,
    material_id: UUID,
    today: date,
    staff_lookback_days: int,
) -> set[UUID]:
    """D8: người tạo phiếu (`quotes.created_by_id`) có dòng của vật tư trong cửa sổ gần đây."""
    creators = (
        await session.execute(
            select(Quote.created_by_id)
            .join(QuoteVersion, QuoteVersion.quote_id == Quote.id)
            .join(QuoteLine, QuoteLine.quote_version_id == QuoteVersion.id)
            .where(
                QuoteLine.material_id == material_id,
                QuoteVersion.status == "confirmed",
                QuoteVersion.confirmed_at.is_not(None),
                Quote.cancelled_at.is_(None),
                Quote.created_by_id.is_not(None),
                QuoteVersion.received_date >= today - timedelta(days=staff_lookback_days),
                QuoteVersion.received_date <= today,
            )
            .distinct(),
        )
    ).scalars()
    return {creator for creator in creators if creator is not None}


async def _users(session: AsyncSession, user_ids: set[UUID]) -> dict[UUID, User]:
    if not user_ids:
        return {}
    rows = (
        await session.execute(
            select(User).where(User.id.in_(user_ids), User.status == UserStatus.ACTIVE),
        )
    ).scalars()
    return {user.id: user for user in rows}


async def _preferences(
    session: AsyncSession,
    user_ids: set[UUID],
) -> dict[UUID, UserAlertPreference]:
    if not user_ids:
        return {}
    rows = (
        await session.execute(
            select(UserAlertPreference).where(UserAlertPreference.user_id.in_(user_ids)),
        )
    ).scalars()
    return {row.user_id: row for row in rows}
