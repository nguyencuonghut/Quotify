"""Deterministic scenarios (2)-(5) of S0(c) + contrast (6) for out-of-order, using controlled `now`."""
import asyncio, sys
from datetime import datetime, timedelta, timezone
from claimlib import *

T0 = datetime(2026, 10, 13, 3, 0, 0, tzinfo=UTC)
results = []
def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}  {detail}")

async def ids(e, chat, now, variant="plan", **kw):
    r = await claim(e, variant, chat, now, **kw)
    return r

async def scenario_out_of_order(e, variant):
    await reset_table(e)
    chat = 7
    await insert_rows(e, chat, [101])
    r = await claim(e, variant, chat, T0)
    got101 = r.claimed and r.claimed.update_id == 101
    await insert_rows(e, chat, [100])               # out-of-order arrival
    r2 = await claim(e, variant, chat, T0 + timedelta(seconds=1))
    blocked = r2.claimed is None
    r3 = await claim(e, variant, chat, T0 + timedelta(seconds=2))
    still_blocked = r3.claimed is None
    ok_complete = await complete(e, 101, 1, T0 + timedelta(seconds=3))
    r4 = await claim(e, variant, chat, T0 + timedelta(seconds=4))
    claimable_after = r4.claimed is not None and r4.claimed.update_id == 100
    return got101, blocked, still_blocked, ok_complete, claimable_after, r2

async def main():
    e = mk_engine()
    print("=== (2) out-of-order insert: 101 claimed, then 100 inserted")
    for v in ["plan", "headlock", "headlock_headcheck", "advisory_nolive", "skip_locked", "nolock_noguard"]:
        got101, blocked, still_blocked, okc, after, r2 = await scenario_out_of_order(e, v)
        if v == "plan":
            check("(2) plan: 101 claimed first", got101)
            check("(2) plan: 100 NOT claimable while 101 lease live", blocked and still_blocked)
            check("(2) plan: complete(101) fenced rowcount==1", okc == 1)
            check("(2) plan: 100 claimable after 101 completes", after)
        else:
            viol = r2.claimed is not None
            print(f"    variant {v:16s}: 100 claimed while 101 live? {viol}  (claimed={r2.claimed})  -> {'BROKEN as expected' if viol else 'NOT broken here'}")
            results.append((f"(6) {v} fails out-of-order", viol))

    print("=== (3) expired-lease takeover, attempts++, MAX_ATTEMPTS => failed(lease_exhausted), next row claimable")
    await reset_table(e)
    chat = 8
    await insert_rows(e, chat, [1, 2])
    lease, MAXA = 240, 3
    t = T0
    r = await claim(e, "plan", chat, t, lease_s=lease, max_attempts=MAXA)
    check("(3) first claim attempts=1", r.claimed and r.claimed.update_id == 1 and r.claimed.attempts == 1)
    r = await claim(e, "plan", chat, t + timedelta(seconds=100), lease_s=lease, max_attempts=MAXA)
    check("(3) live lease: nothing claimable at +100s", r.claimed is None)
    t1 = t + timedelta(seconds=241)
    r = await claim(e, "plan", chat, t1, lease_s=lease, max_attempts=MAXA)
    check("(3) takeover after expiry attempts=2", r.claimed and r.claimed.update_id == 1 and r.claimed.attempts == 2, str(r.claimed))
    t2 = t1 + timedelta(seconds=241)
    r = await claim(e, "plan", chat, t2, lease_s=lease, max_attempts=MAXA)
    check("(3) takeover attempts=3", r.claimed and r.claimed.update_id == 1 and r.claimed.attempts == 3, str(r.claimed))
    t3 = t2 + timedelta(seconds=241)
    r = await claim(e, "plan", chat, t3, lease_s=lease, max_attempts=MAXA)
    row1 = await fetch(e, 1)
    check("(3) after MAX_ATTEMPTS: row1 failed/lease_exhausted, payload cleared, finished_at set",
          row1.status == "failed" and row1.error_category == "lease_exhausted" and row1.payload_text is None and row1.finished_at is not None,
          f"row1={tuple(row1)[:3]} exhausted={r.exhausted}")
    check("(3) same call returns exhausted=[1] and claims row 2 (loop back to step 1)",
          r.exhausted == [1] and r.claimed and r.claimed.update_id == 2 and r.claimed.attempts == 1, str(r))

    print("=== (4) queued row with future lease_until (retry backoff) blocks later rows")
    await reset_table(e)
    chat = 9
    await insert_rows(e, chat, [1, 2, 3])
    r = await claim(e, "plan", chat, T0)
    check("(4) claim row1 (attempts 1)", r.claimed and r.claimed.update_id == 1)
    rc = await requeue(e, 1, 1, T0 + timedelta(seconds=5))   # backoff 5s * attempts(1)
    check("(4) fenced requeue rowcount==1", rc == 1)
    r = await claim(e, "plan", chat, T0 + timedelta(seconds=2))
    check("(4) during backoff: nothing claimable (rows 2,3 NOT skipped ahead)", r.claimed is None, str(r))
    r = await claim(e, "plan", chat, T0 + timedelta(seconds=5, milliseconds=1))
    check("(4) after backoff: row1 claimed again, attempts=2", r.claimed and r.claimed.update_id == 1 and r.claimed.attempts == 2, str(r.claimed))
    # contrast: variant a2/headlock skip ahead? (headlock selects queued whose lease_until is not considered at all)
    await reset_table(e)
    await insert_rows(e, chat, [1, 2, 3])
    await claim(e, "plan", chat, T0); await requeue(e, 1, 1, T0 + timedelta(seconds=5))
    r = await claim(e, "headlock", chat, T0 + timedelta(seconds=2))
    print(f"    (contrast) headlock during backoff claims: {r.claimed}  (ignores retry_at => does NOT honour backoff)")

    print("=== (5) fenced writes after takeover")
    await reset_table(e)
    chat = 10
    await insert_rows(e, chat, [1])
    a = (await claim(e, "plan", chat, T0)).claimed                          # worker A, attempts=1
    b = (await claim(e, "plan", chat, T0 + timedelta(seconds=300))).claimed  # worker B takes over, attempts=2
    check("(5) A attempts=1, B attempts=2", a.attempts == 1 and b.attempts == 2)
    tn = T0 + timedelta(seconds=301)
    ra = await save_reply(e, 1, a.attempts, "stale reply", tn)
    row = await fetch(e, 1)
    check("(5) stale A save_reply rowcount==0, reply untouched", ra == 0 and row.reply_text is None and row.reply_saved_at is None, f"rowcount={ra}")
    rb = await save_reply(e, 1, b.attempts, "owner reply", tn)
    row = await fetch(e, 1)
    check("(5) owner B save_reply rowcount==1", rb == 1 and row.reply_text == "owner reply" and row.reply_saved_at == tn)
    rrq = await requeue(e, 1, a.attempts, tn + timedelta(seconds=9))
    check("(5) stale A requeue rowcount==0", rrq == 0)
    ca = await complete(e, 1, a.attempts, tn)
    check("(5) stale A complete rowcount==0 (row still processing)", ca == 0 and (await fetch(e, 1)).status == "processing")
    cb = await complete(e, 1, b.attempts, tn)
    row = await fetch(e, 1)
    check("(5) owner B complete rowcount==1, status=replied, text cleared, reply_saved_at kept",
          cb == 1 and row.status == "replied" and row.reply_text is None and row.reply_saved_at == tn, f"{tuple(row)[:3]}")
    ca2 = await complete(e, 1, a.attempts, tn); sb2 = await save_reply(e, 1, a.attempts, "late", tn)
    cb2 = await complete(e, 1, b.attempts, tn)
    check("(5) any late write after terminal state rowcount==0 (including owner's duplicate)", ca2 == 0 and sb2 == 0 and cb2 == 0)
    # without fence: show unfenced complete would corrupt
    await reset_table(e); await insert_rows(e, chat, [1])
    a = (await claim(e, "plan", chat, T0)).claimed; b = (await claim(e, "plan", chat, T0 + timedelta(seconds=300))).claimed
    async with e.begin() as c:
        r = await c.execute(text("UPDATE bot_updates SET status='replied' WHERE update_id=1 AND status='processing'"))
    print(f"    (contrast) status-only fence (no attempts check): stale A complete rowcount={r.rowcount} => B's still-running work is silently terminated")

    print("=== (3b) release-on-SIGTERM then re-claim; claim of a processing row whose lease expired but chat has later live rows")
    await reset_table(e)
    chat = 11
    await insert_rows(e, chat, [1, 2])
    a = (await claim(e, "plan", chat, T0)).claimed
    # row 1 lease expires, nobody took over. Is row 2 claimable? must not be (row 1 is head).
    r = await claim(e, "plan", chat, T0 + timedelta(seconds=500))
    check("(3b) expired head row is taken over (not row 2)", r.claimed and r.claimed.update_id == 1 and r.claimed.attempts == 2)
    n_fail = sum(1 for _, ok in results if not ok)
    print(f"\nTOTAL checks={len(results)} failed={n_fail}")
    await e.dispose()

asyncio.run(main())
