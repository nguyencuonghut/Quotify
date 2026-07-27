#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: bash scripts/ops/restore-drill.sh <backup-timestamp-dir>" >&2
  exit 1
fi

BACKUP_DIR="$1"
POSTGRES_ARCHIVE="$BACKUP_DIR/postgres.sql.gz"
MINIO_ARCHIVE="$BACKUP_DIR/minio-data.tar.gz"

if [[ ! -f "$POSTGRES_ARCHIVE" ]]; then
  echo "Missing Postgres archive: $POSTGRES_ARCHIVE" >&2
  exit 1
fi

if [[ ! -f "$MINIO_ARCHIVE" ]]; then
  echo "Missing MinIO archive: $MINIO_ARCHIVE" >&2
  exit 1
fi

echo "Validated backup set:"
echo "- $POSTGRES_ARCHIVE"
echo "- $MINIO_ARCHIVE"

echo "Next steps:"
echo "1. Restore Postgres into an isolated environment:"
echo "   DRY_RUN=true bash scripts/ops/restore-postgres.sh \"$POSTGRES_ARCHIVE\""
echo "2. Restore MinIO into an isolated environment:"
echo "   DRY_RUN=true bash scripts/ops/restore-minio.sh \"$MINIO_ARCHIVE\""
echo "3. Run application smoke tests and document the outcome in the restore runbook."
