import asyncio, time, sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.exc import DBAPIError
from common import DSN

SS = {"default_transaction_read_only": "on", "statement_timeout": "5000", "idle_in_transaction_session_timeout": "15000"}

def mk(**kw):
    return create_async_engine(DSN, connect_args={"server_settings": dict(SS)}, **kw)

def desc(e):
    orig = getattr(e, "orig", None)
    sqlstate = getattr(orig, "sqlstate", None) or getattr(getattr(orig, "__cause__", None), "sqlstate", None)
    return f"{type(e).__name__} / orig={type(orig).__name__} / cause={type(getattr(orig,'__cause__',None)).__name__} / SQLSTATE={sqlstate} / msg={str(orig).strip().splitlines()[0] if orig else e}"

async def setup():
    admin = create_async_engine(DSN, isolation_level="AUTOCOMMIT")
    async with admin.connect() as c:
        await c.execute(text("DROP TABLE IF EXISTS ro_t"))
        await c.execute(text("CREATE TABLE ro_t(id int primary key, v text)"))
        await c.execute(text("INSERT INTO ro_t VALUES (1,'a'),(2,'b')"))
    await admin.dispose()

async def shows(conn):
    r1 = (await conn.execute(text("SHOW default_transaction_read_only"))).scalar()
    r2 = (await conn.execute(text("SHOW statement_timeout"))).scalar()
    r3 = (await conn.execute(text("SHOW idle_in_transaction_session_timeout"))).scalar()
    r4 = (await conn.execute(text("SHOW transaction_read_only"))).scalar()
    r5 = (await conn.execute(text("SHOW transaction_isolation"))).scalar()
    return f"default_ro={r1} stmt_timeout={r2} idle_tx={r3} transaction_read_only={r4} iso={r5}"

async def main():
    await setup()
    eng = mk(pool_size=2, max_overflow=1)
    # (1)
    print("== (1) SELECT")
    async with eng.connect() as c:
        print("select:", (await c.execute(text("SELECT count(*) FROM ro_t"))).scalar())
        print(await shows(c))
        await c.rollback()
    # (2)
    print("== (2) writes")
    stmts = [
        "INSERT INTO ro_t VALUES (3,'c')",
        "UPDATE ro_t SET v='z' WHERE id=1",
        "DELETE FROM ro_t WHERE id=1",
        "CREATE TABLE new_t(id int)",
        "CREATE TEMP TABLE tmp_t(id int)",
        "SELECT * FROM ro_t WHERE id=1 FOR UPDATE",
        "SELECT * FROM ro_t WHERE id=1 FOR SHARE",
        "SELECT nextval('pg_catalog.pg_class_oid_index'::regclass)" if False else "SELECT pg_advisory_xact_lock(42)",
        "SELECT pg_advisory_lock(43)",
    ]
    for s in stmts:
        async with eng.connect() as c:
            try:
                r = await c.execute(text(s))
                print(f"OK   : {s}  -> accepted")
            except DBAPIError as e:
                print(f"FAIL : {s}\n       {desc(e)}")
            await c.rollback()
    # verify no side effects
    admin = create_async_engine(DSN, isolation_level="AUTOCOMMIT")
    async with admin.connect() as c:
        print("table rows after:", (await c.execute(text("SELECT id,v FROM ro_t ORDER BY id"))).all())
    await admin.dispose()
    # (3)
    print("== (3) statement_timeout")
    async with eng.connect() as c:
        t0 = time.monotonic()
        try:
            await c.execute(text("SELECT pg_sleep(7)"))
            print("NOT cancelled!")
        except DBAPIError as e:
            print(f"cancelled after {time.monotonic()-t0:.2f}s: {desc(e)}")
        await c.rollback()
        print("usable after rollback:", (await c.execute(text("SELECT 1"))).scalar(), "|", await shows(c))
    # also without rollback: txn is in failed state in SQLAlchemy? test via session
    async with eng.connect() as c:
        try:
            await c.execute(text("SELECT pg_sleep(7)"))
        except DBAPIError as e:
            pass
        try:
            await c.execute(text("SELECT 1"))
            print("same connection w/o rollback: works?!")
        except DBAPIError as e:
            print("same connection w/o rollback: ", desc(e))
        await c.rollback()
    # (4)
    print("== (4) settings persist")
    async with eng.connect() as c:
        print("initial     :", await shows(c))
        await c.commit()
        print("after commit:", await shows(c))
        await c.rollback()
        print("after rollbk:", await shows(c))
        await c.execute(text("SELECT 1"))
        await c.commit()
        print("2nd commit  :", await shows(c))
        # try RESET / SET LOCAL by a (hypothetical) tool: shows session can override -- expected to be possible!
        await c.rollback()
    # re-checkout from pool
    pids = set()
    for i in range(6):
        async with eng.connect() as c:
            pid = (await c.execute(text("SELECT pg_backend_pid()"))).scalar()
            pids.add(pid)
            s = await shows(c)
            await c.commit()
        print(f"checkout {i} pid={pid}: {s}")
    print("distinct backend pids over sequential checkouts:", pids)
    # pool_pre_ping + reset on return
    eng_pp = mk(pool_size=2, max_overflow=1, pool_pre_ping=True)
    async with eng_pp.connect() as c:
        print("pre_ping engine:", await shows(c))
    await eng_pp.dispose()
    # session API (what BotPrincipal tools would use)
    sm = async_sessionmaker(eng, expire_on_commit=False)
    async with sm() as s:
        try:
            await s.execute(text("INSERT INTO ro_t VALUES (9,'x')"))
        except DBAPIError as e:
            print("ORM Session INSERT:", desc(e))
        await s.rollback()
    # Can model/tool override read-only inside txn? (security-ish surprise)
    async with eng.connect() as c:
        try:
            await c.execute(text("SET TRANSACTION READ WRITE"))
            await c.execute(text("INSERT INTO ro_t VALUES (10,'override')"))
            print("SURPRISE: SET TRANSACTION READ WRITE allowed + INSERT worked")
        except DBAPIError as e:
            print("SET TRANSACTION READ WRITE then INSERT:", desc(e))
        await c.rollback()
    async with eng.connect() as c:
        try:
            await c.execute(text("SET default_transaction_read_only = off"))
            await c.execute(text("INSERT INTO ro_t VALUES (11,'override2')"))
            await c.commit()
            print("SURPRISE: SET default_transaction_read_only=off worked then INSERT committed; settings now:", await shows(c))
        except DBAPIError as e:
            print("SET default_transaction_read_only=off:", desc(e))
        await c.rollback()
    # cleanup possible side effects
    admin = create_async_engine(DSN, isolation_level="AUTOCOMMIT")
    async with admin.connect() as c:
        print("rows after override attempts:", (await c.execute(text("SELECT id,v FROM ro_t ORDER BY id"))).all())
        await c.execute(text("DELETE FROM ro_t WHERE id>2"))
    await admin.dispose()
    await eng.dispose()

    # (5) idle in transaction
    print("== (5) idle_in_transaction_session_timeout")
    eng5 = mk(pool_size=2, max_overflow=1)
    async with eng5.connect() as c:
        pid = (await c.execute(text("SELECT pg_backend_pid()"))).scalar()
        print("backend pid", pid, "txn begun (autobegin by SELECT); sleeping 17s in python")
        await asyncio.sleep(17)
        try:
            await c.execute(text("SELECT 1"))
            print("NOT killed")
        except Exception as e:
            print("after idle:", desc(e) if isinstance(e, DBAPIError) else repr(e))
            orig = getattr(e, "orig", None)
            print("   orig class mro:", [k.__name__ for k in type(orig).__mro__][:6] if orig else None)
            print("   is_disconnect flagged:", getattr(e, "connection_invalidated", None))
        try:
            await c.rollback()
            print("rollback after kill ok")
        except Exception as e:
            print("rollback after kill raised:", repr(e)[:200])
    # pool recovers?
    async with eng5.connect() as c:
        npid = (await c.execute(text("SELECT pg_backend_pid()"))).scalar()
        print("next checkout pid", npid, "(old", pid, ") works; ", await shows(c))
    await eng5.dispose()
    # same with pool_pre_ping=True: a connection that got killed while idle in pool (not in txn) isn't affected by idle_in_tx.
    print("== (5b) idle in txn in pool? connection returned to pool is rolled back so no idle-in-tx")
    eng5b = mk(pool_size=1, max_overflow=0, pool_pre_ping=True)
    async with eng5b.connect() as c:
        await c.execute(text("SELECT 1"))
    await asyncio.sleep(17)
    async with eng5b.connect() as c:
        print("after 17s idle in pool:", (await c.execute(text("SELECT pg_backend_pid()"))).scalar(), await shows(c))
    await eng5b.dispose()

asyncio.run(main())
