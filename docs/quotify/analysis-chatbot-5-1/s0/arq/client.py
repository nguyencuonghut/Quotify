"""helper lib for client scripts"""
import asyncio, time, os
from arq import create_pool
from arq.connections import RedisSettings
RHOST = os.environ.get("RHOST", "s0-arq-redis")
def log(*a): print(f"{time.time():.3f} CLI", *a, flush=True)
async def pool(queue=None, **kw):
    return await create_pool(RedisSettings(host=RHOST, **kw), **({"default_queue_name": queue} if queue else {}))
async def keys(p, pat="*"):
    ks = sorted(k.decode() for k in await p.keys(pat))
    return ks
