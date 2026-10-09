-- Chỉ đọc: ai đang nhận tin Telegram biến động giá và tin nhắc cập nhật giá (Telegram 1C/1D).
-- Chạy: psql -v pilot="$PILOT" -v seed="$SEED" -f price-alert-recipients.sql
--   pilot = PRICE_ALERT_RECIPIENT_EMAILS của worker (rỗng = không giới hạn)
--   seed  = AUTH_SEED_ADMIN_EMAIL (tài khoản seed luôn bị loại)
-- Phản chiếu app/services/price_alert_recipients.py; các điều kiện toàn hệ thống (công tắc tổng,
-- TELEGRAM_ENABLED) in ở truy vấn đầu.

\echo '== 1. Công tắc toàn hệ thống =='
select is_enabled as "bat_tong", freshness_enabled as "bat_nhac_cap_nhat",
       anomaly_enabled as "bat_bat_thuong", staff_lookback_days as "cua_so_nhan_vien_ngay",
       freshness_hour_local as "gio_nhac"
from price_alert_settings;

\echo '== 2. Người dùng đang hoạt động: đã/chưa liên kết Telegram =='
select count(*) filter (where t.id is not null) as "da_lien_ket",
       count(*) filter (where t.id is null) as "chua_lien_ket"
from users u
left join telegram_accounts t on t.user_id = u.id and t.status = 'active'
where u.status = 'active' and lower(u.email) <> lower(:'seed');

\echo '== 3. Người đã liên kết: nhóm, và có nhận tin giá / tin nhắc không =='
with s as (select * from price_alert_settings limit 1),
today as (select (now() at time zone 'Asia/Ho_Chi_Minh')::date as d),
staff as (
  select q.created_by_id as uid, count(distinct ql.material_id) as n
  from quotes q
  join quote_versions qv on qv.quote_id = q.id
  join quote_lines ql on ql.quote_version_id = qv.id, s, today
  where qv.status = 'confirmed' and qv.confirmed_at is not null and q.cancelled_at is null
    and q.created_by_id is not null
    and qv.received_date between today.d - s.staff_lookback_days and today.d
  group by 1
),
base as (
  select u.email, coalesce(nullif(u.full_name, ''), '-') as ten,
    exists (select 1 from user_roles ur join roles r on r.id = ur.role_id
            where ur.user_id = u.id and r.name = 'admin') as is_admin,
    exists (select 1 from user_roles ur
            join role_permissions rp on rp.role_id = ur.role_id
            join permissions p on p.id = rp.permission_id
            where ur.user_id = u.id and p.code = 'price_alerts.receive_all') as is_manager,
    coalesce(st.n, 0) as vat_tu_phu_trach,
    coalesce(p.is_enabled, true) as ca_nhan_bat,
    p.min_level, coalesce(p.admin_receive_all, false) as admin_nhan_tat_ca,
    (:'pilot' = '' or lower(u.email) = any (
       regexp_split_to_array(lower(trim(:'pilot')), '\s*,\s*'))) as trong_pilot
  from users u
  join telegram_accounts t on t.user_id = u.id and t.status = 'active'
  left join user_alert_preferences p on p.user_id = u.id
  left join staff st on st.uid = u.id
  where u.status = 'active' and lower(u.email) <> lower(:'seed')
),
cls as (
  select *,
    case when is_admin then 'admin' when is_manager then 'manager'
         when vat_tu_phu_trach > 0 then 'staff' else '(khong thuoc nhom nao)' end as nhom
  from base
),
elig as (
  select *,
    (nhom in ('manager', 'staff') or (nhom = 'admin' and admin_nhan_tat_ca))
      and ca_nhan_bat and trong_pilot as du_dieu_kien
  from cls
)
select email, ten, nhom,
       case when nhom = 'staff' then vat_tu_phu_trach::text else 'tat ca' end as vat_tu,
       coalesce(min_level, case when nhom = 'staff' then 'light' else 'medium' end) as muc_toi_thieu,
       ca_nhan_bat, trong_pilot,
       case when du_dieu_kien and s.is_enabled then 'CO' else 'khong' end as nhan_tin_gia,
       case when du_dieu_kien and s.is_enabled and s.freshness_enabled
            then 'CO' else 'khong' end as nhan_nhac_cap_nhat
from elig, s
order by nhom, email;

\echo '== 4. Tin đã tạo trong 14 ngày qua, theo người nhận =='
select u.email, m.kind, m.audience, m.status, count(*) as so_tin, max(m.created_at)::date as gan_nhat
from price_alert_messages m
join users u on u.id = m.user_id
where m.created_at > now() - interval '14 days'
group by 1, 2, 3, 4
order by 1, 2, 4;
