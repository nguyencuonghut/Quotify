# Kế Hoạch: Import Lại Các Báo Giá Cũ (Backfill Import)

## Trạng Thái

- Ngày lập kế hoạch: 10/08/2026.
- Người yêu cầu: nguyenvancuong@honghafeed.com.vn.
- Nguồn đọc trước khi lập kế hoạch: `AGENTS.md`, `memory-bank/activeContext.md`,
  `memory-bank/progress.md`, `memory-bank/projectRules.md`,
  `memory-bank/systemPatterns.md`, `memory-bank/bugPatterns.md`, `CONTEXT.md`,
  `docs/quotify/quotify-implementation-plan.md`,
  `docs/quotify/refactor-plan-cong-thuc-gia-quy-doi.md`, và toàn bộ source
  code liên quan tới import CSV danh mục, provenance giá quy đổi, và ghi chú
  báo giá ở backend/frontend.
- Trạng thái: kế hoạch chưa triển khai, đang chờ review.

## Vấn Đề (Từ Góc Nhìn Người Dùng)

Phòng Thu Mua có dữ liệu báo giá cũ (từ file Excel/ghi chép tay trước khi
dùng Quotify) cần nhập lại vào hệ thống để có đầy đủ lịch sử phân tích giá.
Nhập tay từng dòng qua màn hình `Nhập báo giá` hiện tại không phù hợp vì:

1. Số lượng dòng cũ có thể lên tới hàng trăm dòng.
2. Màn hình nhập liệu hiện tại **không cho nhập** thuế nhập khẩu và chi phí
   làm hàng theo giá trị tại thời điểm báo giá cũ — nó luôn lấy từ cấu hình
   **hiện hành** (`quotify_settings`), nên nếu dùng màn hình đó để nhập báo
   giá tháng trước, giá quy đổi sẽ sai vì thuế/chi phí có thể đã thay đổi.
3. Tỷ giá quy đổi tại thời điểm cũ đã được hỗ trợ nhập tay (báo giá quá khứ
   bắt buộc nhập tỷ giá), nhưng thuế và chi phí làm hàng thì chưa.
4. Không có cách nào ghi một ghi chú ngắn cho từng dòng báo giá cũ trong lúc
   nhập lại; ghi chú thị trường hiện tại chỉ có 1 ghi chú **cho cả phiếu**
   (theo `Quote`, không theo dòng).

## Giải Pháp (Từ Góc Nhìn Người Dùng)

Thêm tính năng **Import báo giá cũ** bằng file CSV, tương tự các màn hình
import danh mục (`Loại vật tư`, `Vật tư`, `Nhà cung cấp`) đã có:

1. Tải file mẫu CSV, mỗi dòng là một dòng báo giá cũ, gồm: nhà cung cấp, vật
   tư, giá gốc, tiền tệ/đơn vị, kỳ giao hàng, ngày nhận báo giá, và — chỉ với
   dòng `USD/MT` — tỷ giá, % thuế nhập khẩu, chi phí làm hàng tại đúng thời
   điểm đó, cùng một ghi chú tùy chọn cho dòng đó.
2. Upload file, hệ thống xử lý bất đồng bộ (giống import danh mục), báo tiến
   độ, và cho tải file lỗi nếu có dòng không hợp lệ.
3. Các dòng cùng nhà cung cấp và cùng ngày nhận báo giá được gộp lại thành
   **một phiếu báo giá** (một `Quote` + một `QuoteVersion`), giữ đúng thứ tự
   dòng như trong file — đúng với cách một phiếu báo giá thật có nhiều dòng
   vật tư/kỳ giao hàng khác nhau nhưng chỉ có một ngày nhận.
4. Toàn bộ báo giá import qua tính năng này được đánh dấu `is_backfilled =
   true` tự động, không cần người dùng tick từng dòng.

## Xác Minh Từ Codebase

### Hạ tầng import CSV có thể tái sử dụng

- `backend/app/models/import_job.py`: bảng `import_jobs` dùng chung cho mọi
  loại import qua `entity_type`/`task_name`, có `total_rows`,
  `processed_rows`, `failed_rows`, `error_summary`, `errors_json`. Đây là
  substrate chung, **tái sử dụng được trực tiếp**, không cần bảng mới.
- `backend/app/services/catalog_import.py`: `CatalogImportConfig` +
  `CATALOG_IMPORT_CONFIGS` (`material_types`, `materials`, `suppliers`) định
  nghĩa `permission`, `task_name`, `template_headers` (tuple thứ tự cố định,
  so khớp chính xác), `sample_row`, tên audit action. `CatalogImportService`
  xử lý theo `entity_type`, mỗi dòng dùng `session.begin_nested()` để một
  dòng lỗi không kéo sập cả job. **Không tái sử dụng được trực tiếp** cho
  báo giá vì `_upsert_row` hard-code logic riêng cho 3 loại danh mục hiện có
  (upsert theo `code`) — báo giá cần logic khác (group nhiều dòng thành một
  `Quote`, gọi `QuoteService`/`QuotePricingService`).
- `backend/app/api/v1/catalog_imports.py`: route pattern chuẩn —
  `GET /catalog-imports/templates/{entity_type}`,
  `POST /catalog-imports/{entity_type}`,
  `GET /catalog-imports/{job_id}`,
  `GET /catalog-imports/{job_id}/error-file`. Import báo giá cũ nên có route
  riêng (`/quote-backfill-imports`) theo đúng pattern này, không nhồi thêm
  `entity_type` mới vào `CATALOG_IMPORT_CONFIGS` vì logic xử lý khác hẳn.
- Error report dùng cấu trúc `row, code, errors` (CSV) dựng từ
  `ImportJob.errors_json`, theo `build_catalog_import_error_report(...)`.

### Provenance giá quy đổi — lỗ hổng cần vá để hỗ trợ giá trị lịch sử

- `backend/app/services/quote_pricing.py#resolve_pricing_provenance`: với
  dòng `USD/MT`, `import_tax_rate_percent` và `processing_cost_vnd_per_kg`
  **luôn** lấy từ `QuotifySettingsService.get_or_create_settings()` (cấu
  hình **hiện hành**), không có tham số nào để ghi đè theo giá trị lịch sử.
  Chỉ riêng `exchange_rate` đã có tham số `manual_rate`/`manual_reason` cho
  báo giá quá khứ (`received_date < today` bắt buộc nhập tỷ giá).
- `backend/app/services/quote_service.py#_validate_backfill`: nếu
  `received_date < today` hoặc kỳ giao hàng đã qua, bắt buộc
  `is_backfilled = true`; không bắt buộc `backfill_reason` (đã bỏ theo commit
  `a3f772a`).
- **Kết luận**: cần mở rộng `resolve_pricing_provenance(...)` để nhận thêm
  hai tham số tùy chọn `manual_import_tax_rate_percent` và
  `manual_processing_cost_vnd_per_kg`; khi được truyền vào (chỉ từ luồng
  import báo giá cũ), dùng thay cho giá trị đọc từ `QuotifySettingsService`.
  Luồng nhập tay một phiếu qua `POST /api/v1/quotes` **không** được phép
  truyền hai tham số này — giữ nguyên hành vi hiện tại (luôn dùng cấu hình
  hiện hành), để tránh người dùng vô tình/ chủ ý nhập sai thuế/chi phí cho
  báo giá hiện tại.

### Ghi chú báo giá — mô hình hiện tại là theo phiếu, không theo dòng

- `backend/app/models/quote_note.py`: `QuoteNote.quote_id` có
  `unique=True` — **một ghi chú cho một `Quote`**, không phải theo
  `QuoteLine`. `QuoteNoteRevision` giữ lịch sử chỉnh sửa của ghi chú đó.
- Yêu cầu của tính năng này là **một ghi chú cho một dòng báo giá**
  (`QuoteLine`), và "tạm thời" chỉ cần 1 ghi chú, không cần lịch sử revision
  như ghi chú thị trường hiện tại.
- **Kết luận**: không tái sử dụng được `QuoteNote`/`QuoteNoteRevision` (khác
  cấp độ: phiếu vs dòng, và khác yêu cầu revision). Cần thêm cách lưu ghi chú
  theo dòng, xem mục *Quyết Định Kỹ Thuật*.

### Hợp đồng API tạo báo giá hiện tại

- `backend/app/schemas/quote.py#QuoteLineCreateRequest`: chỉ có
  `material_id`, `price_original`, `currency`, `unit`, `delivery_month`,
  `exchange_rate` (tùy chọn), `exchange_rate_manual_reason` (tùy chọn).
  Không có field cho thuế/chi phí làm hàng lịch sử, cũng không có field ghi
  chú theo dòng.
- `backend/app/schemas/quote.py#QuoteCreateRequest`: `supplier_id`,
  `received_date`, `is_backfilled`, `backfill_reason` (tùy chọn),
  `lines` (`min_length=1`).
- `POST /api/v1/quotes` (`backend/app/api/v1/quotes.py`) chuyển thẳng payload
  vào `QuoteService.create_quote(...)`.

### Frontend — pattern import CSV đã có

- `frontend/src/composables/useCatalogImport.ts` +
  `frontend/src/api/catalog-imports.api.ts`: composable tổng quát theo
  `entityType`, luồng: mở dialog import → upload qua PrimeVue `FileUpload` →
  gọi API tạo job → poll trạng thái job theo interval tới khi
  `completed`/`failed` → cho tải template và tải file lỗi. Composable này
  **tái sử dụng được về mặt pattern** (không phải tái sử dụng trực tiếp code,
  vì entity type và API endpoint khác), tính năng mới nên viết một composable
  song song theo đúng khung này, không tự sáng tạo pattern mới.

## Phạm Vi

**Trong phạm vi:**

- Import CSV báo giá cũ, mỗi dòng file = một dòng báo giá
  (`QuoteLine`), nhóm theo `(tên NCC đã chuẩn hóa, ngày nhận báo giá)` thành một
  `Quote` + một `QuoteVersion` (`status = confirmed` ngay, xem quyết định
  bên dưới), giữ thứ tự dòng trong file làm `line_order`.
- Với dòng `USD/MT`: bắt buộc nhập tỷ giá, % thuế nhập khẩu, chi phí làm
  hàng tại thời điểm đó qua file CSV — không tự động lấy từ cấu hình hiện
  hành.
- Với dòng `VND/KG`: các cột tỷ giá/thuế/chi phí phải để trống (giữ đúng quy
  tắc hiện tại: dòng `VND/KG` không có tỷ giá/thuế/chi phí).
- Một cột ghi chú tùy chọn theo từng dòng, lưu tối đa 1 ghi chú/dòng (không
  có lịch sử chỉnh sửa ở giai đoạn này).
- Toàn bộ dòng import được đánh dấu `is_backfilled = true` tự động.
- Job import bất đồng bộ dùng lại `ImportJob`, `JobAdminService`, worker
  streaming CSV theo chunk, error report theo đúng pattern hiện có.
- Permission riêng cho import báo giá cũ, tách khỏi `quotes.create` thông
  thường.
- Audit event cho start/completed/failed của job, và cho việc tạo từng
  `Quote` từ import (tái sử dụng action tạo phiếu hiện có hoặc thêm action
  riêng, xem quyết định).
- Frontend: trang/nút import trên `/quotes`, tái sử dụng UX pattern
  upload → progress → tải file lỗi.

**Ngoài phạm vi:**

- Không cho sửa báo giá đã import qua giao diện import (sửa sau khi import
  vẫn dùng luồng "Tạo bản điều chỉnh" hiện có của phiếu báo giá bình thường).
- Không thêm lịch sử revision cho ghi chú theo dòng ở giai đoạn này (đúng như
  yêu cầu "tạm thời chỉ có 1 ghi chú"); nếu sau này cần sửa/xóa/lịch sử ghi
  chú theo dòng, đó là một tính năng riêng, không mở rộng ở đây.
- Không cho ghi đè thuế/chi phí làm hàng lịch sử qua màn hình nhập báo giá
  thủ công (`POST /api/v1/quotes` giữ nguyên hành vi hiện tại).
- ~~Không tự động dò trùng lặp...~~ **Đã đổi quyết định ngày 12/08/2026** sau khi
  người dùng test thực tế bị tạo trùng dữ liệu 2 lần: có dò trùng lặp, nhưng
  chỉ chặn khi **trùng hoàn toàn** dữ liệu dòng (NCC + ngày + vật tư + giá +
  kỳ giao + tỷ giá + thuế + chi phí làm hàng), vẫn cho phép NCC báo giá khác
  trong cùng ngày. Xem `_resolve_supplier_id`/`_load_existing_line_keys`
  trong `quote_backfill_import.py`.
- Không hỗ trợ Excel (`.xlsx`); chỉ CSV, đúng theo pattern import danh mục
  hiện tại của Quotify.
- Không đổi công thức giá quy đổi hay bảng `quotify_settings` — tính năng
  này chỉ thêm đường dẫn "override" cho riêng luồng import, không đổi hành
  vi mặc định.

## Cấu Trúc File CSV

Cột theo đúng thứ tự (so khớp chính xác như các template import danh mục
hiện có):

| Cột | Bắt buộc | Ghi chú |
| --- | --- | --- |
| `supplier_name` | Luôn | Tên NCC — khớp theo `Supplier.name` HOẶC `Supplier.code` đã chuẩn hóa (bỏ khoảng trắng dư, không phân biệt hoa/thường); nếu không khớp chính xác, fallback sang khớp gần đúng (containment) với tên/mã NCC trong hệ thống. Đã đổi từ `supplier_code` ngày 10/08/2026 vì file lịch sử thực tế ghi tên NCC, không ghi mã; đến ngày 12/08/2026 mở rộng thêm khớp theo mã/containment vì file thực tế hay ghi tên viết tắt (`ADM`, `CJ`...) không khớp tuyệt đối `Supplier.name` đầy đủ. |
| `received_date` | Luôn | `DD/MM/YYYY` (đổi từ `YYYY-MM-DD` ngày 10/08/2026 vì file lịch sử thực tế ghi theo định dạng này), phải là ngày trong quá khứ. |
| `material_code` | Luôn | Mã vật tư đã có trong danh mục `Vật tư`. |
| `price_original` | Luôn | Số, giá gốc theo `currency`/`unit`. |
| `currency` | Luôn | `VND` hoặc `USD`. |
| `unit` | Luôn | `KG` hoặc `MT`; chỉ chấp nhận cặp `VND/KG` hoặc `USD/MT`. |
| `delivery_month` | Luôn | `MM/YYYY` (đổi từ `YYYY-MM` ngày 10/08/2026, cùng lý do với `received_date`). |
| `exchange_rate` | Bắt buộc nếu `USD/MT`, để trống nếu `VND/KG` | Tỷ giá VNĐ/USD tại thời điểm báo giá. |
| `import_tax_rate_percent` | Bắt buộc nếu `USD/MT`, để trống nếu `VND/KG` | Thuế nhập khẩu (%) tại thời điểm đó. |
| `processing_cost_vnd_per_kg` | Bắt buộc nếu `USD/MT`, để trống nếu `VND/KG` | Chi phí làm hàng (VNĐ/KG) tại thời điểm đó. |
| `note` | Tùy chọn | Ghi chú ngắn cho riêng dòng này. |

## Cân Nhắc Hiệu Năng (Quy Mô Dữ Liệu Lớn)

Dữ liệu cũ cần nhập lại hiện tại chủ yếu cho 3 loại nguyên liệu (Ngô hạt, SBM,
Lúa mỳ), mỗi loại khoảng 10.000 dòng — tổng ước tính **~30.000 dòng** cho một
lần import, lớn hơn nhiều so với quy mô vài trăm dòng của import danh mục
hiện tại. Thiết kế phải chịu được quy mô này mà không timeout, không N+1
query, và không làm phình bảng `import_jobs`/`audit_logs`. Các điểm bắt buộc
áp dụng, không để mặc định như `CatalogImportService`:

1. **Cache mã/tên → id theo NCC/vật tư trong bộ nhớ, không query theo từng
   dòng.** Tải toàn bộ `Supplier.name -> Supplier.id` (không lọc, vì so khớp
   theo tên đã chuẩn hóa không lọc chính xác được bằng SQL `IN(...)`) và
   `material_code -> material_id` (lọc theo mã xuất hiện trong file) một lần
   khi job bắt đầu (2 query), giữ trong `dict` dùng lại cho toàn bộ 30.000
   dòng. Tuyệt đối không query DB theo `material_code`/tên NCC lặp lại cho
   mỗi dòng — đó sẽ là 30.000 round-trip không cần thiết.
2. **Không dùng nguyên trạng `QuoteService.create_quote(...)` cho import.**
   Hàm này sau khi insert xong luôn chạy thêm một `SELECT` để reload toàn bộ
   `Quote` cùng `versions -> lines -> material` (phục vụ response đầy đủ cho
   `POST /api/v1/quotes` tương tác đơn lẻ). Với hàng nghìn nhóm phiếu, mỗi
   nhóm gọi `create_quote` mặc định sẽ tạo thêm hàng nghìn `SELECT` thừa
   không phục vụ mục đích gì cho job import (job chỉ cần biết đã tạo thành
   công, không cần trả nested response). Cần một biến thể nội bộ (ví dụ
   `create_quote(..., skip_reload=True)` trả về `Quote.id` thô, hoặc tách
   phần "build + insert" ra khỏi phần "reload for response") chỉ dùng cho
   luồng import; API tương tác đơn lẻ giữ hành vi reload như cũ.
3. **Commit theo lô, không commit ngay sau mỗi nhóm.** Mỗi nhóm vẫn dùng
   `session.begin_nested()` riêng để cô lập lỗi (đúng Quyết Định 5 ở dưới),
   nhưng gộp `commit()` cấp ngoài theo lô (ví dụ mỗi 200-500 nhóm) thay vì
   commit ngay sau từng nhóm, để giảm số round-trip cấp transaction trong khi
   vẫn giữ đúng ngữ nghĩa "một nhóm lỗi không ảnh hưởng nhóm khác".
4. **Không audit theo từng phiếu được tạo từ import.** Ghi một audit event
   tổng kết duy nhất khi job kết thúc (`quotes.backfill_import_completed`)
   với số liệu tổng hợp (`created_quote_count`, `created_line_count`,
   `failed_group_count`), theo đúng pattern audit terminal của các worker
   import khác (`memory-bank/systemPatterns.md#Import Job Substrate
   Pattern`). Không tái dùng action `quotes.quote_created` lặp lại cho từng
   phiếu import — với 30.000 dòng có thể ra hàng nghìn phiếu, ghi audit theo
   từng phiếu sẽ làm phình bảng `audit_logs` không cần thiết cho một hành
   động import duy nhất.
5. **Cập nhật tiến độ job theo lô, không update sau mỗi dòng.** Ghi
   `processed_rows`/`failed_rows` vào `ImportJob` theo định kỳ (ví dụ mỗi 200
   dòng xử lý, hoặc theo khoảng thời gian) thay vì `UPDATE` sau mỗi dòng —
   tránh 30.000 lần `UPDATE` vào một dòng `import_jobs` chỉ để phục vụ
   progress bar polling ở frontend.
6. **Buffer theo nhóm khi đọc CSV vẫn nằm trong giới hạn RAM hợp lý ở quy mô
   này.** Vì nhóm theo `(supplier_name đã chuẩn hóa, received_date)` có thể không liền kề
   trong file, cần giữ các dòng đã parse (dataclass gọn, không phải dữ liệu
   thô) theo key nhóm cho tới hết file mới biết nhóm nào đầy đủ. Ở quy mô
   30.000 dòng, việc này chỉ tốn vài MB RAM nên chấp nhận được — khác với
   quy tắc "không dùng `rows = list(reader)`" trong
   `memory-bank/systemPatterns.md#Import Job Substrate Pattern`, quy tắc đó
   nhắm tới việc không giữ dữ liệu thô không giới hạn kích thước, còn ở đây
   dữ liệu đã được parse gọn và quy mô thực tế đã biết trước. Nếu tương lai
   quy mô tăng lên hàng trăm nghìn dòng, cần xem lại chiến lược này (ví dụ
   yêu cầu file đã được sắp theo nhóm, hoặc dùng bảng tạm).
7. **Kiểm tra timeout của job hàng đợi (worker/RQ).** Job xử lý 30.000 dòng
   có thể chạy vài phút; phải đo thời gian thực tế trong bước xác minh tích
   hợp Docker dev (mục *Kế Hoạch Kiểm Thử*) và tăng timeout cấu hình worker
   nếu cần, không chỉ dựa vào giá trị mặc định đang dùng cho import danh mục
   quy mô nhỏ.
8. **Xác minh lại hiệu năng các truy vấn đọc `quote_lines` sau khi import ở
   quy mô này** (trang `Bảng báo giá`, dashboard phân tích giá) — dữ liệu
   tăng thêm ~30.000 dòng một lần là mức tăng đáng kể so với hiện tại. Tái sử
   dụng index đã có từ migration
   `20260729_0800_optimize_quote_list_indexes.py`; chỉ thêm index mới nếu đo
   thực tế (ví dụ `EXPLAIN ANALYZE`) cho thấy cần, không thêm trước khi có số
   liệu.

## Quyết Định Kỹ Thuật

1. **Ghi chú theo dòng lưu trực tiếp trên `QuoteLine`, không tạo bảng
   mới.** Thêm cột `note` (`Text`, nullable) trực tiếp trên `quote_lines`,
   thay vì tạo bảng `quote_line_notes` riêng hay tái sử dụng
   `QuoteNote`/`QuoteNoteRevision`. Lý do: yêu cầu hiện tại chỉ cần đúng 1
   ghi chú/dòng, không cần lịch sử/nhiều tác giả — thêm bảng và revision
   ngay từ đầu là over-engineering cho một yêu cầu "tạm thời". Nếu sau này
   cần lịch sử chỉnh sửa ghi chú theo dòng, tách bảng riêng lúc đó (giống
   con đường `QuoteNote` đã đi qua) sẽ dễ hơn suy luận ngược từ một cột đơn.
   Cột này áp dụng cho **mọi** `QuoteLine`, không chỉ dòng import (nhập tay
   qua UI cũng có thể set), nhưng phạm vi hiện tại chỉ làm UI nhập từ import
   — nhập tay ghi chú theo dòng qua form là việc khác, ngoài phạm vi.
2. **Override thuế/chi phí lịch sử chỉ mở cho luồng import, không mở cho API
   tạo báo giá thường.** Thêm hai tham số tùy chọn
   `manual_import_tax_rate_percent`, `manual_processing_cost_vnd_per_kg` vào
   `QuotePricingService.resolve_pricing_provenance(...)`; chỉ service import
   báo giá cũ truyền vào, `QuoteService.create_quote(...)` dùng cho luồng
   thường **không** truyền (giữ `None`, hành vi cũ không đổi).
3. **Bắt buộc đủ cả ba giá trị lịch sử cho dòng `USD/MT` khi import, không
   cho phép fallback về cấu hình hiện hành.** Nếu thiếu bất kỳ giá trị nào
   trong `exchange_rate`/`import_tax_rate_percent`/`processing_cost_vnd_per_kg`
   cho một dòng `USD/MT`, dòng đó (và theo quyết định 5, cả nhóm phiếu chứa
   nó) bị lỗi — không tự lấy giá trị hiện hành để "đoán" giá lịch sử, vì đó
   chính là lỗi đang cố sửa.
4. **Version tạo ra từ import ở trạng thái `confirmed` ngay, không phải
   `draft`.** Đây là dữ liệu lịch sử đã chốt trong thực tế (báo giá đã nhận
   và dùng trong quá khứ), không có ý nghĩa nghiệp vụ khi để ở trạng thái
   "đang soạn". Điều này khác với luồng nhập tay hiện tại (tạo ra `draft`,
   người dùng bấm "Xác nhận" riêng) — luồng import bỏ qua bước xác nhận thủ
   công vì đây là nhập lại dữ liệu đã có sẵn, không phải quy trình duyệt báo
   giá mới.
5. **Một nhóm (một `Quote`) thất bại toàn bộ nếu bất kỳ dòng nào trong nhóm
   lỗi, không tạo phiếu với chỉ các dòng hợp lệ.** Vì các dòng trong một
   phiếu đại diện cho một lần nhận báo giá thống nhất từ một NCC, tạo phiếu
   thiếu dòng do lỗi dữ liệu sẽ gây hiểu sai dữ liệu lịch sử. Đây khác với
   `CatalogImportService` (cho phép `completed` dù có `failed_rows > 0`) vì
   danh mục là các bản ghi độc lập, còn dòng báo giá trong cùng phiếu không
   độc lập với nhau. Job vẫn có thể `completed` với `failed_rows > 0` ở mức
   **nhóm** (nhóm khác trong cùng file vẫn xử lý bình thường).
6. **Nhóm dòng theo `(supplier_name đã chuẩn hóa, received_date)` theo đúng thứ tự xuất
   hiện trong file; `line_order` lấy theo thứ tự dòng trong nhóm.** Không
   yêu cầu các dòng cùng nhóm phải liền kề trong file (cho phép nhóm xen kẽ),
   nhưng thứ tự trong nhóm vẫn theo thứ tự xuất hiện tăng dần trong file.
7. **`is_backfilled` luôn `true`, không đọc từ file.** Không cần cột
   `is_backfilled` trong CSV; validate `received_date`/`delivery_month` vẫn
   chạy qua `_validate_backfill(...)` hiện có để bảo đảm nhất quán (import mà
   `received_date` không thực sự trong quá khứ vẫn nên bị coi là bất thường
   và báo lỗi, không âm thầm chấp nhận).
8. **Permission riêng `quotes.backfill_import`**, không dùng `quotes.create`.
   Đây là đường ghi dữ liệu lịch sử có khả năng ảnh hưởng lớn (hàng trăm
   dòng/lần), tách quyền để admin có thể cấp riêng, không tự động theo
   `quotes.create` hiện có của role `user`.
9. **Route và entity type riêng, không nhồi vào `CATALOG_IMPORT_CONFIGS`.**
   Thêm `backend/app/api/v1/quote_backfill_imports.py` với route
   `POST /quote-backfill-imports`, `GET /quote-backfill-imports/{job_id}`,
   `GET /quote-backfill-imports/{job_id}/error-file`,
   `GET /quote-backfill-imports/template`; `ImportJob.entity_type =
   "quote_backfill"`, `task_name = "import_quote_backfill_task"`. Worker mới
   không tái sử dụng `CatalogImportService`, chỉ tái sử dụng
   `ImportJob`/`JobAdminService`/pattern streaming CSV.
10. **Khớp NCC theo tên đã chuẩn hóa (`Supplier.name`), không theo mã, và
    chấp nhận sai khác khoảng trắng/hoa-thường.** Cập nhật 10/08/2026: dữ
    liệu lịch sử thực tế ghi tên NCC (ví dụ "Tập đoàn Tân Long"), không ghi
    mã NCC như giả định ban đầu của kế hoạch. Cột CSV đổi từ `supplier_code`
    thành `supplier_name`; so khớp bằng cách chuẩn hóa cả tên trong file và
    `Supplier.name` (gộp khoảng trắng dư, không phân biệt hoa/thường) trước
    khi so sánh — không yêu cầu khớp chính xác tuyệt đối từng ký tự. Nếu tên
    đã chuẩn hóa không khớp NCC nào, hoặc khớp nhiều hơn một NCC (hai NCC có
    tên trùng sau khi chuẩn hóa), nhóm dòng đó bị lỗi rõ ràng theo đúng
    Quyết Định 5 (không tạo phiếu thiếu dòng). Vật tư vẫn khớp theo
    `material_code` như cũ (không đổi), vì dữ liệu lịch sử vẫn ghi đúng mã
    vật tư.

## Kế Hoạch Commit (Từng Bước Nhỏ, Luôn Chạy Được)

1. **Migration + model**: thêm cột `note` (`Text`, nullable) trên
   `quote_lines`. Cập nhật `backend/app/models/quote_line.py`.
2. **Mở rộng `QuotePricingService`**: thêm hai tham số tùy chọn
   `manual_import_tax_rate_percent`, `manual_processing_cost_vnd_per_kg` vào
   `resolve_pricing_provenance(...)`; khi được truyền, dùng thay cho giá trị
   đọc từ `QuotifySettingsService`; validate bắt buộc đủ cả ba giá trị lịch
   sử khi có ít nhất một trong số chúng được truyền (tránh truyền thiếu một
   phần). Cập nhật `backend/tests/test_quote_lifecycle.py`/test riêng cho
   `quote_pricing.py` với case override lịch sử.
3. **Schema request cho import**: thêm
   `backend/app/schemas/quote_backfill_import.py` định nghĩa cấu trúc dòng đã
   parse (không phải request HTTP, dùng nội bộ giữa route/service/worker) và
   response job (tái dùng shape response của `ImportJob` hiện có).
4. **`QuoteBackfillImportService`**: thêm
   `backend/app/services/quote_backfill_import.py` — validate header CSV
   theo `template_headers` cố định, đọc CSV streaming theo chunk, nhóm dòng
   theo `(supplier_name đã chuẩn hóa, received_date)` bằng buffer trong bộ nhớ (chấp nhận
   ở quy mô ~30.000 dòng theo mục *Cân Nhắc Hiệu Năng*), tải trước toàn bộ
   mapping `supplier_name (đã chuẩn hóa) -> supplier_id` và `material_code -> material_id`
   một lần thành cache dict (không query lại theo từng dòng), gọi
   `QuoteService.create_quote(..., skip_reload=True)` cho mỗi nhóm trong
   `session.begin_nested()` riêng để một nhóm lỗi không kéo sập nhóm khác,
   commit theo lô (mỗi 200-500 nhóm, không commit ngay sau từng nhóm), cập
   nhật `processed_rows`/`failed_rows` theo lô (không update sau mỗi dòng),
   tích lũy `QuoteBackfillImportSummary` tương tự `CatalogImportSummary`.
5. **Mở rộng `QuoteService.create_quote(...)`**: nhận thêm tham số tùy chọn
   theo dòng cho override lịch sử và `note`, truyền xuống
   `QuotePricingService`, gán `note` vào `QuoteLine`, ép
   `is_backfilled=True` + version `status="confirmed"` khi được gọi từ
   luồng import (thêm tham số `confirm_immediately: bool = False`), và thêm
   tham số `skip_reload: bool = False` để bỏ qua `SELECT` reload
   `Quote`/`versions`/`lines`/`material` sau khi insert khi gọi từ import
   (chỉ trả `Quote.id`) — API `POST /api/v1/quotes` tương tác đơn lẻ giữ
   `skip_reload=False` như hành vi hiện tại, không đổi response shape của
   route đó. Cập nhật `backend/tests/test_quote_lifecycle.py`.
6. **Route + permission**: thêm
   `backend/app/api/v1/quote_backfill_imports.py` với 4 route theo mục 9 ở
   trên, permission `quotes.backfill_import`, audit event
   `quotes.backfill_import_started/completed/failed`, cập nhật
   `backend/app/auth/seed_data.py` (thêm permission mới vào
   `BASE_PERMISSION_CODES`, không tự cấp cho role `user` — admin cấp thủ công
   qua màn hình phân quyền) và `backend/tests/test_permission_inventory.py`.
7. **Worker task**: thêm `import_quote_backfill_task` trong
   `backend/app/worker.py`, đọc file từ MinIO qua `FileAdminService`, gọi
   `QuoteBackfillImportService`, ghi `errors_json`/`error_summary`, ghi
   **một** audit terminal event duy nhất cho cả job (`created_quote_count`,
   `created_line_count`, `failed_group_count`) cùng transaction với terminal
   status — không ghi audit theo từng phiếu được tạo (xem *Cân Nhắc Hiệu
   Năng*, mục 4), dọn file lỗi qua route error-file có sẵn pattern. Kiểm tra
   và tăng timeout job hàng đợi nếu cần cho job quy mô ~30.000 dòng.
8. **Audit metadata allowlist**: thêm các key mới (ví dụ
   `imported_quote_count`, `imported_line_count`, `skipped_group_count`) vào
   `ALLOWED_AUDIT_METADATA_KEYS` trong `backend/app/services/audit_log.py`.
9. **Frontend type + mapper + API client**: thêm
   `frontend/src/types/quote-backfill-imports.ts`,
   `frontend/src/api/quote-backfill-imports.api.ts`,
   `frontend/src/api/quote-backfill-imports.mappers.ts` theo đúng shape của
   `catalog-imports.api.ts`/`catalog-imports.mappers.ts` hiện có.
10. **Frontend composable + UI**: thêm
    `frontend/src/composables/useQuoteBackfillImport.ts` (tái sử dụng pattern
    của `useCatalogImport.ts`: upload → poll → tải template/lỗi), thêm nút
    `Import báo giá cũ` trên `frontend/src/pages/QuotesPage.vue` gated bằng
    quyền `quotes.backfill_import`, dialog upload dùng lại style/markup của
    dialog import danh mục hiện có (không tạo pattern UI mới).
11. **Cập nhật hiển thị ghi chú dòng**: thêm hiển thị `note` (nếu có) trên
    `frontend/src/pages/QuoteDetailPage.vue` ở phần chi tiết dòng báo giá
    (chỉ hiển thị, không có UI sửa ở giai đoạn này vì ngoài phạm vi).
12. **Tài liệu**: cập nhật `CONTEXT.md` (thêm định nghĩa "Ghi chú dòng báo
    giá" nếu cần phân biệt với "Ghi chú thị trường" hiện có),
    `memory-bank/systemPatterns.md` (thêm mục pattern cho import báo giá cũ,
    tương tự mục *Import Job Substrate Pattern* hiện có).

## Quyết Định Kiểm Thử

- **Backend**:
  - `backend/tests/test_quote_pricing_backfill_override.py` (mới hoặc mở
    rộng test hiện có của `quote_pricing.py`): override đủ cả ba giá trị lịch
    sử cho ra đúng `price_converted_vnd_per_kg`; thiếu một trong ba giá trị
    khi có ý định override phải raise lỗi rõ ràng; luồng không override (giữ
    `None` cho cả ba) vẫn dùng cấu hình hiện hành như cũ (regression cho hành
    vi hiện có).
  - `backend/tests/test_quote_backfill_import_service.py` (mới): nhóm đúng
    theo `(supplier_name đã chuẩn hóa, received_date)`; một nhóm có dòng lỗi thì toàn
    nhóm bị loại khỏi kết quả thành công, nhóm khác trong file vẫn xử lý
    được; dòng `USD/MT` thiếu bất kỳ giá trị lịch sử nào bị báo lỗi rõ ràng
    theo số dòng gốc trong file; dòng `VND/KG` có giá trị dư (đáng lẽ để
    trống) bị báo lỗi; `note` được gán đúng cho từng `QuoteLine`; version tạo
    ra có `status="confirmed"` và `is_backfilled=True`.
  - `backend/tests/test_quote_backfill_imports_api.py` (mới): permission
    `quotes.backfill_import` chặn đúng route; job trả về đúng
    `total_rows`/`processed_rows`/`failed_rows`; audit event ghi đủ
    metadata cho phép trong allowlist.
  - Prior art: cấu trúc test đã có trong
    `backend/tests/test_catalog_import_service.py` (nếu tồn tại theo tên
    tương tự) hoặc test import CSV vật tư/NCC hiện có — mở rộng theo đúng
    khuôn mẫu assert `errors_json`/`error_summary`/`failed_rows`.
- **Frontend**:
  - `frontend/tests/unit/quote-backfill-imports.mappers.spec.ts`,
    `frontend/tests/unit/useQuoteBackfillImport.spec.ts`: theo đúng khuôn mẫu
    test đã có cho `useCatalogImport`/`catalog-imports.mappers` (nếu có file
    test tương ứng, dùng làm prior art trực tiếp).
- **Xác minh tích hợp bắt buộc theo `memory-bank/projectRules.md#Rule 14`**:
  sau khi có migration + worker, phải chạy `alembic upgrade head` thật trong
  Docker dev, upload một file CSV mẫu thật (gồm cả nhóm hợp lệ và nhóm có lỗi
  cố ý) qua UI hoặc `curl`, xác nhận job hoàn tất đúng
  `processed_rows`/`failed_rows`, tải file lỗi xem đúng nội dung, và mở phiếu
  báo giá vừa tạo để xác nhận giá quy đổi tính đúng theo thuế/tỷ giá/chi phí
  lịch sử đã nhập (không phải theo cấu hình hiện hành) — không kết luận xong
  chỉ dựa vào unit test.
- **Bắt buộc test ở đúng quy mô dữ liệu thật (~30.000 dòng), không chỉ file
  mẫu nhỏ**: dựng một file CSV thật với khối lượng tương đương dữ liệu cũ
  (3 vật tư × ~10.000 dòng) chạy trong Docker dev, đo thời gian job hoàn tất,
  xác nhận không có lỗi timeout hàng đợi, số lần `UPDATE`
  `import_jobs`/`INSERT audit_logs` ở mức hợp lý (không phải hàng chục nghìn
  lần), và `EXPLAIN ANALYZE` một truy vấn `Bảng báo giá`/dashboard đại diện
  sau khi import để xác nhận vẫn dùng index hiện có, không quét toàn bảng.
  Không kết luận tính năng đạt yêu cầu hiệu năng chỉ dựa trên file test vài
  chục dòng.

## Ngoài Phạm Vi (Nhắc Lại)

- Không hỗ trợ sửa/xóa ghi chú dòng sau khi import (chỉ tạo lúc import).
- Không hỗ trợ Excel, chỉ CSV.
- ~~Không dò trùng lặp dữ liệu~~ — đã đổi ngày 12/08/2026, xem quyết định ở trên.
- Không đổi hành vi `POST /api/v1/quotes` hiện có.
- Không thêm lịch sử revision cho ghi chú dòng.

## Ghi Chú Thêm

- Vì version tạo ra ở trạng thái `confirmed` ngay (không qua `draft`), nếu
  phát hiện sai sau khi import, người dùng sửa bằng đúng luồng "Tạo bản điều
  chỉnh" đã có cho phiếu `confirmed` (không cần tính năng sửa riêng cho dữ
  liệu import).
- Cần thống nhất với người dùng nghiệp vụ: nếu hai dòng trong cùng file có
  cùng `(supplier_name, received_date, material_code, delivery_month,
  currency, unit)` (trùng hoàn toàn), có coi là lỗi hay cho phép (ví dụ NCC
  báo hai lần cho cùng kỳ hàng)? Kế hoạch hiện tại **cho phép** trùng (không
  validate) vì đây là dữ liệu lịch sử tái nhập, có thể có nhiều dòng hợp lệ
  cho cùng tổ hợp do bản chất dữ liệu cũ; nếu nghiệp vụ muốn chặn, cần bổ
  sung một quyết định rõ ràng trước khi triển khai Commit 4.
