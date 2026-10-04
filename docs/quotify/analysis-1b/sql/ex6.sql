COPY (
SELECT q.sequence_number AS qseq, o.id AS oid, o.version_number AS ovn, s.id AS sid, s.version_number AS svn, s.status AS sstatus,
       v.id AS vid, CASE WHEN v.id=o.id THEN 'old' ELSE 'new' END AS side,
       l.line_order, l.material_id, m.name AS material, l.delivery_month, l.currency, l.unit, l.price_original, l.price_converted_vnd_per_kg AS pc
FROM quote_versions o
JOIN quote_versions s ON s.id=o.superseded_by_version_id
JOIN quotes q ON q.id=o.quote_id
JOIN quote_versions v ON v.id IN (o.id, s.id)
JOIN quote_lines l ON l.quote_version_id=v.id
JOIN materials m ON m.id=l.material_id
WHERE o.status='superseded'
ORDER BY q.sequence_number, o.version_number, v.version_number, l.line_order
) TO STDOUT WITH CSV HEADER
