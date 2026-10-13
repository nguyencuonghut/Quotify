import asyncio, sys, os
from client import *
async def main():
    pb = await pool(queue="quotify:bot")
    js = []
    for n in range(1, 51):
        js.append(await pb.enqueue_job("quick", f"u{n}", _job_id=f"bot:{n}"))
    for n in range(51, 56):
        js.append(await pb.enqueue_job("boom", f"u{n}", _job_id=f"bot:{n}"))
    log("enqueued", sum(j is not None for j in js), "jobs; keys now:", len(await keys(pb)))
    await asyncio.sleep(5)
    ks = await keys(pb)
    log("keys after run:", ks)
    log("result keys:", [k for k in ks if "result" in k], " job keys:", [k for k in ks if ":job:" in k], " retry:", [k for k in ks if "retry" in k], " in-progress:", [k for k in ks if "in-progress" in k])
    log("zcard quotify:bot =", await pb.zcard("quotify:bot"))
    j = await pb.enqueue_job("quick", "reuse", _job_id="bot:55")
    log("reuse id of failed job bot:55 ->", j)
    await pb.aclose()
asyncio.run(main())
