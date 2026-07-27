# FastApiVueBoilerplate

Repository này đang được chuẩn bị để trở thành boilerplate fullstack enterprise-grade với:

- FastAPI
- Vue 3 + TypeScript
- Docker dev/prod/test
- Postgres
- MinIO
- PrimeVue v4
- Pinia

## Trạng thái hiện tại

Hiện tại repository đã có:

- workflow cho AI agents
- memory bank cho project
- tài liệu thiết kế tổng thể
- kế hoạch triển khai `Phase 1: Scaffold`

Tài liệu chính:

- `docs/fullstack-boilerplate-design.md`
- `docs/phase-1-scaffold-implementation-plan.md`
- `AGENTS.md`

## Giai đoạn tiếp theo

Tiếp theo sẽ triển khai `Phase 1: Scaffold`:

- scaffold `backend/`
- scaffold `frontend/`
- docker compose cho dev/prod/test
- Postgres và MinIO
- lint, typecheck, test framework

## Chạy môi trường dev bằng Docker

```bash
docker compose up --build
```

Services mặc định:

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`
- Postgres: `127.0.0.1:55432`
- MinIO API: `http://127.0.0.1:59000`
- MinIO Console: `http://127.0.0.1:59001`
- Redis: chỉ dùng nội bộ trong Docker network, không bind host port mặc định

Các host port có thể đổi qua `.env`:

- `BACKEND_HOST_PORT`
- `FRONTEND_HOST_PORT`
- `POSTGRES_HOST_PORT`
- `MINIO_API_HOST_PORT`
- `MINIO_CONSOLE_HOST_PORT`

## Kiểm tra cấu hình production Docker

```bash
docker compose -f docker-compose.prod.yml config
```

Production scaffold hiện có:

- backend image target `prod`
- frontend static build target `prod`
- `reverse-proxy` Nginx route `/api/*` về backend và `/` về frontend
- không mount source code
- không public `postgres` hoặc `minio`

Port public mặc định của production scaffold:

- Reverse proxy: `http://127.0.0.1:8080`

Có thể đổi qua biến `PROXY_HOST_PORT`.

Audit log IP:

- Production Docker mặc định dùng subnet nội bộ `172.30.0.0/24` cho compose và
  `TRUSTED_PROXY_CIDRS=172.30.0.0/24` để backend chỉ tin IP forwarding từ Nginx
  reverse proxy.
- Nếu chạy server local trong LAN/VPN và backend nhận request trực tiếp, để
  `TRUSTED_PROXY_CIDRS` rỗng để audit ghi IP kết nối trực tiếp của máy người
  dùng.
- Nếu LAN/VPN vẫn đi qua reverse proxy nội bộ, đặt `TRUSTED_PROXY_CIDRS` đúng
  IP/CIDR của proxy đó.

## Chạy test bằng Docker

```bash
docker compose -f docker-compose.test.yml run --rm backend-test
docker compose -f docker-compose.test.yml run --rm frontend-test
docker compose -f docker-compose.test.yml run --rm e2e-test
```

Test profile hiện có:

- `backend-test`: `pytest`, `ruff`, `mypy`, `bandit`
- `frontend-test`: `lint`, `typecheck`, `test:unit`
- `e2e-test`: Playwright smoke test qua service `frontend-e2e`
- `postgres-test` và `minio-test` dùng volume riêng, tách khỏi dev data

## Quality gates trước khi commit

Root repo hiện có `Makefile` để gom toàn bộ quality gates:

```bash
make backend-check
make frontend-check
make check
```

Browser E2E được tách riêng:

```bash
make frontend-test-e2e
make frontend-check-e2e
```

Các target chi tiết:

```bash
# Backend
make backend-lint
make backend-format-check
make backend-typecheck
make backend-test
make backend-security
make backend-dependency-audit

# Frontend
make frontend-lint
make frontend-format-check
make frontend-typecheck
make frontend-test-unit
make frontend-test-e2e
make frontend-dependency-audit

# Security / dependency audit
make security-check

# Performance smoke
make perf-users-list
make perf-users-export
```

Target Docker tương ứng:

```bash
make docker-test-backend
make docker-test-frontend
make docker-test-e2e
make docker-test
```

Gợi ý dùng hằng ngày:

```bash
make check
make docker-test-e2e
```

Lý do: `make check` gom toàn bộ lint/format/typecheck/unit/security ổn định trên local, còn browser E2E phụ thuộc khả năng bind port của host nên có target riêng và có path Docker tương ứng.

## Phase 5 Hardening baseline

Repo hiện có baseline hardening ở mức Phase 5:

- Coverage report backend/frontend
- GitHub Actions CI tại `.github/workflows/ci.yml`
- Backend security headers middleware
- Rate limit cho endpoint nhạy cảm:
  - `POST /api/v1/auth/login`
  - `POST /api/v1/files/upload`
  - `POST /api/v1/users/avatar-upload`
  - `POST /api/v1/users/import`
  - `POST /api/v1/users/export`
- Query hardening cho list API với `limit <= 100`
- Backend dependency audit qua `pip-audit`
- Frontend dependency audit qua `npm audit`
- Performance smoke scripts:
  - `scripts/perf/check_users_list.py`
  - `scripts/perf/check_users_export.py`

Trạng thái verify gần nhất:

- Backend `pytest`, `ruff`, `mypy`: đã pass
- Frontend `lint`, `typecheck`, `test:unit`: đã pass
- `make perf-users-list` và `make perf-users-export`: đã sửa để chạy bằng backend Python env thay vì `python3` host
- `make backend-dependency-audit` và `make frontend-dependency-audit`: đã sửa để dùng cache writable trong `/tmp`
- Dependency audit và perf smoke từ host vẫn có thể bị chặn trong môi trường sandbox không có DNS hoặc không cho mở socket localhost

Nếu cần đổi cache cho `uv`, có thể truyền:

```bash
make backend-check UV_CACHE_DIR=/tmp/uv-cache
```

## Lưu ý

- Không commit file `.env`
- `vendor/` chỉ là thư mục reference local, không được track bởi Git
- Agent phải đọc `AGENTS.md`, `docs/agent-rules.md` và `memory-bank/*` trước khi làm việc

## Phase 6 Production Readiness baseline

Repo hiện có baseline Phase 6:

- backend structured JSON logging với `request_id`
- `/metrics` và `/ready`
- OpenTelemetry trace instrumentation baseline cho FastAPI, HTTPX, SQLAlchemy
- observability stack config tại `docker-compose.observability.yml`
- backup/restore scripts cho Postgres và MinIO
- runbooks cho backup/restore và deploy/rollback/restore
- compliance gate script:
  - `bash scripts/compliance/check-production-readiness.sh`
- production env mẫu:
  - `.env.production.example`

Lệnh hữu ích:

```bash
bash scripts/compliance/check-production-readiness.sh
DRY_RUN=true bash scripts/ops/backup-postgres.sh
DRY_RUN=true bash scripts/ops/backup-minio.sh
docker compose -f docker-compose.observability.yml config
```
