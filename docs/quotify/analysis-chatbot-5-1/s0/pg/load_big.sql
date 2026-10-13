TRUNCATE bot_updates;
-- 200k closed rows (mostly replied), spread over 30 days, 500 chats, 12 users
INSERT INTO bot_updates (update_id, chat_id, telegram_user_id, user_id, kind, status, attempts, reply_saved_at, received_at, started_at, finished_at, error_category)
SELECT i,
       1000 + (i % 500),
       1000 + (i % 500),
       ('00000000-0000-0000-0000-' || lpad((((i % 500) % 12) + 1)::text, 12, '0'))::uuid,
       CASE WHEN i % 25 = 0 THEN 'photo' ELSE 'text' END,
       CASE WHEN i % 40 = 0 THEN 'dropped' WHEN i % 97 = 0 THEN 'failed' ELSE 'replied' END,
       1,
       CASE WHEN i % 40 = 0 OR i % 97 = 0 THEN NULL ELSE ts + interval '3 seconds' END,
       ts, ts, ts + interval '4 seconds',
       CASE WHEN i % 40 = 0 THEN 'user_inactive' WHEN i % 97 = 0 THEN 'engine_error' END
FROM (SELECT i, timestamptz '2026-09-13 00:00:00+00' + (i * interval '30 days' / 200000) AS ts FROM generate_series(1, 200000) i) s;
-- 2000 open rows: 4 per chat; first row of every 2nd chat 'processing' with a live lease, the rest queued
INSERT INTO bot_updates (update_id, chat_id, telegram_user_id, user_id, kind, status, attempts, lease_until, received_at, started_at)
SELECT 200000 + g,
       1000 + ((g - 1) % 500),
       1000 + ((g - 1) % 500),
       ('00000000-0000-0000-0000-' || lpad(((((g - 1) % 500) % 12) + 1)::text, 12, '0'))::uuid,
       'text',
       CASE WHEN g <= 500 AND (g % 2 = 0) THEN 'processing' ELSE 'queued' END,
       CASE WHEN g <= 500 AND (g % 2 = 0) THEN 1 ELSE 0 END,
       CASE WHEN g <= 500 AND (g % 2 = 0) THEN timestamptz '2026-10-13 03:00:00+00' + interval '240 seconds' END,
       timestamptz '2026-10-13 02:59:00+00' + g * interval '1 second',
       CASE WHEN g <= 500 AND (g % 2 = 0) THEN timestamptz '2026-10-13 03:00:00+00' END
FROM generate_series(1, 2000) g;
VACUUM ANALYZE bot_updates;
SELECT status, count(*) FROM bot_updates GROUP BY 1 ORDER BY 1;
SELECT pg_size_pretty(pg_relation_size('bot_updates')) tbl, pg_size_pretty(pg_relation_size('ix_bot_updates_chat_open')) chat_open, pg_size_pretty(pg_relation_size('ix_bot_updates_user_received')) user_recv, pg_size_pretty(pg_relation_size('ix_bot_updates_status_received')) status_recv;
