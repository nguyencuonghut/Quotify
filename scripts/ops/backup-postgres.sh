#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKUP_ROOT="${BACKUP_ROOT:-$ROOT_DIR/backups}"
TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%dT%H%M%S)}"
OUTPUT_DIR="$BACKUP_ROOT/$TIMESTAMP"
OUTPUT_FILE="$OUTPUT_DIR/postgres.sql.gz"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-app}"

mkdir -p "$OUTPUT_DIR"

if [[ "${DRY_RUN:-false}" == "true" ]]; then
  echo "[dry-run] docker compose exec -T $POSTGRES_SERVICE pg_dump -U $POSTGRES_USER -d $POSTGRES_DB | gzip > $OUTPUT_FILE"
  exit 0
fi

docker compose exec -T "$POSTGRES_SERVICE" \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" | gzip > "$OUTPUT_FILE"

echo "Postgres backup written to $OUTPUT_FILE"
