# Thiết Kế Boilerplate Fullstack FastAPI + Vue 3

Ngày tạo: 09/06/2026

## Mục tiêu

Biến repository này thành boilerplate fullstack có thể dùng để khởi tạo nhanh các ứng dụng quản trị nội bộ, SaaS admin panel, hoặc hệ thống nghiệp vụ cần authentication, phân quyền, file storage và dashboard.

Boilerplate phải có:

- Backend FastAPI hiện đại, typed, dễ test.
- Frontend Vue 3 + TypeScript theo Composition API.
- Admin dashboard tham khảo Sakai Vue.
- Authentication đầy đủ nhưng không có chức năng tự register user.
- Quản lý user, role, permission.
- Docker cho cả môi trường dev và production.
- Postgres làm database chính.
- MinIO làm object storage.
- Auto test framework cho cả backend và frontend.
- Linter, formatter, typecheck cho cả backend và frontend.
- Giao diện phải mobile responsive, không chỉ tối ưu cho desktop admin.
- Font mặc định của giao diện là `Be Vietnam Pro`.
- Timezone nghiệp vụ mặc định là `Asia/Ho_Chi_Minh` (`GMT+7`).

## Nguồn tham khảo đã xác minh

- FastAPI mới nhất trên PyPI tại thời điểm 09/06/2026 là `0.136.3`, phát hành ngày 23/05/2026.
- FastAPI package yêu cầu Python `>=3.10` và khuyến nghị cài bằng `fastapi[standard]`.
- PrimeVue v4 là thế hệ mới, dùng styled mode dựa trên design token và CSS variables, phù hợp cho dark/light mode.
- Sakai là Vue application template miễn phí dựa trên Vite, có source tại `primefaces/sakai-vue`.
- Sakai có theme sáng/tối và menu mode kiểu Static/Overlay.
- Repo `primefaces/sakai-vue` release mới nhất hiển thị là `5.0.0` ngày 02/02/2026, package đang dùng `primevue ^4.5.4`.
- Vue SFC hỗ trợ tách block bằng `src`, ví dụ `template src`, `style src`, `script src`.
- Vue `<script setup>` không dùng được với `src`, nên nếu bắt buộc tách logic khỏi `.vue`, không dùng `script setup src`.

## Tech Stack Đề Xuất

### Backend

- Python: `3.12` hoặc `3.13`.
- FastAPI: pin ban đầu `fastapi[standard]==0.136.3`.
- Pydantic: v2, đi theo FastAPI hiện tại.
- SQLAlchemy: ORM chính.
- Alembic: migration.
- asyncpg: Postgres async driver.
- JWT: access token + refresh token.
- Passlib hoặc Argon2/bcrypt: hash password.
- MinIO Python SDK hoặc boto3-compatible client: object storage.
- Background job runner: Celery/RQ/Arq hoặc FastAPI-compatible worker cho import/export nặng.
- Redis: broker/cache/job status nếu chọn Celery/RQ hoặc cần cache tập trung.
- pytest + pytest-asyncio: test.
- httpx: test API.
- pytest-cov: coverage.
- testcontainers hoặc Docker Compose test profile: integration test với Postgres/MinIO thật.
- Ruff: lint + format.
- mypy hoặc pyright: typecheck.
- Bandit: security scan.
- Timezone chuẩn của application: `Asia/Ho_Chi_Minh` (`GMT+7`) cho mọi business-facing date/time rule.

### Frontend

- Vue 3.
- TypeScript.
- Vite.
- Vue Router.
- Pinia.
- PrimeVue v4.
- PrimeIcons.
- Sakai Vue làm nguồn tham khảo layout, theme và dashboard.
- VeeValidate + Zod: form validation.
- Axios hoặc native fetch wrapper typed theo OpenAPI.
- ESLint.
- Prettier.
- vue-tsc.
- Vitest + Vue Test Utils: unit/component test.
- Playwright: E2E test.
- MSW hoặc API mock layer: test frontend không phụ thuộc backend thật khi cần.
- Responsive-first layout behavior cho mobile, tablet và desktop.
- Typography chuẩn toàn hệ thống: `Be Vietnam Pro`.
- Mọi formatter ngày giờ phải nhận timezone rõ ràng, mặc định là `Asia/Ho_Chi_Minh`.
- Mọi field bắt buộc trong form phải có dấu sao đỏ ở label để nhắc người dùng trước khi submit.

### Infrastructure

- Docker.
- Docker Compose.
- Dockerfile riêng cho dev và production hoặc multi-stage Dockerfile có target `dev`/`prod`.
- Postgres.
- MinIO.
- Backend API container.
- Frontend dev container.
- Frontend production image build static assets.
- Nginx hoặc Caddy reverse proxy cho production.
- Observability stack: OpenTelemetry, Prometheus-compatible metrics, structured logs, tracing backend tùy môi trường.
- Secret management: Docker secrets, SOPS, Vault hoặc cloud secret manager tùy deployment target.

## Kiến Trúc Tổng Quan

```text
root/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── auth/
│   │   ├── storage/
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── assets/
│   │   ├── components/
│   │   ├── composables/
│   │   ├── layouts/
│   │   ├── pages/
│   │   ├── router/
│   │   ├── stores/
│   │   ├── styles/
│   │   ├── types/
│   │   └── main.ts
│   ├── eslint.config.ts
│   ├── package.json
│   └── Dockerfile
├── docker/
│   ├── backend/
│   ├── frontend/
│   └── nginx/
├── docker-compose.yml
├── docker-compose.prod.yml
├── docker-compose.test.yml
├── docs/
└── scripts/
```

## Backend Design

### Module chính

Backend chia theo domain và tầng trách nhiệm:

- `api/`: route FastAPI, dependency injection, response status.
- `schemas/`: Pydantic request/response DTO.
- `models/`: SQLAlchemy models.
- `repositories/`: query database.
- `services/`: business logic.
- `auth/`: password hashing, JWT, permission guards.
- `storage/`: MinIO adapter.
- `core/`: settings, logging, CORS, config.
- `db/`: session, engine, migration helpers.

Route không chứa business logic. Route chỉ validate input, gọi service và trả response.

### Authentication

Boilerplate hỗ trợ:

- Login bằng email + password.
- Refresh token.
- Logout.
- Lấy profile hiện tại.
- Đổi mật khẩu.
- Admin reset password.
- Không có endpoint public register.

User mới chỉ được tạo bởi admin có quyền phù hợp.

Trong module quản lý user, ảnh đại diện phải hỗ trợ upload ảnh thật qua storage của hệ thống. Không dùng pattern nhập tay `avatar URL` từ nguồn bên ngoài làm UX mặc định cho create/edit user.

### Authorization

RBAC tối thiểu:

- `users`
- `roles`
- `permissions`
- `user_roles`
- `role_permissions`

Permission nên dùng dạng string ổn định:

```text
users.read
users.create
users.update
users.delete
roles.read
roles.create
roles.update
roles.delete
dashboard.read
files.upload
files.read
```

FastAPI dependency mẫu:

```python
require_permission("users.update")
```

### Database

Postgres là database duy nhất cho application state.

Các bảng nền tảng:

- `users`
- `roles`
- `permissions`
- `user_roles`
- `role_permissions`
- `refresh_tokens`
- `audit_logs`
- `files`
- `import_jobs`
- `import_job_errors`
- `export_jobs`

Migration bắt buộc dùng Alembic. Không sửa schema bằng tay trong runtime.

### MinIO

MinIO dùng cho:

- avatar
- tài liệu upload
- attachment nội bộ
- file export nếu cần

Backend không trả trực tiếp path nội bộ của object. API trả signed URL hoặc proxy download tùy policy.

### Backend Quality Gate

Backend test framework:

- `pytest`: test runner chính.
- `pytest-asyncio`: async test.
- `httpx.AsyncClient`: test FastAPI route.
- `pytest-cov`: coverage.
- `testcontainers` hoặc Docker Compose test profile: integration test với Postgres/MinIO thật.

Test layers:

- Unit test cho service, auth, permission policy.
- API test cho route.
- Integration test cho database migration, repository, MinIO adapter.
- Regression test cho bug đã fix.

Các lệnh chuẩn:

```bash
ruff check backend
ruff format backend
mypy backend
pytest backend/tests --cov=backend/app
bandit -r backend/app
```

Mọi endpoint authentication, authorization và file upload phải có test.

## Frontend Design

### Layout Admin

Frontend tham khảo Sakai Vue, nhưng không copy mù quáng. Những phần nên kế thừa:

- sidebar navigation
- topbar
- user menu
- breadcrumb
- responsive layout
- dashboard card/grid
- dark/light mode
- PrimeVue theme tokens

Các page ban đầu:

- Login
- Dashboard
- Users
- Roles
- Role detail
- Profile
- Forbidden
- Not found

### Mobile Responsive

Boilerplate không được xem admin dashboard là giao diện desktop-only.

Yêu cầu bắt buộc:

- Layout phải dùng responsive breakpoints rõ ràng cho mobile, tablet và desktop.
- Sidebar/topbar/menu phải có hành vi phù hợp trên màn hình nhỏ, ví dụ overlay drawer thay vì luôn cố định.
- DataTable, form, dialog, card grid và action bar phải usable trên mobile mà không vỡ layout.
- Không được phụ thuộc vào hover-only interaction cho các hành vi quan trọng.
- Spacing, typography, hit area và overflow phải được kiểm tra trên viewport nhỏ.

Responsive phải là system behavior dùng chung, không xử lý chắp vá theo từng page.

### Dark/Light Mode

Dark/light mode dùng PrimeVue v4 styled mode và design token/CSS variables.

State theme lưu ở Pinia và localStorage:

```text
stores/theme.store.ts
```

Không dùng inline style để đổi màu. Theme chỉ đi qua class, token hoặc CSS variables.

Style dark/light mode là yêu cầu bắt buộc cấp hệ thống, không được xử lý rời rạc theo từng page.

Các thành phần sau phải đồng nhất màu sắc, trạng thái hover/focus/active/disabled và contrast ở mọi page:

- button
- menu/sidebar
- topbar/header
- breadcrumb
- datatable
- form input
- dialog
- toast/notification
- tab/menu item
- card/panel

Quy tắc triển khai:

- Dùng token trung tâm cho màu semantic như `primary`, `surface`, `text`, `muted`, `border`, `danger`, `success`, `warning`, `info`.
- Không hardcode màu trực tiếp trong component hoặc page.
- Không tạo màu riêng cho từng page nếu chưa thêm token vào theme layer.
- Mọi component PrimeVue phải dùng cùng preset/theme config.
- DataTable, Menu, Button và Header là nhóm kiểm tra bắt buộc khi đổi theme.
- Theme switch phải áp dụng tức thì cho toàn app, không cần reload page.

Nếu một page cần màu đặc biệt theo domain, màu đó phải được định nghĩa thành token hoặc class semantic dùng lại được, không viết inline style.

### Quy tắc tách `.vue`

Yêu cầu của project: không để business logic trong `.vue`, không dùng inline style, tách logic và template rõ ràng.

Ngoài ra, không dùng style block trong `.vue`. Style phải nằm trong `src/styles/` tập trung, ưu tiên `.scss`, với class naming rõ ràng.

Vì Vue `<script setup>` không hỗ trợ `src`, áp dụng quy ước sau:

1. Với page hoặc component phức tạp, dùng external block:

```vue
<template src="./UsersPage.template.html"></template>
<script lang="ts" src="./UsersPage.logic.ts"></script>
<style scoped src="./UsersPage.css"></style>
```

2. File `*.logic.ts` dùng Composition API qua `defineComponent({ setup() { ... } })`.

3. Business logic phức tạp phải nằm trong:

```text
src/composables/
src/stores/
src/api/
src/services/
```

4. File `.vue` chỉ là shell nối template, logic và style.

5. Component nhỏ có thể dùng inline `<template>` nếu không có logic đáng kể, nhưng vẫn không được dùng inline style.

### Cấu trúc page frontend

Ví dụ page Users:

```text
frontend/src/pages/users/
├── UsersPage.vue
├── UsersPage.template.html
├── UsersPage.logic.ts
├── UsersPage.css
├── useUsersTable.ts
└── users.form.ts
```

### Form Validation

Form dùng VeeValidate + Zod:

- Zod định nghĩa schema và type.
- VeeValidate quản lý form state, touched, dirty, error.
- PrimeVue input nhận error từ form field.

Không validate thủ công rải rác trong template.

### State Management

Pinia stores:

- `auth.store.ts`
- `theme.store.ts`
- `user.store.ts`
- `role.store.ts`
- `layout.store.ts`

API call không đặt trực tiếp trong template. Page logic gọi composable hoặc store action.

### Frontend Quality Gate

Frontend test framework:

- `Vitest`: unit test.
- `@vue/test-utils`: component test.
- `Playwright`: E2E test.
- `MSW` hoặc API mock layer: mock API trong unit/component test.

Test layers:

- Unit test cho composable.
- Store test cho Pinia.
- Component test cho form, table, dialog.
- E2E test cho login, dashboard access, user CRUD, role CRUD, dark/light mode.
- Visual/theme regression test cho các component shared: Button, Menu, Header, DataTable, Form Input, Dialog.

Các lệnh chuẩn:

```bash
npm run lint
npm run format
npm run typecheck
npm run test:unit
npm run test:e2e
```

ESLint phải chặn:

- inline style trong Vue template
- unused imports
- `any` không có lý do
- logic phức tạp trong `.vue`
- import vòng lặp

## Enterprise Requirements

Boilerplate này phải được thiết kế ở mức enterprise, không chỉ là CRUD demo.

Yêu cầu enterprise gồm:

- User import/export có job async, trạng thái tiến trình, audit log và kiểm soát quyền.
- DataTable phải chịu được hàng vạn dòng bằng server-side pagination/filter/sort và virtual scroll khi phù hợp.
- Import/export file nặng phải xử lý theo chunk/stream, không đọc toàn bộ file vào memory.
- Security phải có baseline rõ ràng cho auth, authorization, file upload, audit, rate limit và secrets.
- Performance phải được đo bằng test hoặc benchmark tối thiểu, không chỉ cảm tính.

### User Import/Export

User import/export là tính năng bắt buộc của module User.

Import hỗ trợ:

- CSV.
- XLSX nếu business cần.
- Upload file lên MinIO trước, sau đó backend tạo import job.
- Validate schema trước khi ghi database.
- Dry-run mode để kiểm tra lỗi mà chưa ghi dữ liệu.
- Batch insert/update theo chunk.
- Idempotency key để tránh import trùng khi retry.
- Progress tracking: pending, running, completed, failed, cancelled.
- Error report theo từng dòng.
- Audit log cho người import, thời gian, file, số dòng thành công/thất bại.

Export hỗ trợ:

- CSV.
- XLSX nếu cần.
- Export theo filter hiện tại của DataTable.
- Export async nếu dataset lớn.
- File export lưu tạm trên MinIO.
- Signed URL có thời hạn.
- Audit log cho request export.

Không được export password hash, token, secret hoặc field nhạy cảm.

Permission đề xuất:

```text
users.import
users.export
users.import.cancel
users.import.read
users.export.read
```

### Performance Backend

Backend phải được thiết kế để xử lý dữ liệu lớn:

- API list dùng server-side pagination, filter, sort.
- Không trả hàng vạn dòng trong một response thông thường.
- Dùng cursor pagination cho dataset lớn hoặc dữ liệu có update liên tục.
- Dùng limit/offset chỉ cho dataset nhỏ hoặc admin table đơn giản.
- Tạo index cho các cột filter/sort phổ biến.
- Query phải tránh N+1.
- Response schema phải gọn, không trả field không cần thiết.
- Endpoint nặng phải có timeout, cancellation hoặc job async.
- Export lớn dùng streaming hoặc background job.
- Import lớn dùng chunk processing.
- File upload lớn đi qua multipart/chunk hoặc presigned upload nếu cần.
- MinIO operation phải có retry và timeout.

Ngưỡng thiết kế ban đầu:

- DataTable phải hoạt động tốt với `10,000+` records.
- Import/export phải thiết kế cho file lớn hơn `50MB`.
- Export lớn không block request thread.
- Import lỗi một dòng không làm mất toàn bộ báo cáo lỗi.

### Performance Frontend

Frontend phải được thiết kế cho bảng dữ liệu lớn:

- PrimeVue DataTable dùng lazy loading cho server-side pagination/filter/sort.
- VirtualScroller chỉ dùng khi thật sự cần hiển thị nhiều dòng trong viewport.
- Không load toàn bộ dataset vào Pinia store.
- Store chỉ giữ query state, selection state và cache ngắn hạn nếu cần.
- Debounce filter/search.
- Cancel request cũ khi user thay đổi filter nhanh.
- Không render component phức tạp trong từng cell nếu không cần.
- Không dùng computed/filter trên mảng hàng vạn dòng ở client.
- Import/export UI phải hiển thị progress, trạng thái job và link tải file sau khi hoàn tất.

DataTable enterprise phải có:

- server-side pagination
- server-side sorting
- server-side filtering
- persisted table state nếu cần
- loading state rõ ràng
- empty state rõ ràng
- error state rõ ràng
- column visibility nếu business cần
- export theo filter hiện tại

### Performance Cho Import/Export File Nặng

Import/export file nặng không được xử lý như request CRUD thường.

Luồng import:

```text
upload file -> create import job -> worker validate/process chunk -> write result -> expose status/error report
```

Luồng export:

```text
create export job -> worker query chunk/stream -> write file to MinIO -> expose signed download URL
```

Yêu cầu:

- Không đọc toàn bộ file vào RAM.
- Không giữ transaction quá lâu.
- Không block event loop.
- Có retry policy rõ ràng.
- Có giới hạn kích thước file theo config.
- Có virus/malware scan hook nếu triển khai production enterprise.
- Có cleanup job cho file tạm và export hết hạn.

### Enterprise Security

Security phải được coi là yêu cầu nền tảng.

Yêu cầu bắt buộc:

- Không có public register.
- RBAC ở mọi endpoint nhạy cảm.
- Principle of least privilege cho role mặc định.
- Password hash mạnh.
- Refresh token rotation/revoke.
- Session/device tracking nếu cần.
- Rate limit cho login, refresh, import/export và upload.
- Audit log cho auth, user/role changes, import/export, file access.
- CORS theo environment, không wildcard trong production.
- CSRF protection nếu dùng cookie auth.
- XSS protection qua output encoding và CSP ở production.
- Input validation cho mọi boundary.
- Database query phải dùng ORM/query builder đúng cách hoặc parameterized query; không nối chuỗi SQL từ input.
- File upload kiểm tra extension, MIME, size và magic bytes nếu cần.
- Không log secret, token, password, signed URL đầy đủ hoặc PII không cần thiết.
- Secrets lấy từ env/secret manager, không commit vào repo.
- `.env`, private key, access token và credential file không được commit.
- Dependency scanning cho BE/FE.
- Container image scanning trong CI nếu có registry.
- HTTPS bắt buộc ở production.
- Security headers ở production: CSP, X-Frame-Options, HSTS, Referrer-Policy.

Security test tối thiểu:

- Auth guard test.
- Permission guard test.
- Login rate limit test.
- File upload validation test.
- Import/export permission test.
- Test không leak field nhạy cảm trong response.

Pre-deployment security checklist:

- không hardcode secret
- `.env` không được commit
- input validation đầy đủ
- query an toàn, không SQL injection
- RBAC hoạt động ở endpoint nhạy cảm
- rate limit bật cho endpoint nhạy cảm/nặng
- CORS đúng environment
- CSRF nếu dùng cookie auth
- CSP và secure headers ở production
- dependency scan sạch hoặc có waiver rõ ràng
- container image scan sạch hoặc có waiver rõ ràng

### Enterprise Production Readiness

Enterprise production readiness là yêu cầu bắt buộc, không phải phần optional.

#### Observability

Hệ thống phải có observability từ đầu:

- Structured logs dạng JSON cho backend, worker và reverse proxy.
- Request id/correlation id đi xuyên suốt API, worker job, audit log và frontend error report.
- OpenTelemetry instrumentation cho FastAPI, SQLAlchemy, HTTP client, background jobs.
- Metrics cho API latency, request count, error rate, DB query time, job duration, import/export throughput.
- Tracing backend có thể dùng Jaeger/Tempo/OTel collector tùy môi trường.
- Dashboard cho API health, worker health, Postgres, MinIO, Redis/broker.
- Alert rule cho error rate cao, p95 latency vượt SLO, job fail tăng, disk usage cao, backup fail.
- Frontend error tracking cho runtime error, route error và API failure.

Log không được chứa password, token, secret, signed URL đầy đủ hoặc PII không cần thiết.

#### Backup/Restore

Backup/restore là một phần của thiết kế, không để tới sau production.

Postgres:

- Scheduled backup tự động.
- Point-in-time recovery nếu môi trường production yêu cầu.
- Retention policy rõ ràng.
- Restore drill định kỳ.
- Backup encryption.
- Backup status alert.

MinIO:

- Backup hoặc replication cho bucket quan trọng.
- Retention policy cho file upload, file import tạm và file export.
- Cleanup job cho object hết hạn.
- Restore drill cho object storage.

Yêu cầu tối thiểu:

- Có runbook restore Postgres.
- Có runbook restore MinIO.
- Có test restore trong môi trường staging hoặc test định kỳ.
- Không coi backup là thành công nếu chưa từng restore thử.

#### Secret Management

Secrets phải được quản lý theo môi trường.

Dev:

- `.env.example` được commit.
- `.env` không được commit.
- Secret dev có thể dùng giá trị local rõ ràng là không dùng cho production.

Production:

- Không dùng secret hardcoded.
- Không commit private key, token, password, access key.
- Ưu tiên Docker secrets, SOPS, Vault hoặc cloud secret manager.
- Secret rotation có quy trình rõ.
- JWT secret, DB password, MinIO access key, SMTP credential và third-party tokens phải có owner và rotation policy.
- Log/exception không được in secret.

#### SLO

Boilerplate phải định nghĩa SLO để performance không chỉ là cảm tính.

SLO ban đầu đề xuất:

- API availability production: `99.9%` theo tháng.
- API p95 latency cho endpoint thường: `< 300ms` khi không tính network client.
- API p95 latency cho DataTable list: `< 500ms` với filter/sort/index đúng.
- Error rate 5xx: `< 1%`.
- Login p95 latency: `< 500ms`.
- Import job `10,000` users: hoàn tất trong ngưỡng cấu hình, có progress và error report.
- Export job `10,000+` users: không block request thread, tạo file async và có signed URL.
- Frontend initial load production: target `< 3s` trên network bình thường.
- DataTable interaction: filter/sort/page change có loading state và không freeze UI.

SLO phải được kiểm tra bằng metrics, performance test hoặc E2E benchmark tối thiểu.

#### Compliance Gates

Compliance gates là các điều kiện bắt buộc trước khi merge hoặc deploy.

Pre-merge gates:

- Backend lint pass.
- Backend typecheck pass.
- Backend tests pass.
- Frontend lint pass.
- Frontend typecheck pass.
- Frontend unit/component tests pass.
- E2E smoke tests pass cho flow auth và admin cơ bản.
- Security tests cho RBAC, upload, import/export pass.
- Không có secret trong source.

Pre-deploy gates:

- Docker image build pass.
- Container scan pass hoặc có waiver được duyệt.
- Dependency scan pass hoặc có waiver được duyệt.
- DB migration dry-run hoặc staging migration pass.
- Backup status healthy.
- Observability endpoint và health check hoạt động.
- SLO dashboard/alert đã cấu hình cho production.
- Runbook deploy/rollback/restore tồn tại.

Production readiness không đạt nếu thiếu observability, backup/restore, secret management hoặc compliance gates.

## Docker Compose Design

Services:

```text
postgres
minio
backend
frontend
```

Optional:

```text
nginx
mailpit
```

Ports dev đề xuất:

- Backend: `8000`
- Frontend: `5173`
- Postgres: `5432`
- MinIO API: `9000`
- MinIO Console: `9001`

Environment variables:

```text
DATABASE_URL
JWT_SECRET_KEY
JWT_REFRESH_SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS
MINIO_ENDPOINT
MINIO_ACCESS_KEY
MINIO_SECRET_KEY
MINIO_BUCKET
CORS_ORIGINS
```

Không hardcode secret trong source code.

### Docker Dev

Dev environment dùng:

- `docker-compose.yml`
- hot reload backend
- hot reload frontend
- mounted source code
- Postgres volume riêng
- MinIO volume riêng

Lệnh dự kiến:

```bash
docker compose up --build
docker compose exec backend pytest backend/tests
docker compose exec frontend npm run test:unit
```

Backend dev image có dependency dev/test. Frontend dev image chạy Vite dev server.

### Docker Production

Production environment dùng:

- `docker-compose.prod.yml`
- backend production image multi-stage
- frontend static assets build bằng Vite
- reverse proxy Nginx hoặc Caddy
- không mount source code
- không expose Postgres/MinIO public nếu không cần
- env lấy từ `.env.production` hoặc secret manager

Lệnh dự kiến:

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

Production image không chứa test dependency nếu không cần runtime.

### Docker Test

Test environment dùng:

- `docker-compose.test.yml`
- Postgres test database
- MinIO test bucket
- backend test runner
- frontend unit/component test runner
- Playwright E2E runner

Lệnh dự kiến:

```bash
docker compose -f docker-compose.test.yml run --rm backend-test
docker compose -f docker-compose.test.yml run --rm frontend-test
docker compose -f docker-compose.test.yml run --rm e2e-test
```

Test profile phải chạy được trong CI mà không cần cấu hình thủ công.

## API Contract

API prefix:

```text
/api/v1
```

Endpoint nền tảng:

```text
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout
GET    /api/v1/auth/me
PATCH  /api/v1/auth/change-password

GET    /api/v1/users
POST   /api/v1/users
GET    /api/v1/users/{id}
PATCH  /api/v1/users/{id}
DELETE /api/v1/users/{id}
POST   /api/v1/users/import-jobs
GET    /api/v1/users/import-jobs
GET    /api/v1/users/import-jobs/{id}
POST   /api/v1/users/import-jobs/{id}/cancel
GET    /api/v1/users/import-jobs/{id}/errors
POST   /api/v1/users/export-jobs
GET    /api/v1/users/export-jobs
GET    /api/v1/users/export-jobs/{id}
GET    /api/v1/users/export-jobs/{id}/download

GET    /api/v1/roles
POST   /api/v1/roles
GET    /api/v1/roles/{id}
PATCH  /api/v1/roles/{id}
DELETE /api/v1/roles/{id}

GET    /api/v1/permissions

POST   /api/v1/files
GET    /api/v1/files/{id}
DELETE /api/v1/files/{id}
```

OpenAPI là nguồn sinh type cho frontend nếu có thể.

## Seed Data

Seed ban đầu:

- user admin mặc định
- role `admin`
- role `user`
- permission nền tảng
- mapping role-permission

Password admin mặc định chỉ dùng cho dev và phải đi qua env.

## Logging Và Audit

Backend cần:

- structured logging
- request id
- audit log cho login, logout, CRUD user/role, thay đổi permission
- audit log cho import/export user
- correlation id cho background jobs

Không log password, token, secret hoặc signed URL đầy đủ.

## Security Baseline

- Password hash mạnh.
- JWT secret lấy từ env.
- Refresh token có rotation hoặc revoke list.
- CORS giới hạn theo env.
- File upload kiểm tra content type, size và extension.
- Không trả thông tin nhạy cảm trong error.
- Không có public register.
- Admin tạo user và cấp role.
- Rate limit cho auth và endpoint nặng.
- CSRF nếu dùng cookie auth.
- CSP và secure headers ở production.
- Audit log cho hành vi nhạy cảm.
- Dependency/container scan trong CI.
- RBAC bắt buộc cho import/export.
- Signed URL phải có expiry ngắn và scope rõ ràng.
- Secret management theo môi trường.
- Backup/restore runbook cho Postgres và MinIO.
- Observability cho API, worker, database và storage.
- SLO/alert cho production.

## Roadmap Implement

### Phase 1: Scaffold

- Tạo `backend/` FastAPI.
- Tạo `frontend/` Vue 3 + Vite + TypeScript.
- Tạo Dockerfile dev/prod cho backend và frontend.
- Tạo `docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.test.yml`.
- Tạo Postgres + MinIO service.
- Cấu hình lint, format, typecheck.
- Cấu hình test framework backend/frontend.

### Phase 2: Auth + RBAC

Trạng thái: Đã hoàn thành và được xác minh ở mức code + quality gate.

- User model.
- Role/permission model.
- Login/refresh/logout/me.
- Permission dependency.
- Admin seed.
- Audit log nền tảng.

### Phase 3: Admin UI

Trạng thái: Đã hoàn thành và được xác minh ở mức code + frontend quality gate.

- Sakai-inspired layout.
- Dark/light mode.
- Login page.
- Dashboard page.
- Users CRUD.
- Roles CRUD.
- DataTable lazy loading với server-side pagination/filter/sort.

### Phase 4: Storage + Audit

Trạng thái: Đã hoàn thành và được xác minh ở mức code + backend/frontend quality gate.

- MinIO adapter.
- File upload endpoint.
- Audit log.
- UI file upload component.
- Background job runner cho import/export.
- User import/export jobs.
- Error report cho import.
- Export theo filter hiện tại.

### Phase 5: Hardening

- Unit tests.
- Integration tests.
- E2E smoke tests.
- Test coverage report cho backend/frontend.
- Dockerized test profile cho CI.
- CI workflow.
- Security scan.
- Performance test cho list API, DataTable và import/export file nặng.
- Security test cho RBAC, rate limit, upload và import/export.

Baseline đã được implement trong repo:

- Backend security headers middleware.
- In-memory rate limit cho `auth.login`, `files.upload`, `users.avatar-upload`, `users.import`, `users.export`.
- Query hardening cho list endpoints với `limit <= 100`.
- Backend hardening tests cho security headers, rate-limit wiring, permission wiring, và query cap.
- Coverage report output cho backend/frontend.
- GitHub Actions CI workflow tại `.github/workflows/ci.yml`.
- Performance smoke scripts cho `users.list` và `users.export`.
- Make targets cho `backend-dependency-audit`, `frontend-dependency-audit`, `security-check`, `perf-users-list`, `perf-users-export`.

Lưu ý verify:

- `pytest`, `ruff`, `mypy` backend và `lint`, `typecheck`, `test:unit` frontend đã được verify.
- Dependency audit và host-side perf smoke cần ghi nhận rõ trạng thái verify theo mỗi môi trường, vì các lệnh này phụ thuộc DNS/socket ra ngoài sandbox.

### Phase 6: Production Readiness

- OpenTelemetry instrumentation.
- Metrics/tracing/logging pipeline.
- Production SLO dashboard.
- Alert rules.
- Secret management setup.
- Backup/restore automation.
- Restore drill.
- Compliance gates trong CI/CD.
- Deploy/rollback/restore runbooks.

Baseline đã được implement trong repo:

- backend structured JSON logging với `request_id`
- `/metrics` và `/ready`
- OpenTelemetry instrumentation baseline cho FastAPI, HTTPX, SQLAlchemy
- observability stack config tại `docker-compose.observability.yml`
- Prometheus scrape config và alert rules
- production env mẫu tại `.env.production.example`
- secret-file support cho JWT, DB URL và MinIO credential
- backup/restore scripts cho Postgres và MinIO
- restore-drill helper script
- compliance gate script cho production readiness
- deploy/rollback/restore runbooks

Lưu ý verify:

- backend production-readiness tests cho metrics, readiness và secret-file loading đã pass
- compliance script parse được production compose và observability compose
- observability stack `up` thật, live alerting và restore thật vẫn cần verify ở môi trường runtime phù hợp

## Nguyên tắc không được vi phạm

1. Không có chức năng public register.
2. Không dùng inline style ở frontend.
3. Không đặt business logic trong `.vue`.
4. Không hardcode secret.
5. Không bỏ qua linter/typecheck.
6. Không tạo endpoint không có permission policy rõ ràng.
7. Không upload file trực tiếp vào local filesystem nếu đã có MinIO.
8. Không chỉ hỗ trợ Docker dev mà bỏ qua production image.
9. Không merge feature nếu chưa có test phù hợp với risk của thay đổi.
10. Không hardcode màu hoặc tạo style dark/light riêng lẻ theo từng page.
11. Không để Button, Menu, Header, DataTable, Form Input có màu/contrast khác nhau giữa các page khi đổi theme.
12. Không load hàng vạn dòng vào frontend store hoặc một API response thông thường.
13. Không xử lý import/export file nặng trong request synchronous kiểu CRUD.
14. Không import/export User nếu chưa có permission, audit log và error report.
15. Không bỏ qua rate limit, validation và security test cho endpoint nhạy cảm.
16. Không deploy production nếu chưa có observability tối thiểu.
17. Không deploy production nếu chưa có backup/restore runbook và restore drill.
18. Không deploy production nếu secrets chưa được quản lý theo môi trường.
19. Không deploy production nếu chưa có SLO và alert cho service chính.
20. Không deploy production nếu compliance gates chưa pass hoặc chưa có waiver rõ ràng.

## Quyết định thiết kế cần chốt khi implement

1. Dùng SQLAlchemy sync hay async. Khuyến nghị: async vì FastAPI + asyncpg.
2. Auth strategy đã chốt cho Phase 2: hybrid. Access token ngắn hạn đi qua `Authorization Bearer`, refresh token đi qua `httpOnly cookie`.
3. Refresh token lưu plain hash hay token id. Khuyến nghị: chỉ lưu hash/token id, không lưu token raw.
4. FE lấy type từ OpenAPI bằng tool nào. Khuyến nghị: `openapi-typescript`.
5. Có dùng Tailwind giống Sakai hay giữ CSS module/custom CSS. Khuyến nghị: dùng CSS variables + utility tối thiểu, tránh phụ thuộc quá nhiều vào utility class.
6. Chọn background job runner nào. Khuyến nghị: Celery nếu cần ecosystem mạnh; Arq/RQ nếu muốn nhẹ hơn.
7. Chọn pagination mặc định. Khuyến nghị: cursor pagination cho dataset lớn, offset pagination chỉ cho bảng nhỏ.
8. Chọn định dạng export mặc định. Khuyến nghị: CSV cho dữ liệu lớn, XLSX cho nhu cầu nghiệp vụ cụ thể.
9. Chọn observability backend nào. Khuyến nghị: OpenTelemetry Collector + Prometheus/Grafana + Tempo/Jaeger tùy môi trường.
10. Chọn secret manager nào. Khuyến nghị: Docker secrets/SOPS cho self-host nhỏ, Vault hoặc cloud secret manager cho production lớn.
11. Chọn backup strategy nào cho Postgres và MinIO. Khuyến nghị: scheduled backup + retention + restore drill định kỳ.

## Tài liệu nguồn

- FastAPI PyPI: https://pypi.org/project/fastapi/
- PrimeVue v4 migration: https://primevue.org/guides/migration/v4/
- Sakai template: https://primevue.org/templates/sakai/
- Sakai source: https://github.com/primefaces/sakai-vue
- Vue SFC syntax: https://vuejs.org/api/sfc-spec
- Vue script setup: https://vuejs.org/api/sfc-script-setup
