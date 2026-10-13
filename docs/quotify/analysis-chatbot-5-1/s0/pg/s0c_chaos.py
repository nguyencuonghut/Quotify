"""Chaos: short lease (40ms) + random hold (0-90ms) so leases expire under live workers -> takeovers race with stale completes.
Invariants: every row gets exactly ONE successful fenced complete; no row is claimed after a successful complete;
attempts strictly increase per row; all rows end 'replied'."""
import asyncio, random, sys, time, multiprocessing as mp
from collections import defaultdict
from datetime import datetime
from claimlib import *

LEASE, HOLD_MAX, ROUNDS_TIMEOUT = 0.040, 0.090, 20.0

async def worker(rank, rounds, barrier, variant, kw):
    engine = mk_engine(pool_size=3, max_overflow=2); ev = []
    loop = asyncio.get_running_loop()
    async def wait(): await loop.run_in_executor(None, lambda: barrier.wait(120))
    try:
        for r in range(rounds):
            chat = 300000 + r; ids = [r * 10 + i for i in range(1, 6)]
            if rank == 0: await insert_rows(engine, chat, ids)
            await wait()
            t_start = time.monotonic()
            while True:
                ts = time.monotonic()
                res = await claim(engine, variant, chat, datetime.now(UTC), lease_s=LEASE, max_attempts=10_000, **kw)
                c = res.claimed
                if c:
                    tc = time.monotonic()
                    await asyncio.sleep(random.uniform(0, HOLD_MAX))
                    rc = await complete(engine, c.update_id, c.attempts, datetime.now(UTC))
                    ev.append((r, c.update_id, c.attempts, rank, ts, tc, time.monotonic(), rc))
                else:
                    async with engine.connect() as conn:
                        done = (await conn.execute(text("SELECT count(*) FROM bot_updates WHERE chat_id=:c AND status='replied'"), {"c": chat})).scalar()
                    if done >= 5: break
                    if time.monotonic() - t_start > ROUNDS_TIMEOUT: ev.append((r, -1, -1, rank, 0, 0, 0, -1)); break
                    await asyncio.sleep(0.002)
            await wait()
    finally:
        await engine.dispose()
    return ev

def proc(rank, rounds, barrier, variant, kw, q):
    q.put(asyncio.run(worker(rank, rounds, barrier, variant, kw)))

if __name__ == "__main__":
    K, rounds, variant = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    kw = eval(sys.argv[4]) if len(sys.argv) > 4 else {}
    async def _r():
        e = mk_engine(); await reset_table(e); await e.dispose()
    asyncio.run(_r())
    ctx = mp.get_context("spawn"); b = ctx.Barrier(K); q = ctx.Queue()
    ps = [ctx.Process(target=proc, args=(i, rounds, b, variant, kw, q)) for i in range(K)]
    for p in ps: p.start()
    ev = [e for _ in ps for e in q.get(timeout=900)]
    for p in ps: p.join()
    by = defaultdict(list)
    for e in ev: by[(e[0], e[1])].append(e)
    viol = defaultdict(int); takeovers = 0; stale_rc0 = 0; timeouts = 0
    for (r, uid), es in by.items():
        if uid == -1: timeouts += 1; continue
        es.sort(key=lambda e: e[4])
        wins = [e for e in es if e[7] == 1]
        if len(wins) != 1: viol["row_not_completed_exactly_once"] += 1
        if wins and any(e[4] > wins[0][6] for e in es): viol["claimed_after_successful_complete(revival)"] += 1
        att = sorted(e[2] for e in es)
        if att != list(range(1, len(es) + 1)): viol["attempts_not_1..n"] += 1
        takeovers += len(es) - 1; stale_rc0 += sum(1 for e in es if e[7] == 0)
    rows = sum(1 for k in by if k[1] != -1)
    print(f"{'PASS' if not viol and not timeouts else 'FAIL'} chaos variant={variant} kw={kw} K={K} rounds={rounds} rows={rows} claims={len([e for e in ev if e[1]!=-1])} "
          f"takeovers(attempts>1)={takeovers} stale_complete_rc0={stale_rc0} timeouts={timeouts} violations={dict(viol)}")
