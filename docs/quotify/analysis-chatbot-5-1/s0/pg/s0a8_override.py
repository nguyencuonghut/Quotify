import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from common import DSN
SS = {"default_transaction_read_only": "on", "statement_timeout": "5000", "idle_in_transaction_session_timeout": "15000"}
async def main():
    ro = create_async_engine(DSN, connect_args={"server_settings": SS}, pool_size=1, max_overflow=0)
    async with ro.connect() as c:
        await c.execute(text("SET default_transaction_read_only = off"))
        await c.commit()
        await c.execute(text("INSERT INTO ro_t VALUES (201,'escaped')"))
        await c.commit()
        print("INSERT committed through 'read-only' engine after SET ... off; commit")
    async with ro.connect() as c:
        print("next checkout default_ro =", (await c.execute(text("SHOW default_transaction_read_only"))).scalar(), "(setting leaked into pool)")
        await c.execute(text("SET statement_timeout = 0")); await c.commit()
    async with ro.connect() as c:
        print("statement_timeout =", (await c.execute(text("SHOW statement_timeout"))).scalar())
        await c.execute(text("DELETE FROM ro_t WHERE id=201")); await c.commit()
    await ro.dispose()
asyncio.run(main())
