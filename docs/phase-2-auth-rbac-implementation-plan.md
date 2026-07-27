# Kế Hoạch Triển Khai Phase 2: Auth + RBAC

Ngày tạo: 10/06/2026

## Trạng thái

Phase 2 hiện đã hoàn thành trong codebase.

Đã xác minh lại bằng backend quality gate:

- `uv run pytest`
- `uv run ruff check .`
- `uv run mypy .`

Scope audit log của phase này cũng đã được hoàn tất: không chỉ auth events mà cả admin mutation tối thiểu cho tạo user và cập nhật role user.

## Mục tiêu

Phase 2 triển khai nền tảng authentication và authorization cho boilerplate.

Kết thúc phase này, repository phải có:

- user model và migration nền tảng
- role/permission model và mapping đầy đủ
- login, refresh, logout, me
- permission dependency cho backend
- route guard và auth state cơ bản cho frontend
- admin seed ban đầu
- audit log nền tảng cho auth và thay đổi role/user
- test nền tảng cho auth, RBAC và các failure mode quan trọng

Phase này phải tạo được một baseline đủ tốt để sang Phase 3 có thể làm `Login page`, `Users CRUD`, `Roles CRUD` và guard UI mà không phải viết lại auth core.

## Phạm vi

### Trong scope

- Thiết kế và tạo bảng `users`, `roles`, `permissions`, `user_roles`, `role_permissions`, `refresh_tokens`, `audit_logs`
- Tạo migration Alembic cho auth/RBAC
- Tạo password hashing, JWT access token, refresh token
- Tạo auth service và permission guard
- Tạo API:
  - `POST /api/v1/auth/login`
  - `POST /api/v1/auth/refresh`
  - `POST /api/v1/auth/logout`
  - `GET /api/v1/auth/me`
- Tạo admin seed đầu tiên
- Tạo frontend auth store, API client, router guard và auth bootstrap
- Tạo page/login flow tối thiểu đủ để verify auth round-trip
- Tạo test backend/frontend cho auth + RBAC nền tảng
- Ghi audit log cho login/logout và thay đổi user/role quan trọng

### Ngoài scope

- Chưa cần hoàn thiện Users CRUD đầy đủ
- Chưa cần Roles CRUD UI đầy đủ
- Chưa cần password reset workflow qua email
- Chưa cần MFA
- Chưa cần session/device management nâng cao
- Chưa cần SSO OAuth/OIDC
- Chưa cần public register user

## Nguyên tắc bắt buộc

1. Không có public register.
2. Không hardcode secret, token config hay default password vào source runtime.
3. Mọi endpoint nhạy cảm phải có permission policy rõ ràng.
4. Không trộn lẫn `authentication` và `authorization` vào một service mơ hồ.
5. Route FastAPI chỉ nhận input, gọi service, trả response.
6. Password không được log, không được trả lại response.
7. Thời gian hết hạn token, audit log timestamp và mọi business-facing datetime phải explicit timezone theo `Asia/Ho_Chi_Minh` hoặc UTC-to-display policy đã khai báo.
8. Frontend không tự suy luận quyền từ UI; quyền phải đi từ backend contract.
9. Không lưu hàng loạt permission logic rải rác trong component/page; guard tập trung trong `stores`, `router`, `composables`.
10. Mọi thay đổi auth/RBAC phải có test và audit log tương ứng ở mức hợp lý.

## Deliverables

### Backend

Tạo hoặc hoàn thiện các vùng sau:

```text
backend/app/
├── api/v1/
│   ├── auth.py
│   ├── users.py
│   └── roles.py
├── auth/
│   ├── dependencies.py
│   ├── hashing.py
│   ├── jwt.py
│   ├── permissions.py
│   └── service.py
├── db/
├── models/
│   ├── user.py
│   ├── role.py
│   ├── permission.py
│   ├── refresh_token.py
│   └── audit_log.py
├── repositories/
├── schemas/
│   ├── auth.py
│   ├── user.py
│   └── role.py
└── services/
```

Backend phải có:

- user entity với status, email, password hash, timestamps
- role và permission entity theo dạng string ổn định
- many-to-many mapping `user_roles`, `role_permissions`
- refresh token persistence hoặc revocation strategy rõ ràng
- permission dependency kiểu `require_permission("users.read")`
- audit log nền tảng cho login/logout/user-role change
- seed dữ liệu ban đầu:
  - role `admin`
  - role `user`
  - permission nền tảng
  - admin user đầu tiên

### Frontend

Tạo hoặc hoàn thiện:

```text
frontend/src/
├── api/
│   ├── auth.api.ts
│   └── http.ts
├── composables/
│   └── useLoginPage.ts
├── pages/
│   └── LoginPage.vue
├── router/
│   └── guards.ts
├── stores/
│   ├── auth.store.ts
│   └── permission.store.ts
└── types/
    └── auth.ts
```

Frontend phải có:

- login page tối thiểu
- auth store lưu access state, current user, roles/permissions đã resolve
- router guard cho public/protected route
- bootstrap auth state khi app load
- logout flow cơ bản
- UI guard nền tảng cho shell/menu dựa trên permission
- form validation cho login bằng VeeValidate + Zod

### Security Baseline

Phase 2 phải chốt rõ:

- hash password bằng Argon2 hoặc cơ chế tương đương đủ mạnh
- refresh token strategy:
  - rotation hoặc revocation rõ ràng
- token expiry config qua env
- error message không làm lộ tài khoản tồn tại hay không
- audit log cho event auth quan trọng
- rate limit định hướng cho login/refresh nếu chưa implement ngay thì phải ghi rõ deferred item

## Thứ tự triển khai

### Bước 1: Chốt auth strategy

1. Chọn hybrid strategy:
   - `access token` ngắn hạn qua `Authorization Bearer`
   - `refresh token` qua `httpOnly cookie`
2. Chốt access token expiry baseline: `15 phút`.
3. Chốt refresh token expiry baseline: `7 ngày`.
4. Chốt refresh token persistence strategy:
   - không lưu raw token
   - chỉ lưu token id hoặc hash
5. Chốt timezone policy cho token/audit timestamp:
   - runtime timestamp explicit
   - business-facing display theo `Asia/Ho_Chi_Minh`
6. Bám theo quyết định đã ghi trong `docs/phase-2-auth-strategy-decision.md`.

Kết quả:

- Có một auth contract rõ ràng trước khi viết model và API.

### Bước 2: Database model + migration

1. Tạo model `users`.
2. Tạo model `roles`, `permissions`.
3. Tạo bảng mapping `user_roles`, `role_permissions`.
4. Tạo `refresh_tokens`.
5. Tạo `audit_logs`.
6. Viết migration Alembic đầu tiên cho auth/RBAC.

Kết quả:

- Schema auth/RBAC chạy được bằng migration.

### Bước 3: Auth core service

1. Viết password hashing module.
2. Viết JWT module.
3. Viết auth service:
   - verify credential
   - issue token
   - refresh token
   - revoke/logout
4. Viết current-user dependency.

Kết quả:

- Backend có auth core độc lập, testable, không phụ thuộc route.

### Bước 4: Permission guard + RBAC service

1. Viết permission resolver từ user -> roles -> permissions.
2. Viết dependency `require_permission(...)`.
3. Tạo helper cho super-admin/admin default role.
4. Chặn endpoint nhạy cảm bằng dependency.

Kết quả:

- RBAC hoạt động thật ở backend, không chỉ là data model.

### Bước 5: Auth API

1. Tạo `login`.
2. Tạo `refresh`.
3. Tạo `logout`.
4. Tạo `me`.
5. Chuẩn hóa response schema, error schema.

Kết quả:

- FE có đủ contract để đăng nhập và bootstrap session.

### Bước 6: Seed dữ liệu nền tảng

1. Seed permission nền tảng.
2. Seed role `admin` và `user`.
3. Seed admin user đầu tiên.
4. Ghi rõ command tạo/refresh seed.

Kết quả:

- Có tài khoản và role mặc định để dev/test/E2E dùng được ngay.

### Bước 7: Frontend auth foundation

1. Tạo `auth.api.ts`.
2. Tạo `auth.store.ts`.
3. Tạo `permission.store.ts` hoặc resolver tương đương.
4. Tạo `router` guard.
5. Tạo `LoginPage.vue`.
6. Nối login -> redirect -> protected page.
7. Nối logout -> clear state -> về login.

Kết quả:

- FE đăng nhập được và guard route đúng.

### Bước 8: Audit log nền tảng

1. Log login success/fail.
2. Log logout.
3. Log admin tạo user hoặc đổi role nếu endpoint đó xuất hiện trong phase này.
4. Chuẩn hóa payload audit.

Kết quả:

- Auth/RBAC có trace nền tảng để phục vụ hardening phase sau.

### Bước 9: Test + hardening nền tảng

1. Backend unit test:
   - password hashing
   - token issue/refresh
   - permission resolver
2. Backend API test:
   - login
   - refresh
   - me
   - logout
   - forbidden access
3. Frontend unit test:
   - auth store
   - router guard
   - login form validation
4. Frontend E2E smoke:
   - login success
   - protected route access
   - logout

Kết quả:

- Auth + RBAC có regression net đủ dùng cho phase kế tiếp.

## API Contract Tối Thiểu

### Auth

```text
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/auth/me
```

### User/Role Foundation

Nếu cần để unblock Phase 3, có thể tạo read-only foundation endpoints:

```text
GET /api/v1/permissions
GET /api/v1/roles
GET /api/v1/users/me/permissions
```

Nhưng chỉ tạo nếu thật sự phục vụ bootstrap FE hoặc admin seed verification.

## Test Matrix

### Backend

- Login đúng credential trả token hợp lệ
- Login sai credential bị từ chối
- Refresh token hết hạn bị từ chối
- Logout revoke được refresh token
- `me` trả đúng role/permission
- Endpoint có guard trả `403` nếu thiếu permission
- User disabled/inactive không đăng nhập được

### Frontend

- Login form validate email/password đúng
- Login success lưu state và redirect đúng
- Login fail hiển thị error đúng
- Protected route bị redirect nếu chưa auth
- Logout clear state và quay lại login

### Security/Edge Cases

- Không lộ password hash trong serializer
- Không lộ permission ngoài scope cần thiết
- Không chấp nhận token malformed
- Không bị lệch ngày do token/audit timestamp xử lý sai timezone

## Acceptance Criteria

Phase 2 được coi là xong khi:

1. Có migration auth/RBAC chạy được trên Postgres.
2. Có admin seed dùng được ngay.
3. Login, refresh, logout, me hoạt động end-to-end.
4. Có permission dependency thực sự chặn endpoint.
5. FE có login page và protected route guard.
6. Test backend/frontend chính của auth pass.
7. Audit log nền tảng cho auth event đã tồn tại.
8. Cấu hình thời gian/token không dùng timezone mơ hồ.

## Rủi ro Và Giảm Thiểu

### Rủi ro 1: Chọn sai token transport

Nếu chọn sai từ đầu, Phase 3 và Phase 5 sẽ phải sửa rộng.

Giảm thiểu:

- chốt strategy ngay ở Bước 1
- ghi rõ trade-off trong docs trước khi code

### Rủi ro 2: RBAC bị hardcode theo UI

Frontend dễ tự giấu/hiện nút nhưng backend không chặn thật.

Giảm thiểu:

- backend permission dependency là nguồn sự thật
- frontend chỉ là consumer của permission contract

### Rủi ro 3: Schema auth thiếu extensibility

Sau này thêm MFA, SSO, reset password sẽ khó mở rộng.

Giảm thiểu:

- tách `auth/`, `services/`, `repositories/` rõ ràng
- không nhét logic vào route handler

### Rủi ro 4: Bug thời gian ở token và audit log

Lỗi lệch ngày/giờ có thể làm expire token sai hoặc audit log khó điều tra.

Giảm thiểu:

- dùng UTC cho lưu trữ nếu cần, nhưng display và business boundary phải explicit
- test timezone boundary theo `Asia/Ho_Chi_Minh`

## Ghi Chú Cho Agent Implement

1. Đọc lại `docs/fullstack-boilerplate-design.md` phần `Authentication`, `Authorization`, `Database`, `Security`, `API Contract`.
2. Không viết Roles CRUD đầy đủ trong Phase 2 nếu chưa cần cho login/RBAC foundation.
3. Không tạo UI auth phức tạp hơn yêu cầu phase này.
4. Nếu phải chọn giữa “nhanh” và “đúng boundary”, ưu tiên boundary đúng.
5. Mọi bug auth/RBAC đã fix phải được ghi ngay vào `memory-bank/bugPatterns.md`.
