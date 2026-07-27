#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKUP_ROOT="${BACKUP_ROOT:-$ROOT_DIR/backups}"
TIMESTAMP="${TIMESTAMP:-$(date +%Y%m%dT%H%M%S)}"
OUTPUT_DIR="$BACKUP_ROOT/$TIMESTAMP"
OUTPUT_FILE="$OUTPUT_DIR/minio-data.tar.gz"
MINIO_SERVICE="${MINIO_SERVICE:-minio}"

mkdir -p "$OUTPUT_DIR"

if [[ "${DRY_RUN:-false}" == "true" ]]; then
  echo "[dry-run] docker compose cp $MINIO_SERVICE:/data - | gzip > $OUTPUT_FILE"
  exit 0
fi

docker compose cp "$MINIO_SERVICE":/data - | gzip > "$OUTPUT_FILE"

echo "MinIO backup written to $OUTPUT_FILE"
