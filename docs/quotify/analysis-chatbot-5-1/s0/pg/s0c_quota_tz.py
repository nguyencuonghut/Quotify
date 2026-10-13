import asyncio, uuid, os, sys
from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from common import DSN

VN = ZoneInfo("Asia/Ho_Chi_Minh"); UTC = timezone.utc
U = uuid.UUID("00000000-0000-0000-0000-0000000000ff")
UID0 = 900000000

def day_bounds_utc(d: date):
    s = datetime.combine(d, time.min, VN); e = datetime.combine(d + timedelta(days=1), time.min, VN)
    return s.astimezone(UTC), e.astimezone(UTC)

COUNT = text("""SELECT count(*) FROM bot_updates WHERE user_id=:u AND reply_saved_at IS NOT NULL
                AND received_at >= :s AND received_at < :e""")
COUNT_FILE = text("""SELECT count(*) FROM bot_updates WHERE user_id=:u AND reply_saved_at IS NOT NULL
                AND kind IN ('photo','document') AND received_at >= :s AND received_at < :e""")
COUNT_DATECAST_BAD = text("""SELECT count(*) FROM bot_updates WHERE user_id=:u AND reply_saved_at IS NOT NULL
                AND received_at::date = :d""")      # depends on session timezone
COUNT_DATECAST_OK = text("""SELECT count(*) FROM bot_updates WHERE user_id=:u AND reply_saved_at IS NOT NULL
                AND (received_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = :d""")

# (label, received_at literal with explicit offset, kind, has_reply, expected business day VN)
ROWS = [
    ("12-10 23:59:59.999999+07", "2026-10-12 23:59:59.999999+07", "text", True, date(2026,10,12)),
    ("13-10 00:00:00+07",        "2026-10-13 00:00:00+07",        "text", True, date(2026,10,13)),
    ("13-10 00:00:00.000001+07", "2026-10-13 00:00:00.000001+07", "photo", True, date(2026,10,13)),
    ("13-10 12:00:00+07",        "2026-10-13 12:00:00+07",        "text", True, date(2026,10,13)),
    ("13-10 12:00:00+07 no reply","2026-10-13 12:00:01+07",       "text", False, date(2026,10,13)),
    ("13-10 23:59:59+07",        "2026-10-13 23:59:59+07",        "document", True, date(2026,10,13)),
    ("13-10 23:59:59.999999+07", "2026-10-13 23:59:59.999999+07", "text", True, date(2026,10,13)),
    ("14-10 00:00:00+07",        "2026-10-14 00:00:00+07",        "text", True, date(2026,10,14)),
    ("14-10 00:00:00+07 as UTC literal 13-10 17:00Z", "2026-10-13 17:00:00+00", "text", True, date(2026,10,14)),
]

async def seed():
    adm = create_async_engine(DSN, isolation_level="AUTOCOMMIT")
    async with adm.connect() as c:
        await c.execute(text("DELETE FROM bot_updates WHERE user_id=:u"), {"u": U})
        for i, (lab, lit, kind, has_reply, _) in enumerate(ROWS):
            rs = f"timestamptz '{lit}'"
            await c.execute(text(f"""INSERT INTO bot_updates(update_id,chat_id,telegram_user_id,user_id,kind,status,received_at,reply_saved_at)
                 VALUES (:id,777,777,:u,:k,'replied', {rs}, {rs + " + interval '5 seconds'" if has_reply else "NULL"})"""),
                 {"id": UID0 + i, "u": U, "k": kind})
    await adm.dispose()

async def counts_for(tzsetting):
    # (a) per-connection timezone via server_settings; (b) check what SHOW timezone says
    e = create_async_engine(DSN, connect_args={"server_settings": {"timezone": tzsetting}})
    out = {}
    async with e.connect() as c:
        out["show_tz"] = (await c.execute(text("SHOW timezone"))).scalar()
        for d in (date(2026,10,12), date(2026,10,13), date(2026,10,14)):
            s, en = day_bounds_utc(d)
            out[d] = ((await c.execute(COUNT, {"u": U, "s": s, "e": en})).scalar(),
                      (await c.execute(COUNT_FILE, {"u": U, "s": s, "e": en})).scalar(),
                      (await c.execute(COUNT_DATECAST_BAD, {"u": U, "d": d})).scalar(),
                      (await c.execute(COUNT_DATECAST_OK, {"u": U, "d": d})).scalar())
    await e.dispose()
    return out

async def main():
    await seed()
    exp = {}
    for lab, lit, kind, has, d in ROWS:
        if has: exp[d] = exp.get(d, 0) + 1
    exp_file = {date(2026,10,13): 2}
    print("expected turn counts by VN business day:", {str(k): v for k, v in exp.items()})
    print("python bounds:", {str(d): tuple(x.isoformat() for x in day_bounds_utc(d)) for d in (date(2026,10,13),)})
    allres = {}
    for tz in ("UTC", "Asia/Ho_Chi_Minh", "America/Los_Angeles"):
        r = await counts_for(tz); allres[tz] = r
        print(f"--- session timezone={r['show_tz']}")
        for d in (date(2026,10,12), date(2026,10,13), date(2026,10,14)):
            tc, fc, bad, ok = r[d]
            print(f"   {d}: python-UTC-bounds turns={tc} files={fc} | DB date-cast `received_at::date` (BAD)={bad} | AT TIME ZONE form={ok}")
    # also at database-default level (ALTER DATABASE ... SET timezone) like a server configured in UTC vs VN
    adm = create_async_engine(DSN, isolation_level="AUTOCOMMIT")
    for tz in ("UTC", "Asia/Ho_Chi_Minh"):
        async with adm.connect() as c:
            await c.execute(text(f"ALTER DATABASE s0 SET timezone TO '{tz}'"))
        e = create_async_engine(DSN)
        async with e.connect() as c:
            shown = (await c.execute(text("SHOW timezone"))).scalar()
            s, en = day_bounds_utc(date(2026,10,13))
            n = (await c.execute(COUNT, {"u": U, "s": s, "e": en})).scalar()
            print(f"--- ALTER DATABASE timezone={tz}: new session SHOW timezone={shown}; python-bounds count 13-10 = {n}")
        await e.dispose()
    async with adm.connect() as c:
        await c.execute(text("ALTER DATABASE s0 RESET timezone"))
    await adm.dispose()
    ok = all(allres[tz][d][0] == exp[d] and allres[tz][date(2026,10,13)][1] == 2 for tz in allres for d in exp)
    same = len({tuple(allres[tz][d][0] for d in exp) for tz in allres}) == 1
    bad_differs = len({tuple(allres[tz][d][2] for d in exp) for tz in allres}) > 1
    print(f"RESULT python-bounds counts equal expected in every timezone: {ok}; identical across tz: {same}; DB date-cast form differs across tz (the trap): {bad_differs}")

    # naive datetime handling by asyncpg
    e = create_async_engine(DSN, connect_args={"server_settings": {"timezone": "UTC"}})
    async with e.connect() as c:
        r = (await c.execute(text("SELECT CAST(:t AS timestamptz) AT TIME ZONE 'UTC'"), {"t": datetime(2026,10,13,12,0,0)})).scalar()
        print(f"naive datetime(2026,10,13,12:00) bound to timestamptz, process TZ={os.environ.get('TZ','(unset)')}, session UTC => stored UTC wall clock {r}")
    await e.dispose()
asyncio.run(main())
