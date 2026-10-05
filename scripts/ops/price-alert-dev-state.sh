#!/usr/bin/env bash
# Theo dõi thông báo biến động giá trong DB DEV (chỉ đọc), dùng cho giai đoạn pilot ở Slice 10.
# Không in email người dùng, không in telegram_user_id, không in nội dung tin.
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root_dir"

psql_cmd=(docker compose exec -T postgres psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-app}")
days="${1:-3}"

echo "(Giờ hiển thị là UTC; giờ Việt Nam = UTC+7. Xem ${days} ngày gần nhất; đổi bằng đối số đầu tiên.)"

echo "== Cờ và nhịp tim cron quét (last_run_at phải mới hơn 2 phút khi cờ bật) =="
"${psql_cmd[@]}" -c "
  select s.is_enabled, s.reference_fallback_days as gốc_dự_phòng_ngày,
         to_char(st.last_run_at, 'DD/MM HH24:MI:SS') as last_run_at,
         round(extract(epoch from (now() - st.last_run_at)))::int as cách_giây,
         to_char(st.watermark_confirmed_at, 'DD/MM HH24:MI:SS') as watermark
  from price_alert_settings s cross join price_alert_scan_state st"

echo "== Lần quét có việc hoặc có lỗi, theo ngày =="
"${psql_cmd[@]}" -c "
  select started_at::date as ngày, count(*) as số_lần_có_việc, sum(versions_scanned) as version,
         sum(events_created) as sự_kiện, sum(messages_created) as tin, sum(error_count) as lỗi
  from price_alert_scan_runs where started_at > now() - interval '${days} days'
  group by 1 order by 1"

echo "== Lỗi quét gần nhất (nếu có) =="
"${psql_cmd[@]}" -c "
  select to_char(started_at, 'DD/MM HH24:MI:SS') as lúc, error_count, left(last_error, 120) as lỗi
  from price_alert_scan_runs where error_count > 0 order by started_at desc limit 5"

echo "== Tin theo trạng thái, theo ngày =="
"${psql_cmd[@]}" -c "
  select created_at::date as ngày, status, coalesce(status_reason, '-') as lý_do, count(*) as số_tin
  from price_alert_messages where created_at > now() - interval '${days} days'
  group by 1, 2, 3 order by 1, 2, 3"

echo "== Tin gửi thất bại hoặc đang kẹt (sending quá hạn) =="
"${psql_cmd[@]}" -c "
  select to_char(created_at, 'DD/MM HH24:MI:SS') as lúc, status, coalesce(status_reason, '-') as lý_do,
         attempts, left(coalesce(last_error, '-'), 80) as lỗi
  from price_alert_messages
  where status = 'failed' or (status = 'sending' and lease_until < now())
  order by created_at desc limit 10"

echo "== Kiểm trùng: sự kiện trùng khóa và tin trùng (phải là 0 dòng) =="
"${psql_cmd[@]}" -c "
  select 'sự_kiện' as loại, quote_version_id::text, material_id::text, count(*)
  from price_alert_events where kind = 'change'
  group by quote_version_id, material_id, delivery_month having count(*) > 1
  union all
  select 'tin', user_id::text, material_id::text, count(*)
  from price_alert_messages where kind = 'change'
  group by user_id, material_id, scan_run_id, kind having count(*) > 1"

echo "== Sự kiện theo mức và chiều (có gốc dự phòng hoặc báo tiếp) =="
"${psql_cmd[@]}" -c "
  select created_at::date as ngày, level as mức, direction as chiều, count(*) as số_sự_kiện,
         count(reference_age_days) as gốc_dự_phòng, count(prior_alert_price) as báo_tiếp
  from price_alert_events where created_at > now() - interval '${days} days'
  group by 1, 2, 3 order by 1, 2, 3"
