# Kế Hoạch Triển Khai Quotify Theo Từng Giai Đoạn

## Trạng Thái

- Ngày lập kế hoạch: 27/07/2026.
- Nguồn yêu cầu: `docs/quotify/Requirements.txt`.
- Ngôn ngữ nghiệp vụ: `CONTEXT.md`.
- Trạng thái: đã qua hai vòng local reviewer; Phase 0 đã chốt ba prerequisite
  nghiệp vụ DG-01, DG-02 và DG-03 ngày 27/07/2026.
- Chế độ thực thi hiện tại: trực tiếp trên repository; máy chưa có GitHub CLI
  (`gh`), vì vậy kế hoạch không phụ thuộc vào lệnh tạo PR tự động.

## Mục Tiêu

Xây dựng Quotify thành hệ thống đơn giản để:

1. Lưu đầy đủ phiếu báo giá, dòng báo giá và các phiên bản do NCC điều chỉnh.
2. Lưu giá gốc, tỷ giá, chi phí quy đổi và giá VNĐ/KG tại thời điểm nhập.
3. Theo dõi lịch sử ghi chú thị trường và người tạo/sửa.
4. Đánh dấu dòng báo giá đã chốt mua và ghi nhận chính xác thời điểm thao tác
   này trong hệ thống.
5. Tra cứu dữ liệu báo giá bằng DataTable server-side.
6. Hiển thị xu hướng, MIN, MAX, TRUNG BÌNH, KPI số báo giá theo người dùng và
   các điểm đã chốt mua.
7. Cung cấp hai góc nhìn tham khảo quanh thời điểm đánh dấu chốt mua, dựa trên
   đúng tập dữ liệu đã tồn tại trong hệ thống tại từng thời điểm, không tự kết
   luận quyết định đúng hay sai.

## Ngoài Phạm Vi

- Quản lý tồn kho, nhu cầu sản xuất hoặc kế hoạch nguyên liệu.
- Quản lý hợp đồng, đơn mua hàng, khối lượng mua hoặc quy trình phê duyệt.
- Lead time, Incoterms, điều kiện thanh toán hoặc chấm điểm NCC.
- Mô hình dự báo giá, AI recommendation hoặc tự động đề xuất thời điểm mua.
- Email nhắc người chưa nhập báo giá.
- Dashboard nâng cao ngoài các chỉ số đã nêu trong yêu cầu.

## Căn Cứ Đã Xác Minh

### Nền Tảng Có Thể Tái Sử Dụng

- Backend: FastAPI, SQLAlchemy async, Alembic, PostgreSQL, Pydantic.
- Frontend: Vue 3, TypeScript, PrimeVue v4, Pinia, VeeValidate, Zod.
- Storage: MinIO qua `FileAdminService`.
- Auth/RBAC: `require_permission(...)`, role/permission seed hiện có.
- Audit: `AuditLogService`, `AuditLogContext.from_request(...)`, metadata
  sanitizer, viewer audit.
- Dữ liệu lớn: server-side pagination/filter/sort và async import job.
- Kiểm thử: pytest, Ruff, mypy, Bandit, Vitest và Docker Playwright E2E.
- Cách chạy browser E2E chuẩn: `make docker-test-e2e`.
- Timezone nghiệp vụ: `Asia/Ho_Chi_Minh`.

### Khoảng Trống Và Chênh Lệch Cần Xử Lý

1. Chưa có model, migration, API hoặc frontend module nào cho nghiệp vụ Quotify.
2. Branding mặc định cũ đã được xử lý ở Phase 0 cho runtime fallback, package
   metadata, router metadata, HTML title, cookie mặc định và observability metric
   prefix. Không đổi migration/history cũ nếu việc đổi tên gây rủi ro.
3. Phase 0 đã bổ sung permission seed còn thiếu (`users.import`, `users.export`,
   `files.read_all`) và toàn bộ permission Quotify dự kiến. Test
   inventory quét `require_permission(...)`, `has_permission(...)` và
   `permissionStore.can(...)` để tránh seed lệch usage.
4. `.env.production.example` đã được khôi phục ở Phase 0 với biến production mẫu
   cho Quotify.
5. Frontend chưa có thư viện biểu đồ; Phase 9 phải bổ sung dependency phù hợp,
   ưu tiên PrimeVue Chart kết hợp `chart.js`.

## Nguyên Tắc Kiến Trúc

1. Mỗi giai đoạn là một vertical slice có migration/API/UI/test tương ứng nếu
   phạm vi giai đoạn có giao diện.
2. Route mỏng, logic nghiệp vụ nằm trong service.
3. Service chỉ `flush()`; route ghi audit và `commit()` một lần để mutation và
   audit cùng transaction.
4. Không tạo hệ thống file, audit, auth hoặc job thứ hai.
5. Không dùng `float` cho tiền và tỷ giá; dùng `Decimal`/`NUMERIC` với precision
   rõ ràng.
6. Backend là nguồn sự thật của giá quy đổi; frontend chỉ hiển thị preview.
7. Không tính lại báo giá lịch sử bằng tỷ giá hoặc chi phí cấu hình hiện tại.
8. Không ghi đè phiên bản báo giá đã xác nhận.
9. Không hard-delete danh mục đang được dữ liệu lịch sử tham chiếu.
10. Mọi DataTable nghiệp vụ dùng server-side pagination/filter/sort.
11. Mọi field bắt buộc trên UI có dấu sao đỏ.
12. Vue SFC không có `<style>`; style nằm trong `frontend/src/styles/`.
13. Rich text phải được sanitize ở backend trước khi lưu hoặc trả ra.
14. Audit metadata không chứa raw rich text, secret, token hoặc nội dung file.
15. Mọi boundary ngày phải dùng `Asia/Ho_Chi_Minh`; datetime lưu có timezone.
16. Phân tích hồi cứu chỉ được dùng version đã xác nhận và thực sự tồn tại trong
    hệ thống tại mốc phân tích; không suy diễn từ `received_date` được nhập lùi.
17. Backend phải kiểm tra quyền theo dòng dữ liệu cho mọi mutation phiếu báo giá:
    role `user` chỉ được sửa, xóa ghi chú, tick chốt mua, upload file hoặc tạo
    bản điều chỉnh trên phiếu do chính mình tạo; role `admin` được thao tác trên
    tất cả phiếu.

## Mô Hình Dữ Liệu Mục Tiêu

```text
MaterialType 1 ─── n Material
Supplier     1 ─── n SupplierContact
Supplier     n ─── n Material              qua SupplierMaterial
Supplier     1 ─── n Quote
Quote        1 ─── n QuoteVersion
QuoteVersion 1 ─── n QuoteLine
QuoteVersion 0 ─── 1 File                  tệp báo giá gốc
Quote        1 ─── n QuoteNote
QuoteNote    1 ─── n QuoteNoteRevision
```

### Quy Ước Dữ Liệu Chính

- `delivery_month` lưu bằng `date` là ngày đầu tháng, API/UI biểu diễn
  `MM/YYYY`; không lưu chuỗi tự do.
- `quote_date` và `received_date` là business date, không phải datetime.
- `created_at`, `updated_at`, `confirmed_at`, `purchase_marked_at` và
  `purchase_unmarked_at` là datetime có timezone.
- `currency` giai đoạn đầu chỉ nhận `VND`, `USD`.
- `unit` giai đoạn đầu chỉ nhận `KG`, `MT`.
- Cặp nghiệp vụ hợp lệ ban đầu là `VND/KG` và `USD/MT`.
- `original_price`, `exchange_rate`, `conversion_cost_vnd_per_kg` và
  `converted_price_vnd_per_kg` dùng `NUMERIC`.
- `QuoteLine` là nguồn sự thật duy nhất cho provenance quy đổi của báo giá:
  `exchange_rate`, `exchange_rate_source`, `exchange_rate_source_mode`,
  `exchange_rate_retrieved_at`, `exchange_rate_manual_reason`,
  `exchange_rate_entered_by_id`, `conversion_cost_vnd_per_kg` và
  `converted_price_vnd_per_kg`.
- Không tạo bảng snapshot tỷ giá riêng trong V1 và không mở CRUD tỷ giá độc lập.
  Helper Vietcombank chỉ cung cấp dữ liệu đầu vào; quote write flow đóng băng
  dữ liệu đó trực tiếp trên dòng báo giá.
- `Quote.created_by_id` là người nhập phiếu bất biến, dùng làm nguồn KPI; người
  tạo các version sau được lưu riêng trên `QuoteVersion.created_by_id`.
- Khi `is_purchased` chuyển từ `false` sang `true`, backend tự lưu
  `purchase_marked_at` và `purchase_marked_by_id`; UI vẫn chỉ hiển thị checkbox.
  Đây là thời điểm đánh dấu trong Quotify, không được trình bày như thời điểm ký
  hợp đồng thực tế nếu người dùng thao tác muộn.
- Khi bỏ đánh dấu, backend lưu `purchase_unmarked_at` và
  `purchase_unmarked_by_id`; audit là nguồn lịch sử đầy đủ của các lần toggle.
- Các giá trị quy đổi đã đóng băng trên dòng báo giá không thay đổi khi cấu hình
  hệ thống thay đổi.

## Permission Dự Kiến

| Nhóm | Permission |
|---|---|
| Loại vật tư | `material_types.read`, `material_types.create`, `material_types.update`, `material_types.delete`, `material_types.import` |
| Vật tư | `materials.read`, `materials.create`, `materials.update`, `materials.delete`, `materials.import` |
| NCC | `suppliers.read`, `suppliers.create`, `suppliers.update`, `suppliers.delete`, `suppliers.import` |
| Báo giá | `quotes.read`, `quotes.create`, `quotes.update`, `quotes.mark_purchased` |
| Ghi chú | `quote_notes.read`, `quote_notes.create`, `quote_notes.update` |
| Tra cứu tỷ giá | `exchange_rates.read` |
| Cấu hình quy đổi | `quotify_settings.read`, `quotify_settings.update` |
| Dashboard | tiếp tục dùng `dashboard.read` |

Không tạo permission xóa báo giá hoặc xóa lịch sử ghi chú trong phiên bản đầu.

### Ma Trận Route Và Permission

| Route/khả năng | Permission backend | Hiển thị frontend |
|---|---|---|
| Danh sách/lookup loại vật tư | `material_types.read` | nhóm Danh mục nếu có quyền |
| Tạo/sửa/xóa loại vật tư | `material_types.create` / `material_types.update` / `material_types.delete` | action theo từng quyền |
| Import loại vật tư, xem job, tải file lỗi | `material_types.import` | dialog import theo quyền |
| Danh sách/lookup vật tư | `materials.read` | nhóm Danh mục nếu có quyền |
| Tạo/sửa/xóa vật tư | `materials.create` / `materials.update` / `materials.delete` | action theo từng quyền |
| Import vật tư, xem job, tải file lỗi | `materials.import` | dialog import theo quyền |
| Danh sách/lookup NCC | `suppliers.read` | nhóm Danh mục nếu có quyền |
| Tạo/sửa/xóa NCC, contact và mapping vật tư | `suppliers.create` / `suppliers.update` / `suppliers.delete` | action theo từng quyền |
| Import NCC, xem job, tải file lỗi | `suppliers.import` | dialog import theo quyền |
| Lookup material/NCC trong form quote | `quotes.read` | nằm trong form, không có menu riêng |
| Lấy USD bán ra hôm nay | `exchange_rates.read` | chỉ gọi trong form quote |
| Đọc/cập nhật chi phí quy đổi | `quotify_settings.read` / `quotify_settings.update` | menu Cấu hình chỉ hiện khi có quyền đọc |
| Upload tệp cho quote mới | `quotes.create` | action trong form quote |
| Upload/thay tệp cho version draft | `quotes.update` và ownership quote | action trong form quote |
| Tải tệp nguồn của version | `quotes.read` và association quote-version-file hợp lệ | action trong quote detail |
| Tạo/đọc/cập nhật quote | `quotes.create` / `quotes.read` / `quotes.update`; mutation quote kiểm ownership với role `user` | nhóm Báo giá |
| Tạo bản điều chỉnh | `quotes.update` và ownership quote | nút theo quyền và chủ phiếu |
| Xóa bản nháp | `quotes.update` và ownership quote; chỉ áp dụng với version `draft` | nút danger trên quote detail |
| Tick/untick chốt mua | `quotes.mark_purchased` và ownership quote | checkbox theo quyền và chủ phiếu |
| Đọc/tạo/sửa/xóa ghi chú | `quote_notes.read` / `quote_notes.create` / `quote_notes.update` và ownership quote khi ghi/xóa | panel trong quote detail |
| Dashboard Quotify | `dashboard.read` | nhóm Tổng quan |

Upload tệp trong quote không yêu cầu thêm `files.upload`; quote module sở hữu
authorization và chỉ tái sử dụng `FileAdminService` để lưu file private.
Tương tự, file nguồn và file lỗi import phải được tải qua endpoint theo phạm vi
nghiệp vụ. Không chuyển người dùng sang endpoint file generic vốn chỉ cho
uploader hoặc `files.read_all`.

Role được cấp `quotes.create` hoặc `quotes.update` phải đồng thời có
`quotes.read`, `exchange_rates.read` và `quotify_settings.read`; Phase 0 seed/test
phải bảo vệ bundle prerequisite này.

## Audit Event Dự Kiến

- `material_types.material_type_created|updated|deleted|import_started`
- `materials.material_created|updated|deleted|import_started`
- `suppliers.supplier_created|updated|deleted|import_started`
- `suppliers.contact_created|updated|deleted`
- `suppliers.materials_updated`
- `quotify.exchange_rate_manual_entered`
- `quotify.exchange_rate_fallback_used`
- `quotify.conversion_cost_updated`
- `quotes.quote_created`
- `quotes.version_created`
- `quotes.version_confirmed`
- `quotes.purchase_marked`
- `quotes.purchase_unmarked`
- `quote_notes.note_created`
- `quote_notes.note_updated`

Các event update phải ghi `changes` với `old_value`/`new_value` cho dữ liệu ngắn,
an toàn. Nội dung rich text đầy đủ nằm trong bảng revision, không nằm trong audit.

## Prerequisite Nghiệp Vụ Của Phase 0

Ba quyết định sau đã được người dùng xác nhận và đồng bộ vào `Requirements.txt`
cùng `CONTEXT.md` trong Phase 0. Không tạo migration quote hoặc dashboard nếu
những quyết định này bị thay đổi mà chưa cập nhật lại tài liệu nguồn.

### DG-01: Nội Dung Phiên Bản Mới

Quyết định đã chốt: khi NCC điều chỉnh báo giá, Quotify sao chép toàn bộ phiên
bản trước thành phiên bản mới, sau đó người dùng chỉnh các dòng thay đổi. Mỗi
version là một snapshot đầy đủ và độc lập. Quy tắc copy chi tiết:

| Dữ liệu | Xử lý khi tạo version mới |
|---|---|
| NCC và identity của `Quote` | giữ nguyên |
| Material, giá gốc, tiền tệ, đơn vị của từng dòng | sao chép |
| Ngày báo giá, ngày nhận | yêu cầu người dùng xác nhận/nhập cho version mới |
| Tỷ giá, nguồn tỷ giá, chi phí và giá quy đổi | nếu bản điều chỉnh giữ nguyên ngày nhận báo giá của version cũ thì dùng lại snapshot tỷ giá/chi phí cũ và chỉ tính lại giá quy đổi theo giá gốc mới; nếu ngày nhận đổi sang hôm nay thì lấy tỷ giá Vietcombank tự động tại thời điểm tạo/xác nhận bản điều chỉnh |
| `is_purchased`, actor và các timestamp chốt mua | reset; không sao chép |
| File nguồn | không sao chép; version mới upload file riêng nếu có |
| Ghi chú | giữ ở cấp `Quote`; không nhân bản revision |

Dashboard phải có regression test chứng minh tạo version mới không nhân đôi
điểm chốt mua.

### DG-02: KPI Số Báo Giá Theo User

Quyết định đã chốt: đếm số phiếu báo giá do user tạo, không đếm số dòng, để
một phiếu nhiều dòng không làm sai lệch KPI. Nguồn actor là
`Quote.created_by_id` bất biến, không phải người tạo version mới nhất.

### DG-03: Mốc Thời Gian Phân Tích Chốt Mua

Quyết định đã chốt để giữ UX checkbox đơn giản: không yêu cầu nhập ngày mua
riêng. Hệ thống tự ghi `purchase_marked_at` khi tick và dashboard dùng nhãn
“tại thời điểm đánh dấu chốt mua”. Tập dữ liệu tại mốc này chỉ gồm version có
`confirmed_at <= purchase_marked_at`; `received_date` nhập lùi không đủ để một
version được coi là đã tồn tại tại thời điểm đó.

## Dependency Graph

```text
Phase 0
├── Phase 1 ── Phase 2 ── Phase 3
└── Phase 4

Phase 1 + Phase 2 + Phase 4
└── Phase 5
    └── Phase 6
        └── Phase 7
            └── Phase 8
                └── Phase 9

Phase 0..Phase 9 ── Phase 10
```

Khả năng chạy song song:

- Sau Phase 0, Phase 1 và Phase 4 có thể triển khai song song.
- Phase 3 có thể chạy song song với Phase 5 sau khi Phase 2 và Phase 4 hoàn tất.
- Phase 7 bắt đầu sau Phase 6 vì panel ghi chú cần quote detail surface do Phase
  6 tạo.

---

## Phase 0: Nền Tảng Sản Phẩm Và Hợp Đồng Kỹ Thuật

### Bối Cảnh Cho Agent

Repo hiện là boilerplate đã đổi tên project nhưng vẫn còn fallback branding cũ,
permission seed đang lệch route và chưa có module Quotify. Giai đoạn này đóng
băng contract trước khi tạo bảng nghiệp vụ.

### Mục Tiêu

- Đồng bộ nhận diện Quotify.
- Chốt permission, audit taxonomy, URL và quy ước dữ liệu.
- Sửa các chênh lệch nền tảng có thể làm những phase sau thất bại.

### Việc Cần Làm

1. Đổi fallback `APP_NAME`, `VITE_APP_NAME`, package metadata và router
   description sang Quotify.
2. Không xóa tên kỹ thuật cũ trong migration/history nếu việc đổi tên gây rủi ro.
3. Quét mọi `require_permission(...)`, `has_permission(...)` và
   `permissionStore.can(...)`; đồng bộ `BASE_PERMISSION_CODES` trước khi thêm
   permission Quotify.
4. Thêm toàn bộ permission dự kiến và seed idempotent cho role `admin`.
5. Chốt nhóm sidebar:
   - `Tổng quan`
   - `Danh mục`
   - `Báo giá`
   - `Người dùng`
   - `Hệ thống`
6. Tạo inventory test đối chiếu `route/action -> permission -> seed -> frontend
   visibility`, bao phủ cả permission kiểm trực tiếp trong code.
7. Chốt API prefix:
   - `/material-types`
   - `/materials`
   - `/suppliers`
   - `/quotify-settings`
   - `/exchange-rates`
   - `/quotes`
   - `/quote-notes`
   - `/dashboard/quotify`
8. Chốt DG-01, DG-02 và DG-03 trong mục prerequisite trước khi kết thúc Phase
   0; đồng bộ kết quả vào `Requirements.txt` và `CONTEXT.md`. Việc này đã hoàn
   tất ngày 27/07/2026.
9. Xác minh tình trạng `.env.production.example`; khôi phục file hoặc cập nhật
   Memory Bank để không tiếp tục báo sai. Việc này đã hoàn tất ngày 27/07/2026.
10. Thêm test tự động so sánh permission code dùng trong route/action với seed.
    Việc này đã hoàn tất ngày 27/07/2026 bằng `test_permission_inventory.py`.

### File Dự Kiến

- `backend/app/auth/seed_data.py`
- `backend/tests/test_rbac_core.py`
- `backend/tests/test_permission_inventory.py`
- `backend/app/core/config.py`
- `.env.example`
- `frontend/package.json`
- `frontend/src/router/index.ts`
- `frontend/src/layouts/AdminLayout.vue`
- `frontend/src/composables/useDashboardPage.ts`
- `memory-bank/techContext.md`
- `.env.production.example`

### Kiểm Thử

```bash
make backend-check
make frontend-check
npm --prefix frontend run build
```

### Điều Kiện Hoàn Thành

- Không còn fallback branding cũ trên UI runtime.
- Permission route/seed không lệch.
- Permission Quotify được admin nhận sau reseed.
- Contract URL, action code và rule version được ghi rõ.
- DG-01, DG-02 và DG-03 đã có quyết định bằng văn bản.

### Rollback

- Revert branding và permission seed bằng commit của Phase 0.
- Không có migration nghiệp vụ nên rollback không tác động dữ liệu.

---

## Phase 1: Danh Mục Loại Vật Tư Và Vật Tư

### Bối Cảnh Cho Agent

Đây là vertical slice nghiệp vụ đầu tiên. Hãy sao chép pattern CRUD từ Roles/Users:
model -> migration -> schema -> service -> route -> type/mapper/api/composable ->
page/style/test.

### Mục Tiêu

- CRUD, tìm kiếm, filter, sort và phân trang cho loại vật tư và vật tư.
- Bảo vệ bằng RBAC và ghi audit.

### Backend

1. Tạo `MaterialType` và `Material`.
2. Thêm unique constraint cho mã; chuẩn hóa trim và so sánh mã không phân biệt
   hoa/thường.
3. `Material.material_type_id` dùng foreign key `RESTRICT`.
4. Status chỉ nhận `active|inactive`.
5. Service dùng sort whitelist; không dùng `getattr` trực tiếp từ input chưa
   kiểm soát.
6. Delete chỉ thành công khi entity chưa được tham chiếu; nếu đã có lịch sử thì
   trả `409` và yêu cầu chuyển `inactive`.
7. Mutation + audit commit cùng transaction.
8. API list dùng `limit` mặc định 10, tối đa 100.

### Frontend

1. Tạo trang `Loại vật tư` và `Vật tư`.
2. DataTable lazy, rows 10/20/30/50 và report tiếng Việt chuẩn.
3. Form thêm/sửa dùng VeeValidate + Zod.
4. Field bắt buộc có dấu sao đỏ.
5. Filter theo trạng thái; vật tư filter theo loại vật tư.
6. Mobile action bar stack, table scroll trong wrapper.

### File Dự Kiến

- `backend/app/models/material_type.py`
- `backend/app/models/material.py`
- `backend/app/schemas/material_type.py`
- `backend/app/schemas/material.py`
- `backend/app/services/material_type_admin.py`
- `backend/app/services/material_admin.py`
- `backend/app/api/v1/material_types.py`
- `backend/app/api/v1/materials.py`
- `backend/alembic/versions/*_create_material_catalog.py`
- `frontend/src/types/materials.ts`
- `frontend/src/api/materials.api.ts`
- `frontend/src/api/materials.mappers.ts`
- `frontend/src/composables/useMaterialTypesPage.ts`
- `frontend/src/composables/useMaterialsPage.ts`
- `frontend/src/pages/MaterialTypesPage.vue`
- `frontend/src/pages/MaterialsPage.vue`
- `frontend/src/styles/pages/_material-types-page.scss`
- `frontend/src/styles/pages/_materials-page.scss`

### Kiểm Thử

- Unique code và case normalization.
- Không xóa loại vật tư đang có vật tư.
- Không xóa vật tư đang được tham chiếu.
- RBAC `401/403`.
- Audit create/update/delete có old/new.
- Mapper, composable, page states và pagination.

```bash
make backend-check
make frontend-check
npm --prefix frontend run build
```

### Điều Kiện Hoàn Thành

- Admin quản lý được hai danh mục từ UI.
- User thiếu permission không thấy menu và API trả `403`.
- Migration upgrade/downgrade chạy được trên database test trống.

### Rollback

- Downgrade migration chỉ khi chưa có dữ liệu production.
- Khi đã có dữ liệu, dùng forward-fix; không drop bảng.

---

## Phase 2: Nhà Cung Cấp, Liên Hệ Và Vật Tư Cung Cấp

### Bối Cảnh Cho Agent

Phase 1 đã cung cấp Material. Phase này tạo NCC, nhiều liên hệ và quan hệ nhiều-
nhiều giữa NCC với vật tư. Loại NCC không được quyết định tiền tệ/đơn vị.

### Mục Tiêu

- CRUD NCC.
- Quản lý danh sách liên hệ.
- Quản lý danh sách vật tư NCC có thể cung cấp.

### Backend

1. Tạo `Supplier`, `SupplierContact`, `SupplierMaterial`.
2. `supplier_type` chỉ nhận `domestic|international`.
3. Unique `supplier.code`; unique cặp `(supplier_id, material_id)`.
4. Contact có status `active|inactive`; email và số điện thoại optional.
5. API lookup NCC theo `material_id` để phục vụ form báo giá.
6. Eager-load contact/material đúng chỗ; tránh N+1.
7. Không xóa NCC đã có báo giá; chuyển inactive.
8. Không cho gắn material inactive vào NCC mới.
9. Audit riêng cho thay đổi NCC, liên hệ và danh sách vật tư.

### Frontend

1. Trang danh sách NCC server-side.
2. Dialog NCC có tab/thành phần con cho liên hệ và vật tư cung cấp.
3. Dùng MultiSelect cho danh sách vật tư; lookup tối đa 100 mỗi request và có
   search server-side nếu danh mục tăng lớn.
4. Hiển thị liên hệ inactive nhưng không chọn mặc định.
5. Mobile dialog và table không tràn viewport.

### File Dự Kiến

- `backend/app/models/supplier.py`
- `backend/app/models/supplier_contact.py`
- `backend/app/models/supplier_material.py`
- `backend/app/schemas/supplier.py`
- `backend/app/services/supplier_admin.py`
- `backend/app/api/v1/suppliers.py`
- `backend/alembic/versions/*_create_suppliers.py`
- `frontend/src/types/suppliers.ts`
- `frontend/src/api/suppliers.api.ts`
- `frontend/src/api/suppliers.mappers.ts`
- `frontend/src/composables/useSuppliersPage.ts`
- `frontend/src/pages/SuppliersPage.vue`
- `frontend/src/styles/pages/_suppliers-page.scss`

### Kiểm Thử

- Một NCC có nhiều contact và material.
- Duplicate supplier-material bị chặn.
- Lookup theo material chỉ trả NCC active có quan hệ hợp lệ.
- Supplier type không thay đổi validation tiền tệ của báo giá.
- Audit old/new và RBAC.
- UI create/edit/filter/detail.

### Điều Kiện Hoàn Thành

- Tạo được NCC với nhiều contact và material.
- Form lookup API sẵn sàng cho Phase 6.
- Không có N+1 trong list/detail chính.

### Rollback

- Giữ Phase 1 nguyên vẹn.
- Downgrade riêng migration NCC nếu chưa có dữ liệu production.

---

## Phase 3: Import Danh Mục

### Bối Cảnh Cho Agent

Requirements yêu cầu import loại vật tư, vật tư và NCC. Repo đã có
`ImportJob`, MinIO, Redis/ARQ và worker cho user import; cần mở rộng pattern hiện
có thay vì tạo pipeline song song.

### Mục Tiêu

- Import CSV có theo dõi tiến độ và báo cáo lỗi.
- Không làm hỏng user import đang tồn tại.

### Phase 3A: Tổng Quát Hóa Job Substrate

1. Mở rộng `ImportJob` bằng `entity_type` hoặc `job_type`; migration phải backfill
   job cũ thành `users`.
2. Refactor `JobAdminService` để nhận task/type rõ ràng nhưng giữ contract user
   import hiện tại.
3. Loại bỏ `rows = list(reader)` ở worker user import; chuyển sang đọc streaming
   hoặc theo chunk trước khi dùng substrate cho danh mục.
4. Tách route/task/permission/audit user-specific khỏi job lifecycle dùng chung.
5. Chỉ enqueue sau khi file, job và audit start event đã commit.
6. Terminal status và audit terminal event commit cùng transaction.
7. Giữ test backward compatibility cho toàn bộ user import hiện tại.

Điều kiện qua 3A:

- User import cũ vẫn pass.
- Job substrate nhận được `entity_type`, task name và permission context mà không
  hardcode `users.*`.
- Worker không đọc toàn bộ CSV vào RAM.

### Phase 3B: Import Danh Mục Theo Chiều Dọc

1. Triển khai `Loại vật tư` trước như luồng mẫu hoàn chỉnh từ API đến UI/E2E.
2. Sau khi luồng mẫu pass, mở rộng cùng contract cho `Vật tư` và `NCC`.
3. Tạo template CSV riêng cho:
   - loại vật tư
   - vật tư
   - NCC, contact và mã vật tư cung cấp
4. Upsert theo mã; row hợp lệ được lưu, row lỗi vào error
   report.
5. `completed` có thể có `failed_rows > 0`; `failed` dành cho lỗi toàn file hoặc
   lỗi hệ thống.
6. Validate toàn bộ header trước khi xử lý row.
7. Chạy chunk; không đọc toàn bộ file lớn vào RAM.
8. Không ghi raw row hoặc exception nhạy cảm vào audit.
9. UI tái sử dụng dialog import/job progress hiện có nhưng tách composable dùng
    chung nếu việc tách thật sự giảm lặp.
10. V1 không hỗ trợ XLSX; chỉ bổ sung sau một kế hoạch riêng nếu CSV không đáp
    ứng vận hành thực tế.
11. Mỗi route start/status/error-file xác định permission từ `entity_type` bằng
    allowlist server-side; không nhận permission code tùy ý từ client.
12. Tải error report phải kiểm tra job thuộc đúng loại danh mục và user có
    permission import tương ứng; không dùng `files.read_all`.

### API Import Dự Kiến

- `POST /catalog-imports/{entity_type}`
- `GET /catalog-imports/{job_id}`
- `GET /catalog-imports/{job_id}/error-file`
- `GET /catalog-imports/templates/{entity_type}`

`entity_type` chỉ nhận `material_types|materials|suppliers`. Cả bốn route ánh xạ
lần lượt sang `material_types.import`, `materials.import` hoặc
`suppliers.import`.

### File Dự Kiến

- `backend/app/models/import_job.py`
- `backend/app/services/job_admin.py`
- `backend/app/api/v1/catalog_imports.py`
- `backend/app/worker.py`
- `backend/app/schemas/job.py`
- `backend/alembic/versions/*_extend_import_jobs_for_catalog.py`
- `frontend/src/types/jobs.ts`
- `frontend/src/api/catalog-imports.api.ts`
- `frontend/src/components/shared/ImportJobDialog.vue`
- các composable/page của Phase 1 và Phase 2

### Kiểm Thử

- Backward compatibility user import.
- Phase 3A pass trước khi bắt đầu Phase 3B.
- Header sai, duplicate code, FK không tồn tại, row partial error.
- Retry từ processing/running.
- Không duplicate terminal audit.
- File lớn xử lý theo chunk.
- RBAC import từng danh mục.

```bash
make backend-check
make frontend-check
make docker-test-e2e
```

### Điều Kiện Hoàn Thành

- Ba loại danh mục import được và có file lỗi tải xuống.
- User import cũ vẫn hoạt động.
- V1 chỉ nhận CSV và thông báo rõ định dạng hỗ trợ.
- E2E kiểm tra ít nhất một import có row hợp lệ và row lỗi.

### Rollback

- Giữ nullable/default `entity_type` trong một release chuyển tiếp nếu cần.
- Không downgrade sau khi đã tạo job mới; dùng migration forward-fix.

---

## Phase 4: Cấu Hình Quy Đổi Và Tích Hợp Tỷ Giá

### Bối Cảnh Cho Agent

Phase này độc lập với danh mục. Tỷ giá dùng USD bán ra Vietcombank. Ngày nhận
hiện tại lấy tự động; ngày quá khứ nhập tay; khi nguồn tự động lỗi được nhập tay
với lý do bắt buộc.

### Mục Tiêu

- Có adapter lấy tỷ giá và cấu hình chi phí quy đổi.
- Có fallback vận hành rõ ràng.
- Giữ surface V1 nhỏ: một helper đọc tỷ giá hôm nay và API read/update cấu hình.

### Backend

1. Tạo typed setting cho URL, timeout và retry của nguồn Vietcombank.
2. Tạo `VietcombankExchangeRateClient` bọc `httpx`; không gọi HTTP trực tiếp từ
   route.
3. Không hardcode parser vào service báo giá; adapter trả contract nội bộ ổn định.
4. Tạo bảng cấu hình chi phí quy đổi hiện hành.
5. API public V1 chỉ gồm:
   - `GET /exchange-rates/usd-sell/today`
   - `GET /quotify-settings`
   - `PUT /quotify-settings/conversion-cost`
6. Helper hôm nay trả rate, source và retrieved time; không persist snapshot độc
   lập.
7. Manual past và manual fallback không có CRUD riêng; Phase 5 validate và đóng
   băng chúng trực tiếp trên `QuoteLine`.
8. Rate limit endpoint gọi nguồn ngoài.
9. Dùng `Decimal`; quy định rounding giá VNĐ/KG một lần ở backend.
10. Audit config update ở Phase 4; audit manual/fallback nằm trong quote write
    transaction ở Phase 5.

### Frontend

1. Form cấu hình nhỏ cho chi phí quy đổi, chỉ hiện với user có quyền.
2. Tạo API client/type cho helper tỷ giá hôm nay để Phase 6 tái sử dụng.
3. UI manual/fallback nằm trong quote editor Phase 6, không có màn hình quản lý
   snapshot tỷ giá riêng.

### File Dự Kiến

- `backend/app/models/quotify_setting.py`
- `backend/app/integrations/vietcombank.py`
- `backend/app/services/exchange_rate_service.py`
- `backend/app/services/quotify_settings_service.py`
- `backend/app/api/v1/exchange_rates.py`
- `backend/app/api/v1/quotify_settings.py`
- `backend/app/schemas/exchange_rate.py`
- `backend/alembic/versions/*_create_quotify_settings.py`
- `frontend/src/types/exchange-rates.ts`
- `frontend/src/api/exchange-rates.api.ts`
- `frontend/src/components/quotes/ExchangeRateField.vue`
- `frontend/src/pages/QuotifySettingsPage.vue`

### Kiểm Thử

- Parser với fixture response; không gọi live Vietcombank trong unit test.
- Timeout, HTTP lỗi, response đổi format.
- Today boundary theo `Asia/Ho_Chi_Minh`.
- Helper không persist bản ghi lịch sử độc lập.
- Decimal/rounding tại các giá trị biên.
- RBAC và audit.

### Điều Kiện Hoàn Thành

- Helper lấy được tỷ giá tự động hoặc trả error contract rõ để quote workflow mở
  fallback thủ công.
- Quote write contract đã có field provenance để Phase 5 lưu manual/fallback.
- Source outage không làm mất dữ liệu người dùng đang nhập.

### Rollback

- Feature flag tắt automatic fetch và dùng manual workflow tạm thời.
- Không thay đổi dữ liệu quy đổi đã đóng băng trên `QuoteLine`.

---

## Phase 5: Backend Vòng Đời Phiếu Báo Giá

### Bối Cảnh Cho Agent

Phase 1, 2 và 4 đã cung cấp material, supplier và exchange rate. Đây là domain
core; frontend hoàn chỉnh được làm ở Phase 6.

### Mục Tiêu

- Lưu phiếu, phiên bản và dòng báo giá.
- Giữ lịch sử bất biến.
- Tính giá quy đổi chính xác.
- Hỗ trợ nhập lại và tick chốt mua.

### Mô Hình Và Quy Tắc

1. `Quote` giữ identity ổn định, NCC và `created_by_id` bất biến.
2. `QuoteVersion` giữ `version_number`, ngày báo giá, ngày nhận, file gốc, người
   tạo, `confirmed_at`, người confirm và trạng thái `draft|confirmed`.
3. `QuoteLine` thuộc đúng một version.
4. Version mới là snapshot đầy đủ được sao chép từ version trước rồi chỉnh những
   dòng thay đổi theo copy matrix DG-01; đây là mặc định đề xuất và cần chốt ở
   Phase 0.
5. Version `confirmed` không sửa giá/date/material trực tiếp; khi phát hiện nhập sai,
   người dùng tạo bản điều chỉnh có lý do bắt buộc. Khi bản điều chỉnh được xác
   nhận, version `confirmed` cũ chuyển sang `superseded` và không còn là dữ liệu
   hiệu lực cho danh sách báo giá/dashboard mặc định.
6. Version draft được sửa/xóa dòng trước khi confirm; nếu tạo nhầm bản nháp thì
   được xóa toàn bộ version draft. Nếu đó là version duy nhất của phiếu, hệ thống
   xóa cả phiếu nháp để không để lại quote rỗng.
7. Mỗi `Quote` chỉ có tối đa một draft; unique `(quote_id, version_number)` và
   partial unique index cho draft là constraint ở database.
8. Khi tạo version, service khóa hàng `Quote` bằng `SELECT ... FOR UPDATE`, cấp
   `version_number` kế tiếp trong transaction và xử lý conflict idempotent.
9. Confirm dùng conditional update `draft -> confirmed`; update draft và confirm
   chạy đua phải có đúng một kết quả thành công.
10. Chỉ cặp `VND/KG` và `USD/MT` hợp lệ trong phase đầu.
11. Dòng `VND/KG`: giá quy đổi bằng giá gốc, không có tỷ giá/chi phí quy đổi.
12. Dòng `USD/MT`: backend tính và đóng băng toàn bộ provenance trực tiếp trên
   `QuoteLine`; không reference bảng snapshot khác.
13. Với ngày nhận hiện tại, backend tự gọi adapter khi submit. Nếu adapter lỗi,
    payload manual fallback phải có rate và reason; nếu adapter đang hoạt động,
    backend từ chối manual fallback.
14. Với ngày nhận quá khứ, payload bắt buộc có manual rate; source mode là
    `manual_past`.
15. Với bản điều chỉnh báo giá đã xác nhận: nếu `received_date` giữ nguyên như
    version hiệu lực cũ, backend phải dùng lại snapshot tỷ giá/chi phí của dòng
    cũ có cùng material, kỳ giao, tiền tệ và đơn vị; nếu `received_date` đổi sang
    hôm nay, backend lấy lại tỷ giá Vietcombank tự động theo quy tắc ngày hiện tại.
16. `QuoteLine` lưu rate, source, source mode, retrieved/entered time, manual
    reason, actor nhập tay, conversion cost và converted price.
17. NCC phải đang cung cấp material được chọn.
18. Ngày nhận không ở tương lai.
19. Predicate nhập lại duy nhất là `received_date < today` **hoặc**
    `delivery_month < first_day_of_current_month`, tính theo
    `Asia/Ho_Chi_Minh`. Khi đúng, backend và UI đều bắt buộc
    `is_backfilled=true` cùng lý do. Định nghĩa này đã được Phase 0 đồng bộ vào
    `Requirements.txt` và `CONTEXT.md`.
20. Checkbox purchase tự lưu `purchase_marked_at`,
    `purchase_marked_by_id`; không nhận timestamp do frontend gửi.
21. Untick được phép nếu user có `quotes.mark_purchased`; lưu actor/time bỏ đánh
    dấu và audit vẫn giữ lịch sử.
22. Tệp báo giá gốc tái sử dụng `FileAdminService`, file private.
23. Với role `user`, mọi mutation trên phiếu báo giá phải kiểm
    `Quote.created_by_id == current_user.id`; role `admin` được bỏ qua ownership.
    Rule này áp dụng cho sửa draft, confirm, upload/thay tệp, tick/untick chốt
    mua, tạo bản điều chỉnh, thêm/sửa/xóa ghi chú và các endpoint mutation tương
    lai của quote.
24. Không cho xóa version `confirmed` hoặc `superseded`. Xóa bản nháp phải ghi
    audit `quotes.version_deleted`; nếu bản nháp có tệp nguồn, quote module chịu
    trách nhiệm xóa hoặc unlink file qua `FileAdminService` sau khi đã kiểm
    ownership quote.

### API Dự Kiến

- `POST /quotes`
- `GET /quotes/{id}`
- `POST /quotes/{id}/versions`
- `PUT /quotes/{id}/versions/{version_id}/draft`
- `DELETE /quotes/{id}/versions/{version_id}`
- `POST /quotes/{id}/versions/{version_id}/confirm`
- `POST /quotes/{id}/versions/{version_id}/source-file`
- `GET /quotes/{id}/versions/{version_id}/source-file`
- `PUT /quotes/{id}/lines/{line_id}/purchase`
- lookup cần thiết cho form

### Transaction Và Audit

- Upload file có compensation rõ nếu DB commit thất bại.
- Download file xác minh `quote -> version -> file` association và
  `quotes.read`; không dùng generic file permission thay cho ownership nghiệp
  vụ.
- Create/version/confirm/purchase event commit cùng mutation.
- Audit metadata lưu mã/giá tóm tắt; không lưu file content hoặc signed URL.
- Idempotency cho confirm và purchase toggle.
- Cấp version number và confirm an toàn khi có request đồng thời.

### File Dự Kiến

- `backend/app/models/quote.py`
- `backend/app/models/quote_version.py`
- `backend/app/models/quote_line.py`
- `backend/app/schemas/quote.py`
- `backend/app/services/quote_service.py`
- `backend/app/services/quote_pricing.py`
- `backend/app/api/v1/quotes.py`
- `backend/alembic/versions/*_create_quote_core.py`

### Kiểm Thử

- Tạo phiếu một/nhiều dòng.
- VND/KG và USD/MT.
- Invalid currency-unit pair.
- Giá quy đổi Decimal và rounding.
- Today/past/future.
- Automatic/manual past/manual fallback provenance.
- Manual fallback bị từ chối khi nguồn tự động đang hoạt động.
- Backfill reason.
- Supplier-material validation.
- Predicate nhập lại giống nhau ở schema, service và API.
- Confirm bất biến; copy matrix đầy đủ; purchase state không bị nhân bản.
- Unique version/draft constraints và concurrency test cho create/confirm/update.
- Delete draft test cover ba nhánh: xóa draft điều chỉnh chỉ xóa version nháp,
  xóa draft duy nhất xóa cả phiếu nháp, và không xóa được `confirmed`.
- Upload/download file private; cross-user có `quotes.read` tải được file nguồn,
  user không có quyền nhận `403`.
- Purchase mark/unmark và timestamps do server sinh.
- Transaction rollback nếu audit lỗi.
- RBAC.

### Điều Kiện Hoàn Thành

- API hoàn thành toàn bộ vòng đời bằng test.
- Version cũ không bị ghi đè.
- Giá lịch sử không đổi khi tỷ giá/cấu hình thay đổi.

### Rollback

- Có thể tắt route bằng router registration.
- Không drop quote tables sau khi có dữ liệu; forward-fix bắt buộc.

---

## Phase 6: Giao Diện Nhập Và Xem Phiếu Báo Giá

### Bối Cảnh Cho Agent

Backend Phase 5 đã ổn định. UI phải dùng thin-SFC, composable và API mapper như
Users/Audit Logs. Không đưa logic pricing authoritative vào Vue.

### Mục Tiêu

- Người dùng tạo phiếu, thêm nhiều dòng, upload file, xác nhận và tạo phiên bản
  mới.
- Hỗ trợ nhập lại báo giá và fallback tỷ giá.

### UX Dự Kiến

1. Route:
   - `/quotes/new`
   - `/quotes/:quoteId`
   - `/quotes/:quoteId/versions/new`
2. Chọn NCC ở header; danh sách material trong dòng chỉ gồm material NCC cung
   cấp.
3. Dynamic line editor có layout bảng trên desktop và row blocks gọn trên mobile.
4. Currency/unit là control riêng, không suy ra từ loại NCC.
5. USD/MT hiển thị tỷ giá, chi phí và preview giá quy đổi.
6. Khi predicate nhập lại chung của Phase 5 đúng, mở reason field bắt buộc; UI
   không tự định nghĩa điều kiện khác backend.
7. Tệp gốc dùng FileUpload và hiển thị tiến độ/lỗi.
8. Confirm có dialog nhắc version sẽ khóa.
9. Tạo version mới bắt đầu từ bản copy đầy đủ của version hiện tại.
10. Checkbox chốt mua nằm trên từng dòng và có xác nhận ngắn; UI hiển thị
    “Thời điểm đánh dấu” lấy từ server, không gọi đó là ngày giao dịch.
11. Loading/error/empty/dirty-form guard đầy đủ.

### File Dự Kiến

- `frontend/src/types/quotes.ts`
- `frontend/src/api/quotes.api.ts`
- `frontend/src/api/quotes.mappers.ts`
- `frontend/src/composables/useQuoteEditor.ts`
- `frontend/src/composables/useQuoteDetail.ts`
- `frontend/src/components/quotes/QuoteHeaderForm.vue`
- `frontend/src/components/quotes/QuoteLinesEditor.vue`
- `frontend/src/components/quotes/QuoteVersionHistory.vue`
- `frontend/src/pages/QuoteEditorPage.vue`
- `frontend/src/pages/QuoteDetailPage.vue`
- `frontend/src/styles/pages/_quote-editor-page.scss`
- `frontend/src/styles/pages/_quote-detail-page.scss`

### Kiểm Thử

- Mapper DTO/domain.
- Validation required marker.
- Supplier/material dependent lookup.
- Automatic/manual/fallback exchange-rate states.
- Backfill reason.
- Add/remove multiple lines.
- Version mới tuân thủ copy matrix: reset purchase/file và tính lại provenance
  USD khi confirm.
- Confirm/version copy/purchase toggle.
- Desktop và mobile viewport.

```bash
make frontend-check
npm --prefix frontend run build
make docker-test-e2e
```

### Điều Kiện Hoàn Thành

- Browser E2E chạy trọn vòng đời: tạo phiếu -> confirm -> tạo version mới ->
  tick chốt mua -> reload -> dữ liệu giữ nguyên.
- UI light/dark và mobile không tràn.

### Rollback

- Gỡ route/menu frontend nhưng giữ backend/data.
- Không xóa dữ liệu người dùng đã nhập.

---

## Phase 7: Ghi Chú Thị Trường Và Lịch Sử Chỉnh Sửa

### Bối Cảnh Cho Agent

Ghi chú là domain history riêng, không phải audit metadata. Từ rule ownership
đã chốt ngày 31/07/2026, role `user` chỉ được thêm/sửa/xóa ghi chú trên phiếu
do chính mình tạo; role `admin` được thao tác trên tất cả phiếu.

### Mục Tiêu

- Tạo/sửa ghi chú rich text.
- Xem toàn bộ revision với tác giả và thời gian.
- Không mất nội dung cũ.

### Phase 7.0: Chốt Contract Rich Text Trước Khi Tạo Model

1. Stored format của V1 là sanitized HTML.
2. Frontend dùng PrimeVue Editor và bổ sung dependency `quill`; tài liệu chính
   thức PrimeVue xác nhận Editor dùng Quill.
3. Backend bổ sung một thư viện sanitizer allowlist được pin version; khuyến nghị
   `nh3`, nhưng phải chạy security/dependency review trước khi khóa dependency.
4. Allowlist V1 chỉ gồm các tag tối thiểu: paragraph, line break, bold, italic,
   unordered/ordered list, list item và link.
5. Link chỉ chấp nhận protocol an toàn đã định nghĩa; không cho script, inline
   event, iframe, image, style hoặc data URL.
6. Giới hạn payload sau sanitize; khuyến nghị tối đa 20 KB mỗi revision.
7. Tạo fixture XSS bắt buộc trước implementation.

Không bắt đầu Phase 7 model/API/UI nếu contract này chưa có test và dependency
đã được pin.

### Backend

1. Tạo `QuoteNote` và append-only `QuoteNoteRevision`.
2. Mỗi lần sửa tạo revision mới; không update/delete revision cũ.
3. `QuoteNote` có thể giữ pointer/current version để query nhanh.
4. Sanitize rich text bằng allowlist server-side.
5. Giới hạn kích thước nội dung.
6. API create/update/list revisions/read.
7. Audit chỉ lưu note id, revision number, actor và outcome; không lưu raw HTML.
8. Permission ghi/xóa ghi chú phải đi kèm kiểm tra ownership quote ở backend.
9. Nếu mở delete revision, phải kiểm tra revision thuộc đúng quote trên path.

### Frontend

1. Panel ghi chú trong trang chi tiết báo giá.
2. Editor có toolbar tối thiểu: bold, italic, bullet, link nếu sanitizer cho phép.
3. Timeline revision thể hiện người tạo/sửa và timestamp GMT+7.
4. Nội dung render an toàn, không dùng HTML chưa sanitize từ nguồn khác.
5. User thường không thấy action ghi chú nếu không phải chủ phiếu; Admin vẫn
   thấy action trên mọi phiếu.

### File Dự Kiến

- `backend/app/models/quote_note.py`
- `backend/app/models/quote_note_revision.py`
- `backend/app/schemas/quote_note.py`
- `backend/app/services/quote_note_service.py`
- `backend/app/api/v1/quote_notes.py`
- `backend/alembic/versions/*_create_quote_notes.py`
- `backend/pyproject.toml`
- `backend/uv.lock`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/src/types/quote-notes.ts`
- `frontend/src/api/quote-notes.api.ts`
- `frontend/src/api/quote-notes.mappers.ts`
- `frontend/src/composables/useQuoteNotes.ts`
- `frontend/src/components/quotes/QuoteNotesPanel.vue`
- `frontend/src/styles/components/quotes/quote-notes-panel.scss`

### Kiểm Thử

- User khác không phải chủ phiếu bị chặn tạo/sửa/xóa ghi chú; Admin thao tác
  được trên mọi phiếu.
- Revision không mất.
- XSS payload bị loại.
- Audit không chứa raw content.
- Timezone display.
- RBAC.

### Điều Kiện Hoàn Thành

- Xem được old/new qua revision timeline.
- Audit viewer hiển thị event an toàn.
- E2E hoặc API test cover User A tạo phiếu, User B bị chặn thêm/sửa/xóa ghi chú,
  và Admin vẫn thao tác được.

### Rollback

- Tắt UI/API create/update nhưng giữ dữ liệu revision.
- Không xóa revision trong rollback.

---

## Phase 8: Bảng Báo Giá Và Lịch Sử

### Bối Cảnh Cho Agent

Phase 5-7 đã tạo dữ liệu. Phase này xây read model tối ưu cho người dùng tra cứu,
không bắt frontend ghép nhiều API hoặc tải toàn bộ dữ liệu.

### Mục Tiêu

- DataTable toàn bộ dòng báo giá.
- Filter theo cột, global search.
- Xem phiên bản, file gốc và ghi chú.

### Backend

1. Tạo `QuoteQueryService` riêng cho read path.
2. API `GET /quotes` trả flattened rows đủ cho table:
   - quote/version/line id
   - NCC
   - material
   - quote date/received date/delivery month
   - original price/currency/unit
   - rate/conversion cost/converted price
   - purchased state
   - creator/version
3. Filter:
   - global search
   - material type/material
   - supplier
   - received date range
   - delivery month
   - currency
   - purchased
   - created by
4. Sort whitelist.
5. Offset pagination giai đoạn đầu; index theo workload.
6. Detail endpoint trả version timeline và note summary.
7. Date filters theo `Asia/Ho_Chi_Minh`.

### Frontend

1. Trang `/quotes` là màn hình nghiệp vụ chính.
2. DataTable lazy, rows 10/20/30/50, report tiếng Việt.
3. Filter thường dùng luôn hiển thị; filter phụ trong panel nâng cao.
4. Rows dropdown đứng trước paging.
5. Giá format VNĐ/USD đúng locale; không biến đổi giá gốc.
6. Click row mở detail/version/note, không nhồi mọi thứ vào table.
7. Có action tạo phiếu mới và tạo version nếu có quyền.

### File Dự Kiến

- `backend/app/services/quote_query_service.py`
- `backend/app/api/v1/quotes.py`
- migration index riêng nếu query plan yêu cầu
- `frontend/src/composables/useQuotesPage.ts`
- `frontend/src/pages/QuotesPage.vue`
- `frontend/src/styles/pages/_quotes-page.scss`

### Kiểm Thử

- Pagination không lặp/mất row.
- Filter/sort/global search.
- Date/month boundaries.
- Query count/N+1.
- Empty/loading/error.
- Mobile table scroll.
- Permission menu/route/API.

### Điều Kiện Hoàn Thành

- Tra cứu được dữ liệu lịch sử mà không load toàn bảng.
- Version/note/file truy cập được từ row.
- API có index phù hợp với filter chính.

### Rollback

- Gỡ read route/page mà không tác động write data.
- Index có thể downgrade riêng nếu thực sự cần.

---

## Phase 9: Dashboard Phân Tích Giá

### Bối Cảnh Cho Agent

Dashboard chỉ dùng dữ liệu đã chuẩn hóa từ QuoteQuery/QuoteLine. Không thêm dự báo
hoặc KPI ngoài Requirements.

### Mục Tiêu

- KPI số báo giá theo user.
- Xu hướng giá VNĐ/KG.
- MIN, MAX, TRUNG BÌNH.
- Điểm chốt mua.
- Hai góc nhìn tại và sau thời điểm đánh dấu chốt mua.

### Backend

1. Tạo aggregate service và endpoint:
   - `GET /dashboard/quotify/entry-kpis`
   - `GET /dashboard/quotify/price-trends`
2. Filter bắt buộc/optional:
   - material
   - delivery month
   - received date range
3. Chỉ dùng version confirmed.
4. MIN/MAX/AVG tính bằng SQL trên `converted_price_vnd_per_kg`.
5. Series trả:
   - received date
   - converted price
   - supplier label
   - quote/line id
   - purchased flag
   - purchase_marked_at
6. KPI user đếm `Quote` theo `Quote.created_by_id` bất biến, không đếm dòng hoặc
   người tạo version sau.
7. Góc nhìn “tại thời điểm đánh dấu chốt mua” dùng cùng material/kỳ giao hàng và
   chỉ nhận version có `confirmed_at <= purchase_marked_at`. `received_date`
   nhập lùi không thể làm version xuất hiện trong tập dữ liệu quá khứ.
8. Góc nhìn “sau thời điểm đánh dấu” chỉ nhận version có
   `confirmed_at > purchase_marked_at`; trục biểu đồ vẫn thể hiện
   `received_date` nhưng tập dữ liệu được giới hạn theo thời điểm hệ thống biết
   bản ghi.
9. Endpoint không trả nhãn “đúng/sai”.

### Frontend

1. Thay dashboard boilerplate bằng dashboard Quotify.
2. Bổ sung `chart.js` và dùng PrimeVue Chart; tài liệu chính thức PrimeVue xác
   nhận Chart component cần dependency `chart.js`.
3. Filter bar theo Requirements.
4. KPI cards: MIN, MAX, TRUNG BÌNH, tổng báo giá.
5. Biểu đồ line/scatter:
   - line cho xu hướng
   - marker riêng cho điểm chốt mua
6. KPI số báo giá theo user ở panel/table gọn.
7. Tooltip hiển thị NCC, ngày nhận, kỳ giao hàng và giá.
8. Light/dark theme dùng semantic tokens; không hardcode palette một màu.
9. Empty state khi chưa đủ dữ liệu.

### File Dự Kiến

- `backend/app/services/quotify_dashboard_service.py`
- `backend/app/api/v1/quotify_dashboard.py`
- `backend/app/schemas/quotify_dashboard.py`
- `frontend/src/types/dashboard.ts`
- `frontend/src/api/dashboard.api.ts`
- `frontend/src/api/dashboard.mappers.ts`
- `frontend/src/composables/useDashboardPage.ts`
- `frontend/src/pages/DashboardPage.vue`
- `frontend/src/components/dashboard/PriceTrendChart.vue`
- `frontend/src/components/dashboard/QuoteEntryKpi.vue`
- các SCSS dashboard hiện có

### Kiểm Thử

- Aggregate đúng với nhiều NCC/version.
- Version draft không lọt dashboard.
- Date/month filters.
- Purchased marker và before/after series dựa trên `confirmed_at`, không để bản
  ghi nhập lùi lọt vào tập dữ liệu quá khứ.
- KPI đếm đúng `Quote.created_by_id` khi version sau do user khác tạo.
- Không chia sai timezone.
- Chart nonblank ở desktop/mobile.
- Permission và empty/error state.

```bash
make backend-check
make frontend-check
npm --prefix frontend run build
make docker-test-e2e
```

### Điều Kiện Hoàn Thành

- Dashboard khớp dữ liệu seed kiểm soát được.
- Marker chốt mua khớp dòng báo giá.
- Không có câu kết luận tự động đúng/sai.
- Screenshot desktop/mobile và canvas-pixel check xác nhận chart render.

### Rollback

- Giữ API aggregate, khôi phục dashboard trước nếu frontend chart có regression.
- Dependency chart chỉ gỡ khi không còn import.

---

## Phase 10: Dữ Liệu Mẫu, E2E, Hardening Và Phát Hành

### Bối Cảnh Cho Agent

Mọi module đã hoàn tất. Giai đoạn này kiểm tra toàn bộ lifecycle và chuẩn bị vận
hành, không bổ sung feature mới.

### Mục Tiêu

- Chứng minh hệ thống hoạt động end-to-end.
- Có dữ liệu mẫu và runbook.
- Không làm giảm production readiness của boilerplate.

### Việc Cần Làm

1. Seed idempotent:
   - loại vật tư
   - vật tư
   - NCC/contact/material mapping
   - báo giá VND/KG và USD/MT
   - version điều chỉnh
   - ghi chú từ user khác
   - dòng đã chốt mua
2. Tạo E2E lifecycle:
   - login
   - tạo danh mục
   - tạo NCC
   - lấy/fallback tỷ giá
   - tạo và confirm báo giá
   - tạo version mới
   - ghi chú bằng user khác
   - tick chốt mua
   - tra cứu table
   - xem dashboard
   - kiểm audit
3. Test `403` cho từng nhóm permission.
4. Kiểm tra dark/light, desktop/mobile.
5. Performance smoke cho list quotes và dashboard aggregate.
6. Security:
   - rich text XSS
   - upload type/size
   - SSRF/timeout source tỷ giá
   - rate limit
   - audit secret safety
7. Chạy migration từ database hiện tại và database trống.
8. Backup/restore drill với dữ liệu Quotify.
9. Cập nhật README, runbook deploy, cấu hình tỷ giá và hướng dẫn import.
10. Nếu cần đưa Excel lịch sử vào hệ thống, tạo kế hoạch migration một lần sau
    khi người dùng cung cấp file mẫu; không trộn script chưa xác minh vào release.

### Quality Gates

```bash
make check
make docker-test-backend
make docker-test-frontend
make docker-test-e2e
make security-check
make production-readiness-check
```

Các dependency audit cần mạng ngoài; nếu môi trường chặn DNS phải ghi rõ
`unverified`, không báo pass giả.

### Điều Kiện Hoàn Thành

- Full lifecycle E2E pass trên Docker runner chuẩn.
- Migration, backup và restore drill pass.
- Không còn permission route/seed mismatch.
- Không có tài liệu tiếng Việt không dấu.
- Memory Bank và runbook phản ánh đúng trạng thái code.

### Rollback

- Rollback deployment bằng image/version trước.
- Database ưu tiên forward-fix; restore chỉ dùng khi migration gây mất khả năng
  vận hành và đã xác minh backup.

---

## Ma Trận Kiểm Thử Tối Thiểu

| Lớp | Nội dung |
|---|---|
| Unit backend | pricing Decimal, tỷ giá, date/month, sanitizer, version copy |
| Service backend | CRUD, constraints, transaction, import, dashboard aggregate |
| API contract | schema, RBAC, filter/sort/paging, error mapping |
| Unit frontend | mapper, composable, validation, state machine |
| Component | dynamic quote lines, exchange-rate fallback, notes, dashboard states |
| E2E | full lifecycle, permissions, audit, light/dark, desktop/mobile |
| Security | XSS, file validation, rate limit, external HTTP timeout, metadata |
| Operations | migration, seed, backup/restore, observability |

## Invariant Phải Kiểm Sau Mỗi Phase

1. `make backend-check` pass cho phase có backend.
2. `make frontend-check` và build pass cho phase có frontend.
3. Migration có downgrade path trong môi trường test, trừ migration forward-only
   được ghi rõ.
4. Permission mới có seed và test.
5. Mutation mới có audit event an toàn.
6. Không có `<style>` trong Vue SFC.
7. DataTable rows mặc định 10, options 10/20/30/50.
8. Date/time explicit `Asia/Ho_Chi_Minh`.
9. Tài liệu tiếng Việt đầy đủ dấu.
10. `git diff --check` không có lỗi.

## Anti-Pattern Cấm

- Suy ra currency/unit từ loại NCC.
- Dùng tỷ giá hiện tại để render lại báo giá lịch sử.
- Dùng JavaScript/Python float cho tiền.
- Tin giá quy đổi do frontend gửi mà không tính lại.
- Ghi đè version confirmed.
- Dùng generic audit log thay cho lịch sử note revision.
- Lưu raw rich text trong audit metadata.
- Hard-delete master data đang được quote tham chiếu.
- Load toàn bộ báo giá lên frontend để filter/chart.
- Gọi Vietcombank trực tiếp từ Vue hoặc trực tiếp trong route.
- Enqueue import trước khi transaction job/audit commit.
- Chạy Playwright trong frontend dev container rồi dùng kết quả để kết luận.

## Giao Thức Thay Đổi Kế Hoạch

Nếu phát hiện yêu cầu mới hoặc assumption sai:

1. Ghi finding vào mục `Nhật ký thay đổi` ở cuối tài liệu.
2. Xác định phase bị ảnh hưởng và dependency downstream.
3. Không sửa schema đã triển khai bằng cách chỉnh migration cũ; tạo migration mới.
4. Có thể split phase nếu vượt quá một vertical slice có thể review.
5. Có thể bỏ phase chỉ khi ghi rõ dữ liệu/API/UI nào bị loại khỏi scope.
6. Sau thay đổi, chạy lại review dependency graph và acceptance criteria.

## Definition Of Done Toàn Dự Án

Quotify được coi là hoàn thành phiên bản đầu khi:

1. Danh mục và NCC CRUD/import hoạt động.
2. Tỷ giá tự động/manual/fallback hoạt động và có audit.
3. Phiếu/version/line lưu đúng lịch sử.
4. Ghi chú có revision và actor rõ ràng.
5. Quote DataTable server-side hoạt động.
6. Dashboard đúng scope đơn giản đã chốt.
7. Full Docker E2E và quality gates pass.
8. Migration, backup/restore và runbook đã được kiểm chứng.
9. Không còn chênh lệch giữa Requirements, CONTEXT, Memory Bank và code.

## Nhật Ký Thay Đổi

- 27/07/2026: Tạo kế hoạch ban đầu từ `Requirements.txt`, `CONTEXT.md`, codebase
  hiện tại và các guardrail trong Memory Bank.
- 27/07/2026: Chỉnh kế hoạch sau local reviewer: đóng băng provenance tỷ giá
  trực tiếp trên `QuoteLine`, thu nhỏ API tỷ giá, hạ import xuống CSV-only và
  chia 3A/3B, sửa dependency graph, thêm route-permission matrix, chuyển decision
  gate thành prerequisite Phase 0 và bổ sung contract rich text.
- 27/07/2026: Chỉnh kế hoạch sau vòng review thứ hai: phân biệt thời điểm đánh
  dấu chốt mua với thời điểm giao dịch thực tế, giới hạn hồi cứu theo
  `confirmed_at`, bổ sung copy matrix, constraint/concurrency cho version,
  predicate nhập lại duy nhất, quote-scoped file download và
  `Quote.created_by_id` làm nguồn KPI bất biến.
