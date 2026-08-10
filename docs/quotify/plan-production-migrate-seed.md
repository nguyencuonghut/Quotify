# Phương án: Migrate + Seed cho môi trường Production

## 1. Bối cảnh

Makefile hiện có 3 lệnh, tất cả đang trỏ vào compose context mặc định (dev), không phải `docker-compose.prod.yml`:

```makefile
migrate:
	docker compose exec backend uv run alembic upgrade head

migrate-refresh:
	docker compose exec backend uv run alembic downgrade base
	docker compose exec backend uv run alembic upgrade head

seed:
	docker compose exec backend uv run python scripts/seed_auth_rbac.py
	docker compose exec backend uv run python scripts/seed_quotify.py
```

Yêu cầu: chạy đúng trên production — (a) migrate đầy đủ toàn bộ table, (b) seed vừa đủ (1 admin + giá trị khởi tạo cần để hệ thống chạy đúng), không seed dư dữ liệu không phù hợp cho một hệ thống thật.

## 2. Rà soát hành vi thực tế của từng phần

### 2.1. `alembic upgrade head` — an toàn cho production

Áp dụng tuần tự toàn bộ migration, tạo đủ mọi table hiện có. Migration
`20260728_0930_seed_default_quotify_settings.py` seed sẵn 1 dòng `quotify_settings`
mặc định ngay trong quá trình migrate (idempotent, dùng `INSERT ... ON CONFLICT`-style
check) — nghĩa là **giá trị khởi tạo hệ thống (settings) đã được migration lo, không
cần thêm bước seed riêng cho phần này.**

### 2.2. `alembic downgrade base && upgrade head` (`migrate-refresh`) — PHẢI CẤM DÙNG TRÊN PROD

`downgrade base` xoá toàn bộ schema (và dữ liệu). Đây là lệnh chỉ dành cho
dev/test để "làm mới" DB. Tuyệt đối không được có đường chạy tới lệnh này trong
quy trình production — kể cả vô tình gõ nhầm target.

### 2.3. `scripts/seed_auth_rbac.py` → `AuthSeedService.seed()` — đúng là phần "seed vừa đủ"

Đã đọc `backend/app/services/auth_seed.py`:

- Idempotent: chỉ tạo permission/role/admin nếu chưa có; nếu đã có thì cập nhật
  trạng thái/role, không tạo trùng.
- Tự chặn seed nếu `AUTH_SEED_ADMIN_PASSWORD` rỗng hoặc còn là placeholder
  `change-me-admin-password` → ném `AuthSeedConfigurationError`, dừng seed. Đây
  là cơ chế bảo vệ đã có sẵn, không cần thêm gì.
- Chỉ cập nhật lại password admin khi `AUTH_SEED_UPDATE_ADMIN_PASSWORD=true`
  (mặc định `false` trong `.env.production.example`) — an toàn để chạy lại
  nhiều lần mà không vô tình reset password admin đang dùng.
- Kết quả: đúng 1 tài khoản admin (từ `AUTH_SEED_ADMIN_EMAIL`) + toàn bộ
  permission trong `BASE_PERMISSION_CODES` + 2 role hệ thống (`admin` có full
  quyền, `user` có quyền baseline).

→ **Đây chính là phần "seed vừa đủ: 1 admin + giá trị khởi tạo để chạy đúng"
mà yêu cầu đang nhắc tới.** Không có phần nào trong script này tạo dữ liệu
nghiệp vụ hay tài khoản người dùng thật khác ngoài admin.

### 2.4. `scripts/seed_quotify.py` → `QuotifySeedService.seed()` — CẦN CẢNH BÁO, KHÔNG NÊN CHẠY THẲNG TRÊN PROD

Đã đọc `backend/app/quotify/seed_data.py` và `backend/app/services/quotify_seed.py`.
Script này seed 3 loại dữ liệu rất khác nhau về bản chất, đang bị gộp chung
một lệnh:

1. **Danh mục nghiệp vụ tĩnh** (`MATERIAL_TYPE_SEEDS`, `MATERIAL_SEEDS`): 4 nhóm
   vật tư + ~27 mã vật tư (Ngô hạt, Khô dầu đậu nành, Lúa mì, DDGS, Bột cá,
   Premix, Bao bì...). Đây là dữ liệu cấu hình nghiệp vụ hợp lệ, cần có để hệ
   thống có danh mục mà tạo báo giá — **nên seed trên production.**
2. **Danh sách nhà cung cấp mẫu quốc tế** (`SUPPLIER_SEEDS`, ví dụ Cargill,
   Bunge, ADM, LDC, Wilmar, Tan Long...) — cần xác nhận với nghiệp vụ đây có
   phải danh sách nhà cung cấp THẬT đang giao dịch hay chỉ là dữ liệu mẫu dùng
   để test tính năng. Nếu là thật thì nên seed; nếu là mẫu thì không nên đưa
   vào production.
3. **7 tài khoản người dùng thật thuộc phòng Thu Mua** (`QUOTIFY_USER_SEEDS`),
   với email thật `@honghafeed.com.vn` / `@longhaigroup.com.vn`, và **mật khẩu
   dùng chung, hard-code dạng plaintext trong source code**: `Hongha@123`.

Điểm 3 là rủi ro thật, không phải rủi ro giả định: một mật khẩu cố định, nằm
trong source code (ai đọc được repo là biết mật khẩu), tự động được gán cho
7 tài khoản email thật — nếu chạy thẳng script này lên production, hệ thống
thật sẽ có 7 tài khoản thật với mật khẩu ai cũng biết trước, không có bước bắt
đổi mật khẩu lần đầu.

**Đã xác nhận với nghiệp vụ (2026-08-10):**

- Danh sách nhà cung cấp trong `SUPPLIER_SEEDS` **không phải dữ liệu thật** —
  chỉ là dữ liệu mẫu, không seed lên production.
- 7 tài khoản Thu Mua thật trong `QUOTIFY_USER_SEEDS` **tạo thủ công** (qua
  UI/API tạo user với mật khẩu riêng từng người), **không đưa vào seeder của
  production**.

**Quyết định:**

- Production seed **KHÔNG chạy `seed_quotify.py` nguyên bản** (script này gộp
  cả 2 phần không phù hợp production ở trên).
- Tách riêng phần danh mục vật tư (material types + materials — dữ liệu
  nghiệp vụ thật, cần để hệ thống tạo báo giá đúng) thành một service method
  mới `QuotifySeedService.seed_material_catalog()` (`backend/app/services/quotify_seed.py`)
  và script riêng `backend/scripts/seed_quotify_catalog.py`, không đụng tới
  `Supplier`/`User`.
- Nhà cung cấp thật và 7 tài khoản Thu Mua: tạo thủ công qua UI/API sau khi
  go-live, không qua bất kỳ seed script nào.

## 3. Quy trình production đề xuất

### 3.1. Nguyên tắc

- Luôn chỉ định rõ compose file production: `docker compose -f docker-compose.prod.yml ...`.
  Không dùng compose context mặc định (dev) cho bất kỳ lệnh production nào.
- Không có, và không thêm, một target `migrate-refresh` nào chạy được trên
  production. Chỉ tồn tại đúng 1 con đường migrate cho prod: `upgrade head`.
- Backup trước khi migrate (theo Waiver Rule ở `docs/runbooks/deploy-rollback-restore.md`
  — không deploy production nếu thiếu runbook backup/restore và restore drill).

### 3.2. Các bước

```bash
# 0. Backup trước khi migrate (bắt buộc theo Waiver Rule)
bash scripts/ops/backup-postgres.sh

# 1. Build image production (nếu chưa build)
docker compose -f docker-compose.prod.yml build backend frontend worker

# 2. Migrate — tạo đầy đủ toàn bộ table, bao gồm seed idempotent quotify_settings
docker compose -f docker-compose.prod.yml exec backend uv run alembic upgrade head

# 3. Seed vừa đủ — auth/RBAC + 1 admin
docker compose -f docker-compose.prod.yml exec backend uv run python scripts/seed_auth_rbac.py

# 3.5. Seed danh mục vật tư (material types + materials — không kèm nhà cung cấp/user)
docker compose -f docker-compose.prod.yml exec backend uv run python scripts/seed_quotify_catalog.py

# 4. Lên stack đầy đủ
docker compose -f docker-compose.prod.yml up -d

# 5. Verify (theo runbook có sẵn): /health, /ready, /metrics, login flow, users list
# 6. Tạo thủ công qua UI/API: nhà cung cấp thật và 7 tài khoản Thu Mua (mật khẩu riêng từng người)
```

Bước 3 yêu cầu `.env` production đã set:

```
AUTH_SEED_ADMIN_EMAIL=<email thật của admin>
AUTH_SEED_ADMIN_PASSWORD=<mật khẩu mạnh, KHÔNG để giá trị placeholder mẫu>
AUTH_SEED_UPDATE_ADMIN_PASSWORD=false   # giữ false sau lần setup đầu, tránh reset password ngoài ý muốn khi seed lại
```

Service tự chặn (raise lỗi, không seed) nếu `AUTH_SEED_ADMIN_PASSWORD` còn là
placeholder `change-me-admin-password` — không cần thêm safeguard nào ở tầng
Makefile/script cho việc này, chỉ cần đảm bảo `.env` thật đã được set đúng.

### 3.3. Makefile — thêm target riêng cho production, giữ nguyên target dev

Đề xuất thêm (không sửa `migrate`/`seed` hiện tại, để không ảnh hưởng workflow dev):

```makefile
PROD_COMPOSE := docker compose -f docker-compose.prod.yml

.PHONY: migrate-prod seed-prod-auth seed-prod-catalog

migrate-prod:
	$(PROD_COMPOSE) exec backend uv run alembic upgrade head

seed-prod-auth:
	$(PROD_COMPOSE) exec backend uv run python scripts/seed_auth_rbac.py

seed-prod-catalog:
	$(PROD_COMPOSE) exec backend uv run python scripts/seed_quotify_catalog.py
```

Chủ đích: **không thêm** `seed-prod-quotify` hay `migrate-refresh-prod` — để
không ai vô tình gõ `make migrate-refresh-prod` hay chạy `seed_quotify.py`
nguyên bản và đưa dữ liệu/rủi ro không phù hợp vào production.

**Trạng thái: đã triển khai** — xem `Makefile`, `docs/runbooks/deploy-rollback-restore.md`,
`backend/app/services/quotify_seed.py::seed_material_catalog()`,
`backend/scripts/seed_quotify_catalog.py`.

### 3.4. Runbook (đã cập nhật)

`docs/runbooks/deploy-rollback-restore.md` đã có bước 3.5 "Seed auth/RBAC"
(`make seed-prod-auth`) và bước 3.6 "Seed danh mục vật tư" (`make seed-prod-catalog`)
giữa bước 3 (migrate) và bước 4 (up -d).

## 4. Việc còn để mở, xử lý ngoài quy trình seed tự động (đã xác nhận với nghiệp vụ)

- Nhà cung cấp thật (khác với `SUPPLIER_SEEDS` — đã xác nhận chỉ là dữ liệu
  mẫu, không seed) và 7 tài khoản Thu Mua thật: tạo thủ công qua UI/API sau
  khi go-live, mật khẩu riêng từng người, không qua seed script nào.
- Chưa có tính năng "buộc đổi mật khẩu lần đăng nhập đầu tiên" trong
  `AuthSeedService`/`UserAdminService` — vì việc tạo 7 tài khoản Thu Mua giờ
  là thủ công (người tạo tự đặt mật khẩu riêng, không dùng giá trị chung),
  rủi ro mật khẩu chung không còn áp dụng nữa; không cần làm thêm tính năng
  này chỉ vì lý do này.

## 5. Tóm tắt quyết định

| Lệnh | Dùng trên production? | Ghi chú |
|---|---|---|
| `alembic upgrade head` | ✅ Có (`make migrate-prod`) | Migrate đầy đủ, đã bao gồm seed `quotify_settings` |
| `alembic downgrade base` | ❌ Không, vĩnh viễn | Xoá toàn bộ dữ liệu; không có target Makefile nào expose ra prod |
| `seed_auth_rbac.py` | ✅ Có (`make seed-prod-auth`) | 1 admin + permissions/roles |
| `seed_quotify_catalog.py` (mới) | ✅ Có (`make seed-prod-catalog`) | Chỉ material types + materials, không kèm supplier/user |
| `seed_quotify.py` (nguyên bản) | ❌ Không chạy trên production | Nhà cung cấp mẫu (đã xác nhận không phải dữ liệu thật) + 7 tài khoản thật dùng chung mật khẩu hard-code trong source — cả hai đều không phù hợp seed tự động |
| Nhà cung cấp thật + 7 tài khoản Thu Mua | Tạo thủ công qua UI/API | Ngoài mọi quy trình seed tự động, mật khẩu riêng từng người |
