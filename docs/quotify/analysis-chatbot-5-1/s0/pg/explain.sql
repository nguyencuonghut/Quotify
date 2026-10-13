\timing off
\echo ===== Q1 step2 live-lease check, chat 1000 (no processing row -> must scan all open rows of chat), literals
EXPLAIN (ANALYZE, BUFFERS) SELECT 1 FROM bot_updates WHERE chat_id = 1000 AND status = 'processing' AND lease_until > timestamptz '2026-10-13 03:00:10+00' LIMIT 1;
\echo ===== Q1 chat 1001 (has live processing row)
EXPLAIN (ANALYZE, BUFFERS) SELECT 1 FROM bot_updates WHERE chat_id = 1001 AND status = 'processing' AND lease_until > timestamptz '2026-10-13 03:00:10+00' LIMIT 1;
\echo ===== Q2 step3 head row selection, chat 1000
EXPLAIN (ANALYZE, BUFFERS) SELECT update_id, status, lease_until, attempts FROM bot_updates WHERE chat_id = 1000 AND status IN ('queued','processing') ORDER BY update_id LIMIT 1;
\echo ===== Q2b head row selection with FOR UPDATE
EXPLAIN (ANALYZE, BUFFERS) SELECT update_id, status, lease_until, attempts FROM bot_updates WHERE chat_id = 1000 AND status IN ('queued','processing') ORDER BY update_id LIMIT 1 FOR UPDATE;
\echo ===== Q3 TAKE by pk (rolled back)
BEGIN;
EXPLAIN (ANALYZE, BUFFERS) UPDATE bot_updates SET status='processing', lease_until=timestamptz '2026-10-13 03:04:00+00', attempts=attempts+1, started_at=coalesce(started_at, timestamptz '2026-10-13 03:00:00+00') WHERE update_id=200501 AND status IN ('queued','processing') RETURNING update_id, attempts, chat_id;
ROLLBACK;
\echo ===== GENERIC PLAN (what asyncpg prepared statements may settle on after 5 executions)
SET plan_cache_mode = force_generic_plan;
PREPARE q1(bigint, timestamptz) AS SELECT 1 FROM bot_updates WHERE chat_id = $1 AND status = 'processing' AND lease_until > $2 LIMIT 1;
PREPARE q2(bigint) AS SELECT update_id, status, lease_until, attempts FROM bot_updates WHERE chat_id = $1 AND status IN ('queued','processing') ORDER BY update_id LIMIT 1;
EXPLAIN (ANALYZE, BUFFERS) EXECUTE q1(1000, '2026-10-13 03:00:10+00');
EXPLAIN (ANALYZE, BUFFERS) EXECUTE q2(1000);
RESET plan_cache_mode;
\echo ===== Q4 webhook pending cap: count open rows of chat
EXPLAIN (ANALYZE, BUFFERS) SELECT count(*) FROM bot_updates WHERE chat_id = 1000 AND status IN ('queued','processing');
\echo ===== Q5 cron sweep: chats with claimable rows older than 30s
EXPLAIN (ANALYZE, BUFFERS) SELECT DISTINCT chat_id FROM bot_updates WHERE status IN ('queued','processing') AND received_at < timestamptz '2026-10-13 03:00:00+00' AND (lease_until IS NULL OR lease_until < timestamptz '2026-10-13 03:00:00+00');
\echo ===== CONTROL: same Q2 without the partial index (drop in a txn, rolled back)
BEGIN;
DROP INDEX ix_bot_updates_chat_open;
EXPLAIN (ANALYZE, BUFFERS) SELECT update_id, status, lease_until, attempts FROM bot_updates WHERE chat_id = 1000 AND status IN ('queued','processing') ORDER BY update_id LIMIT 1;
ROLLBACK;
