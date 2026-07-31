# System Patterns

## Agent Workflow Pattern

This repository uses a two-layer memory pattern:

1. `AGENTS.md` for always-loaded startup instructions
2. `memory-bank/` for durable, human-readable project context

## Memory Pattern

The chosen memory design is adapted from `axiomhq/agent-memory`:

1. capture durable learning
2. consolidate into structured memory
3. surface hot memory into startup instructions

## Documentation Pattern

If code and docs disagree:

1. verify with code or commands
2. fix the docs
3. record any recurring mismatch as a bug pattern

## Theme Consistency Pattern

Frontend theme must be centralized.

Use shared semantic tokens/classes for:

- button
- menu/sidebar
- topbar/header
- datatable
- form input
- dialog
- notification

Dark/light mode must change the whole application consistently. Page-level color overrides are only allowed when they are backed by reusable semantic tokens.

## Responsive UI Pattern

Frontend layout must be responsive by default.

Use shared responsive rules for:

- sidebar/menu behavior
- topbar actions
- page spacing
- card grids
- forms
- datatable wrappers
- dialog sizing

Do not rely on page-by-page fixes for mobile. Responsive behavior should come from centralized layout/component styles and tested breakpoints.

## Required Field Marker Pattern

Mandatory form fields must communicate that requirement before user interaction.

Add a visible red asterisk at label level for any required field, including create/edit dialogs, upload forms, and required filter inputs. Do not rely only on placeholders or validation errors after submit.

## Typography Pattern

Frontend typography is centralized.

Use one shared body font family across the application: `Be Vietnam Pro`.

Font changes belong in the centralized style layer, not in page-level or component-level overrides.

## Time Handling Pattern

Application-facing time behavior must be explicit.

1. treat `Asia/Ho_Chi_Minh` (`GMT+7`) as the default business timezone
2. distinguish `date` from `datetime` in API contracts and UI forms
3. store and transmit datetimes with explicit timezone/offset rules
4. convert display values intentionally instead of relying on runtime defaults
5. verify date-range filters against start-of-day and end-of-day boundaries in the target timezone

## Auth Strategy Pattern

Phase 2 auth uses a hybrid browser-first token model.

1. access token is short-lived and sent via `Authorization Bearer`
2. refresh token is longer-lived and stored in an `httpOnly` cookie
3. frontend keeps access token in memory only
4. refresh token must not be exposed as raw JSON payload or stored raw in the database
5. auth bootstrap should attempt refresh before treating the user as anonymous

Auth API contract follows that strategy:

1. `POST /auth/login` returns access token JSON and sets refresh cookie
2. `POST /auth/refresh` reads refresh token from cookie, not request body
3. `POST /auth/logout` revokes refresh token and clears cookie
4. `GET /auth/me` returns resolved roles and permissions for the current user

## Frontend Auth Foundation Pattern

Frontend auth should bootstrap once and guard routes centrally.

1. keep access token in Pinia memory only
2. use refresh-cookie bootstrap on app start or first protected navigation
3. route guards own the public/protected decision, not individual pages
4. treat missing or invalid refresh session as anonymous state, not as a fatal app crash
5. expose resolved roles and permissions from one auth source of truth, then consume them through a permission store or equivalent helper
6. keep login form logic in a composable and page styles in centralized `src/styles/`
7. if an admin page edits the currently authenticated user, refresh the auth source of truth immediately after save so shell UI like avatar, display name, roles, and permissions do not go stale

## Frontend API Boundary Pattern

Frontend code should isolate backend contract changes behind a thin adapter layer.

1. keep raw backend DTO shapes separate from frontend domain models
2. normalize response fields in `src/api/*mappers.ts` before data reaches stores or pages
3. let stores consume domain models only, not backend `snake_case` payloads
4. if backend URLs or payload fields change, prefer fixing `api/*` and mapper files before touching stores, router guards, or pages

## RBAC Resolver Pattern

Permission checks must be backend-first and centralized.

1. resolve permissions from `user -> roles -> permissions`
2. keep `require_permission(...)` as the route-level enforcement boundary
3. eager-load `roles -> permissions` before authz checks to avoid async lazy-load surprises during request handling
4. frontend visibility rules are consumers of backend permission truth, not substitutes for backend enforcement

## Auth Seed Pattern

Initial auth/RBAC data must be created through an idempotent service, not ad hoc SQL.

1. keep baseline permission codes in one central module
2. seed `admin` and `user` roles explicitly
3. assign all baseline permissions to `admin`
4. keep `user` minimal by default and expand intentionally later
5. create the initial admin account from environment-backed config
6. never allow the seeder to run with a placeholder default password
7. if admin password rotation during reseed is needed, gate it behind an explicit boolean setting

## Audit Log Pattern

Audit logging should be service-based and event-shaped.

1. keep audit persistence in a shared service instead of inlining raw ORM writes across routes
2. use stable action codes such as `auth.login_succeeded` and `auth.logout`
3. include request correlation and client IP when the request context is available
4. never log passwords or raw refresh tokens
5. keep auth audit payloads minimal and structured so later dashboards or filters can query them reliably
6. when admin mutation endpoints exist, emit dedicated action codes per mutation instead of reusing generic auth events
7. API đọc audit phải đi qua `AuditLogAdminService`, chỉ đọc, bắt buộc quyền `audit.read`, và dùng keyset cursor `(created_at, id)` thay vì nhúng query tùy ý trong route
8. Audit metadata phải được sanitize tập trung trước khi lưu và trước khi trả response; các key chứa password, token, secret, cookie, authorization, session, credential hoặc signed URL phải bị redact
9. Filter ngày của audit diễn giải boundary nghiệp vụ theo `Asia/Ho_Chi_Minh`, trong đó `created_from` inclusive và `created_to` exclusive
10. Route mutation phải tạo audit context qua `AuditLogContext.from_request(...)`; không import helper IP riêng từ route khác và không dùng trực tiếp `request.client.host` trong API route
11. `X-Forwarded-For` và `X-Real-IP` chỉ được dùng khi IP kết nối trực tiếp nằm trong `TRUSTED_PROXY_CIDRS`; nếu không, audit và rate limit phải dùng IP socket trực tiếp. Production Docker qua Nginx nên dùng subnet compose cố định cho reverse proxy; LAN/VPN direct nên để `TRUSTED_PROXY_CIDRS` rỗng.
12. Khi route mutation cần ghi audit cùng dữ liệu nghiệp vụ, service nghiệp vụ chỉ nên `flush()` và trả entity; route ghi audit rồi `commit()` một lần để mutation và audit event không bị chia transaction
13. Manual backup chỉ được enqueue Redis sau khi `BackupLog` và audit event đã commit thành công; không publish job trước commit vì worker có thể nhận `backup_log_id` chưa tồn tại nếu transaction rollback
14. Worker terminal audit phải ghi trong cùng `AsyncSession` và trước cùng `commit()` với terminal status; metadata chỉ là summary an toàn, không dùng raw exception, stderr, filesystem path, `storage_path`, nội dung CSV, token, password hoặc secret
15. Worker retry với job/log đã ở trạng thái terminal phải return sớm và không tạo thêm terminal audit event; notification side effect không được làm đổi kết quả nghiệp vụ đã hoàn thành

## Enterprise Data Pattern

Large data flows must be server-driven.

DataTable implementations use server-side pagination, filtering, and sorting. Frontend state stores query/selection state, not entire large datasets.

Import/export flows use asynchronous jobs:

1. upload or create request
2. create job
3. process by worker in chunks
4. expose progress/status
5. write output or error report to MinIO
6. audit the operation

## Quotify Quote Version Correction Pattern

Phiếu báo giá giữ lịch sử bất biến bằng version.

1. Không sửa trực tiếp version đã `confirmed`.
2. Khi người dùng nhập sai báo giá đã xác nhận, tạo bản điều chỉnh mới từ phiếu cũ và bắt buộc nhập lý do điều chỉnh.
3. Version điều chỉnh bắt đầu ở trạng thái `draft`; chỉ khi confirm mới trở thành dữ liệu hiệu lực.
4. Khi confirm bản điều chỉnh, các version `confirmed` cũ của cùng quote chuyển sang `superseded`, ghi `superseded_at`, `superseded_by_id` và `superseded_by_version_id`.
5. Dashboard phân tích và danh sách báo giá mặc định chỉ dùng dữ liệu hiệu lực; bản `superseded` vẫn xem được trong lịch sử chi tiết để audit và truy vết.
6. Action chốt mua chỉ áp dụng với version đang `confirmed`; không cho tick mua trên `draft` hoặc `superseded`.
7. Nếu bản điều chỉnh giữ nguyên `received_date` của version hiệu lực cũ, backend phải dùng lại snapshot tỷ giá/nguồn/chi phí trên dòng cũ có cùng `material_id`, `delivery_month`, `currency` và `unit`, rồi tính lại giá quy đổi theo `price_original` mới.
8. Nếu bản điều chỉnh đổi `received_date` sang ngày nghiệp vụ hiện tại, backend phải resolve lại tỷ giá Vietcombank tự động theo quy tắc báo giá trong ngày; frontend không được tự ép ngày nhận về hôm nay khi clone bản điều chỉnh.
9. Chỉ được xóa version `draft`. Không xóa version `confirmed` hoặc `superseded`.
   Nếu draft là version duy nhất, xóa cả phiếu nháp; nếu quote đã có version hiệu
   lực, chỉ xóa draft điều chỉnh. Mọi xóa draft phải ghi audit
   `quotes.version_deleted` và vẫn đi qua ownership guard.

## Quotify Quote Ownership Mutation Pattern

Permission code chỉ là điều kiện cần cho mutation phiếu báo giá, không phải điều
kiện đủ.

1. Role `admin` được thao tác trên tất cả phiếu báo giá.
2. Role `user` chỉ được sửa, confirm, xóa bản nháp, upload/thay tệp,
   tick/untick chốt mua và tạo bản điều chỉnh trên phiếu có
   `Quote.created_by_id == current_user.id`.
3. Backend route mutation phải gọi helper ownership chung trước khi gọi service
   hoặc ghi audit. Frontend chỉ ẩn/disable action để UX rõ hơn, không được coi là
   lớp bảo mật.
4. Với mutation theo resource con như `line_id`, `version_id` hoặc
   `revision_id`, route phải kiểm resource con thuộc đúng `quote_id` trên path
   để tránh thao tác chéo phiếu bằng ID hợp lệ của phiếu khác.
5. Regression test phải cover ít nhất ba nhánh: User khác chủ phiếu bị `403`,
   User là chủ phiếu được phép, Admin được phép trên phiếu của người khác.

## Quotify Quote Note Collaboration Pattern

Ghi chú thị trường là phần cộng tác nhận định, không phải mutation dữ liệu báo
giá lõi.

1. User có `quote_notes.read` được đọc ghi chú của phiếu báo giá mà họ truy cập
   được.
2. User có `quote_notes.create` được thêm revision ghi chú trên mọi phiếu báo giá
   mà họ đọc được, không bị giới hạn bởi `Quote.created_by_id`.
3. Nút `Thêm` trong card `Ghi chú thị trường` phải dựa vào
   `quote_notes.create`, không dựa vào `quotes.update` hoặc ownership quote.
4. Sửa/xóa revision ghi chú dùng quyền riêng `quote_notes.update`; user thường
   chỉ được sửa/xóa revision có `author_id == current_user.id`, còn Admin được
   quản trị tất cả.
5. Backend vẫn phải kiểm `revision_id` thuộc đúng `quote_id` trên path trước khi
   kiểm tác giả để tránh thao tác chéo phiếu.
6. Không dùng helper ownership của mutation quote cho endpoint thêm ghi chú, vì
   điều đó sẽ làm user thường không thể góp nhận định vào báo giá của người khác.

## User Avatar Upload Pattern

User avatars should not be entered as raw external URLs in admin forms.

1. the Users module owns avatar upload UX and permission checks
2. avatar binaries are still stored through the shared file-storage service and MinIO adapter
3. the Users API exposes a dedicated avatar-upload endpoint so user administration does not depend on generic `files.upload` UI permissions
4. create/edit user forms upload the image first, receive an `avatar_url`, then submit normal JSON payloads to create/update the user
5. current avatar rendering relies on a directly displayable URL suitable for `<img>` preview in the admin UI
6. browser-facing file/avatar URLs should be returned as same-origin relative API paths, not absolute URLs derived from backend host metadata
7. nếu user không có `avatarUrl`, frontend phải hiển thị avatar mặc định nội bộ từ `frontend/public/default-avatars/` thông qua helper dùng seed ổn định ưu tiên `user.id`; không ghi URL avatar mặc định vào database và không thay thế ảnh thật đã upload
8. cùng một user phải có cùng avatar fallback ở mọi nơi trong cùng phiên đăng nhập và giữa các page, ví dụ topbar, hồ sơ, danh sách user và card `Ghi chú thị trường`; không seed fallback bằng id của bản ghi phụ như `revision.id`

## Production Readiness Pattern

Production readiness is part of the architecture, not a deployment afterthought.

Every production service must have:

- observability: logs, metrics, traces, request/correlation id
- backup/restore: scheduled backups, retention, restore drill
- secret management: environment-specific secret source, no committed secrets
- SLO: explicit availability, latency, error-rate targets
- compliance gates: lint, tests, security scans, image scans, migration checks, backup health

## Backend Scaffold Pattern

The backend uses a thin-entrypoint FastAPI structure:

1. `app/main.py` exposes the ASGI app
2. `app/core/application.py` owns app creation and middleware wiring
3. `app/api/router.py` and `app/api/v1/router.py` compose routers by version
4. `app/core/config.py` owns typed settings
5. `app/db/session.py` owns SQLAlchemy async engine/session factory
6. `app/storage/minio.py` owns MinIO client construction

Health endpoints exist at both `/health` and `/api/v1/health`.

Request correlation is centralized through middleware, not repeated inside route handlers.

## Frontend Scaffold Pattern

The frontend uses a thin-SFC and external-logic pattern:

1. `src/main.ts` wires Pinia, Router, PrimeVue, and theme initialization
2. `src/router/index.ts` owns route registration
3. `src/stores/` owns cross-page UI state such as theme and layout
4. `src/composables/` owns page logic and validation orchestration
5. `src/layouts/` owns the admin shell
6. `src/components/` owns reusable view blocks
7. `src/styles/` is the source of truth for tokens, base styles, vendors, layouts, components, and pages
8. `src/styles/main.scss` is the single style entrypoint imported by `src/main.ts`

Vue SFCs must not use style blocks. Keep styles in the centralized `src/styles/**/*.scss` tree and rely on explicit class namespaces per component/layout/page.

The frontend lint pipeline should fail if any `.vue` file contains a `<style>` block.

Vitest unit tests must not scan Playwright specs. Keep `tests/unit` and `tests/e2e` separated and constrain Vitest `include` patterns explicitly.

PrimeVue is configured with a custom preset and `darkModeSelector` bound to `.app-dark` so manual theme switching stays consistent across shared components.

Admin shell should follow a Sakai-like separation of concerns:

1. topbar owns global controls such as sidebar toggle, theme mode, notifications, profile, and logout
2. page context such as section label and page title should live in a dedicated page-header area below the topbar, not inside the topbar itself
3. collapsed desktop sidebar must switch nav to icon-first rendering and hide text labels instead of letting them overflow
4. mobile sidebar must not stay in normal page flow; it should open as an off-canvas overlay with a backdrop so the topbar and content remain vertically ordered
5. footer belongs to the shared admin shell, not to individual pages, so global metadata such as product identity and default timezone stay consistent across the app
6. authenticated user controls should be compact: dark/light toggle plus avatar trigger in the topbar, with account actions exposed through an avatar dropdown instead of a persistent email chip or standalone logout button
7. Điều hướng sidebar phải tách nhóm quản trị người dùng khỏi nhóm quản trị hệ thống; khi thêm menu mới, đặt item vào đúng nhóm thay vì mở rộng một danh sách phẳng bị trộn lẫn

## Docker Dev Pattern

Docker dev should optimize for repeatable local startup and low-friction rebuilds:

1. keep dedicated Dockerfiles under `docker/`
2. use a root `.dockerignore` so build context excludes docs, memory, vendor mirrors, caches, and local artifacts
3. keep source bind-mounted for backend/frontend dev loops
4. persist `.venv` and `node_modules` in named volumes so bind mounts do not erase installed dependencies
5. expose infra ports through environment-overridable host-port variables because `5432`, `9000`, and `9001` frequently collide with other local services
6. verify service readiness with healthchecks and container-internal HTTP calls when host localhost access is constrained by the agent environment

## Docker Production Pattern

Docker production should differ from dev in explicit, auditable ways:

1. use multi-stage Dockerfiles with separate `dev` and `prod` targets
2. do not mount source code in production compose
3. run backend with a non-reload server command
4. build frontend static assets ahead of runtime instead of serving Vite dev server
5. place reverse-proxy routing in `docker/nginx/` and keep `/api/*` to backend, `/` to frontend
6. do not publish Postgres or MinIO ports publicly in production scaffold unless a later requirement explicitly needs it
7. keep the public entrypoint isolated to a single proxy port that is environment-overridable

## Docker Test Pattern

Docker test should separate runner responsibilities:

1. keep `backend-test`, `frontend-test`, and `e2e-test` as explicit services
2. give test infra its own Postgres/MinIO services and volumes
3. set `PYTHONPATH=/app` explicitly for backend test containers when the package layout requires it
4. point browser E2E at internal service DNS names like `frontend-e2e` and `backend-e2e`
5. prefer a dedicated Docker build path for Playwright dependencies instead of relying on host-installed browsers
6. when browser tests hit a Vite dev server through Docker DNS, explicitly allow the service hostname in `server.allowedHosts`

## Playwright E2E Pattern

Trong repo này, cách chạy Playwright chuẩn là:

```bash
make docker-test-e2e
```

Không chạy Playwright trực tiếp bằng `docker compose exec frontend ...` hoặc
container dev đang sống nếu mục tiêu là kết luận tính năng đã ổn. Lý do:

- `frontend`/`frontend-e2e` target `dev` không đảm bảo đã cài browser system
  dependencies của Playwright.
- Docker Playwright E2E chạy `workers: 1` trong `frontend/playwright.docker.config.ts`
  để tránh các test auth song song tự vượt rate limit đăng nhập. Nếu cần tăng
  worker, phải điều chỉnh rate-limit E2E hoặc giảm số lần login trong suite trước.
- E2E credentials (`E2E_ADMIN_EMAIL`, `E2E_ADMIN_PASSWORD`) được inject qua
  service `e2e-test` trong `docker-compose.test.yml`, không nằm mặc định trong
  container frontend dev.
- `e2e-test` dùng Dockerfile target `e2e`, trong đó có
  `npx playwright install --with-deps chromium`; đây là nơi hợp lệ để có browser
  và dependency hệ thống.
- `make docker-test-e2e` dùng `docker compose -f docker-compose.test.yml run
  --build --rm e2e-test`, nên image được rebuild theo source hiện tại và tránh
  lỗi stale image.
- Base URL Docker E2E là `http://frontend-e2e:4173` theo
  `frontend/playwright.docker.config.ts`; Vite dev server phải allow hostname
  `frontend-e2e`.

Chỉ dùng lệnh local:

```bash
npm --prefix frontend run test:e2e
```

khi đã tự chạy được frontend/backend local đúng port, có browser Playwright trên
máy host, và đã set env cần thiết cho spec. Không dùng lệnh local để thay thế
Docker E2E khi task liên quan auth, cookie, proxy, audit hoặc network.

## Quality Gate Pattern

The root `Makefile` is the canonical developer entrypoint for pre-commit checks:

1. `make backend-check` runs backend lint, format-check, typecheck, tests, and Bandit
2. `make frontend-check` runs frontend lint, format-check, typecheck, and unit tests
3. `make frontend-test-e2e` is a separate local browser gate because host socket policies may differ by environment
4. `make docker-test-e2e` is the reliable browser E2E gate for sandboxed or CI-like environments
5. `make check` should stay stable and fast enough for routine local validation

Docker test targets must rebuild before running:

- `docker-test-backend`, `docker-test-frontend`, and `docker-test-e2e` use
  `docker compose run --build --rm ...`.
- This prevents stale images from hiding or inventing failures after files such
  as `alembic.ini`, Playwright specs, Dockerfiles, or package manifests change.
- If a Docker E2E failure references a path or config that no longer exists in
  the current worktree, suspect a stale image first and re-run through the
  Makefile target.

Phase 5 hardening adds a second layer of quality gates:

- `make backend-dependency-audit`
- `make frontend-dependency-audit`
- `make security-check`
- `make perf-users-list`
- `make perf-users-export`

These commands must be runnable from a clean clone without depending on host Python packages or writable cache paths under `$HOME`. If a command needs Python dependencies, run it through the backend environment (`.venv` or `uv run`). If a command uses package-manager caches, direct them to writable paths such as `/tmp` in restricted environments.

For security/rate-limit route tests in this repo, prefer a mixed strategy:

- runtime request tests for stable paths like headers and general API behavior
- unit tests for limiter engines
- route-contract assertions for dependency wiring on upload/export endpoints when ASGI multipart/request-path tests become unstable in the sandbox harness

This keeps hardening verification deterministic without falsely treating sandbox transport behavior as an application bug.

## Mobile CRUD Page Width Discipline

Shared admin-shell responsiveness is not enough on its own. CRUD pages that contain filter bars, action groups, and PrimeVue DataTables must also enforce their own mobile width discipline:

- header/filter/action wrappers need `min-width: 0`
- search/select controls must drop desktop `min-width` constraints on mobile
- mobile action groups should stack vertically and use full-width buttons
- table card wrappers should use `overflow-x: auto` rather than clipping, so horizontal table content scrolls inside the card instead of stretching the whole page

If page-level containers do not follow these rules, the entire page can overflow horizontally and make shared shell controls like the topbar toolbar appear missing off-screen.

## Frontend Audit Viewer Pattern

Audit Log viewer frontend phải giữ boundary nhỏ và read-only:

- API client chỉ gọi `GET /audit-logs` qua shared `apiRequest`, truyền Bearer token
  và `credentials: include` theo chuẩn hiện tại.
- Mapper chịu trách nhiệm snake_case -> camelCase và format thời gian theo
  `VITE_APP_TIMEZONE` fallback `Asia/Ho_Chi_Minh`.
- Composable page giữ filter state, loading/error state và cursor map cho keyset
  pagination tuần tự; Vue page chỉ render UI và gọi action từ composable.
- DataTable vẫn dùng paginator chuẩn của giao diện: rows mặc định 10, options
  10/20/30/50, `RowsPerPageDropdown` đứng trước điều hướng, và report
  `Hiển thị từ {first} đến {last} trên tổng số {totalRecords} dòng`. Với backend
  keyset cursor, không bật `PageLinks` hoặc `LastPageLink` nếu chưa có offset
  hoặc cursor snapshot hỗ trợ nhảy trang bền vững.
- Table mặc định phải ưu tiên thông tin người dùng hiểu được: email/người thao
  tác, nhãn hoạt động tiếng Việt, đối tượng dễ nhận diện và tóm tắt thay đổi.
  Các định danh kỹ thuật như actor user id, entity id, request id và IP chỉ nên
  nằm trong bộ lọc nâng cao hoặc dialog chi tiết.
- Metadata của mutation nên có cấu trúc `changes`, mỗi item gồm `field`, `label`,
  `old_value` và `new_value`. Với user create/update, route phải snapshot trạng
  thái trước/sau ở boundary API để ghi được thay đổi thật, gồm cả `avatar_url`;
  thông tin nhạy cảm như mật khẩu chỉ được biểu diễn bằng nhãn an toàn, không ghi
  raw secret vào metadata.
- Route và sidebar phải cùng gated bằng `audit.read`; không thêm permission cục bộ
  khác cho viewer.
- Metadata dialog chỉ render `metadata` đã được backend sanitize, không tự gọi thêm
  endpoint thô hoặc dựng lại dữ liệu nhạy cảm ở frontend.

## Import Job Substrate Pattern

Các luồng import bất đồng bộ phải dùng `ImportJob` như substrate dùng chung, không
hardcode toàn bộ logic quanh user import:

- `ImportJob.entity_type` xác định nghiệp vụ import, ví dụ `users`,
  `materials`, `suppliers`.
- `ImportJob.task_name` là tên Redis/RQ task được enqueue, ví dụ
  `import_users_task`.
- Service tạo import job chỉ tạo record và `flush`; route chịu trách nhiệm ghi
  audit start event và `commit` file/job/audit cùng transaction trước khi gọi
  `enqueue_import_job(...)`.
- Các endpoint thuộc user import phải luôn filter `entity_type="users"` để job
  catalog sau này không bị lộ vào màn hình import user.
- Worker phải kiểm tra `entity_type` trước khi xử lý task cụ thể, và phải đọc
  CSV theo streaming/chunk. Không dùng `rows = list(reader)` hoặc đọc toàn bộ
  CSV vào RAM trong worker.
- Terminal status và terminal audit event phải được ghi cùng transaction. Metadata
  audit của import chỉ chứa summary an toàn và các trường đã allowlist.
- Catalog import dùng route riêng `/catalog-imports`, trong đó server allowlist
  `entity_type` và tự map permission `material_types.import`, `materials.import`
  hoặc `suppliers.import`; client không được truyền permission code.
- Mỗi loại catalog có template CSV riêng và phải validate header trước khi xử lý
  row. `completed` được phép có `failed_rows > 0` nếu vẫn có dòng được xử lý
  thành công; `failed` dành cho lỗi toàn file, header sai, file rỗng hoặc toàn bộ
  dòng đều lỗi.
- Error report của catalog import được dựng từ `ImportJob.errors_json` qua route
  `/catalog-imports/{job_id}/error-file`, sau khi kiểm tra job đúng loại catalog
  và người dùng có permission import tương ứng. Không dùng `files.read_all` để
  tải lỗi import catalog.

## Quotify Pricing And Exchange Rate Pattern

Luồng quy đổi giá của Quotify phải giữ provenance ổn định và không tính lại dữ
liệu lịch sử bằng cấu hình hiện tại:

- Không dùng `float` cho tiền, tỷ giá hoặc giá quy đổi. Backend dùng `Decimal`,
  `ROUND_HALF_UP` và scale 2 chữ số cho `conversion_cost_vnd_per_kg`, tỷ giá và
  `converted_price_vnd_per_kg`.
- Cặp USD/MT được quy đổi theo công thức `(Giá USD/MT / 1000) * tỷ giá USD bán ra
  + chi phí quy đổi`; rounding chỉ thực hiện một lần ở backend sau khi cộng chi
  phí.
- Ngày hiện tại của nghiệp vụ tỷ giá phải tính theo `Asia/Ho_Chi_Minh`, không
  dùng timezone host, UTC date hoặc `date.today()` không timezone.
- Phase 4 chỉ có helper đọc USD bán ra hôm nay và cấu hình chi phí quy đổi hiện
  hành. Không tạo CRUD hoặc bảng snapshot tỷ giá độc lập; Phase 5/quote write
  flow sẽ đóng băng rate/source/retrieved-at/manual reason trực tiếp trên
  `QuoteLine`.
- Frontend Phase 4 chỉ expose màn hình cấu hình chi phí quy đổi và API client
  cho helper tỷ giá. Màn hình quote sau này phải tái sử dụng client/mapper này,
  không gọi `fetch` trực tiếp hoặc tự định nghĩa lại DTO tỷ giá/cấu hình trong
  component.
- Route không gọi HTTP ra Vietcombank trực tiếp. Nguồn ngoài phải đi qua adapter
  `VietcombankExchangeRateClient`, bọc `httpx`, có timeout/retry bằng typed
  settings và test bằng fixture/mock transport, không gọi live Vietcombank trong
  unit test.
- Endpoint gọi nguồn tỷ giá ngoài phải có rate limit riêng và quyền
  `exchange_rates.read`. Cấu hình chi phí quy đổi dùng `quotify_settings.read` và
  `quotify_settings.update`.
- Audit update cấu hình phải dùng metadata `changes` có `field`, `label`,
  `old_value`, `new_value`; mọi key metadata mới cho pricing/exchange-rate phải
  được đưa vào sanitizer allowlist trước khi ghi event.

## Production Readiness Pattern

Production-readiness in this repo is split into four layers:

1. application runtime:
   - structured logs
   - request id propagation
   - `/metrics`
   - `/ready`
   - optional OpenTelemetry exporter configuration
2. observability stack assets:
   - collector config
   - Prometheus scrape config
   - alert rules
3. recovery assets:
   - backup scripts
   - restore scripts
   - restore drill helper
   - written runbooks
4. compliance gate:
   - a script that validates required assets exist and production compose files parse correctly

The repo should not treat production readiness as "docs only". At minimum, each layer above must have either runnable code, executable scripts, or machine-checkable config committed in the repo.
