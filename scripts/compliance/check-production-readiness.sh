#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

required_files=(
  "docker-compose.prod.yml"
  "docker-compose.observability.yml"
  "docker/observability/otel-collector.yaml"
  "docker/observability/prometheus.yml"
  "docker/observability/alert_rules.yml"
  "docs/runbooks/backup-restore.md"
  "docs/runbooks/deploy-rollback-restore.md"
  "docs/phase-6-production-readiness.md"
  "scripts/ops/backup-postgres.sh"
  "scripts/ops/backup-minio.sh"
  "scripts/ops/restore-postgres.sh"
  "scripts/ops/restore-minio.sh"
  "scripts/ops/restore-drill.sh"
)

for relative_path in "${required_files[@]}"; do
  if [[ ! -f "$ROOT_DIR/$relative_path" ]]; then
    echo "Missing required production-readiness asset: $relative_path" >&2
    exit 1
  fi
done

bash "$ROOT_DIR/scripts/compliance/check-price-alert-readiness.sh"
bash "$ROOT_DIR/scripts/compliance/check-chatbot-readiness.sh"

docker compose -f "$ROOT_DIR/docker-compose.prod.yml" config >/dev/null
# `config` thường bỏ qua service có profile; nêu profile để lỗi trong bot-worker không lọt.
docker compose -f "$ROOT_DIR/docker-compose.prod.yml" --profile chatbot config >/dev/null
docker compose -f "$ROOT_DIR/docker-compose.observability.yml" config >/dev/null

echo "Production readiness compliance assets are present and compose files are valid."
