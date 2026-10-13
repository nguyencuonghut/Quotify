"""Configurable arq worker module for S0(b). Config via env."""
import asyncio, os, sys, time
from arq.connections import RedisSettings

def log(*a):
    print(f"{time.time():.3f} APP", *a, flush=True)

E = os.environ
RHOST = E.get("RHOST", "s0-arq-redis")

async def slow(ctx, tag, seconds):
    log(f"START {tag} try={ctx['job_try']} sleep={seconds}")
    await asyncio.sleep(seconds)
    log(f"END {tag}")
    return f"done-{tag}"

async def slow_cleanup(ctx, tag, seconds):
    """simulates KT18: DB lease release on cancel, shielded"""
    log(f"START {tag} try={ctx['job_try']} sleep={seconds}")
    async def release():
        log(f"CLEANUP begin {tag}")
        await asyncio.sleep(1.0)   # stands in for a DB UPDATE
        log(f"CLEANUP done {tag}")
    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        log(f"GOT CancelledError {tag}")
        await asyncio.shield(release())
        log(f"re-raising {tag}")
        raise
    log(f"END {tag}")
    return f"done-{tag}"

async def quick(ctx, tag):
    log(f"QUICK {tag} try={ctx['job_try']}")
    return tag

async def boom(ctx, tag):
    log(f"BOOM {tag}")
    raise ValueError("x")

async def startup(ctx):
    log("worker on_startup")
async def shutdown(ctx):
    log("worker on_shutdown")

class WorkerSettings:
    functions = [slow, slow_cleanup, quick, boom]
    redis_settings = RedisSettings(host=RHOST)
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = int(E.get("MAX_JOBS", "10"))
    job_timeout = int(E.get("JOB_TIMEOUT", "300"))
    max_tries = int(E.get("MAX_TRIES", "5"))
    keep_result = int(E.get("KEEP_RESULT", "3600"))
    health_check_interval = int(E.get("HC_INTERVAL", "3600"))
    job_completion_wait = int(E.get("JCW", "0"))
    retry_jobs = E.get("RETRY_JOBS", "1") == "1"
    poll_delay = float(E.get("POLL_DELAY", "0.5"))
    if E.get("QUEUE"):
        queue_name = E["QUEUE"]

# inheritance test class
class Child(WorkerSettings):
    pass
