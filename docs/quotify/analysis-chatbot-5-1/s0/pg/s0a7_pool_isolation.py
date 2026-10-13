import asyncio, time
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from common import DSN

SS = {"default_transaction_read_only": "on", "statement_timeout": "5000", "idle_in_transaction_session_timeout": "15000"}

async def main():
    ro = create_async_engine(DSN, connect_args={"server_settings": SS}, pool_size=2, max_overflow=1, pool_timeout=2)
    main_e = create_async_engine(DSN, pool_size=5, max_overflow=10)
    held = []
    for i in range(3):
        c = await ro.connect()
        pid = (await c.execute(text("SELECT pg_backend_pid()"))).scalar()
        held.append(c); print(f"ro conn {i} held pid={pid}")
    print("ro pool status:", ro.pool.status())
    t0 = time.monotonic()
    try:
        c4 = await ro.connect()
        print("UNEXPECTED: 4th ro connection granted")
    except Exception as e:
        print(f"4th ro checkout failed after {time.monotonic()-t0:.2f}s: {type(e).__name__}: {str(e)[:110]}")
    # main engine unaffected
    t0 = time.monotonic()
    async with main_e.connect() as m:
        r = (await m.execute(text("SELECT pg_backend_pid(), current_setting('default_transaction_read_only')"))).one()
        print(f"main engine served in {time.monotonic()-t0:.3f}s pid={r[0]} default_ro={r[1]}; main pool: {main_e.pool.status()}")
    # reverse: exhaust main pool partially? exhaust fully then ro serves?
    mains = [await main_e.connect() for _ in range(15)]
    for m in mains: await m.execute(text("SELECT 1"))
    print("main pool exhausted:", main_e.pool.status())
    for c in held: await c.close()
    async with ro.connect() as c:
        print("ro served while main exhausted:", (await c.execute(text("SELECT 1"))).scalar())
    # backend connections used
    async with ro.connect() as c:
        pass
    adm = create_async_engine(DSN, isolation_level="AUTOCOMMIT")
    async with adm.connect() as c:
        print("pg_stat_activity for db s0:", (await c.execute(text("select count(*) from pg_stat_activity where datname='s0'"))).scalar())
    for m in mains: await m.close()
    await ro.dispose(); await main_e.dispose(); await adm.dispose()

asyncio.run(main())
