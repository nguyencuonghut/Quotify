import asyncio, sys, os, time
from arq import create_pool
from arq.connections import RedisSettings
from client import log, RHOST
S = "/s0/"
def touch(n): open(S + "f_" + n, "w").close()
async def waitfile(n):
    while not os.path.exists(S + "f_" + n): await asyncio.sleep(0.05)
async def timed(label, coro, limit):
    t = time.time()
    try:
        r = await asyncio.wait_for(coro, limit)
        log(f"{label}: returned {r!r} after {time.time()-t:.2f}s")
    except BaseException as e:
        log(f"{label}: raised {type(e).__module__}.{type(e).__name__} {str(e)[:80]!r} after {time.time()-t:.2f}s")
def pstate(p):
    cp = p.connection_pool
    return f"in_use={len(cp._in_use_connections)} available={len(cp._available_connections)}"
async def main():
    p = await create_pool(RedisSettings(host=RHOST))
    await timed("warm enqueue w1", p.enqueue_job("quick", "w1", _job_id="w1"), 2)
    log("pool:", pstate(p))
    touch("ready"); await waitfile("paused"); log("---- redis PAUSED ----")
    await timed("A1 enqueue_job w2 inside wait_for(2)", p.enqueue_job("quick", "w2", _job_id="w2"), 2)
    log("pool:", pstate(p))
    await timed("A2 ping inside wait_for(2)", p.ping(), 2)
    await timed("A3 enqueue_job w3 inside wait_for(2)", p.enqueue_job("quick", "w3", _job_id="w3"), 2)
    await timed("A4 enqueue_job w4 inside wait_for(2)", p.enqueue_job("quick", "w4", _job_id="w4"), 2)
    log("pool after 4 timeouts:", pstate(p))
    await timed("B1 NEW create_pool (defaults) inside wait_for(8)", create_pool(RedisSettings(host=RHOST)), 8)
    await timed("B2 NEW create_pool inside wait_for(2)", create_pool(RedisSettings(host=RHOST)), 2)
    # raw: does the bare enqueue (no wait_for) ever return? cap at 6s using a task we cancel ourselves
    touch("stage1"); await waitfile("unpaused"); log("---- redis UNPAUSED ----")
    await timed("C1 ping on SAME pool", p.ping(), 5)
    await timed("C2 enqueue_job w5 on SAME pool", p.enqueue_job("quick", "w5", _job_id="w5"), 5)
    bad = 0
    for i in range(30):
        await p.set(f"k{i}", f"v{i}"); v = await p.get(f"k{i}")
        if v != f"v{i}".encode(): bad += 1; log(f"DESYNC at i={i}: get returned {v!r}")
    log(f"C3 30 set/get round trips on same pool: mismatches={bad}")
    for n in ("w1","w2","w3","w4","w5"):
        log(f"job key {n} exists in redis: {await p.exists('arq:job:'+n)}")
    log("zset arq:queue:", [x.decode() for x in await p.zrange("arq:queue", 0, -1)])
    log("pool:", pstate(p))
    await p.aclose()
asyncio.run(main())
