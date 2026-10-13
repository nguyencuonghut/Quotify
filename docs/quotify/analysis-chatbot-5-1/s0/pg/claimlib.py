"""Claim algorithm of plan 4.5 (literal) + deliberately broken variants for contrast."""
import asyncio, random, time, os, uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncConnection

from common import DSN

UTC = timezone.utc
CHAT_SALT = "bot:chat:"
USER = uuid.UUID("00000000-0000-0000-0000-000000000001")

# ---- SQL, exactly the plan's steps -------------------------------------------------
# NOTE: the plan writes  hashtextextended('bot:chat:' || chat_id, 0)  (no cast); we bind chat_id as a parameter.
SQL_LOCK = text("SELECT pg_advisory_xact_lock(hashtextextended('bot:chat:' || CAST(:chat_id AS BIGINT), 0))")
SQL_LIVE = text("""
    SELECT 1 FROM bot_updates
    WHERE chat_id = :chat_id AND status = 'processing' AND lease_until > :now
    LIMIT 1""")
SQL_HEAD = text("""
    SELECT update_id, status, lease_until, attempts FROM bot_updates
    WHERE chat_id = :chat_id AND status IN ('queued','processing')
    ORDER BY update_id
    LIMIT 1""")
SQL_HEAD_FU = text(SQL_HEAD.text + " FOR UPDATE")
SQL_EXHAUST = text("""
    UPDATE bot_updates
       SET status='failed', error_category='lease_exhausted', finished_at=:now,
           payload_text=NULL, reply_text=NULL
     WHERE update_id=:id AND status IN ('queued','processing')""")
# Guarded take (status IN open) vs unguarded take (for the contrast test)
SQL_TAKE_GUARDED = text("""
    UPDATE bot_updates
       SET status='processing', lease_until=:lease_until, attempts=attempts+1,
           started_at=coalesce(started_at, :now)
     WHERE update_id=:id AND status IN ('queued','processing')
 RETURNING update_id, attempts, chat_id""")
SQL_TAKE_UNGUARDED = text("""
    UPDATE bot_updates
       SET status='processing', lease_until=:lease_until, attempts=attempts+1,
           started_at=coalesce(started_at, :now)
     WHERE update_id=:id
 RETURNING update_id, attempts, chat_id""")
SQL_POSTCHECK = text("""
    SELECT count(*) FROM bot_updates
    WHERE chat_id=:chat_id AND status='processing' AND lease_until > :now""")

@dataclass
class Claimed:
    update_id: int
    attempts: int
    chat_id: int
    live_count_in_txn: int = 1

@dataclass
class Result:
    claimed: Claimed | None
    exhausted: list = field(default_factory=list)

async def claim_plan(conn: AsyncConnection, chat_id: int, now: datetime, *, lease_s=240, max_attempts=3,
                     guarded_take=True, sleep_between_head_and_take=0.0, retake_on_miss=True, head_for_update=False) -> Result:
    """Plan 4.5 claim steps 1-4 in the caller's (single) transaction."""
    res = Result(None)
    await conn.execute(SQL_LOCK, {"chat_id": chat_id})                                  # 1
    while True:
        if (await conn.execute(SQL_LIVE, {"chat_id": chat_id, "now": now})).first():    # 2
            return res
        head = (await conn.execute(SQL_HEAD_FU if head_for_update else SQL_HEAD, {"chat_id": chat_id})).first()  # 3
        if head is None:
            return res
        if head.status == "queued" and head.lease_until is not None and head.lease_until > now:
            return res                                                                  # no skipping ahead
        if head.attempts >= max_attempts:                                               # 4
            await conn.execute(SQL_EXHAUST, {"id": head.update_id, "now": now})
            res.exhausted.append(head.update_id)
            continue                                                                    # back to step 1 (lock re-entrant, no-op)
        if sleep_between_head_and_take:
            await asyncio.sleep(sleep_between_head_and_take)
        row = (await conn.execute(SQL_TAKE_GUARDED if guarded_take else SQL_TAKE_UNGUARDED, {
            "id": head.update_id, "now": now, "lease_until": now + timedelta(seconds=lease_s)})).first()
        if row is None:
            if retake_on_miss:
                sleep_between_head_and_take = 0.0
                continue
            return res
        live = (await conn.execute(SQL_POSTCHECK, {"chat_id": chat_id, "now": now})).scalar()
        res.claimed = Claimed(row.update_id, row.attempts, row.chat_id, live)
        return res

# ---- broken variants ----------------------------------------------------------------
async def claim_headlock(conn, chat_id, now, *, lease_s=240, max_attempts=3, **_):
    """(a) plain head-row lock: no advisory lock, no 'live lease' predicate."""
    res = Result(None)
    head = (await conn.execute(text("""
        SELECT update_id, attempts FROM bot_updates
        WHERE chat_id=:chat_id AND (status='queued' OR (status='processing' AND lease_until <= :now))
        ORDER BY update_id LIMIT 1 FOR UPDATE"""), {"chat_id": chat_id, "now": now})).first()
    if head is None:
        return res
    row = (await conn.execute(SQL_TAKE_GUARDED, {"id": head.update_id, "now": now,
                                                  "lease_until": now + timedelta(seconds=lease_s)})).first()
    if row:
        live = (await conn.execute(SQL_POSTCHECK, {"chat_id": chat_id, "now": now})).scalar()
        res.claimed = Claimed(row.update_id, row.attempts, row.chat_id, live)
    return res

async def claim_advisory_nolive(conn, chat_id, now, *, lease_s=240, max_attempts=3, **_):
    """(a2) advisory lock but WITHOUT the step-2 live-lease predicate."""
    res = Result(None)
    await conn.execute(SQL_LOCK, {"chat_id": chat_id})
    head = (await conn.execute(text("""
        SELECT update_id, attempts FROM bot_updates
        WHERE chat_id=:chat_id AND (status='queued' OR (status='processing' AND lease_until <= :now))
        ORDER BY update_id LIMIT 1"""), {"chat_id": chat_id, "now": now})).first()
    if head is None:
        return res
    row = (await conn.execute(SQL_TAKE_GUARDED, {"id": head.update_id, "now": now,
                                                  "lease_until": now + timedelta(seconds=lease_s)})).first()
    if row:
        live = (await conn.execute(SQL_POSTCHECK, {"chat_id": chat_id, "now": now})).scalar()
        res.claimed = Claimed(row.update_id, row.attempts, row.chat_id, live)
    return res

async def claim_skip_locked(conn, chat_id, now, *, lease_s=240, max_attempts=3, **_):
    """(b) FOR UPDATE SKIP LOCKED over queued rows."""
    res = Result(None)
    head = (await conn.execute(text("""
        SELECT update_id, attempts FROM bot_updates
        WHERE chat_id=:chat_id AND status='queued'
        ORDER BY update_id LIMIT 1 FOR UPDATE SKIP LOCKED"""), {"chat_id": chat_id})).first()
    if head is None:
        return res
    row = (await conn.execute(SQL_TAKE_GUARDED, {"id": head.update_id, "now": now,
                                                  "lease_until": now + timedelta(seconds=lease_s)})).first()
    if row:
        live = (await conn.execute(SQL_POSTCHECK, {"chat_id": chat_id, "now": now})).scalar()
        res.claimed = Claimed(row.update_id, row.attempts, row.chat_id, live)
    return res

async def claim_nolock_noguard(conn, chat_id, now, *, lease_s=240, max_attempts=3, **_):
    """(c) reviewer's: read head without any lock, UPDATE by update_id only (no status/lease guard)."""
    res = Result(None)
    head = (await conn.execute(text("""
        SELECT update_id, attempts FROM bot_updates
        WHERE chat_id=:chat_id AND status IN ('queued','processing')
        ORDER BY update_id LIMIT 1"""), {"chat_id": chat_id})).first()
    if head is None:
        return res
    row = (await conn.execute(SQL_TAKE_UNGUARDED, {"id": head.update_id, "now": now,
                                                    "lease_until": now + timedelta(seconds=lease_s)})).first()
    if row:
        live = (await conn.execute(SQL_POSTCHECK, {"chat_id": chat_id, "now": now})).scalar()
        res.claimed = Claimed(row.update_id, row.attempts, row.chat_id, live)
    return res

async def claim_due_filter(conn, chat_id, now, *, lease_s=240, max_attempts=3, **_):
    """(4-contrast) advisory lock + live check, but picks the smallest *due* row (skips rows still in backoff)."""
    res = Result(None)
    await conn.execute(SQL_LOCK, {"chat_id": chat_id})
    if (await conn.execute(SQL_LIVE, {"chat_id": chat_id, "now": now})).first():
        return res
    head = (await conn.execute(text("""
        SELECT update_id, attempts FROM bot_updates
        WHERE chat_id=:chat_id AND ((status='queued' AND (lease_until IS NULL OR lease_until <= :now)) OR status='processing')
        ORDER BY update_id LIMIT 1"""), {"chat_id": chat_id, "now": now})).first()
    if head is None:
        return res
    row = (await conn.execute(SQL_TAKE_GUARDED, {"id": head.update_id, "now": now,
                                                  "lease_until": now + timedelta(seconds=lease_s)})).first()
    if row:
        live = (await conn.execute(SQL_POSTCHECK, {"chat_id": chat_id, "now": now})).scalar()
        res.claimed = Claimed(row.update_id, row.attempts, row.chat_id, live)
    return res

async def claim_headlock_headcheck(conn, chat_id, now, *, lease_s=240, max_attempts=3, **_):
    """(a') head-row lock WITH a check on the head row only (no chat-wide live-lease predicate, no advisory lock)."""
    res = Result(None)
    head = (await conn.execute(text("""
        SELECT update_id, status, lease_until, attempts FROM bot_updates
        WHERE chat_id=:chat_id AND status IN ('queued','processing')
        ORDER BY update_id LIMIT 1 FOR UPDATE"""), {"chat_id": chat_id})).first()
    if head is None or (head.lease_until is not None and head.lease_until > now):
        return res
    row = (await conn.execute(SQL_TAKE_GUARDED, {"id": head.update_id, "now": now,
                                                  "lease_until": now + timedelta(seconds=lease_s)})).first()
    if row:
        live = (await conn.execute(SQL_POSTCHECK, {"chat_id": chat_id, "now": now})).scalar()
        res.claimed = Claimed(row.update_id, row.attempts, row.chat_id, live)
    return res

VARIANTS = {
    "headlock_headcheck": claim_headlock_headcheck,
    "due_filter": claim_due_filter,
    "plan": claim_plan,
    "headlock": claim_headlock,
    "advisory_nolive": claim_advisory_nolive,
    "skip_locked": claim_skip_locked,
    "nolock_noguard": claim_nolock_noguard,
}

async def claim(engine, variant, chat_id, now, **kw) -> Result:
    async with engine.connect() as conn:       # short txn: autobegin, commit at the end
        res = await VARIANTS[variant](conn, chat_id, now, **kw)
        await conn.commit()
        return res

# ---- fenced writes ------------------------------------------------------------------
async def save_reply(engine, update_id, attempts, text_, now) -> int:
    async with engine.begin() as c:
        r = await c.execute(text("""UPDATE bot_updates SET reply_text=:t, reply_saved_at=:now
            WHERE update_id=:id AND status='processing' AND attempts=:mine"""),
            {"t": text_, "now": now, "id": update_id, "mine": attempts})
        return r.rowcount

async def complete(engine, update_id, attempts, now) -> int:
    async with engine.begin() as c:
        r = await c.execute(text("""UPDATE bot_updates SET status='replied', finished_at=:now,
              payload_text=NULL, reply_text=NULL
            WHERE update_id=:id AND status='processing' AND attempts=:mine"""),
            {"now": now, "id": update_id, "mine": attempts})
        return r.rowcount

async def requeue(engine, update_id, attempts, retry_at) -> int:
    async with engine.begin() as c:
        r = await c.execute(text("""UPDATE bot_updates SET status='queued', lease_until=:retry_at
            WHERE update_id=:id AND status='processing' AND attempts=:mine"""),
            {"retry_at": retry_at, "id": update_id, "mine": attempts})
        return r.rowcount

# ---- helpers ------------------------------------------------------------------------
def mk_engine(**kw):
    kw.setdefault("pool_size", 8); kw.setdefault("max_overflow", 4)
    return create_async_engine(DSN, **kw)

async def insert_rows(engine, chat_id, ids, *, status="queued", lease_until=None, attempts=0, now=None,
                      reply_saved_at=None, kind="text", user_id=USER, received_at=None):
    async with engine.begin() as c:
        for i in ids:
            await c.execute(text("""INSERT INTO bot_updates
              (update_id, chat_id, telegram_user_id, user_id, kind, status, payload_text, attempts, lease_until, reply_saved_at, received_at)
              VALUES (:id,:chat,:tg,:u,:kind,:st,'hello',:att,:lease,:rsa, coalesce(:rcv, now()))"""),
              {"id": i, "chat": chat_id, "tg": chat_id, "u": user_id, "kind": kind, "st": status, "att": attempts,
               "lease": lease_until, "rsa": reply_saved_at, "rcv": received_at})

async def reset_table(engine):
    async with engine.begin() as c:
        await c.execute(text("TRUNCATE bot_updates"))

async def fetch(engine, update_id):
    async with engine.connect() as c:
        return (await c.execute(text("SELECT update_id,status,attempts,lease_until,error_category,finished_at,payload_text,reply_text,reply_saved_at FROM bot_updates WHERE update_id=:i"), {"i": update_id})).first()
