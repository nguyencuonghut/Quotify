import asyncio
from client import *
async def main():
    p = await pool()
    await p.enqueue_job("slow_cleanup", "tmo", 20, _job_id="bot:30")
    await asyncio.sleep(8)
    log("keys:", await keys(p)); log("reuse id ->", await p.enqueue_job("quick", "x", _job_id="bot:30"))
    await p.aclose()
asyncio.run(main())
