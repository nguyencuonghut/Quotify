import asyncio
from datetime import datetime, timezone
from claimlib import *
async def main():
    e = mk_engine()
    await reset_table(e)
    await insert_rows(e, 1, [1,2,3])
    now = datetime.now(UTC)
    r = await claim(e, "plan", 1, now)
    print(r)
    r = await claim(e, "plan", 1, now)
    print(r)
    print(await complete(e, 1, 1, now))
    print(await claim(e, "plan", 1, now))
    await e.dispose()
asyncio.run(main())
