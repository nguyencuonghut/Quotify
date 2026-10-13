import asyncio, sys
from client import *
async def main():
    p = await pool()
    await p.flushall()
    log("== E1a: two enqueues of bot:1 while queued (no worker)")
    j1 = await p.enqueue_job("slow", "a", 3, _job_id="bot:1")
    j2 = await p.enqueue_job("slow", "a", 3, _job_id="bot:1")
    log("first:", j1, " second:", j2)
    log("keys:", await keys(p))
    await p.aclose()
asyncio.run(main())
