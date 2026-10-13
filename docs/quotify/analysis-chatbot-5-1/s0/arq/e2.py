import asyncio, sys
from client import *
async def main():
    p = await pool()
    for n in (101, 102, 103):
        j = await p.enqueue_job("slow", f"chatA-u{n}", 3, _job_id=f"bot:{n}")
        log(f"enqueue bot:{n} ->", j)
    j = await p.enqueue_job("slow", "chatA-dup", 3, _job_id="bot:102"); log("dup bot:102 ->", j)
    await asyncio.sleep(8)
    log("keys:", await keys(p))
    await p.aclose()
asyncio.run(main())
