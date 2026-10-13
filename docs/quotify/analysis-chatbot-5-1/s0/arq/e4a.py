import asyncio, sys, os
from client import *
async def main():
    p = await pool()
    j = await p.enqueue_job(os.environ.get("FN","slow_cleanup"), "term", float(os.environ.get("SLEEP","60")), _job_id="bot:9")
    log("enqueue bot:9 ->", j)
    while not await p.exists("arq:in-progress:bot:9"):
        await asyncio.sleep(0.05)
    log("RUNNING")
    await p.aclose()
asyncio.run(main())
