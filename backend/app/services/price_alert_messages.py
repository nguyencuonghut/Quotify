from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    PriceAlertEvent,
    PriceAlertMessage,
    PriceAlertMessageEvent,
    PriceAlertSetting,
    Quote,
    QuoteVersion,
)
from app.services.price_alert_candidates import BUSINESS_TIMEZONE
from app.services.price_alert_recipients import (
    LEVEL_ORDER,
    Recipient,
    resolve_recipients,
)

# Trần thứ hai (L27, RR-46): tin gửi ngay cho một người trong 10 phút gần nhất.
ROLLING_CAP = 30
ROLLING_WINDOW = timedelta(minutes=10)
_COUNTED_STATUSES = ("pending", "sending", "sent", "digest_queued")
_IMMEDIATE_STATUSES = ("pending", "sending", "sent")


@dataclass(slots=True)
class BuildResult:
    created: int = 0
    by_status: dict[str, int] = field(default_factory=lambda: defaultdict(int))


@dataclass(frozen=True, slots=True)
class _Group:
    material_id: UUID
    level: str
    direction: str
    event_ids: list[UUID]
    is_followup: bool = False


class PriceAlertMessageService:
    """Gộp sự kiện của một lần quét thành tin theo từng người nhận (D5b, L18, L27).

    Service chỉ `flush`; chạy trong cùng giao dịch với lần quét.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        seed_user_id: UUID | None,
        pilot_emails: frozenset[str] = frozenset(),
    ) -> None:
        self.session = session
        self.seed_user_id = seed_user_id
        self.pilot_emails = pilot_emails
        self._now: datetime = datetime.min

    async def build_for_run(
        self,
        *,
        scan_run_id: UUID,
        now: datetime,
        settings: PriceAlertSetting,
    ) -> BuildResult:
        self._now = now
        result = BuildResult()
        groups = await self._groups(scan_run_id)
        if not groups:
            return result

        local_date = now.astimezone(BUSINESS_TIMEZONE).date()
        immediate_in_scan: dict[UUID, int] = defaultdict(int)
        rolling_base: dict[UUID, int] = {}
        overflow: dict[UUID, tuple[Recipient, list[UUID]]] = {}

        # Mức cao trước để trần không cắt nhầm tin Lớn.
        for group in sorted(groups, key=lambda g: (-LEVEL_ORDER[g.level], str(g.material_id))):
            decision = await resolve_recipients(
                self.session,
                material_id=group.material_id,
                event_level=group.level,
                kind="change",
                now=now,
                seed_user_id=self.seed_user_id,
                pilot_emails=self.pilot_emails,
                staff_lookback_days=settings.staff_lookback_days,
            )
            for skipped in decision.skipped:
                await self._insert(
                    result,
                    scan_run_id=scan_run_id,
                    user_id=skipped.user_id,
                    account_id=None,
                    group=group,
                    local_date=local_date,
                    status="skipped",
                    reason=skipped.reason,
                )
            for recipient in decision.recipients:
                status, reason = await self._decide(
                    recipient,
                    group,
                    local_date=local_date,
                    now=now,
                    cap=settings.immediate_cap_per_scan,
                    immediate_in_scan=immediate_in_scan,
                    rolling_base=rolling_base,
                )
                if status == "pending":
                    immediate_in_scan[recipient.user_id] += 1
                if reason == "cap":
                    overflow.setdefault(recipient.user_id, (recipient, []))[1].extend(
                        group.event_ids,
                    )
                await self._insert(
                    result,
                    scan_run_id=scan_run_id,
                    user_id=recipient.user_id,
                    account_id=recipient.telegram_account_id,
                    group=group,
                    local_date=local_date,
                    status=status,
                    reason=reason,
                )

        for recipient, event_ids in overflow.values():
            await self._insert_summary(
                result,
                scan_run_id=scan_run_id,
                recipient=recipient,
                local_date=local_date,
                event_ids=event_ids,
            )
        return result

    async def _groups(self, scan_run_id: UUID) -> list[_Group]:
        rows = (
            await self.session.execute(
                select(
                    PriceAlertEvent.id,
                    PriceAlertEvent.material_id,
                    PriceAlertEvent.level,
                    PriceAlertEvent.direction,
                    PriceAlertEvent.delivery_month,
                    PriceAlertEvent.prior_alert_price,
                )
                .where(
                    PriceAlertEvent.scan_run_id == scan_run_id,
                    PriceAlertEvent.kind == "change",
                )
                .order_by(PriceAlertEvent.material_id, PriceAlertEvent.delivery_month),
            )
        ).all()
        by_material: dict[UUID, list[tuple[UUID, str, str, bool]]] = defaultdict(list)
        for event_id, material_id, level, direction, _month, prior_price in rows:
            by_material[material_id].append((event_id, level, direction, prior_price is not None))
        groups = []
        for material_id, events in by_material.items():
            # Tiêu đề theo kỳ có mức cao nhất; hòa thì lấy kỳ giao hàng sớm nhất (đã sắp theo kỳ).
            top = max(events, key=lambda e: LEVEL_ORDER[e[1]])
            # Chỉ khi kỳ đứng đầu là báo tiếp mới bỏ qua giới hạn 'leo thang trong ngày'.
            followup = top[3]
            groups.append(_Group(material_id, top[1], top[2], [e[0] for e in events], followup))
        return groups

    async def _decide(
        self,
        recipient: Recipient,
        group: _Group,
        *,
        local_date: date,
        now: datetime,
        cap: int,
        immediate_in_scan: dict[UUID, int],
        rolling_base: dict[UUID, int],
    ) -> tuple[str, str | None]:
        # Tin báo tiếp (giá đi thêm đáng kể so với lần báo trước) không bị coi là lặp trong ngày.
        if not group.is_followup and not await self._escalates(
            recipient.user_id, group, local_date
        ):
            return "suppressed", "no_escalation"
        if group.level == "light":
            return "digest_queued", "light"
        if recipient.user_id not in rolling_base:
            rolling_base[recipient.user_id] = await self._recent_immediate(recipient.user_id, now)
        sent_recently = rolling_base[recipient.user_id] + immediate_in_scan[recipient.user_id]
        if immediate_in_scan[recipient.user_id] >= cap or sent_recently >= ROLLING_CAP:
            return "digest_queued", "cap"
        return "pending", None

    async def _escalates(self, user_id: UUID, group: _Group, local_date: date) -> bool:
        """D5(b): cùng ngày chỉ có tin mới khi mức cao hơn mức cao nhất đã có, hoặc đổi chiều."""
        rows = (
            await self.session.execute(
                select(PriceAlertMessage.level_max, PriceAlertMessage.direction)
                .where(
                    PriceAlertMessage.user_id == user_id,
                    PriceAlertMessage.material_id == group.material_id,
                    PriceAlertMessage.local_date == local_date,
                    PriceAlertMessage.kind == "change",
                    PriceAlertMessage.status.in_(_COUNTED_STATUSES),
                    # Tin bị trần cắt chưa từng được gửi riêng nên không chặn tin sau (D5b).
                    func.coalesce(PriceAlertMessage.status_reason, "") != "cap",
                    # Tin chỉ gồm sự kiện của phiếu đã hủy không được tính là "đã có tin" hôm nay.
                    PriceAlertMessage.id.in_(
                        select(PriceAlertMessageEvent.message_id)
                        .join(
                            PriceAlertEvent,
                            PriceAlertEvent.id == PriceAlertMessageEvent.event_id,
                        )
                        .join(QuoteVersion, QuoteVersion.id == PriceAlertEvent.quote_version_id)
                        .join(Quote, Quote.id == QuoteVersion.quote_id)
                        .where(Quote.cancelled_at.is_(None)),
                    ),
                )
                .order_by(PriceAlertMessage.sequence_number),
            )
        ).all()
        if not rows:
            return True
        highest = max(LEVEL_ORDER[level] for level, _ in rows)
        last_direction = rows[-1][1]
        return LEVEL_ORDER[group.level] > highest or group.direction != last_direction

    async def _recent_immediate(self, user_id: UUID, now: datetime) -> int:
        return (
            await self.session.execute(
                select(func.count())
                .select_from(PriceAlertMessage)
                .where(
                    PriceAlertMessage.user_id == user_id,
                    PriceAlertMessage.kind == "change",
                    PriceAlertMessage.status.in_(_IMMEDIATE_STATUSES),
                    # Tin Nhẹ đã gộp vào bản tin hằng ngày chưa từng được gửi riêng.
                    func.coalesce(PriceAlertMessage.status_reason, "") != "in_digest",
                    PriceAlertMessage.created_at > now - ROLLING_WINDOW,
                    PriceAlertMessage.created_at <= now,
                ),
            )
        ).scalar_one()

    async def _insert(
        self,
        result: BuildResult,
        *,
        scan_run_id: UUID,
        user_id: UUID,
        account_id: UUID | None,
        group: _Group,
        local_date: date,
        status: str,
        reason: str | None,
    ) -> None:
        inserted = await self.session.execute(
            pg_insert(PriceAlertMessage)
            .values(
                user_id=user_id,
                telegram_account_id=account_id,
                material_id=group.material_id,
                local_date=local_date,
                scan_run_id=scan_run_id,
                kind="change",
                level_max=group.level,
                direction=group.direction,
                status=status,
                status_reason=reason,
                created_at=self._now,
            )
            .on_conflict_do_nothing(constraint="uq_price_alert_messages_unit")
            .returning(PriceAlertMessage.id),
        )
        message_id = inserted.scalar_one_or_none()
        if message_id is None:
            return
        result.created += 1
        result.by_status[status] += 1
        await self._link_events(message_id, group.event_ids)

    async def _insert_summary(
        self,
        result: BuildResult,
        *,
        scan_run_id: UUID,
        recipient: Recipient,
        local_date: date,
        event_ids: list[UUID],
    ) -> None:
        recent_summary = (
            await self.session.execute(
                select(func.count())
                .select_from(PriceAlertMessage)
                .where(
                    PriceAlertMessage.user_id == recipient.user_id,
                    PriceAlertMessage.kind == "digest",
                    PriceAlertMessage.audience.is_(None),
                    # Bản tin hằng ngày không phải tin tóm tắt tràn trần (1C, Slice 1).
                    PriceAlertMessage.digest_kind.is_(None),
                    PriceAlertMessage.created_at > self._now - ROLLING_WINDOW,
                    PriceAlertMessage.created_at <= self._now,
                ),
            )
        ).scalar_one()
        if recent_summary:
            # Đã có tin tóm tắt trong cửa sổ 10 phút: không gửi thêm (đó là trần L27 định chặn).
            return
        inserted = await self.session.execute(
            pg_insert(PriceAlertMessage)
            .values(
                user_id=recipient.user_id,
                telegram_account_id=recipient.telegram_account_id,
                material_id=None,
                local_date=local_date,
                scan_run_id=scan_run_id,
                kind="digest",
                status="pending",
                status_reason="overflow",
                created_at=self._now,
            )
            .on_conflict_do_nothing(
                index_elements=["user_id", "scan_run_id"],
                index_where=text("kind = 'digest' AND material_id IS NULL"),
            )
            .returning(PriceAlertMessage.id),
        )
        message_id = inserted.scalar_one_or_none()
        if message_id is None:
            return
        result.created += 1
        result.by_status["pending"] += 1
        await self._link_events(message_id, event_ids)

    async def _link_events(self, message_id: UUID, event_ids: list[UUID]) -> None:
        if not event_ids:
            return
        await self.session.execute(
            pg_insert(PriceAlertMessageEvent)
            .values([{"message_id": message_id, "event_id": event_id} for event_id in event_ids])
            .on_conflict_do_nothing(),
        )
