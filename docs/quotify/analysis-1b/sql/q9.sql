\echo == non-backfilled real lines per ISO week of confirmed_at (doc: wk34..40 = 89,175,20,96,49,45,91)
WITH seed AS (SELECT id FROM users WHERE email=:'seed_email')
SELECT to_char(qv.confirmed_at AT TIME ZONE 'Asia/Ho_Chi_Minh','IYYY-"W"IW') wk, count(*) lines_notbf
FROM quote_lines ql JOIN quote_versions qv ON qv.id=ql.quote_version_id JOIN quotes q ON q.id=qv.quote_id
WHERE qv.status='confirmed' AND q.cancelled_at IS NULL AND q.created_by_id<>(SELECT id FROM seed) AND NOT qv.is_backfilled GROUP BY 1 ORDER BY 1;
\echo == all real lines per ISO week of confirmed_at
WITH seed AS (SELECT id FROM users WHERE email=:'seed_email')
SELECT to_char(qv.confirmed_at AT TIME ZONE 'Asia/Ho_Chi_Minh','IYYY-"W"IW') wk, count(*) lines_all_real, count(DISTINCT qv.id) versions FROM quote_lines ql JOIN quote_versions qv ON qv.id=ql.quote_version_id JOIN quotes q ON q.id=qv.quote_id
WHERE qv.status='confirmed' AND q.cancelled_at IS NULL AND q.created_by_id<>(SELECT id FROM seed) GROUP BY 1 ORDER BY 1;
\echo == weekend confirm share among D6-qualifying versions (lag<=3 WD)
WITH seed AS (SELECT id FROM users WHERE email=:'seed_email'),
v AS (SELECT qv.id, (qv.confirmed_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date cd, qv.received_date rd FROM quotes q JOIN quote_versions qv ON qv.quote_id=q.id WHERE qv.status='confirmed' AND q.cancelled_at IS NULL AND q.created_by_id<>(SELECT id FROM seed)),
w AS (SELECT v.*, (SELECT count(*) FROM generate_series(v.rd+1, v.cd, interval '1 day') g WHERE extract(isodow from g) BETWEEN 1 AND 5) lag FROM v)
SELECT count(*) d6_versions, count(*) FILTER (WHERE extract(isodow from cd) IN (6,7)) weekend_conf, round(100.0*count(*) FILTER (WHERE extract(isodow from cd) IN (6,7))/count(*),1) pct FROM w WHERE lag<=3;
\echo == hours: min..max of real confirmed hour (VN) 
SELECT min(extract(hour from qv.confirmed_at AT TIME ZONE 'Asia/Ho_Chi_Minh')), max(extract(hour from qv.confirmed_at AT TIME ZONE 'Asia/Ho_Chi_Minh')) FROM quote_versions qv JOIN quotes q ON q.id=qv.quote_id WHERE qv.status='confirmed' AND q.created_by_id<>(SELECT id FROM users WHERE email=:'seed_email');
\echo == 12-month versions (rd > 2025-10-02): total, not backfilled
SELECT count(*) versions12, count(*) FILTER (WHERE NOT is_backfilled) notbf FROM quote_versions qv JOIN quotes q ON q.id=qv.quote_id WHERE qv.status='confirmed' AND q.cancelled_at IS NULL AND qv.received_date > date '2025-10-02';
\echo == multiple versions same day same chain point for real (>=2 versions on same received_date for a chain, not backfilled)
SELECT count(*) FROM (SELECT ql.material_id, ql.delivery_month, qv.received_date FROM quote_lines ql JOIN quote_versions qv ON qv.id=ql.quote_version_id JOIN quotes q ON q.id=qv.quote_id WHERE qv.status='confirmed' AND q.cancelled_at IS NULL AND NOT qv.is_backfilled GROUP BY 1,2,3 HAVING count(DISTINCT qv.id)>=2) s;
