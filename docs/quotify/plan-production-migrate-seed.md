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

**Khuyến nghị (đưa ra quyết định thay vì hỏi lại, có thể điều chỉnh sau khi
review):**

- Production seed **KHÔNG chạy `seed_quotify.py` nguyên bản**.
- Tách seed danh mục nghiệp vụ (mục 1, và mục 2 nếu xác nhận là dữ liệu thật)
  thành thao tác nhập liệu qua UI (trang quản lý vật tư / nhà cung cấp đã có
  sẵn trong app) hoặc một script seed riêng chỉ seed `MaterialType`/`Material`/
  `Supplier`, không đụng tới `User`.
- Nếu vẫn cần cấp sẵn 7 tài khoản Thu Mua ngay khi go-live, xử lý thủ công
  ngoài quy trình seed tự động: tạo qua UI/API "tạo user" với mật khẩu ngẫu
  nhiên riêng từng người, gửi qua kênh an toàn (không phải seed script), và
  bắt đổi mật khẩu ngay lần đăng nhập đầu (nếu tính năng "buộc đổi mật khẩu
  lần đầu" đã tồn tại — cần kiểm tra; nếu chưa có, đây là gap cần làm trước
  khi go-live nếu nghiệp vụ yêu cầu).

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

# 3. Seed vừa đủ — CHỈ auth/RBAC + 1 admin, không seed danh mục/user nghiệp vụ
docker compose -f docker-compose.prod.yml exec backend uv run python scripts/seed_auth_rbac.py

# 4. Lên stack đầy đủ
docker compose -f docker-compose.prod.yml up -d

# 5. Verify (theo runbook có sẵn): /health, /ready, /metrics, login flow, users list
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

.PHONY: migrate-prod seed-prod-auth

migrate-prod:
	$(PROD_COMPOSE) exec backend uv run alembic upgrade head

seed-prod-auth:
	$(PROD_COMPOSE) exec backend uv run python scripts/seed_auth_rbac.py
```

Chủ đích: **không thêm** `seed-prod-quotify` hay `migrate-refresh-prod` — để
không ai vô tình gõ `make migrate-refresh-prod` hay `make seed-prod` (chạy cả
seed_quotify) và đưa dữ liệu/rủi ro không phù hợp vào production.

### 3.4. Cập nhật runbook

`docs/runbooks/deploy-rollback-restore.md` hiện chỉ có bước migrate (bước 3),
chưa có bước seed. Đề xuất chèn bước 3.5 "Seed auth/RBAC (chỉ lần đầu setup,
idempotent nên chạy lại vẫn an toàn)" giữa bước 3 (migrate) và bước 4 (up -d),
dùng đúng lệnh `make seed-prod-auth` ở trên.

## 4. Việc cần nghiệp vụ xác nhận trước khi go-live (không tự quyết được từ code)

- `SUPPLIER_SEEDS` trong `seed_data.py` (Cargill, Bunge, ADM, LDC, Wilmar, Tan
  Long...) là nhà cung cấp thật hay dữ liệu mẫu? Nếu thật, cần seed riêng danh
  mục này (không qua `seed_quotify.py` nguyên bản vì nó cũng tạo 7 user thật).
- Có cần tính năng "buộc đổi mật khẩu lần đăng nhập đầu tiên" trước khi cấp
  tài khoản Thu Mua thật lên production không? Hiện chưa thấy cơ chế này
  trong `AuthSeedService`/`QuotifySeedService`.

## 5. Tóm tắt quyết định

| Lệnh | Dùng trên production? | Ghi chú |
|---|---|---|
| `alembic upgrade head` | ✅ Có | Migrate đầy đủ, đã bao gồm seed `quotify_settings` |
| `alembic downgrade base` | ❌ Không, vĩnh viễn | Xoá toàn bộ dữ liệu |
| `seed_auth_rbac.py` | ✅ Có | Đúng nghĩa "seed vừa đủ": 1 admin + permissions/roles |
| `seed_quotify.py` (nguyên bản) | ❌ Không chạy nguyên bản | Gộp cả danh mục nghiệp vụ + 7 tài khoản thật với mật khẩu chung hard-code trong source — cần tách và xác nhận nghiệp vụ trước |
