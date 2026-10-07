set default_transaction_read_only = on;

-- B.1 va B.2: so lieu tong hop (vat tu dang hoat dong; phieu hop le = da chot, chua huy, ngay nhan khong o tuong lai)
with today as (select (now() at time zone 'Asia/Ho_Chi_Minh')::date as d),
valid as (
  select ql.material_id, qv.id as version_id, qv.received_date
  from quote_lines ql
  join quote_versions qv on qv.id = ql.quote_version_id
    and qv.status = 'confirmed' and qv.confirmed_at is not null
  join quotes q on q.id = qv.quote_id and q.cancelled_at is null
  where qv.received_date <= (select d from today)
),
per as (
  select m.id as material_id,
    count(distinct case when v.received_date >= (select d from today) - 6 then v.version_id end) as v7,
    count(distinct case when v.received_date >= (select d from today) - 29 then v.version_id end) as v30,
    count(distinct case when v.received_date >= (select d from today) - 89 then v.version_id end) as v90,
    count(distinct v.version_id) as v_all
  from materials m
  left join valid v on v.material_id = m.id
  where m.status = 'active'
  group by m.id
),
days as (
  select distinct v.material_id, v.received_date as d
  from valid v join materials m on m.id = v.material_id and m.status = 'active'
  where v.received_date >= (select d from today) - 89
),
gaps as (
  select material_id, count(*) as n_days,
    case when count(*) > 1 then (max(d) - min(d))::numeric / (count(*) - 1) end as mean_gap
  from days group by 1
)
select k, v from (
  select 1 as o, 'materials_total' as k, (select count(*) from materials)::text as v
  union all select 2, 'materials_active', count(*)::text from per
  union all select 3, 'updated_7d', count(*)::text from per where v7 > 0
  union all select 4, 'updated_30d', count(*)::text from per where v30 > 0
  union all select 5, 'updated_90d', count(*)::text from per where v90 > 0
  union all select 6, 'never_updated', count(*)::text from per where v_all = 0
  union all select 7, 'stale_over_30d_but_ever_updated', count(*)::text from per where v_all > 0 and v30 = 0
  union all select 8, 'median_updates_30d_among_updated',
    coalesce(round((percentile_cont(0.5) within group (order by v30))::numeric, 1)::text, '-') from per where v30 > 0
  union all select 9, 'max_updates_30d', coalesce(max(v30), 0)::text from per
  union all select 10, 'update_days_90d = 1', count(*)::text from gaps where n_days = 1
  union all select 11, 'update_days_90d = 2', count(*)::text from gaps where n_days = 2
  union all select 12, 'update_days_90d >= 3 (watch list)', count(*)::text from gaps where n_days >= 3
  union all select 13, 'tier 7 (mean gap <= 5)', count(*)::text from gaps where n_days >= 3 and mean_gap <= 5
  union all select 14, 'tier 14 (5 < gap <= 12)', count(*)::text from gaps where n_days >= 3 and mean_gap > 5 and mean_gap <= 12
  union all select 15, 'tier 30 (gap > 12)', count(*)::text from gaps where n_days >= 3 and mean_gap > 12
  union all select 16, 'mean_gap_median', coalesce(round((percentile_cont(0.5) within group (order by mean_gap))::numeric, 1)::text, '-') from gaps where n_days >= 3
  union all select 17, 'mean_gap_avg', coalesce(round(avg(mean_gap), 1)::text, '-') from gaps where n_days >= 3
  union all select 18, 'mean_gap_p25', coalesce(round((percentile_cont(0.25) within group (order by mean_gap))::numeric, 1)::text, '-') from gaps where n_days >= 3
  union all select 19, 'mean_gap_p75', coalesce(round((percentile_cont(0.75) within group (order by mean_gap))::numeric, 1)::text, '-') from gaps where n_days >= 3
) t order by o;

-- B.3 theo loai vat tu
with today as (select (now() at time zone 'Asia/Ho_Chi_Minh')::date as d),
valid as (
  select ql.material_id, qv.id as version_id, qv.received_date
  from quote_lines ql
  join quote_versions qv on qv.id = ql.quote_version_id
    and qv.status = 'confirmed' and qv.confirmed_at is not null
  join quotes q on q.id = qv.quote_id and q.cancelled_at is null
  where qv.received_date <= (select d from today)
),
days as (
  select distinct v.material_id, v.received_date as d
  from valid v where v.received_date >= (select d from today) - 89
),
n as (select material_id, count(*) as n_days from days group by 1)
select mt.name as loai_vat_tu,
  count(*) as vat_tu_hoat_dong,
  count(n.material_id) as co_cap_nhat_90_ngay,
  count(*) filter (where n.n_days >= 3) as tu_3_ngay_tro_len
from materials m
join material_types mt on mt.id = m.material_type_id
left join n on n.material_id = m.id
where m.status = 'active'
group by mt.name order by 2 desc;

-- B.4 muoi vat tu cap nhat day nhat (de quan ly doi chieu tinh hop ly)
with today as (select (now() at time zone 'Asia/Ho_Chi_Minh')::date as d),
days as (
  select distinct ql.material_id, qv.received_date as d
  from quote_lines ql
  join quote_versions qv on qv.id = ql.quote_version_id
    and qv.status = 'confirmed' and qv.confirmed_at is not null
  join quotes q on q.id = qv.quote_id and q.cancelled_at is null
  where qv.received_date between (select d from today) - 89 and (select d from today)
)
select m.code, m.name, count(*) as so_ngay_cap_nhat,
  round(((max(d) - min(d))::numeric / nullif(count(*) - 1, 0)), 1) as khoang_cach_tb_ngay,
  max(d) as nhan_gan_nhat
from days join materials m on m.id = days.material_id and m.status = 'active'
group by m.code, m.name having count(*) >= 3
order by 4 asc nulls last limit 10;
