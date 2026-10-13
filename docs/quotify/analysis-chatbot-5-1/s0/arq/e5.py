import asyncio, sys, os
from client import *
async def main():
    pd = await pool()                       # default pool
    pb = await pool(queue="quotify:bot")    # pool whose default queue is the bot queue
    log("default_queue_name of pb:", pb.default_queue_name)
    r = []
    r.append(("D1 default pool, no _queue_name", await pd.enqueue_job("quick", "D1", _job_id="d1")))
    r.append(("B1 default pool, _queue_name=quotify:bot", await pd.enqueue_job("quick", "B1", _job_id="b1", _queue_name="quotify:bot")))
    r.append(("B2 pb pool (default_queue_name=quotify:bot), no _queue_name", await pb.enqueue_job("quick", "B2", _job_id="b2")))
    r.append(("D2 pb pool, _queue_name=arq:queue", await pb.enqueue_job("quick", "D2", _job_id="d2", _queue_name="arq:queue")))
    for k, v in r: log(k, "->", v)
    log("zsets:", {q: [x.decode() for x in await pd.zrange(q, 0, -1)] for q in ("arq:queue", "quotify:bot")})
    await asyncio.sleep(3)
    log("after 3s zsets:", {q: [x.decode() for x in await pd.zrange(q, 0, -1)] for q in ("arq:queue", "quotify:bot")})
    log("keys:", await keys(pd))
    await pd.aclose(); await pb.aclose()
asyncio.run(main())
