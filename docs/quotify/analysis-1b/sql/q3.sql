\echo == 3 lag distribution (working days) for real-user confirmed versions
WITH seed AS (SELECT id FROM users WHERE email=:'seed_email'),
v AS (
 SELECT qv.id vid, qv.received_date rd, qv.is_backfilled bf, (qv.confirmed_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date cd,
        (SELECT count(*) FROM quote_lines ql WHERE ql.quote_version_id=qv.id) nl
 FROM quotes q JOIN quote_versions qv ON qv.quote_id=q.id
 WHERE qv.status='confirmed' AND q.cancelled_at IS NULL AND q.created_by_id IS DISTINCT FROM (SELECT id FROM seed)),
w AS (
 SELECT v.*, (v.cd - v.rd) cal_lag,
   (SELECT count(*) FROM generate_series(v.rd + 1, v.cd, interval '1 day') g WHERE extract(isodow from g) BETWEEN 1 AND 5) wd_lag
 FROM v)
SELECT CASE WHEN cal_lag<0 THEN 'negative' WHEN wd_lag>=5 THEN '5+' ELSE wd_lag::text END wd_bucket,
  count(*) versions, sum(nl) lines, sum(nl) FILTER (WHERE bf) lines_backfilled, sum(nl) FILTER (WHERE NOT bf) lines_not_backfilled
FROM w GROUP BY 1 ORDER BY 1;
\echo == 3b same, cumulative <=0,1,2,3,5,7 working days and calendar days
WITH seed AS (SELECT id FROM users WHERE email=:'seed_email'),
v AS (
 SELECT qv.id vid, qv.received_date rd, qv.is_backfilled bf, (qv.confirmed_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date cd,
        (SELECT count(*) FROM quote_lines ql WHERE ql.quote_version_id=qv.id) nl
 FROM quotes q JOIN quote_versions qv ON qv.quote_id=q.id
 WHERE qv.status='confirmed' AND q.cancelled_at IS NULL AND q.created_by_id IS DISTINCT FROM (SELECT id FROM seed)),
w AS (
 SELECT v.*, (v.cd - v.rd) cal_lag,
   (SELECT count(*) FROM generate_series(v.rd + 1, v.cd, interval '1 day') g WHERE extract(isodow from g) BETWEEN 1 AND 5) wd_lag
 FROM v)
SELECT 'total' k, count(*) versions, sum(nl) lines, sum(nl) FILTER (WHERE bf) lines_bf, sum(nl) FILTER (WHERE NOT bf) lines_nobf FROM w
UNION ALL SELECT 'wd<=0', count(*), sum(nl), sum(nl) FILTER (WHERE bf), sum(nl) FILTER (WHERE NOT bf) FROM w WHERE wd_lag<=0
UNION ALL SELECT 'wd<=1', count(*), sum(nl), sum(nl) FILTER (WHERE bf), sum(nl) FILTER (WHERE NOT bf) FROM w WHERE wd_lag<=1
UNION ALL SELECT 'wd<=2', count(*), sum(nl), sum(nl) FILTER (WHERE bf), sum(nl) FILTER (WHERE NOT bf) FROM w WHERE wd_lag<=2
UNION ALL SELECT 'wd<=3', count(*), sum(nl), sum(nl) FILTER (WHERE bf), sum(nl) FILTER (WHERE NOT bf) FROM w WHERE wd_lag<=3
UNION ALL SELECT 'wd<=5', count(*), sum(nl), sum(nl) FILTER (WHERE bf), sum(nl) FILTER (WHERE NOT bf) FROM w WHERE wd_lag<=5
UNION ALL SELECT 'wd<=7', count(*), sum(nl), sum(nl) FILTER (WHERE bf), sum(nl) FILTER (WHERE NOT bf) FROM w WHERE wd_lag<=7
UNION ALL SELECT 'cal<=0', count(*), sum(nl), sum(nl) FILTER (WHERE bf), sum(nl) FILTER (WHERE NOT bf) FROM w WHERE cal_lag<=0
UNION ALL SELECT 'cal<=1', count(*), sum(nl), sum(nl) FILTER (WHERE bf), sum(nl) FILTER (WHERE NOT bf) FROM w WHERE cal_lag<=1
UNION ALL SELECT 'cal<=3', count(*), sum(nl), sum(nl) FILTER (WHERE bf), sum(nl) FILTER (WHERE NOT bf) FROM w WHERE cal_lag<=3
UNION ALL SELECT 'cal<=7', count(*), sum(nl), sum(nl) FILTER (WHERE bf), sum(nl) FILTER (WHERE NOT bf) FROM w WHERE cal_lag<=7
UNION ALL SELECT 'cal<0 (received after confirm)', count(*), sum(nl), sum(nl) FILTER (WHERE bf), sum(nl) FILTER (WHERE NOT bf) FROM w WHERE cal_lag<0;
\echo == 3c calendar-lag stats of backfilled real-user lines (doc: n=1151 median 13 P75 76 P90 179 max 316)
WITH seed AS (SELECT id FROM users WHERE email=:'seed_email'),
l AS (
 SELECT ql.id, (qv.confirmed_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date - qv.received_date cal_lag
 FROM quotes q JOIN quote_versions qv ON qv.quote_id=q.id JOIN quote_lines ql ON ql.quote_version_id=qv.id
 WHERE qv.status='confirmed' AND q.cancelled_at IS NULL AND q.created_by_id IS DISTINCT FROM (SELECT id FROM seed) AND qv.is_backfilled)
SELECT count(*) n, percentile_disc(0.5) WITHIN GROUP (ORDER BY cal_lag) med, percentile_disc(0.75) WITHIN GROUP (ORDER BY cal_lag) p75, percentile_disc(0.9) WITHIN GROUP (ORDER BY cal_lag) p90, max(cal_lag) mx FROM l;
