#!/usr/bin/env bash
# Xem trạng thái Telegram trong DB DEV (chỉ đọc). Dùng khi kiểm thử tay trên dev.
# Không in telegram_user_id đầy đủ (chỉ 4 số cuối), không in mã liên kết (DB chỉ lưu băm).
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root_dir"

psql_cmd=(docker compose exec -T postgres psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-app}")

echo "(Giờ hiển thị là UTC; giờ Việt Nam = UTC+7)"
echo "== Liên kết Telegram (mới nhất ở cuối) =="
"${psql_cmd[@]}" -c "
  select u.email, right(a.telegram_user_id::text, 4) as tg_cuoi, a.status, a.revoked_reason,
         a.username, a.first_name, to_char(a.linked_at, 'HH24:MI:SS') as linked_at
  from telegram_accounts a join users u on u.id = a.user_id
  order by a.linked_at"

echo "== Đường dẫn liên kết còn hiệu lực =="
"${psql_cmd[@]}" -c "
  select u.email, to_char(t.expires_at, 'HH24:MI:SS') as het_han_luc,
         greatest(0, round(extract(epoch from (t.expires_at - now()))))::int as con_giay
  from telegram_link_tokens t join users u on u.id = t.user_id
  where t.used_at is null and t.expires_at > now()
  order by t.expires_at"

echo "== Audit Telegram (10 sự kiện gần nhất) =="
"${psql_cmd[@]}" -c "
  select to_char(created_at, 'HH24:MI:SS') as luc, action,
         metadata_json->>'channel' as kenh, metadata_json->>'reason' as ly_do
  from (select * from audit_logs where action like 'telegram.%' order by created_at desc limit 10) x
  order by created_at"

echo "== Update Telegram đã xử lý =="
"${psql_cmd[@]}" -tA -c "select count(*) || ' update (dọn tự động sau 3 ngày)' from telegram_processed_updates"
