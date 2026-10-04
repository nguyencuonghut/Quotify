\echo == 5a delivery_month day != 1 (all lines, any status)
SELECT count(*) total_lines, count(*) FILTER (WHERE extract(day from delivery_month) <> 1) not_day1,
  count(*) FILTER (WHERE delivery_month <> date_trunc('month', delivery_month)::date) not_first FROM quote_lines;
\echo == 5b delivery_month range
SELECT min(delivery_month), max(delivery_month) FROM quote_lines;
\echo == 5c received_date weekend: confirmed, uncancelled - lines and distinct daily-min points (chain-day) and versions
WITH x AS (
 SELECT ql.material_id m, ql.delivery_month dm, qv.received_date rd, qv.id vid, ql.id lid
 FROM quote_lines ql JOIN quote_versions qv ON qv.id=ql.quote_version_id JOIN quotes q ON q.id=qv.quote_id
 WHERE qv.status='confirmed' AND q.cancelled_at IS NULL)
SELECT 'all-time' scope, count(*) lines, count(*) FILTER (WHERE extract(isodow from rd)=6) sat, count(*) FILTER (WHERE extract(isodow from rd)=7) sun,
  round(100.0*count(*) FILTER (WHERE extract(isodow from rd) IN (6,7))/count(*),2) pct_lines_weekend,
  (SELECT count(*) FROM (SELECT DISTINCT m,dm,rd FROM x) p) points,
  (SELECT count(*) FROM (SELECT DISTINCT m,dm,rd FROM x WHERE extract(isodow from rd) IN (6,7)) p) points_weekend,
  count(DISTINCT vid) FILTER (WHERE extract(isodow from rd) IN (6,7)) versions_weekend, count(DISTINCT vid) versions
FROM x
UNION ALL
SELECT 'last 12 months (received_date >= 2025-10-02)', count(*), count(*) FILTER (WHERE extract(isodow from rd)=6), count(*) FILTER (WHERE extract(isodow from rd)=7),
  round(100.0*count(*) FILTER (WHERE extract(isodow from rd) IN (6,7))/count(*),2),
  (SELECT count(*) FROM (SELECT DISTINCT m,dm,rd FROM x WHERE rd >= date '2025-10-02') p),
  (SELECT count(*) FROM (SELECT DISTINCT m,dm,rd FROM x WHERE rd >= date '2025-10-02' AND extract(isodow from rd) IN (6,7)) p),
  count(DISTINCT vid) FILTER (WHERE extract(isodow from rd) IN (6,7)), count(DISTINCT vid)
FROM x WHERE rd >= date '2025-10-02';
\echo == 5d received_date range
SELECT min(received_date), max(received_date) FROM quote_versions WHERE status='confirmed';
\echo == 5e received_date weekday distribution (confirmed versions)
SELECT extract(isodow from received_date) dow, count(*) versions FROM quote_versions WHERE status='confirmed' GROUP BY 1 ORDER BY 1;
\echo == 5f 12-month window cross-check: lines, seed share, real not-backfilled lines
WITH seed AS (SELECT id FROM users WHERE email=:'seed_email')
SELECT count(*) lines12m, count(*) FILTER (WHERE q.created_by_id=(SELECT id FROM seed)) seed_lines, count(*) FILTER (WHERE NOT qv.is_backfilled) notbf_lines,
 count(*) FILTER (WHERE q.created_by_id<>(SELECT id FROM seed) AND qv.is_backfilled) real_bf_lines, count(DISTINCT qv.id) versions12m,
 count(DISTINCT (ql.material_id, ql.delivery_month)) chains12m
FROM quote_lines ql JOIN quote_versions qv ON qv.id=ql.quote_version_id JOIN quotes q ON q.id=qv.quote_id
WHERE qv.status='confirmed' AND q.cancelled_at IS NULL AND qv.received_date >= date '2025-10-02';
\echo == 5g weekend real-user versions confirmed on weekend (VN) share, last real period
SELECT count(*) versions_real, count(*) FILTER (WHERE extract(isodow from (qv.confirmed_at AT TIME ZONE 'Asia/Ho_Chi_Minh')) IN (6,7)) conf_weekend,
  round(100.0*count(*) FILTER (WHERE extract(isodow from (qv.confirmed_at AT TIME ZONE 'Asia/Ho_Chi_Minh')) IN (6,7))/count(*),1) pct
FROM quotes q JOIN quote_versions qv ON qv.quote_id=q.id
WHERE qv.status='confirmed' AND q.cancelled_at IS NULL AND q.created_by_id <> (SELECT id FROM users WHERE email=:'seed_email');
\echo == 5h hour of confirmation VN real users
SELECT extract(hour from qv.confirmed_at AT TIME ZONE 'Asia/Ho_Chi_Minh') h, count(*) FROM quotes q JOIN quote_versions qv ON qv.quote_id=q.id
WHERE qv.status='confirmed' AND q.cancelled_at IS NULL AND q.created_by_id <> (SELECT id FROM users WHERE email=:'seed_email') GROUP BY 1 ORDER BY 1;
