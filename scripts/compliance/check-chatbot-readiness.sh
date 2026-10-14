#!/usr/bin/env bash
# Kiểm tra các tài sản vận hành của chatbot (Telegram, kế hoạch 5.1) có đủ trong repo.
# Dùng: ROOT_DIR=/duong/dan bash scripts/compliance/check-chatbot-readiness.sh
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
RUNBOOK="docs/runbooks/deploy-vps-production.md"
failed=0

fail() {
  echo "Thiếu tài sản vận hành của chatbot: $1" >&2
  failed=1
}

require_file() {
  [[ -f "$ROOT_DIR/$1" ]] || fail "${2:-$1}"
}

require_text() {
  local file="$1" pattern="$2" label="$3"
  if [[ ! -f "$ROOT_DIR/$file" ]] || ! grep -q -E -- "$pattern" "$ROOT_DIR/$file"; then
    fail "$label ($file)"
  fi
}

# Chỉ tìm trong mục 16 đến hết file: từ khóa ở mục khác không phải hướng dẫn cho chatbot. Gom mục vào
# biến rồi mới grep (không dùng đường ống: `grep -q` thoát sớm làm `sed` nhận SIGPIPE, gặp pipefail
# thì kiểm tra báo thiếu oan).
runbook_section_16=""
if [[ -f "$ROOT_DIR/$RUNBOOK" ]]; then
  runbook_section_16="$(sed -n '/^## 16\. /,$p' "$ROOT_DIR/$RUNBOOK")"
fi

require_section_16() {
  local pattern="$1" label="$2"
  grep -q -E -- "$pattern" <<<"$runbook_section_16" || fail "$label ($RUNBOOK)"
}

# Chỉ tìm trong khối service `bot-worker` của compose production, bỏ dòng ghi chú: cùng một dòng nằm ở
# service khác (vd profile bị chuyển sang `worker`) hay đã bị comment thì không phải bot-worker có nó.
COMPOSE_PROD="docker-compose.prod.yml"
bot_worker_block=""
if [[ -f "$ROOT_DIR/$COMPOSE_PROD" ]]; then
  bot_worker_block="$(awk '
    /^  bot-worker:/ { in_block = 1; next }
    in_block && /^[^ #]/ { exit }
    in_block && /^  [^ #]/ { exit }
    in_block && !/^[[:space:]]*#/ { print }
  ' "$ROOT_DIR/$COMPOSE_PROD")"
fi

require_bot_worker() {
  local pattern="$1" label="$2"
  grep -q -E -- "$pattern" <<<"$bot_worker_block" || fail "$label ($COMPOSE_PROD)"
}

require_text "$RUNBOOK" '^## 16\. ' "mục 16 của runbook (Chatbot)"
require_section_16 'CHATBOT_ENABLED=false' "công tắc tắt khẩn cấp trong mục 16"
require_section_16 '--profile chatbot' "cách bật bot-worker trong mục 16"
require_section_16 'CHATBOT_PILOT_USER_EMAILS' "cách đặt danh sách pilot trong mục 16"
require_section_16 '--max-connections' "đăng ký lại webhook với max_connections trong mục 16"

require_text "$COMPOSE_PROD" '^  bot-worker:' "service bot-worker trong compose production"
require_bot_worker '^    profiles:' "profile chatbot của bot-worker"
require_bot_worker '^      - chatbot$' "profile chatbot của bot-worker"
require_bot_worker '^    restart: unless-stopped$' "restart của bot-worker"
require_bot_worker '^    stop_grace_period:' "stop_grace_period của bot-worker"
require_bot_worker '--check.*app\.bot_worker\.BotWorkerSettings' "healthcheck của bot-worker"

require_text ".env.production.example" '^CHATBOT_ENABLED=' "biến CHATBOT_ENABLED"
require_text ".env.production.example" '^CHATBOT_PILOT_USER_EMAILS=' "biến CHATBOT_PILOT_USER_EMAILS"
require_text ".env.production.example" '^BOT_MAX_ATTEMPTS=' "biến BOT_MAX_ATTEMPTS"

require_file "backend/alembic/versions/20261013_1000_create_bot_updates.py" "migration của hộp thư bot"
require_text "docker/observability/alert_rules.yml" 'alert: ChatbotQueueStuck' "luật cảnh báo hàng đợi kẹt"
require_text "docker/observability/alert_rules.yml" 'alert: ChatbotUpdatesFailing' "luật cảnh báo lỗi liên tiếp"
require_text "docker/observability/alert_rules.yml" 'alert: ChatbotMetricsUnavailable' "luật cảnh báo mất số đo"

if [[ "$failed" -ne 0 ]]; then
  exit 1
fi
echo "Tài sản vận hành của chatbot đầy đủ."
