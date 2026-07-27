# Phase 7: Kế Hoạch Triển Khai Module Audit Log

## Trạng Thái

Đã hoàn thành Slice 1: Backend Audit Read Foundation.
Đã hoàn thành Slice 2: Audit Write Sanitizer Và Context Helper.
Đã hoàn thành Slice 3: Frontend Audit Log Viewer.
Đã hoàn thành Slice 4: Request-Layer Coverage Expansion.
Đã hoàn thành Slice 5: Worker-Layer Coverage Expansion.
Đã hoàn thành Slice 6: End-To-End Verification Và Docs.

Kế hoạch này đã được review bằng local skill `improve-codebase-architecture`
và các local subagent `reviewer` / `explorer` vào ngày 24/07/2026.
Slice 1 cũng đã được review thêm bằng local subagent `reviewer` trong lúc
triển khai.
Slice 4 đã được rà soát bằng local subagent `explorer` và `reviewer` trong lúc
triển khai để kiểm tra transaction boundary, metadata sanitizer và RBAC.
Slice 5 đã được rà soát bằng local subagent `explorer` và `reviewer` trong lúc
triển khai để kiểm tra worker lifecycle, secret-safe metadata và idempotency.
Slice 6 đã được rà soát bằng local subagent `explorer` và `reviewer` trong lúc
triển khai để kiểm tra Docker E2E, quyền `audit.read`, screenshot desktop/mobile
và tài liệu hoàn tất module.

## Mục Tiêu

Xây dựng module Audit Log thành một phần hoàn chỉnh của boilerplate:

1. Admin có quyền `audit.read` xem được lịch sử thay đổi gây ra bởi user.
2. Audit log có API đọc riêng, filter/sort/pagination phù hợp với bảng log lớn.
3. Metadata được sanitize tập trung, không rò rỉ password, token, cookie, secret,
   raw Authorization header hoặc signed URL đầy đủ.
4. Các mutation quan trọng còn thiếu audit event được bổ sung.
5. Frontend có trang viewer đúng style hiện tại, responsive, permission-gated.

## Căn Cứ Đã Xác Minh

- Audit model đã tồn tại: `backend/app/models/audit_log.py`.
- Audit write service đã tồn tại: `backend/app/services/audit_log.py`.
- Audit service hiện chỉ có `log_event(...)`, chưa có read/query interface.
- Permission `audit.read` đã nằm trong seed: `backend/app/auth/seed_data.py`.
- API router hiện chưa include route đọc audit log.
- Frontend chưa có route/page/sidebar item cho Audit Logs.
- User, Role, File, Job và Auth routes đã có nhiều audit event.
- Backup routes chưa inject `AuditLogService`, nên các mutation backup chưa có audit.
- `audit_logs` hiện chỉ có index đơn cho `actor_user_id`, `action`, `entity_type`;
  chưa có index phù hợp cho timeline, entity history và request correlation.

## Ngoài Scope

- SIEM integration, long-term archive pipeline, immutable external storage.
- Full forensic hash chain bắt buộc cho mọi record.
- Free-text search trong `metadata_json`.
- User self-service xem audit log cá nhân.

Những mục này có thể làm sau khi viewer/API đọc ổn định.

## Nguyên Tắc Bắt Buộc

1. Reuse `AuditLog` model và `AuditLogService`; không tạo hệ logging song song.
2. Ghi log theo stable action code, ví dụ `users.user_updated`.
3. Route đọc audit bắt buộc dùng `require_permission("audit.read")`.
4. Không có API update/delete audit log.
5. Backend phải sanitize metadata trước khi persist và trước khi response.
6. Query audit log phải server-side, không load bảng log lớn lên frontend.
7. Thời gian filter phải explicit timezone theo `Asia/Ho_Chi_Minh`.
8. Vue SFC không được có `<style>`; style nằm trong `frontend/src/styles`.
9. DataTable viewer dùng paging chuẩn: rows default 10, options 10/20/30/50,
   report tiếng Việt và rows dropdown đặt trước paging.

## Kiến Trúc Đề Xuất

### Backend Modules

- `backend/app/schemas/audit_log.py`
  - `AuditLogResponse`
  - `AuditLogListResponse`
  - `AuditLogListQueryParams`
  - `AuditLogMetadata`

- `backend/app/services/audit_log.py`
  - giữ `AuditLogService.log_event(...)` cho write path
  - thêm sanitizer/allowlist metadata tập trung
  - thêm helper build context từ request nếu phù hợp

- `backend/app/services/audit_log_admin.py`
  - module read/query riêng cho viewer
  - expose interface nhỏ: `list_audit_logs(query)`
  - xử lý filter, cursor/keyset, sort whitelist, eager-load actor

- `backend/app/api/v1/audit_logs.py`
  - adapter route mỏng
  - `GET /api/v1/audit-logs`
  - protected bằng `audit.read`

- `backend/alembic/versions/*_audit_log_query_indexes.py`
  - thêm index cho workload viewer.

### Frontend Modules

- `frontend/src/types/audit-logs.ts`
- `frontend/src/api/audit-logs.api.ts`
- `frontend/src/api/audit-logs.mappers.ts`
- `frontend/src/composables/useAuditLogsPage.ts`
- `frontend/src/pages/AuditLogsPage.vue`
- `frontend/src/styles/pages/_audit-logs-page.scss`
- update `frontend/src/router/index.ts`
- update `frontend/src/layouts/AdminLayout.vue`
- update `frontend/src/styles/main.scss`

## API Contract

Endpoint:

```http
GET /api/v1/audit-logs
```

Permission:

```text
audit.read
```

Query parameters:

- `limit`: default `10`, min `1`, max `100`
- `cursor`: optional keyset cursor encoded từ `(created_at, id)`
- `actor_user_id`: optional UUID exact match
- `action`: optional exact match
- `entity_type`: optional exact match
- `entity_id`: optional exact match
- `request_id`: optional exact match
- `created_from`: optional datetime/date boundary, inclusive
- `created_to`: optional datetime/date boundary, exclusive

Sort:

- Default và only supported initial sort: `created_at DESC, id DESC`.
- Không mở `sort_by` tùy ý trong phase đầu.

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "actor_user_id": "uuid-or-null",
      "actor_email": "admin@example.com",
      "action": "users.user_updated",
      "entity_type": "user",
      "entity_id": "uuid-or-null",
      "request_id": "req-123",
      "ip_address": "127.0.0.1",
      "metadata": {},
      "created_at": "2026-07-24T09:00:00+00:00"
    }
  ],
  "next_cursor": "opaque-or-null",
  "total": 30
}
```

`total` có thể giữ để hợp với DataTable hiện tại, nhưng keyset cursor là hướng
chính cho bảng log lớn. Nếu `COUNT(*)` trở nên đắt, có thể biến `total` thành
optional trong slice tối ưu sau.

## Index Và Database

Thêm migration riêng:

1. `(created_at DESC, id DESC)` cho feed mặc định.
2. `(actor_user_id, created_at DESC, id DESC)` cho filter theo actor.
3. `(entity_type, entity_id, created_at DESC, id DESC)` cho history theo object.
4. `(request_id)` cho correlation lookup.
5. Cân nhắc `(action, created_at DESC, id DESC)` nếu UI lọc action thường xuyên.

Không filter free-text trên `metadata_json` trong phase này. Nếu cần metadata
search sau này, cần chuyển sang `JSONB + GIN` hoặc tách field hay truy vấn ra cột
riêng.

## Metadata Và Bảo Mật

`AuditLogService` phải có sanitizer trung tâm:

- Cấm các key có chứa: `password`, `token`, `secret`, `cookie`, `authorization`,
  `session`, `credential`, `signed_url`.
- URL file/download chỉ lưu relative path hoặc object id; không lưu signed URL đầy đủ.
- Email, filename, role names, permission codes có thể hiển thị vì đây là audit
  context cần thiết, nhưng phải có allowlist rõ ràng.
- UI dialog metadata chỉ render metadata đã sanitize từ backend.

Tamper-resistance tối thiểu:

- Không tạo update/delete API cho audit log.
- Route viewer read-only.
- Có test khẳng định router không expose mutation audit route.

Deferred hardening:

- DB trigger chặn `UPDATE/DELETE` trên `audit_logs`.
- App DB role chỉ có insert/select phù hợp với bảng audit.
- Hash chain hoặc external append-only sink.

## Slice 0: Audit Inventory Và Contract

Mục tiêu:

- Đóng băng taxonomy action code và entity type trước khi code.
- Xác nhận route nào đã log, route nào chưa log.
- Đồng bộ permission seed với route permissions thực tế.

Việc cần làm:

1. Tạo audit coverage matrix trong plan hoặc test doc.
2. Ghi rõ các event hiện có:
   - `auth.login_failed`
   - `auth.login_succeeded`
   - `auth.session_refreshed`
   - `auth.logout`
   - `users.avatar_uploaded`
   - `users.user_created`
   - `users.user_updated`
   - `users.roles_updated`
   - `users.user_deleted`
   - `roles.role_created`
   - `roles.role_updated`
   - `roles.role_deleted`
   - `files.file_uploaded`
   - `files.file_deleted`
   - `users.import_started`
   - `users.export_started`
3. Ghi rõ gap hiện tại:
   - `backups.manual_backup_triggered`
   - `backups.schedule_created`
   - `backups.schedule_updated`
   - `backups.schedule_deleted`
   - optional `auth.refresh_failed`
4. Kiểm tra và đồng bộ `BASE_PERMISSION_CODES` với route đang dùng:
   - `users.import`
   - `users.export`
   - `files.delete`
   - `files.read_all`
   - giữ `audit.read`

Acceptance:

- Có matrix coverage rõ ràng.
- Permission seed không lệch với route permissions.
- Không đổi behavior người dùng ở slice này, trừ khi phát hiện seed thiếu.

## Slice 1: Backend Audit Read Foundation

Trạng thái: Đã hoàn thành ngày 24/07/2026.

Mục tiêu:

- Có API đọc audit log read-only, protected bằng `audit.read`.
- Có service query riêng, không query trực tiếp trong route.
- Có index phù hợp viewer.

Kết quả đã triển khai:

- Thêm schema response audit log.
- Thêm `AuditLogAdminService` cho filter exact, eager-load actor, sort mặc định
  `created_at DESC, id DESC`, và keyset cursor theo `(created_at, id)`.
- Thêm route `GET /api/v1/audit-logs`, chỉ đọc và protected bằng
  `require_permission("audit.read")`.
- Thêm migration index cho feed mặc định, actor, entity history, request
  correlation và action filter.
- Thêm sanitizer metadata tập trung trong `AuditLogService`, dùng cả write path
  và read response để không trả password, token, cookie, secret, authorization,
  session, credential hoặc signed URL thô.
- Cursor chứa datetime không có timezone bị từ chối và trả lỗi `422`.

Xác minh đã chạy:

- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check .`
- `UV_CACHE_DIR=/tmp/uv-cache uv run mypy .`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_audit_log_service.py tests/test_audit_logs_api.py tests/test_audit_log_admin_service.py -q --tb=short --no-header --no-cov`
- `make backend-security`

Ghi chú: `make backend-check` đầy đủ đã qua `ruff`, format và `mypy`, nhưng bị
ngắt ở pha full `pytest` vì test suite treo lâu trong môi trường hiện tại, khớp
với bug pattern ASGITransport/test hang đã biết. Targeted tests của Slice 1 đã
pass.

Việc cần làm:

1. Thêm schemas audit log.
2. Thêm `AuditLogAdminService`.
3. Thêm migration indexes.
4. Thêm route `backend/app/api/v1/audit_logs.py`.
5. Include router trong `backend/app/api/v1/router.py`.
6. Eager-load actor user để hiển thị `actor_email`.
7. Implement keyset cursor theo `(created_at, id)`.
8. Implement filters exact và date boundary.

Tests:

- `GET /api/v1/audit-logs` thiếu auth -> `401`.
- Có auth nhưng thiếu `audit.read` -> `403`.
- Có `users.read` nhưng thiếu `audit.read` vẫn `403`.
- Filter theo actor/action/entity/request_id đúng.
- Date boundary inclusive/exclusive đúng với `Asia/Ho_Chi_Minh`.
- Duplicate timestamp không làm mất/lặp record khi paginate.
- Sort whitelist không cho sort field tùy ý.

Quality gate:

```bash
make backend-check
```

## Slice 2: Audit Metadata Sanitizer Và Context Helper

Trạng thái: Đã hoàn thành ngày 24/07/2026.

Mục tiêu:

- Làm `AuditLogService` sâu hơn: caller đưa metadata, service đảm bảo an toàn.
- Giảm việc mỗi route tự xử lý request id/IP khác nhau.

Kết quả đã triển khai:

- Mở rộng sanitizer trong `AuditLogService` theo hướng allowlist: key nhạy cảm
  và key chưa được phê duyệt đều bị redact thành `[REDACTED]`.
- Sensitive-key detection bao phủ `api_key`, password, token, secret, cookie,
  authorization, session, credential và signed URL.
- Thêm `AuditLogContext.from_request(...)` để tạo context từ `Request` và
  `current_user`, tự resolve actor, client IP và `request_id`.
- Chuẩn hóa client IP qua helper chung có trusted-proxy boundary: chỉ đọc
  `X-Forwarded-For` hoặc `X-Real-IP` khi IP kết nối trực tiếp nằm trong
  `TRUSTED_PROXY_CIDRS`; nếu không thì fallback về `request.client.host`.
- Chuyển auth/users/roles/files/jobs sang `AuditLogContext.from_request(...)`,
  giữ nguyên action code, entity type và metadata nghiệp vụ hiện có.
- Thêm guardrail test để route API không dùng `_extract_client_ip` hoặc
  `request.client.host` trực tiếp nữa.
- Thêm test fallback `request_id` từ middleware context khi caller không truyền
  request id rõ ràng.

Ghi chú bảo mật:

- `X-Forwarded-For` không được tin mặc định. Production Docker qua Nginx dùng
  subnet compose cố định và cấu hình `TRUSTED_PROXY_CIDRS` để backend chỉ tin
  header từ reverse proxy nội bộ. Mô hình LAN/VPN direct nên để
  `TRUSTED_PROXY_CIDRS` rỗng để audit log ghi IP kết nối trực tiếp.

Xác minh đã chạy:

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_audit_log_service.py tests/test_audit_logs_api.py tests/test_audit_context_usage.py -q --tb=short --no-header --no-cov`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check .`
- `UV_CACHE_DIR=/tmp/uv-cache uv run mypy .`
- `make backend-security`

Ghi chú: `timeout 120s make backend-check` đã qua `ruff`, format và `mypy`,
đồng thời full pytest đã pass qua toàn bộ audit tests mới, nhưng bị timeout ở
pha full pytest sau `test_backup_service.py`, khớp với bug pattern test hang đã
biết trong môi trường hiện tại.

Việc cần làm:

1. Thêm sanitizer/allowlist trong `AuditLogService`.
2. Thêm helper tạo `AuditLogContext` từ `Request` + `current_user`.
3. Chuyển auth/users/roles/files/jobs sang dùng helper nếu phù hợp.
4. Chuẩn hóa client IP theo cùng một helper có trusted-proxy boundary; không
   dùng trực tiếp `request.client.host` trong API route và không tin
   `X-Forwarded-For` từ client không tin cậy.
5. Đảm bảo `request_id` luôn lấy từ middleware context nếu route không truyền.

Tests:

- Metadata có sensitive keys bị mask hoặc reject.
- Không persist password/token/cookie/secret/Authorization.
- Existing event action/entity không đổi vô tình.
- Request id fallback từ context vẫn hoạt động.

Quality gate:

```bash
make backend-check
```

## Slice 3: Frontend Audit Log Viewer

Trạng thái: Đã hoàn thành ngày 27/07/2026.

Mục tiêu:

- Admin có màn hình xem audit logs.
- UI theo đúng style admin hiện tại và responsive.

Việc cần làm:

1. Thêm `types/audit-logs.ts`.
2. Thêm `api/audit-logs.api.ts`.
3. Thêm `api/audit-logs.mappers.ts`.
4. Thêm `composables/useAuditLogsPage.ts`.
5. Thêm `pages/AuditLogsPage.vue`.
6. Thêm `styles/pages/_audit-logs-page.scss`.
7. Import style trong `styles/main.scss`.
8. Thêm route `/audit-logs` với `requiredPermission: "audit.read"`.
9. Thêm sidebar item gated bằng `permissionStore.can("audit.read")`.

UI yêu cầu:

- Filter bar: actor, action, entity type, entity id, request id, date range.
- DataTable lazy, paginator, rows default 10, options 10/20/30/50.
- Current page report: `Hiển thị từ {first} đến {last} trên tổng số {totalRecords} dòng`.
- Rows dropdown đặt trước paging.
- Metadata dialog chỉ hiện sanitized metadata.
- Mobile: header/filter stack gọn, table wrapper scroll ngang trong card.

Tests:

- Mapper dto -> domain.
- Composable fetch/page/filter state.
- Page render empty/loading/error states.
- Router guard/sidebar permission visibility nếu đã có pattern test phù hợp.

Quality gate:

```bash
make frontend-check
npm --prefix frontend run build
```

Kết quả đã triển khai:

- Thêm type, API client, mapper và composable riêng cho Audit Logs ở frontend.
- Thêm trang `AuditLogsPage` với filter actor/action/entity/request/date range,
  DataTable lazy, rows mặc định 10, options 10/20/30/50, report tiếng Việt và
  rows dropdown đặt trước paging.
- Nối route `/audit-logs` với `requiredPermission: "audit.read"` và thêm sidebar
  item chỉ hiện khi `permissionStore.can("audit.read")`.
- Metadata dialog chỉ render `metadata` nhận từ backend, không tự lấy hoặc hiển
  thị nguồn dữ liệu thô khác ở frontend.
- Composable giữ cursor map cho điều hướng tuần tự prev/next trên API keyset
  cursor của backend, không giả lập nhảy trang xa bằng offset hoặc nhiều request
  nối tiếp.
- Thêm unit tests cho mapper, composable fetch/filter/page state, page
  empty/loading/error state, route permission và sidebar visibility.
- Đã xác minh `make frontend-check` và `npm --prefix frontend run build` pass.

## Slice 4: Request-Layer Coverage Expansion

Trạng thái: Đã hoàn thành ngày 27/07/2026.

Mục tiêu:

- Các mutation request-layer quan trọng đều có audit event.

Việc cần làm:

1. Thêm audit cho `POST /backups/now`:
   - action `backups.manual_backup_triggered`
   - entity_type `backup_log`
2. Thêm audit cho `POST /backups/schedules`:
   - action `backups.schedule_created`
   - entity_type `backup_schedule`
3. Thêm audit cho `PUT /backups/schedules/{schedule_id}`:
   - action `backups.schedule_updated`
   - entity_type `backup_schedule`
4. Thêm audit cho `DELETE /backups/schedules/{schedule_id}`:
   - action `backups.schedule_deleted`
   - entity_type `backup_schedule`
5. Cân nhắc thêm `auth.refresh_failed` cho refresh token missing/invalid.

Cần lưu ý:

- `BackupAdminService` hiện đang commit nội bộ; khi thêm audit cần tránh commit
  bị chia cắt làm event và mutation không atomic.
- Nên cân nhắc đưa commit về route-level hoặc có transaction pattern rõ trước khi
  thêm audit backup.

Tests:

- Backup API tests assert audit action/entity/metadata.
- Failure path không ghi success event.
- 204 route vẫn return `None`, không return Response object.

Quality gate:

```bash
make backend-check
```

Kết quả đã triển khai:

- Thêm audit event cho `POST /backups/now`, `POST /backups/schedules`,
  `PUT /backups/schedules/{schedule_id}` và
  `DELETE /backups/schedules/{schedule_id}`.
- Chuyển commit ownership của các mutation trong `BackupAdminService` về
  route-level: service chỉ `flush()`, route ghi audit rồi `commit()` để mutation
  và audit event không bị chia transaction.
- Với manual backup, route chỉ enqueue job sau khi `BackupLog` và audit event đã
  commit thành công; nếu audit hoặc commit lỗi thì không publish job ra Redis.
- `DELETE /backups/schedules/{schedule_id}` tiếp tục là route `204` trả
  `None`, nhưng service trả schedule đã xóa để route có metadata audit an toàn.
- Thêm guardrail cho `backups.write`: bốn mutation backup đều dùng
  `require_permission("backups.write")` và có test dependency từ chối user chỉ có
  `backups.read`.
- Thêm regression test cho allowlist metadata backup gồm `backup_log_id`,
  `backup_schedule_id`, `name`, `status` và `outcome`.

Xác minh:

- `pytest tests/test_backup_audit_routes.py tests/test_backup_service.py tests/test_audit_log_service.py -q --tb=short --no-header`
  pass với 26 tests.
- Backend ruff targeted pass.
- Backend mypy targeted pass.
- `make backend-security` pass, Bandit không phát hiện issue.
- `git diff --check` pass.
- `timeout 180s make backend-check` đã pass ruff toàn repo, format-check toàn
  repo và mypy toàn repo, sau đó timeout tại `tests/test_backups_api.py`; đây
  khớp bug pattern hiện có của ASGI backup API test harness và không phải lỗi
  assertion Slice 4.

## Slice 5: Worker-Layer Coverage Expansion

Trạng thái: Đã hoàn thành ngày 27/07/2026.

Mục tiêu:

- Import/export/backup có audit event cho lifecycle kết thúc, không chỉ request start.

Việc cần làm:

1. Log import job completed/failed:
   - `users.import_completed`
   - `users.import_failed`
2. Log export job completed/failed:
   - `users.export_completed`
   - `users.export_failed`
3. Log backup run completed/failed:
   - `backups.run_completed`
   - `backups.run_failed`
4. Bảo toàn request/correlation id nếu worker có context.
5. Metadata chỉ gồm summary an toàn:
   - row counts
   - failed rows count
   - file id
   - backup log id
   - error category/summary đã sanitize

Tests:

- Worker success/failure tạo đúng audit event.
- Error summary không chứa secret/path nhạy cảm.
- Audit event liên kết đúng job id hoặc backup log id.

Quality gate:

```bash
make backend-check
```

Kết quả đã triển khai:

- Thêm audit event cuối lifecycle trong `import_users_task`:
  `users.import_completed` và `users.import_failed`.
- Thêm audit event cuối lifecycle trong `export_users_task`:
  `users.export_completed` và `users.export_failed`.
- Thêm audit event cuối lifecycle trong `run_backup_task`:
  `backups.run_completed` và `backups.run_failed`.
- Worker audit dùng cùng `AsyncSession` và được ghi trước `commit()` trạng thái
  cuối để terminal status và terminal audit đi cùng transaction.
- Metadata audit worker chỉ chứa summary an toàn: id job/log/file, status,
  outcome, counts, size bytes, error category và error summary chuẩn hóa. Không
  ghi raw exception, stderr `pg_dump`, `storage_path`, path filesystem, nội dung
  CSV, token, password hoặc secret.
- `export_users_task` và `run_backup_task` bỏ qua job/log đã ở trạng thái
  terminal `completed`/`failed` để tránh retry tạo duplicate terminal audit;
  trạng thái đang chạy như `processing`/`running` vẫn được xử lý tiếp.
- Backup success notification được cô lập khỏi lifecycle chính: nếu gửi email
  thành công bị lỗi, backup vẫn giữ `completed` và không ghi nhầm
  `backups.run_failed`.
- Mở rộng metadata allowlist cho worker keys: `import_job_id`,
  `export_job_id`, `backup_type`.

Chưa triển khai trong Slice 5:

- Correlation id xuyên queue từ request-layer sang worker-layer. Hiện queue
  payload chỉ truyền `job.id` hoặc `backup_log_id`, và bảng job/log chưa có cột
  lưu request id. Việc này cần slice riêng để đổi queue contract/schema mà không
  làm vỡ job đã enqueue.

Xác minh:

- `pytest tests/test_worker_tasks.py tests/test_audit_log_service.py -q --tb=short --no-header`
  pass với 20 tests.
- Backend ruff targeted pass.
- Backend mypy targeted pass.
- `make backend-security` pass, Bandit không phát hiện issue.
- `git diff --check` pass.
- `timeout 180s make backend-check` đã pass ruff toàn repo, format-check toàn
  repo và mypy toàn repo, sau đó timeout tại `tests/test_backups_api.py`; đây
  khớp bug pattern ASGI backup API test harness đã ghi từ Slice 4.

## Slice 6: End-To-End Verification Và Docs

Trạng thái: Đã hoàn thành ngày 27/07/2026.

Mục tiêu:

- Chứng minh flow thật hoạt động qua browser/API, không chỉ pass unit test.
- Cập nhật memory để future agents biết audit module đã hoàn tất.

Việc cần làm:

1. E2E admin login -> tạo/cập nhật user hoặc role -> mở Audit Logs -> thấy event.
2. E2E hoặc API test user không có `audit.read` không xem được audit logs.
3. Playwright screenshot desktop/mobile cho Audit Logs viewer.
4. Update `memory-bank/progress.md`.
5. Nếu phát hiện bug, update `memory-bank/bugPatterns.md`.
6. Ghi `.agent-memory/inbox` bằng `scripts/agent-task-close.sh`.

Quality gates:

```bash
make check
make docker-test-e2e
```

Nếu sandbox chặn Docker, DNS hoặc localhost socket, phải ghi rõ phần nào verified
và phần nào chưa verified.

Kết quả đã triển khai:

- Thêm Playwright E2E spec `frontend/tests/e2e/audit-logs.spec.ts`.
- Spec đăng nhập admin bằng credential lấy từ biến môi trường
  `E2E_ADMIN_EMAIL` / `E2E_ADMIN_PASSWORD`, không hardcode secret trong test.
- Flow E2E admin tạo role thật qua `POST /api/v1/roles`, mở trang
  `/audit-logs`, lọc action `roles.role_created`, thấy event thật trong bảng,
  mở metadata dialog và xác minh metadata đã sanitize chứa tên role vừa tạo.
- Flow E2E negative tạo user role `user`, đăng nhập user đó qua API, gọi
  `GET /api/v1/audit-logs` bằng access token của user thiếu `audit.read` và
  nhận `403`.
- Spec tạo screenshot desktop và mobile cho Audit Logs viewer:
  `test-results/audit-logs-desktop.png` và
  `test-results/audit-logs-mobile.png`; Docker E2E mount artifact ra
  `frontend/test-results/` trên host.
- `docker-compose.test.yml` truyền credential seed admin vào container
  `e2e-test` qua env riêng cho E2E và mount Playwright artifacts ra host.
- `Makefile` đổi các target Docker test sang `run --build --rm` để quality gate
  luôn chạy image từ source hiện tại, tránh kiểm chứng nhầm bằng image stale.
- `.gitignore` bỏ qua artifact Playwright `frontend/test-results/` và
  `frontend/playwright-report/`.

Xác minh:

- `make docker-test-e2e` pass với 3 Playwright tests:
  smoke login redirect, admin thấy audit event thật, user thiếu `audit.read`
  bị API chặn `403`.
- `make frontend-check` pass: lint, format-check, typecheck và 23 unit tests.
- Targeted backend audit tests pass:
  `pytest tests/test_audit_logs_api.py tests/test_audit_log_admin_service.py tests/test_audit_log_service.py -q --tb=short --no-header`
  pass với 18 tests.
- `git diff --check` pass.
- `timeout 180s make check` pass backend ruff, format-check và mypy, nhưng bị
  timeout tại `tests/test_backups_api.py`; đây là bug pattern ASGITransport
  backup API test hang đã biết, không phải failure assertion của Slice 6.

## Test Matrix Tổng Hợp

| Area | Test |
| --- | --- |
| Backend RBAC | `audit.read` required, `users.read` alone cannot view |
| Backend query | actor/action/entity/request_id/date filters |
| Backend pagination | keyset stable with duplicate timestamps |
| Backend security | metadata sensitive keys masked/rejected |
| Backend DB | migration creates indexes, downgrade works |
| Backup coverage | backup now/schedule create/update/delete logged |
| Worker coverage | job/backup completed/failed logged |
| Frontend API | query params and mappers correct |
| Frontend page | loading/error/empty/table/filter/dialog states |
| E2E | admin mutation visible in audit logs |
| E2E/RBAC | user without `audit.read` blocked |

## Rủi Ro Và Cách Giảm

1. Log nhầm secret.
   - Giảm bằng sanitizer trung tâm và tests redaction.

2. Bảng audit lớn chậm.
   - Giảm bằng keyset pagination, index theo timeline/entity/request id, limit cap.

3. Timezone lệch ngày khi filter.
   - Giảm bằng contract `created_from` inclusive, `created_to` exclusive,
     convert date boundary theo `Asia/Ho_Chi_Minh`.

4. Permission false positive do admin bypass.
   - Giảm bằng test với user có `users.read` nhưng không có `audit.read`.

5. Backup audit không atomic với mutation.
   - Giảm bằng review transaction ownership của `BackupAdminService` trước khi log.

6. UI dump metadata quá nhiều.
   - Giảm bằng backend response sanitized và frontend dialog chỉ render sanitized fields.

## Thứ Tự Ưu Tiên

1. Slice 0
2. Slice 1
3. Slice 2
4. Slice 3
5. Slice 4
6. Slice 5
7. Slice 6

Lý do: viewer cần query/read foundation và metadata safety trước; coverage expansion
sau đó mới đưa thêm event vào bảng log; E2E chạy cuối cùng để xác nhận cả flow.
