COPY (
SELECT ql.id AS lid, qv.id AS vid, qv.quote_id AS qid, q.sequence_number AS qseq, qv.version_number AS vn, qv.status,
  (q.created_by_id = (SELECT id FROM users WHERE email=:'seed_email'))::int AS is_seed,
  qv.is_backfilled::int AS is_bf, qv.received_date AS rd,
  to_char(qv.confirmed_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US') AS conf_utc,
  to_char(qv.superseded_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US') AS sup_utc,
  qv.superseded_by_version_id AS sup_by_vid,
  ql.material_id AS mid, m.name AS material, ql.delivery_month AS dm, ql.currency, ql.unit, ql.price_original AS po, ql.price_converted_vnd_per_kg AS pc, ql.line_order AS lo,
  q.created_by_id::text AS quser
FROM quote_lines ql JOIN quote_versions qv ON qv.id=ql.quote_version_id JOIN quotes q ON q.id=qv.quote_id JOIN materials m ON m.id=ql.material_id
WHERE qv.status IN ('confirmed','superseded') AND q.cancelled_at IS NULL
ORDER BY qv.confirmed_at, qv.id, ql.line_order
) TO STDOUT WITH CSV HEADER
