import asyncio, sys
from client import *
async def main():
    p = await pool()
    j = await p.enqueue_job("slow", "k", 1, _job_id="bot:1")
    log("enqueued", j)
    await asyncio.sleep(2.5)
    log("keys after finish (keep_result=3600):", await keys(p))
    log("result key ttl(s):", await p.ttl("arq:result:bot:1"))
    j = await p.enqueue_job("quick", "again", _job_id="bot:1")
    log("re-enqueue immediately after finish ->", j)
    j = await p.enqueue_job("quick", "other", _job_id="bot:2")
    log("different id bot:2 ->", j)
    # failing job w/ keep_result=3600 too
    await asyncio.sleep(1.5)
    log("keys:", await keys(p))
    await p.aclose()
asyncio.run(main())
