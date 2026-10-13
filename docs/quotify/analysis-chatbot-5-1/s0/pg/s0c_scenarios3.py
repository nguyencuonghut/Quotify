"""Stale-HEAD races: A (stale owner) completes / requeues between B's HEAD read and B's TAKE; plain HEAD vs HEAD ... FOR UPDATE."""
import asyncio
from datetime import datetime, timedelta
from claimlib import *
T0 = datetime(2026, 10, 13, 3, 0, 0, tzinfo=UTC); late = T0 + timedelta(seconds=300)
async def run(e, action, **kw):
    await reset_table(e); chat = 40
    await insert_rows(e, chat, [1, 2])
    await claim(e, "plan", chat, T0)                       # A attempts=1, lease expired at `late`
    tb = asyncio.create_task(claim(e, "plan", chat, late, sleep_between_head_and_take=0.5, retake_on_miss=True, **kw))
    await asyncio.sleep(0.2)
    if action == "complete":
        ta = asyncio.create_task(complete(e, 1, 1, late))
    else:
        ta = asyncio.create_task(requeue(e, 1, 1, late + timedelta(seconds=30)))
    await asyncio.sleep(0.1)
    ta_done_early = ta.done()
    rb = await tb; rc = await ta
    row1 = await fetch(e, 1)
    return rb.claimed, rc, ta_done_early, row1
async def main():
    e = mk_engine()
    for fu in (False, True):
        for action in ("complete", "requeue"):
            claimed, rc, early, row1 = await run(e, action, head_for_update=fu)
            print(f"head_for_update={fu!s:5} A.{action:8}: A_rc={rc} (A finished before B's TAKE: {early}) B.claimed={claimed and (claimed.update_id, claimed.attempts)} row1={row1.status}/attempts={row1.attempts}/lease={row1.lease_until and row1.lease_until.isoformat()}")
    await e.dispose()
asyncio.run(main())
