\echo == 12m window boundary: lines with received_date = 2025-10-02 / lines > 2025-10-02
SELECT count(*) FILTER (WHERE qv.received_date = date '2025-10-02') lines_on_20251002, count(*) FILTER (WHERE qv.received_date > date '2025-10-02') lines_after,
  count(*) FILTER (WHERE qv.received_date >= date '2025-10-02') lines_ge
FROM quote_lines ql JOIN quote_versions qv ON qv.id=ql.quote_version_id JOIN quotes q ON q.id=qv.quote_id WHERE qv.status='confirmed' AND q.cancelled_at IS NULL;
\echo == points (chain-day) with received_date > 2025-10-02
SELECT count(*) FROM (SELECT DISTINCT ql.material_id, ql.delivery_month, qv.received_date FROM quote_lines ql JOIN quote_versions qv ON qv.id=ql.quote_version_id JOIN quotes q ON q.id=qv.quote_id WHERE qv.status='confirmed' AND q.cancelled_at IS NULL AND qv.received_date > date '2025-10-02') s;
\echo == weekend confirm share by group
WITH seed AS (SELECT id FROM users WHERE email=:'seed_email')
SELECT CASE WHEN q.created_by_id<>(SELECT id FROM seed) AND NOT qv.is_backfilled THEN 'real_not_backfilled' WHEN q.created_by_id<>(SELECT id FROM seed) THEN 'real_backfilled' ELSE 'seed' END grp,
 count(*) versions, count(*) FILTER (WHERE extract(isodow from qv.confirmed_at AT TIME ZONE 'Asia/Ho_Chi_Minh') IN (6,7)) conf_weekend,
 round(100.0*count(*) FILTER (WHERE extract(isodow from qv.confirmed_at AT TIME ZONE 'Asia/Ho_Chi_Minh') IN (6,7))/count(*),1) pct,
 count(*) FILTER (WHERE extract(hour from qv.confirmed_at AT TIME ZONE 'Asia/Ho_Chi_Minh') NOT BETWEEN 8 AND 21) outside_08_21
FROM quotes q JOIN quote_versions qv ON qv.quote_id=q.id WHERE qv.status='confirmed' AND q.cancelled_at IS NULL GROUP BY 1 ORDER BY 1;
\echo == real not-backfilled hours
SELECT extract(hour from qv.confirmed_at AT TIME ZONE 'Asia/Ho_Chi_Minh') h, count(*) FROM quotes q JOIN quote_versions qv ON qv.quote_id=q.id
WHERE qv.status='confirmed' AND q.cancelled_at IS NULL AND NOT qv.is_backfilled AND q.created_by_id <> (SELECT id FROM users WHERE email=:'seed_email') GROUP BY 1 ORDER BY 1;
\echo == real-user lines: received_date weekend share (all real) and by dow
SELECT extract(isodow from qv.received_date) dow, count(*) lines FROM quotes q JOIN quote_versions qv ON qv.quote_id=q.id JOIN quote_lines ql ON ql.quote_version_id=qv.id
WHERE qv.status='confirmed' AND q.cancelled_at IS NULL AND q.created_by_id <> (SELECT id FROM users WHERE email=:'seed_email') GROUP BY 1 ORDER BY 1;
\echo == per-person (anonymised) real-user distribution
SELECT row_number() OVER (ORDER BY count(*) DESC) person, count(DISTINCT q.id) quotes, count(*) FILTER (WHERE ql.id IS NOT NULL) lines
FROM quotes q JOIN quote_versions qv ON qv.quote_id=q.id LEFT JOIN quote_lines ql ON ql.quote_version_id=qv.id
WHERE qv.status='confirmed' AND q.cancelled_at IS NULL AND q.created_by_id <> (SELECT id FROM users WHERE email=:'seed_email') GROUP BY q.created_by_id ORDER BY 3 DESC;
\echo == quotes.created_by NULL count
SELECT count(*) FROM quotes WHERE created_by_id IS NULL;
