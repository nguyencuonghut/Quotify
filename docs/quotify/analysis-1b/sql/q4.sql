\echo == db now
SELECT now(), now() AT TIME ZONE 'Asia/Ho_Chi_Minh' vn_now, (now() - interval '60 days') AT TIME ZONE 'Asia/Ho_Chi_Minh' cutoff60_vn;
\echo == 4a 60 days summary: real-user confirmed versions
WITH seed AS (SELECT id FROM users WHERE email=:'seed_email'),
x AS (
 SELECT qv.id vid, qv.confirmed_at, qv.received_date rd, qv.is_backfilled bf, ql.material_id m, ql.delivery_month dm, ql.id lid,
  (qv.confirmed_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date cd,
  (SELECT count(*) FROM generate_series(qv.received_date + 1, (qv.confirmed_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date, interval '1 day') g WHERE extract(isodow from g) BETWEEN 1 AND 5) wd_lag
 FROM quotes q JOIN quote_versions qv ON qv.quote_id=q.id JOIN quote_lines ql ON ql.quote_version_id=qv.id
 WHERE qv.status='confirmed' AND q.cancelled_at IS NULL AND q.created_by_id IS DISTINCT FROM (SELECT id FROM seed)
   AND qv.confirmed_at > now() - interval '60 days')
SELECT 'all real (60d)' k, count(DISTINCT vid) versions, count(*) lines, count(DISTINCT (m,dm)) chains, count(DISTINCT m) materials, min(cd) first_day, max(cd) last_day, count(DISTINCT cd) active_days FROM x
UNION ALL
SELECT 'D6-qualifying (wd_lag<=3)', count(DISTINCT vid), count(*), count(DISTINCT (m,dm)), count(DISTINCT m), min(cd), max(cd), count(DISTINCT cd) FROM x WHERE wd_lag<=3
UNION ALL
SELECT 'wd_lag=0 (same-day)', count(DISTINCT vid), count(*), count(DISTINCT (m,dm)), count(DISTINCT m), min(cd), max(cd), count(DISTINCT cd) FROM x WHERE wd_lag=0;
\echo == 4b by VN day (real users, all lags) with D6-qualifying columns
WITH seed AS (SELECT id FROM users WHERE email=:'seed_email'),
x AS (
 SELECT qv.id vid, ql.material_id m, ql.delivery_month dm, ql.id lid,
  (qv.confirmed_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date cd,
  (SELECT count(*) FROM generate_series(qv.received_date + 1, (qv.confirmed_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date, interval '1 day') g WHERE extract(isodow from g) BETWEEN 1 AND 5) wd_lag
 FROM quotes q JOIN quote_versions qv ON qv.quote_id=q.id JOIN quote_lines ql ON ql.quote_version_id=qv.id
 WHERE qv.status='confirmed' AND q.cancelled_at IS NULL AND q.created_by_id IS DISTINCT FROM (SELECT id FROM seed)
   AND qv.confirmed_at > now() - interval '60 days')
SELECT cd, to_char(cd,'Dy') dow, count(DISTINCT vid) versions, count(*) lines, count(DISTINCT (m,dm)) chains,
  count(DISTINCT vid) FILTER (WHERE wd_lag<=3) v_d6, count(*) FILTER (WHERE wd_lag<=3) lines_d6, count(DISTINCT (m,dm)) FILTER (WHERE wd_lag<=3) chains_d6
FROM x GROUP BY cd ORDER BY cd;
