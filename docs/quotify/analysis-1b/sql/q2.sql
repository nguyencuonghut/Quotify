\echo == users
SELECT u.id, u.email IS NOT NULL has_email, u.email = :'seed_email' AS is_seed, u.status FROM users u ORDER BY is_seed DESC, u.email;
\echo == roles per user
SELECT split_part(u.email,'@',1) u, (u.email=:'seed_email') seed, string_agg(r.name, ',') roles FROM users u LEFT JOIN user_roles ur ON ur.user_id=u.id LEFT JOIN roles r ON r.id=ur.role_id GROUP BY u.id, u.email ORDER BY seed DESC, u;
