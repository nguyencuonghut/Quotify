\echo ===== business day 2026-10-13 +07 => [2026-10-12 17:00Z, 2026-10-13 17:00Z) ; user ...01 has ~16.7k rows in 30 days
\echo ----- Q9a turn count (literal bounds)
EXPLAIN (ANALYZE, BUFFERS) SELECT count(*) FROM bot_updates WHERE user_id = '00000000-0000-0000-0000-000000000001' AND reply_saved_at IS NOT NULL AND received_at >= timestamptz '2026-09-30 17:00:00+00' AND received_at < timestamptz '2026-10-01 17:00:00+00';
\echo ----- Q9b file count (kind photo/document)
EXPLAIN (ANALYZE, BUFFERS) SELECT count(*) FROM bot_updates WHERE user_id = '00000000-0000-0000-0000-000000000001' AND reply_saved_at IS NOT NULL AND kind IN ('photo','document') AND received_at >= timestamptz '2026-09-30 17:00:00+00' AND received_at < timestamptz '2026-10-01 17:00:00+00';
\echo ----- Q9a generic plan via PREPARE
SET plan_cache_mode = force_generic_plan;
PREPARE q9(uuid, timestamptz, timestamptz) AS SELECT count(*) FROM bot_updates WHERE user_id = $1 AND reply_saved_at IS NOT NULL AND received_at >= $2 AND received_at < $3;
EXPLAIN (ANALYZE, BUFFERS) EXECUTE q9('00000000-0000-0000-0000-000000000001', '2026-09-30 17:00:00+00', '2026-10-01 17:00:00+00');
RESET plan_cache_mode;
\echo ----- CONTRAST: date cast form (session tz dependent, cannot use the range)
EXPLAIN (ANALYZE, BUFFERS) SELECT count(*) FROM bot_updates WHERE user_id = '00000000-0000-0000-0000-000000000001' AND reply_saved_at IS NOT NULL AND (received_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = date '2026-10-01';
\echo ----- realistic: user with few rows (replace 1000 closed rows)
EXPLAIN (ANALYZE, BUFFERS) SELECT count(*) FROM bot_updates WHERE user_id = '00000000-0000-0000-0000-00000000000c' AND reply_saved_at IS NOT NULL AND received_at >= timestamptz '2026-10-12 17:00:00+00' AND received_at < timestamptz '2026-10-13 17:00:00+00';
