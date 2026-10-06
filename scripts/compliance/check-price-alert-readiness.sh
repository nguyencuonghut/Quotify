#!/usr/bin/env bash
# Kiểm tra các tài sản vận hành của thông báo giá (Telegram 1B/1C) có đủ trong repo.
# Dùng: ROOT_DIR=/duong/dan bash scripts/compliance/check-price-alert-readiness.sh
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
failed=0

fail() {
  echo "Thiếu tài sản vận hành của thông báo giá: $1" >&2
  failed=1
}

require_file() {
  [[ -f "$ROOT_DIR/$1" ]] || fail "$1"
}

require_text() {
  local file="$1" pattern="$2" label="$3"
  if [[ ! -f "$ROOT_DIR/$file" ]] || ! grep -q -E -- "$pattern" "$ROOT_DIR/$file"; then
    fail "$label ($file)"
  fi
}

require_file "docker/nginx/maintenance.conf"
require_text "docs/runbooks/deploy-vps-production.md" '^## 13\. ' "mục 13 của runbook (đưa 1B lên production)"
require_text "docs/runbooks/deploy-vps-production.md" '^## 14\. ' "mục 14 của runbook (phát hành 1C)"
require_text ".env.production.example" '^PRICE_ALERT_RECIPIENT_EMAILS=' "biến PRICE_ALERT_RECIPIENT_EMAILS"
require_text ".env.production.example" '^APP_PUBLIC_URL=' "biến APP_PUBLIC_URL"
require_text "docker/observability/alert_rules.yml" 'quotify_price_alert_scan_lag_seconds' "luật cảnh báo quét trễ"
require_text "docker/observability/alert_rules.yml" 'quotify_price_alert_metrics_up' "luật cảnh báo mất số đo"

if [[ "$failed" -ne 0 ]]; then
  exit 1
fi
echo "Tài sản vận hành của thông báo giá đầy đủ."
