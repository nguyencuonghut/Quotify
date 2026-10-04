\echo == 2a distribution by quotes.created_by_id (all quotes/versions/lines, all statuses)
WITH seed AS (SELECT id FROM users WHERE email=:'seed_email'),
base AS (
 SELECT q.id qid, q.created_by_id, qv.id vid, qv.status, qv.confirmed_at,
        (SELECT count(*) FROM quote_lines ql WHERE ql.quote_version_id=qv.id) nlines,
        q.cancelled_at
 FROM quotes q JOIN quote_versions qv ON qv.quote_id=q.id)
SELECT CASE WHEN b.created_by_id=(SELECT id FROM seed) THEN 'seed_admin' WHEN b.created_by_id IS NULL THEN 'NULL' ELSE 'other' END grp,
  count(DISTINCT qid) quotes, count(*) versions, sum(nlines) lines
FROM base b GROUP BY 1 ORDER BY 1;
\echo == 2b same but only confirmed versions of uncancelled quotes
WITH seed AS (SELECT id FROM users WHERE email=:'seed_email'),
base AS (
 SELECT q.id qid, q.created_by_id, qv.id vid, qv.status, qv.confirmed_at,
        (SELECT count(*) FROM quote_lines ql WHERE ql.quote_version_id=qv.id) nlines
 FROM quotes q JOIN quote_versions qv ON qv.quote_id=q.id WHERE qv.status='confirmed' AND q.cancelled_at IS NULL)
SELECT CASE WHEN b.created_by_id=(SELECT id FROM seed) THEN 'seed_admin' WHEN b.created_by_id IS NULL THEN 'NULL' ELSE 'other' END grp,
  count(DISTINCT qid) quotes, count(*) versions, sum(nlines) lines,
  min(confirmed_at AT TIME ZONE 'Asia/Ho_Chi_Minh') min_conf_vn, max(confirmed_at AT TIME ZONE 'Asia/Ho_Chi_Minh') max_conf_vn
FROM base b GROUP BY 1 ORDER BY 1;
\echo == 2c seed admin confirmed_at by VN date
WITH seed AS (SELECT id FROM users WHERE email=:'seed_email')
SELECT (qv.confirmed_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date d, count(*) versions, (SELECT count(*) FROM quote_lines ql WHERE ql.quote_version_id = ANY(array_agg(qv.id))) lines
FROM quotes q JOIN quote_versions qv ON qv.quote_id=q.id WHERE q.created_by_id=(SELECT id FROM seed) AND qv.status='confirmed' AND q.cancelled_at IS NULL GROUP BY 1 ORDER BY 1;
\echo == 2d created_by mismatch: version.created_by_id is seed but quote.created_by_id not, and vice versa (confirmed uncancelled)
WITH seed AS (SELECT id FROM users WHERE email=:'seed_email')
SELECT (q.created_by_id=(SELECT id FROM seed)) q_seed, (qv.created_by_id=(SELECT id FROM seed)) v_seed, count(*) FROM quotes q JOIN quote_versions qv ON qv.quote_id=q.id WHERE qv.status='confirmed' AND q.cancelled_at IS NULL GROUP BY 1,2 ORDER BY 1,2;
