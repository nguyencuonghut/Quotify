import asyncio, sys, os
from client import *
DUR = float(os.environ.get("DUR", "40"))
async def status(p, tag):
    log(f"[{tag}] job-pttl={await p.pttl('arq:job:bot:7')}ms inprog-pttl={await p.pttl('arq:in-progress:bot:7')}ms "
        f"retry={await p.get('arq:retry:bot:7')} result-exists={await p.exists('arq:result:bot:7')} "
        f"queue={[ (k.decode()) for k in await p.zrange('arq:queue',0,-1)]}")
async def main():
    p = await pool()
    j = await p.enqueue_job("slow", "orphan", 60, _job_id="bot:7")
    log("enqueue bot:7 ->", j)
    while not await p.exists("arq:in-progress:bot:7"):
        await asyncio.sleep(0.05)
    log("RUNNING")
    t0 = time.time(); last = 0; first_ok = None
    while time.time() - t0 < DUR:
        j = await p.enqueue_job("quick", "probe", _job_id="bot:7")
        if j is not None:
            first_ok = time.time(); log("PROBE bot:7 -> NON-NONE (enqueued)", j); break
        if time.time() - last > 4:
            last = time.time(); await status(p, "poll")
        await asyncio.sleep(0.25)
    if first_ok is None: log(f"PROBE bot:7 still None after {DUR}s"); await status(p, "final")
    await asyncio.sleep(3)
    log("keys at end:", await keys(p))
    await p.aclose()
asyncio.run(main())
