import asyncio, sys, os, time
from arq import create_pool
from arq.connections import RedisSettings
from client import log
async def attempt(label, host, wait=None, **kw):
    t = time.time()
    try:
        coro = create_pool(RedisSettings(host=host, **kw))
        p = await (asyncio.wait_for(coro, wait) if wait else coro)
        log(f"{label}: OK after {time.time()-t:.2f}s"); await p.aclose()
    except BaseException as e:
        log(f"{label}: raised {type(e).__module__}.{type(e).__name__}: {str(e)[:90]!r} after {time.time()-t:.2f}s")
async def main():
    a = sys.argv[1]
    if a == "down-dns":
        await attempt("A  redis container STOPPED (DNS name gone), defaults retries=5 delay=1 timeout=1", "s0-arq-redis")
        await attempt("A2 same, conn_retries=0", "s0-arq-redis", conn_retries=0)
        await attempt("A3 same, conn_retries=2 conn_retry_delay=0.5", "s0-arq-redis", conn_retries=2, conn_retry_delay=0.5)
        await attempt("A4 same, defaults inside asyncio.wait_for(2)", "s0-arq-redis", wait=2)
        await attempt("B  host up, port closed (ECONNREFUSED), defaults", "s0-arq-client")
        await attempt("B2 host up, port closed, conn_retries=0", "s0-arq-client", conn_retries=0)
        await attempt("C  black-hole IP (no host answers), defaults", sys.argv[2])
        await attempt("C2 black-hole IP, conn_retries=0 conn_timeout=1", sys.argv[2], conn_retries=0)
        await attempt("C3 black-hole IP, defaults inside wait_for(2)", sys.argv[2], wait=2)
asyncio.run(main())
