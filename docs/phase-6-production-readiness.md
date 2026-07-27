# Phase 6: Production Readiness

## Mục tiêu

Phase 6 đưa repo từ mức scaffold + hardening sang mức có baseline production-readiness rõ ràng:

- observability có thể cắm vào runtime thật
- backup/restore có script và runbook
- secret management có đường đi qua env file hoặc secret file
- SLO/alert/compliance có artifact để CI và vận hành kiểm tra

## Những gì đã được implement

### 1. Observability backend

- JSON structured logging với `request_id`
- `/metrics` theo chuẩn Prometheus
- `/ready` trả trạng thái readiness cho:
  - database
  - redis
  - minio
- OpenTelemetry trace instrumentation baseline cho:
  - FastAPI
  - HTTPX
  - SQLAlchemy

### 2. Observability stack config

- `docker-compose.observability.yml`
- `docker/observability/otel-collector.yaml`
- `docker/observability/prometheus.yml`
- `docker/observability/alert_rules.yml`

### 3. Secret management baseline

Backend settings hỗ trợ đọc secret từ file cho:

- `JWT_SECRET_KEY_FILE`
- `JWT_REFRESH_SECRET_KEY_FILE`
- `DATABASE_URL_FILE`
- `MINIO_ACCESS_KEY_FILE`
- `MINIO_SECRET_KEY_FILE`

Điều này cho phép dùng Docker secrets hoặc secret volume thay vì hardcode vào `.env`.

### 4. Backup / restore

Scripts:

- `bash scripts/ops/backup-postgres.sh`
- `bash scripts/ops/backup-minio.sh`
- `bash scripts/ops/restore-postgres.sh <backup.sql.gz>`
- `bash scripts/ops/restore-minio.sh <backup.tar.gz>`
- `bash scripts/ops/restore-drill.sh <backup-dir>`

### 5. Compliance gate

Script:

```bash
bash scripts/compliance/check-production-readiness.sh
```

Script này kiểm tra:

- production compose tồn tại và parse được
- observability compose tồn tại và parse được
- runbook bắt buộc tồn tại
- backup/restore assets tồn tại

## Trạng thái verify

Đã verify local trong repo:

- backend `pytest`, `ruff`, `mypy`
- metrics/readiness/secret-file tests
- frontend `lint`, `typecheck`, `test:unit`

Chưa verify end-to-end trong phiên sandbox hiện tại:

- dependency audit live từ internet
- performance smoke host-side tới API runtime
- observability stack `up` thật
- restore thật vào môi trường tách biệt

## Lệnh khuyến nghị

```bash
make backend-check
make frontend-check
bash scripts/compliance/check-production-readiness.sh
```

```bash
DRY_RUN=true bash scripts/ops/backup-postgres.sh
DRY_RUN=true bash scripts/ops/backup-minio.sh
DRY_RUN=true bash scripts/ops/restore-postgres.sh backups/<timestamp>/postgres.sql.gz
DRY_RUN=true bash scripts/ops/restore-minio.sh backups/<timestamp>/minio-data.tar.gz
```

```bash
docker compose -f docker-compose.observability.yml up -d
```
