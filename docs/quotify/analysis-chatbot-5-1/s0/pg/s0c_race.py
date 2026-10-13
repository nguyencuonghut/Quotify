"""S0(c)(1)/(6): racing claimers. modes: async (tasks, own connection each) | mp (OS processes).
usage: s0c_race.py MODE VARIANT K ROUNDS [shuffle]"""
import asyncio, random, sys, time, multiprocessing as mp
from collections import Counter, defaultdict
from datetime import datetime, timezone
from claimlib import *

HOLD_MAX = 0.004
ROUND_TIMEOUT = 10.0

class AsyncSync:
    def __init__(self, k): self.b = asyncio.Barrier(k)
    async def wait(self, tag=''): await self.b.wait()

class MPSync:
    def __init__(self, barrier): self.b = barrier
    async def wait(self, tag=""):
        import threading, traceback
        try:
            await asyncio.get_running_loop().run_in_executor(None, lambda: self.b.wait(60))
        except threading.BrokenBarrierError:
            import os
            print(f"BARRIER BROKEN pid={os.getpid()} tag={tag}", flush=True)
            e = mk_engine()
            async with e.connect() as c:
                rows = (await c.execute(text("select pid,state,wait_event_type,wait_event,left(query,60),now()-state_change from pg_stat_activity where datname='s0' and pid<>pg_backend_pid()"))).all()
            for r in rows: print("   ", tuple(r), flush=True)
            await e.dispose()
            raise

async def producer(engine, chat, ids, shuffle):
    order = list(ids)
    if shuffle:
        random.shuffle(order)
    for i in order:
        await insert_rows(engine, chat, [i])
        if shuffle:
            await asyncio.sleep(random.uniform(0, 0.003))

async def drain(engine, variant, rank, chat, events, rnd):
    t_start = time.monotonic()
    while True:
        now = datetime.now(UTC)
        res = await claim(engine, variant, chat, now, lease_s=240, max_attempts=50)
        c = res.claimed
        if c:
            t0 = time.monotonic()
            await asyncio.sleep(random.uniform(0, HOLD_MAX))
            t1 = time.monotonic()
            rc = await complete(engine, c.update_id, c.attempts, datetime.now(UTC))
            events.append((rnd, chat, c.update_id, c.attempts, rank, t0, t1, c.live_count_in_txn, rc))
        else:
            async with engine.connect() as conn:
                done = (await conn.execute(text("SELECT count(*) FROM bot_updates WHERE chat_id=:c AND status='replied'"), {"c": chat})).scalar()
            if done >= 5:
                return True
            if time.monotonic() - t_start > ROUND_TIMEOUT:
                return False
            await asyncio.sleep(0.0005)

async def worker(rank, K, rounds, variant, sync, shuffle, chat_base=100000):
    engine = mk_engine(pool_size=3, max_overflow=2)
    events, timeouts = [], 0
    try:
        for r in range(rounds):
            chat = chat_base + r
            ids = [r * 10 + i for i in range(1, 6)]
            prod = None
            if rank == 0:
                if shuffle:
                    prod = asyncio.create_task(producer(engine, chat, ids, True))
                else:
                    await producer(engine, chat, ids, False)
            await sync.wait(f'before-drain r={r} rank={rank}')
            ok = await drain(engine, variant, rank, chat, events, r)
            if not ok: timeouts += 1
            if prod: await prod
            await sync.wait(f'after-drain r={r} rank={rank} ok={ok}')
    finally:
        await engine.dispose()
    return events, timeouts

def proc_main(rank, K, rounds, variant, barrier, shuffle, q):
    ev, to = asyncio.run(worker(rank, K, rounds, variant, MPSync(barrier), shuffle))
    q.put((ev, to))

def analyse(events, rounds, shuffle):
    by_round = defaultdict(list)
    for e in events: by_round[e[0]].append(e)
    viol = Counter()
    rounds_bad = set()
    for r in range(rounds):
        ev = sorted(by_round.get(r, []), key=lambda e: e[5])
        expected = [r * 10 + i for i in range(1, 6)]
        got = [e[2] for e in ev]
        bad = False
        if sorted(got) != expected:
            viol["claim_multiplicity(not each row exactly once)"] += 1; bad = True
        if not shuffle and got != expected:
            viol["order(not ascending update_id)"] += 1; bad = True
        if any(e[3] != 1 for e in ev):
            viol["attempts!=1"] += 1; bad = True
        if any(e[7] != 1 for e in ev):
            viol["live_processing_rows_in_claim_txn!=1"] += 1; bad = True
        # overlap of [t0,t1] intervals of different claims in same chat
        ov = any(ev[i + 1][5] < max(x[6] for x in ev[: i + 1]) for i in range(len(ev) - 1))
        if ov:
            viol["overlap(two rows held concurrently)"] += 1; bad = True
        if any(e[8] != 1 for e in ev):
            viol["complete_rowcount!=1"] += 1; bad = True
        if bad: rounds_bad.add(r)
    return viol, rounds_bad

async def run_async(variant, K, rounds, shuffle):
    e = mk_engine(); await reset_table(e); await e.dispose()
    sync = AsyncSync(K)
    out = await asyncio.gather(*[worker(i, K, rounds, variant, sync, shuffle) for i in range(K)])
    return out

def run_mp(variant, K, rounds, shuffle):
    async def _r():
        e = mk_engine(); await reset_table(e); await e.dispose()
    asyncio.run(_r())
    ctx = mp.get_context("spawn")
    barrier = ctx.Barrier(K); q = ctx.Queue()
    ps = [ctx.Process(target=proc_main, args=(i, K, rounds, variant, barrier, shuffle, q)) for i in range(K)]
    for p in ps: p.start()
    out = [q.get(timeout=600) for _ in ps]
    for p in ps: p.join()
    return out

if __name__ == "__main__":
    mode, variant, K, rounds = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    shuffle = len(sys.argv) > 5 and sys.argv[5] == "shuffle"
    t = time.monotonic()
    out = asyncio.run(run_async(variant, K, rounds, shuffle)) if mode == "async" else run_mp(variant, K, rounds, shuffle)
    events = [e for ev, _ in out for e in ev]; timeouts = sum(to for _, to in out)
    viol, bad = analyse(events, rounds, shuffle)
    per_worker = Counter(e[4] for e in events)
    status = "PASS" if not viol and timeouts == 0 else "FAIL"
    print(f"{status} mode={mode} variant={variant} K={K} rounds={rounds} shuffle={shuffle} claims={len(events)} "
          f"rounds_with_violation={len(bad)} timeouts={timeouts} claims_per_worker={dict(sorted(per_worker.items()))} "
          f"elapsed={time.monotonic()-t:.1f}s violations={dict(viol)}")
