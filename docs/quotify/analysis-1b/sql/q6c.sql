\echo == duplicates (version, material, delivery_month) groups >=2 lines, confirmed uncancelled, by origin
WITH seed AS (SELECT id FROM users WHERE email=:'seed_email'),
g AS (SELECT ql.quote_version_id vid, ql.material_id, ql.delivery_month, count(*) n, (q.created_by_id=(SELECT id FROM seed)) is_seed
 FROM quote_lines ql JOIN quote_versions qv ON qv.id=ql.quote_version_id JOIN quotes q ON q.id=qv.quote_id WHERE qv.status='confirmed' AND q.cancelled_at IS NULL GROUP BY 1,2,3,5)
SELECT is_seed, count(*) groups_total, count(*) FILTER (WHERE n>1) groups_dup, count(DISTINCT vid) FILTER (WHERE n>1) versions_with_dup, max(n) max_dup FROM g GROUP BY 1;
\echo == example of a duplicate group differences (min vs max price in same version/material/dm)
SELECT count(*) groups_dup, count(*) FILTER (WHERE mx>mn) price_differs FROM (SELECT ql.quote_version_id, ql.material_id, ql.delivery_month, min(price_converted_vnd_per_kg) mn, max(price_converted_vnd_per_kg) mx FROM quote_lines ql JOIN quote_versions qv ON qv.id=ql.quote_version_id JOIN quotes q ON q.id=qv.quote_id WHERE qv.status='confirmed' AND q.cancelled_at IS NULL GROUP BY 1,2,3 HAVING count(*)>1) s;
