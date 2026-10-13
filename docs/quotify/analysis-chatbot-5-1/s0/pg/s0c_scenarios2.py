"""(4) contrast skip-ahead, revival of a finished row (unguarded TAKE), (7) per-chat advisory lock parallelism."""
import asyncio, time
from datetime import datetime, timedelta
from claimlib import *

T0 = datetime(2026, 10, 13, 3, 0, 0, tzinfo=UTC)
res = []
def check(name, cond, detail=""):
    res.append(bool(cond)); print(f"[{'PASS' if cond else 'FAIL'}] {name}  {detail}")

async def main():
    e = mk_engine()
    print("=== (4) contrast: claiming the next *due* row instead of the head row skips ahead")
    await reset_table(e); chat = 20
    await insert_rows(e, chat, [1, 2, 3])
    await claim(e, "plan", chat, T0); await requeue(e, 1, 1, T0 + timedelta(seconds=5))
    r = await claim(e, "due_filter", chat, T0 + timedelta(seconds=2))
    print(f"    due_filter during row1 backoff claims: {r.claimed}  -> {'SKIPS AHEAD (broken)' if r.claimed and r.claimed.update_id==2 else 'no skip'}")
    check("(4/6) due_filter variant is broken (claims row 2 while row 1 is in backoff)", r.claimed is not None and r.claimed.update_id == 2)

    print("=== stale-select race: HEAD read, finished row completed by stale worker, then TAKE")
    for guarded in (True, False):
        await reset_table(e); chat = 21
        await insert_rows(e, chat, [1, 2])
        a = (await claim(e, "plan", chat, T0)).claimed        # A attempts=1
        late = T0 + timedelta(seconds=300)                        # A's lease expired, A still running
        async def claimer_B():
            return await claim(e, "plan", chat, late, guarded_take=guarded, sleep_between_head_and_take=0.5, retake_on_miss=False)
        tb = asyncio.create_task(claimer_B())
        await asyncio.sleep(0.2)                                  # B has read HEAD=row1 (processing, expired)
        rc = await complete(e, 1, 1, late)                        # stale A completes concurrently (fenced rowcount 1, attempts still 1)
        rb = await tb
        row1 = await fetch(e, 1)
        print(f"    guarded_take={guarded}: A.complete rc={rc}; B claimed={rb.claimed}; row1 now status={row1.status} attempts={row1.attempts}")
        if guarded:
            check("guarded TAKE: finished row not revived (B claim returns nothing)", row1.status == "replied" and rb.claimed is None)
            # with retake_on_miss, B re-evaluates and takes row 2
            await reset_table(e); await insert_rows(e, chat, [1, 2])
            a = (await claim(e, "plan", chat, T0)).claimed
            tb = asyncio.create_task(claim(e, "plan", chat, late, sleep_between_head_and_take=0.5, retake_on_miss=True))
            await asyncio.sleep(0.2); await complete(e, 1, 1, late); rb = await tb
            check("guarded TAKE + loop-back on miss: B claims row 2 in the same call", rb.claimed is not None and rb.claimed.update_id == 2, str(rb.claimed))
        else:
            check("UNGUARDED TAKE revives the completed row (broken, as predicted)", row1.status == "processing" and rb.claimed is not None and rb.claimed.update_id == 1 and row1.attempts == 2)

    print("=== (7) different chats do not block each other (advisory lock per chat)")
    await reset_table(e)
    for c_ in (31, 32):
        await insert_rows(e, c_, [c_ * 10 + 1])
    holder_started = asyncio.Event(); release = asyncio.Event()
    async def holder():
        async with e.connect() as c:
            await c.execute(SQL_LOCK, {"chat_id": 31})
            holder_started.set()
            await release.wait()
            await c.commit()
    th = asyncio.create_task(holder())
    await holder_started.wait()
    t = time.monotonic(); r2 = await claim(e, "plan", 32, datetime.now(UTC)); dt2 = time.monotonic() - t
    check("(7) chat 32 claim completes while chat 31's lock is held", r2.claimed is not None and dt2 < 0.5, f"{dt2*1000:.1f} ms")
    t = time.monotonic()
    t31 = asyncio.create_task(claim(e, "plan", 31, datetime.now(UTC)))
    await asyncio.sleep(1.0)
    still_blocked = not t31.done()
    release.set(); await th
    r31 = await t31; dt31 = time.monotonic() - t
    check("(7) same-chat claim blocks until holder commits, then succeeds", still_blocked and r31.claimed is not None and dt31 >= 1.0, f"blocked {dt31:.2f}s")
    # throughput: 500 chats claim concurrently
    await reset_table(e)
    for c_ in range(500):
        await insert_rows(e, 5000 + c_, [100000 + c_])
    sem = asyncio.Semaphore(12)
    async def one(c_):
        async with sem:
            return await claim(e, "plan", 5000 + c_, datetime.now(UTC))
    t = time.monotonic(); rs = await asyncio.gather(*[one(c_) for c_ in range(500)]); dt = time.monotonic() - t
    check("(7) 500 chats claimed concurrently (12 in flight), all got their row", all(r.claimed for r in rs), f"{dt:.2f}s total")
    # hash collisions
    async with e.connect() as c:
        d, n = (await c.execute(text("select count(distinct hashtextextended('bot:chat:'||g,0)), count(*) from generate_series(1,2000000) g"))).one()
        print(f"    hashtextextended('bot:chat:'||chat_id,0): {d} distinct keys for {n} chat ids")
        check("(7) no 64-bit key collisions in 2M chat ids", d == n)
    print(f"TOTAL {len(res)} checks, failed={res.count(False)}")
    await e.dispose()
asyncio.run(main())
