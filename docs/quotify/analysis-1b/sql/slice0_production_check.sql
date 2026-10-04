SET default_transaction_read_only = on;
\echo '== 1. Tên role'
select name from roles order by 1;
\echo '== 2. Người dùng theo role, trạng thái (is_seed = tài khoản admin hệ thống)'
select (u.email = :'seed_email') as is_seed, coalesce(string_agg(distinct r.name, ','), '-') as roles, u.status, count(distinct u.id) as so_nguoi
from users u left join user_roles ur on ur.user_id = u.id left join roles r on r.id = ur.role_id
group by 1, 3 order by 1 desc, 3;
\echo '== 3. Ai đã tải import (chỉ hiện email nếu KHÔNG phải tài khoản seed)'
select ij.entity_type, ij.task_name, case when u.email = :'seed_email' then '(seed)' else coalesce(u.email, '(NULL)') end as nguoi_tai, count(*) as so_job
from import_jobs ij left join users u on u.id = ij.created_by_id group by 1, 2, 3 order by 1, 2, 3;
\echo '== 4. Phiếu của tài khoản seed theo ngày tạo (phải chỉ có ngày import)'
select q.created_at::date as ngay, count(*) as so_phieu
from quotes q join users u on u.id = q.created_by_id where u.email = :'seed_email' group by 1 order by 1;
\echo '== 5. Phiếu của người khác: số người và số phiếu'
select count(distinct q.created_by_id) as so_nguoi, count(*) as so_phieu, min(q.created_at)::date as tu, max(q.created_at)::date as den
from quotes q left join users u on u.id = q.created_by_id where u.email is distinct from :'seed_email';
\echo '== 6. Dữ liệu cần đếm: delivery_month khác ngày 01, version confirmed thiếu confirmed_at'
select (select count(*) from quote_lines where extract(day from delivery_month) <> 1) as delivery_month_khac_ngay_01,
       (select count(*) from quote_versions where status = 'confirmed' and confirmed_at is null) as confirmed_thieu_confirmed_at;
\echo '== 7. Liên kết Telegram (is_seed = tài khoản admin hệ thống)'
select (u.email = :'seed_email') as is_seed, ta.status, count(*) as so_lien_ket
from telegram_accounts ta join users u on u.id = ta.user_id group by 1, 2 order by 1 desc, 2;
