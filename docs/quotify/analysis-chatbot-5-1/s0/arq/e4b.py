import asyncio, sys, os
from client import *
async def main():
    p = await pool()
    log("keys after worker exit:", await keys(p))
    log(f"job-pttl={await p.pttl('arq:job:bot:9')} inprog-pttl={await p.pttl('arq:in-progress:bot:9')} retry={await p.get('arq:retry:bot:9')} queue={await p.zrange('arq:queue',0,-1)}")
    j = await p.enqueue_job("quick", "probe", _job_id="bot:9")
    log("same-id enqueue right after worker exit (no worker running) ->", j)
    await p.aclose()
asyncio.run(main())
