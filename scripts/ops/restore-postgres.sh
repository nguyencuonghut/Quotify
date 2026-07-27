#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: bash scripts/ops/restore-postgres.sh <backup-file.sql.gz>" >&2
  exit 1
fi

BACKUP_FILE="$1"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-app}"

if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "Backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

if [[ "${DRY_RUN:-false}" == "true" ]]; then
  echo "[dry-run] gunzip -c $BACKUP_FILE | docker compose exec -T $POSTGRES_SERVICE psql -U $POSTGRES_USER -d $POSTGRES_DB"
  exit 0
fi

gunzip -c "$BACKUP_FILE" | docker compose exec -T "$POSTGRES_SERVICE" \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"

echo "Postgres restore completed from $BACKUP_FILE"
