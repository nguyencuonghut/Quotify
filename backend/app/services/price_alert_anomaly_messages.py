from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    PriceAlertEvent,
    PriceAlertMessage,
    PriceAlertMessageEvent,
    PriceAlertSetting,
    QuoteVersion,
)
from app.services.price_alert_candidates import BUSINESS_TIMEZONE
from app.services.price_alert_recipients import Recipient, resolve_recipients

CLUSTER_MIN_POINTS = 3
CLUSTER_REASON = "anomaly_cluster"


@dataclass(frozen=True, slots=True)
class _Flag:
    event_id: UUID
    material_id: UUID
    direction: str
    entered_by_id: UUID | None


@dataclass(slots=True)
class _Inbox:
    recipient: Recipient
    flags: list[_Flag] = field(default_factory=list)


async def build_anomaly_messages(
    session: AsyncSession,
    *,
    scan_run_id: UUID,
    now: datetime,
    settings: PriceAlertSetting,
    seed_user_id: UUID | None,
    pilot_emails: frozenset[str] = frozenset(),
) -> tuple[int, dict[str, int]]:
    """Tin cho các điểm bất thường mới của một lần quét (D12, L28); trả (số tin, theo trạng thái).

    Điểm gắn vào thẻ đang chờ (`attached_to_event_id`) không có tin riêng. Người nhận là trưởng
    phòng (thẻ có nút) và người nhập phiếu (thẻ không nút); một người chỉ nhận một thẻ cho mỗi
    vật tư. Từ 3 điểm trở lên cho cùng một người trong một lần quét thì gộp thành một tin tóm tắt.
    """
    flags = await _new_flags(session, scan_run_id)
    if not flags:
        return 0, {}

    local_date = now.astimezone(BUSINESS_TIMEZONE).date()
    inboxes: dict[UUID, _Inbox] = {}
    skipped: dict[tuple[UUID, UUID], str] = {}
    for flag in flags:
        decision = await resolve_recipients(
            session,
            material_id=flag.material_id,
            event_level=None,
            kind="anomaly",
            now=now,
            seed_user_id=seed_user_id,
            pilot_emails=pilot_emails,
            staff_lookback_days=settings.staff_lookback_days,
            entered_by_id=flag.entered_by_id,
        )
        for recipient in decision.recipients:
            inboxes.setdefault(recipient.user_id, _Inbox(recipient)).flags.append(flag)
        for skip in decision.skipped:
            skipped.setdefault((skip.user_id, flag.material_id), skip.reason)

    created = 0
    by_status: dict[str, int] = defaultdict(int)

    async def insert(
        *,
        user_id: UUID,
        account_id: UUID | None,
        material_id: UUID,
        kind: str,
        direction: str | None,
        audience: str | None,
        status: str,
        reason: str | None,
        event_ids: list[UUID],
    ) -> None:
        nonlocal created
        message_id = (
            await session.execute(
                pg_insert(PriceAlertMessage)
                .values(
                    user_id=user_id,
                    telegram_account_id=account_id,
                    material_id=material_id,
                    local_date=local_date,
                    scan_run_id=scan_run_id,
                    kind=kind,
                    direction=direction,
                    audience=audience,
                    status=status,
                    status_reason=reason,
                    created_at=now,
                )
                .on_conflict_do_nothing(constraint="uq_price_alert_messages_unit")
                .returning(PriceAlertMessage.id),
            )
        ).scalar_one_or_none()
        if message_id is None:
            return
        created += 1
        by_status[status] += 1
        await session.execute(
            pg_insert(PriceAlertMessageEvent)
            .values([{"message_id": message_id, "event_id": event_id} for event_id in event_ids])
            .on_conflict_do_nothing(),
        )

    for (user_id, material_id), reason in skipped.items():
        if user_id in inboxes:
            continue
        ids = [f.event_id for f in flags if f.material_id == material_id]
        await insert(
            user_id=user_id,
            account_id=None,
            material_id=material_id,
            kind="anomaly",
            direction=None,
            audience=None,
            status="skipped",
            reason=reason,
            event_ids=ids,
        )

    for user_id, inbox in inboxes.items():
        recipient = inbox.recipient
        if len(inbox.flags) >= CLUSTER_MIN_POINTS:
            await insert(
                user_id=user_id,
                account_id=recipient.telegram_account_id,
                material_id=inbox.flags[0].material_id,
                kind="digest",
                direction=None,
                audience=recipient.audience,
                status="pending",
                reason=CLUSTER_REASON,
                event_ids=[f.event_id for f in inbox.flags],
            )
            continue
        by_material: dict[UUID, list[_Flag]] = defaultdict(list)
        for flag in inbox.flags:
            by_material[flag.material_id].append(flag)
        for material_id, material_flags in by_material.items():
            await insert(
                user_id=user_id,
                account_id=recipient.telegram_account_id,
                material_id=material_id,
                kind="anomaly",
                direction=material_flags[0].direction,
                audience=recipient.audience,
                status="pending",
                reason=None,
                event_ids=[f.event_id for f in material_flags],
            )
    return created, dict(by_status)


async def _new_flags(session: AsyncSession, scan_run_id: UUID) -> list[_Flag]:
    rows = (
        await session.execute(
            select(
                PriceAlertEvent.id,
                PriceAlertEvent.material_id,
                PriceAlertEvent.direction,
                QuoteVersion.created_by_id,
            )
            .join(QuoteVersion, QuoteVersion.id == PriceAlertEvent.quote_version_id)
            .where(
                PriceAlertEvent.scan_run_id == scan_run_id,
                PriceAlertEvent.kind == "anomaly",
                PriceAlertEvent.review_status == "pending",
                PriceAlertEvent.attached_to_event_id.is_(None),
            )
            .order_by(
                PriceAlertEvent.material_id,
                PriceAlertEvent.delivery_month,
                PriceAlertEvent.sequence_number,
            ),
        )
    ).all()
    return [_Flag(r[0], r[1], r[2], r[3]) for r in rows]
