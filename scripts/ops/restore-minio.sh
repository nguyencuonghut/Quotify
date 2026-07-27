#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: bash scripts/ops/restore-minio.sh <backup-file.tar.gz>" >&2
  exit 1
fi

BACKUP_FILE="$1"
MINIO_SERVICE="${MINIO_SERVICE:-minio}"

if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "Backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

if [[ "${DRY_RUN:-false}" == "true" ]]; then
  echo "[dry-run] gunzip -c $BACKUP_FILE | docker compose cp - $MINIO_SERVICE:/"
  exit 0
fi

gunzip -c "$BACKUP_FILE" | docker compose cp - "$MINIO_SERVICE":/

echo "MinIO restore completed from $BACKUP_FILE"
