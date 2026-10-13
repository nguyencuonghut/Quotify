import asyncio, sys
from client import *
async def main():
    p = await pool()
    log("keys before:", await keys(p))
    log("== while RUNNING (worker started, job sleeping 4s): enqueue same id")
    await asyncio.sleep(1.5)
    log("keys during run:", await keys(p))
    j = await p.enqueue_job("slow", "a", 3, _job_id="bot:1")
    log("enqueue while running ->", j)
    # wait for finish
    t0 = time.time()
    while await p.exists("arq:job:bot:1"):
        await asyncio.sleep(0.05)
    log(f"job key gone after {time.time()-t0:.2f}s from here")
    log("keys after finish:", await keys(p))
    t = time.time()
    j = await p.enqueue_job("quick", "again", _job_id="bot:1")
    log(f"re-enqueue immediately after finish ({time.time()-t:.3f}s) ->", j)
    await asyncio.sleep(1.5)
    log("keys after 2nd run:", await keys(p))
    await p.aclose()
asyncio.run(main())
