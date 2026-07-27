# Kế Hoạch Triển Khai Phase 1: Scaffold

Ngày tạo: 09/06/2026

## Mục tiêu

Phase 1 tạo nền móng kỹ thuật cho boilerplate fullstack enterprise-grade.

Kết thúc phase này, repository phải có:

- `backend/` FastAPI scaffold.
- `frontend/` Vue 3 + Vite + TypeScript scaffold.
- Docker cho dev, production và test.
- Postgres và MinIO chạy bằng Docker Compose.
- Linter, formatter, typecheck cho backend/frontend.
- Test framework tự động cho backend/frontend.
- Cấu trúc sẵn sàng mở rộng sang auth, RBAC, dashboard và import/export ở các phase sau.
- Frontend foundation phải mobile responsive ngay từ scaffold.

## Phạm vi

### Trong scope

- Tạo cấu trúc thư mục backend/frontend.
- Cấu hình Python/FastAPI project.
- Cấu hình Vue 3/TypeScript project.
- Cấu hình Dockerfile dev/prod cho backend và frontend.
- Cấu hình `docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.test.yml`.
- Cấu hình Postgres, MinIO, optional Redis nếu cần chuẩn bị background jobs.
- Cấu hình lint, format, typecheck, test.
- Tạo health endpoint và smoke page tối thiểu.
- Tạo README hoặc docs ngắn cho cách chạy dev/test.

### Ngoài scope

- Chưa implement full authentication.
- Chưa implement RBAC đầy đủ.
- Chưa implement admin dashboard hoàn chỉnh.
- Chưa implement User CRUD.
- Chưa implement import/export job thật.
- Chưa implement production observability đầy đủ.

Những phần ngoài scope chỉ cần scaffold/config đủ để phase sau mở rộng.

## Nguyên tắc bắt buộc

1. Không hardcode secret.
2. Không tạo source app nếu chưa có lint/test command tương ứng.
3. Docker phải có dev, prod và test path rõ ràng.
4. Backend route không chứa business logic.
5. Frontend không dùng inline style.
6. Frontend không nhồi business logic trong `.vue`.
7. Frontend không dùng style block trong `.vue`.
8. Dark/light theme phải đi qua token/class dùng chung.
9. Test framework phải chạy được trong local và Docker test profile.
10. File config phải có `.env.example`, không commit `.env`.
11. Layout và shared UI phải responsive cho mobile, tablet và desktop.

## Deliverables

### Backend

Tạo cấu trúc:

```text
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── repositories/
│   ├── auth/
│   ├── storage/
│   └── main.py
├── alembic/
├── tests/
├── pyproject.toml
└── Dockerfile
```

Backend tối thiểu:

- `GET /health`
- `GET /api/v1/health`
- settings typed bằng Pydantic Settings hoặc giải pháp tương đương.
- DB session scaffold.
- MinIO client scaffold.
- logging scaffold có request id/correlation id nếu đơn giản được.

Backend tools:

- FastAPI `0.136.3`.
- Python `3.12` hoặc `3.13`.
- Ruff.
- mypy hoặc pyright.
- pytest.
- pytest-asyncio.
- pytest-cov.
- httpx.
- Bandit.

### Frontend

Tạo cấu trúc:

```text
frontend/
├── src/
│   ├── api/
│   ├── assets/
│   ├── components/
│   ├── composables/
│   ├── layouts/
│   ├── pages/
│   ├── router/
│   ├── stores/
│   ├── styles/
│   ├── types/
│   ├── App.vue
│   └── main.ts
├── tests/
├── eslint.config.ts
├── package.json
├── tsconfig.json
├── vite.config.ts
└── Dockerfile
```

Frontend tối thiểu:

- Vue 3 + TypeScript + Vite.
- Vue Router.
- Pinia.
- PrimeVue v4.
- PrimeIcons.
- VeeValidate + Zod.
- `theme.store.ts` scaffold.
- `layout.store.ts` scaffold.
- Health/smoke page tối thiểu.
- Dark/light mode token layer ban đầu.
- Không dùng style block trong `.vue`.
- Responsive layout scaffold ban đầu cho mobile/tablet/desktop.

Quy tắc `.vue`:

- Component/page phức tạp dùng external template/logic/style.
- Business logic nằm trong `composables/`, `stores/`, `api/`, `services/`.
- Không dùng inline style.
- Không dùng style block trong `.vue`.

Frontend tools:

- ESLint.
- Prettier.
- vue-tsc.
- Vitest.
- Vue Test Utils.
- Playwright.
- MSW hoặc API mock layer nếu cần.

### Docker

Tạo:

```text
docker-compose.yml
docker-compose.prod.yml
docker-compose.test.yml
docker/
├── backend/
├── frontend/
└── nginx/
```

Dev compose:

- backend dev container có hot reload.
- frontend dev container chạy Vite.
- Postgres.
- MinIO.
- optional Redis.

Production compose:

- backend production image.
- frontend static build.
- Nginx hoặc Caddy reverse proxy.
- không mount source code.
- không expose Postgres/MinIO public nếu không cần.

Test compose:

- backend test runner.
- frontend test runner.
- e2e test runner.
- Postgres test database.
- MinIO test bucket.

## Thứ tự triển khai

### Bước 1: Chuẩn bị repository

1. Kiểm tra `.gitignore`.
2. Tạo `.env.example`.
3. Đảm bảo `vendor/` không bị track.
4. Tạo README ngắn nếu chưa có.

Kết quả:

- Repo sạch, không có nested Git repo ảnh hưởng commit.
- `.env.example` có đủ biến dev cơ bản.

### Bước 2: Scaffold backend

1. Tạo thư mục `backend/`.
2. Tạo `pyproject.toml`.
3. Cài dependency FastAPI và tooling.
4. Tạo `app/main.py`.
5. Tạo route health.
6. Tạo settings.
7. Tạo DB/MinIO scaffold.
8. Tạo test health endpoint.

Kết quả:

- Backend chạy local.
- Backend test pass.
- Lint/typecheck command có sẵn.

### Bước 3: Scaffold frontend

1. Tạo `frontend/` bằng Vite Vue TypeScript.
2. Cài PrimeVue v4, PrimeIcons, Pinia, Vue Router.
3. Cài VeeValidate + Zod.
4. Cấu hình ESLint, Prettier, vue-tsc.
5. Cấu hình Vitest + Vue Test Utils.
6. Cấu hình Playwright smoke test.
7. Tạo layout/smoke page tối thiểu.
8. Tạo theme token layer và dark/light toggle scaffold.
9. Đảm bảo admin layout và smoke page responsive trên mobile.

Kết quả:

- Frontend chạy local.
- Unit test pass.
- Typecheck pass.
- E2E smoke test có thể chạy.
- Layout không vỡ ở viewport mobile cơ bản.

### Bước 4: Docker dev

1. Tạo backend Dockerfile target dev.
2. Tạo frontend Dockerfile target dev.
3. Tạo `docker-compose.yml`.
4. Cấu hình Postgres.
5. Cấu hình MinIO.
6. Cấu hình healthcheck cơ bản.

Kết quả:

```bash
docker compose up --build
```

phải chạy được backend, frontend, Postgres và MinIO.

### Bước 5: Docker production

1. Tạo backend Dockerfile target prod.
2. Tạo frontend static build target.
3. Tạo reverse proxy config.
4. Tạo `docker-compose.prod.yml`.
5. Đảm bảo không mount source code trong production compose.

Kết quả:

```bash
docker compose -f docker-compose.prod.yml config
```

phải hợp lệ.

### Bước 6: Docker test profile

1. Tạo `docker-compose.test.yml`.
2. Tạo service `backend-test`.
3. Tạo service `frontend-test`.
4. Tạo service `e2e-test`.
5. Tách Postgres/MinIO test data khỏi dev data.

Kết quả:

```bash
docker compose -f docker-compose.test.yml run --rm backend-test
docker compose -f docker-compose.test.yml run --rm frontend-test
docker compose -f docker-compose.test.yml run --rm e2e-test
```

phải có command rõ ràng, kể cả khi Phase 1 mới chỉ có smoke test.

### Bước 7: Quality gates

Tạo script hoặc npm/make command để chạy:

```bash
# Backend
ruff check backend
ruff format --check backend
mypy backend
pytest backend/tests --cov=backend/app
bandit -r backend/app

# Frontend
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run typecheck
npm --prefix frontend run test:unit
npm --prefix frontend run test:e2e
```

Kết quả:

- Developer có một bộ command rõ ràng trước khi commit.
- Docker test profile có command tương ứng.

## Acceptance Criteria

Phase 1 hoàn thành khi:

1. `backend/` tồn tại và có health endpoint.
2. `frontend/` tồn tại và có smoke page.
3. `docker-compose.yml` chạy được dev stack.
4. `docker-compose.prod.yml` hợp lệ và có production build path.
5. `docker-compose.test.yml` có backend/frontend/e2e test runner.
6. Backend lint/typecheck/test command chạy được.
7. Frontend lint/typecheck/test command chạy được.
8. `.env.example` có đủ biến cần thiết.
9. `.env` không bị commit.
10. `vendor/` không bị track.
11. Tài liệu chạy dev/test được cập nhật.

## Rủi ro và cách giảm thiểu

### Rủi ro 1: Scaffold quá rộng

Giảm thiểu:

- Phase 1 chỉ tạo nền và smoke tests.
- Auth/RBAC/import-export để phase sau.

### Rủi ro 2: Docker dev/prod/test bị lệch nhau

Giảm thiểu:

- Dùng multi-stage Dockerfile.
- Dùng compose riêng nhưng chung env naming.
- Test `docker compose config` cho từng file.

### Rủi ro 3: Frontend vi phạm rule tách logic/template

Giảm thiểu:

- Tạo page mẫu đúng pattern ngay từ đầu.
- ESLint rule hoặc convention check nếu có thể.

### Rủi ro 4: Test framework có nhưng không dùng được trong Docker

Giảm thiểu:

- Phase 1 phải chạy test qua Docker test profile.
- Không chỉ test local.

## Ghi chú cho agent implement

Trước khi implement Phase 1:

1. Đọc `AGENTS.md`.
2. Đọc `docs/agent-rules.md`.
3. Đọc `memory-bank/*`.
4. Đọc `docs/fullstack-boilerplate-design.md`.
5. Không phỏng đoán version nếu chưa xác minh.
6. Nếu chọn tool khác tài liệu, phải ghi rõ lý do và cập nhật memory bank.

Khi kết thúc Phase 1:

1. Cập nhật `memory-bank/techContext.md`.
2. Cập nhật `memory-bank/progress.md`.
3. Ghi journal bằng `scripts/agent-task-close.sh`.
