# Kế Hoạch Refactor: Công Thức Giá Quy Đổi (Thuế Nhập Khẩu + Chi Phí Làm Hàng)

## Trạng Thái

- Ngày lập kế hoạch: 10/08/2026.
- Người yêu cầu: nguyenvancuong@honghafeed.com.vn.
- Nguồn đọc trước khi lập kế hoạch: `AGENTS.md`, `docs/agent-rules.md`,
  `docs/agent-memory-integration.md`, `memory-bank/quick-start.md`,
  `memory-bank/activeContext.md`, `memory-bank/progress.md`,
  `memory-bank/projectRules.md`, `memory-bank/techContext.md`,
  `memory-bank/systemPatterns.md`, `memory-bank/bugPatterns.md`, `CONTEXT.md`,
  `docs/quotify/quotify-implementation-plan.md`, và toàn bộ source code liên
  quan tới cấu hình quy đổi/giá quy đổi ở backend và frontend.
- Trạng thái: kế hoạch chưa triển khai, đang chờ review trước khi tách thành
  các commit nhỏ.

## Vấn Đề (Từ Góc Nhìn Người Dùng)

Cấu hình quy đổi hiện tại của Quotify chỉ có một tham số duy nhất là "Chi phí
quy đổi", đang hard-code giá trị mặc định `200 VNĐ/KG`
(`backend/app/services/quotify_settings_service.py`,
`DEFAULT_CONVERSION_COST_VND_PER_KG`). Công thức tính giá quy đổi hiện tại là:

```
Giá quy đổi = (Giá USD/MT / 1000) * Tỷ giá + Chi phí quy đổi
```

(`backend/app/services/exchange_rate_service.py`, hàm
`convert_usd_mt_to_vnd_kg`).

Công thức này không phản ánh đúng thực tế mua hàng của phòng Thu Mua: giá vật
tư nhập khẩu còn chịu thuế nhập khẩu tính theo phần trăm trên giá gốc, cộng
thêm chi phí làm hàng cố định theo VNĐ/KG. Vì vậy giá quy đổi hiển thị trên
Quotify hiện tại thấp hơn giá vốn thực tế khi vật tư có thuế nhập khẩu > 0%.

## Giải Pháp (Từ Góc Nhìn Người Dùng)

Tách cấu hình quy đổi hiện tại thành hai tham số độc lập, đều nằm trong trang
`Cấu hình quy đổi` (`/quotify-settings`):

1. **Thuế nhập khẩu**: đơn vị `%`, mặc định hard-code `0%`.
2. **Chi phí làm hàng**: đơn vị `VNĐ/KG`, mặc định `200 VNĐ/KG` — đây chính là
   giá trị "Chi phí quy đổi" cũ, chỉ đổi tên cho đúng bản chất nghiệp vụ vì
   thuế nhập khẩu đã được tách ra thành tham số riêng.

Công thức tính "Giá quy đổi" mới:

```
Giá quy đổi = [ Giá USD/MT / 1000 + (Giá USD/MT / 1000) * Thuế nhập khẩu (%) ] * Tỷ giá
              + Chi phí làm hàng
```

Tương đương:

```
Giá quy đổi = (Giá USD/MT / 1000) * (1 + Thuế nhập khẩu) * Tỷ giá + Chi phí làm hàng
```

Khi `Thuế nhập khẩu = 0%` (giá trị mặc định), công thức mới cho kết quả giống
hệt công thức cũ — đây là điều kiện bắt buộc để không làm sai lệch dữ liệu
lịch sử đã đóng băng trên các `QuoteLine` cũ.

## Xác Minh Từ Codebase

### Backend

- `backend/app/models/quotify_setting.py`: bảng `quotify_settings` (singleton,
  `singleton_key='default'`) hiện chỉ có `conversion_cost_vnd_per_kg`
  (`Numeric(12,2)`, default `200.00`).
- `backend/app/services/quotify_settings_service.py`: hằng số
  `DEFAULT_CONVERSION_COST_VND_PER_KG = Decimal("200.00")`,
  `get_or_create_settings()`, `update_conversion_cost(...)`,
  `validate_conversion_cost(...)`.
- `backend/app/schemas/quotify_settings.py`: `QuotifySettingsResponse`,
  `ConversionCostUpdateRequest`.
- `backend/app/api/v1/quotify_settings.py`: `GET /quotify-settings`,
  `PUT /quotify-settings/conversion-cost`; audit action
  `quotify_settings.conversion_cost_updated` với metadata `changes` (`old_value`
  / `new_value`).
- `backend/app/services/exchange_rate_service.py`: hàm thuần
  `convert_usd_mt_to_vnd_kg(original_price_usd_per_mt, exchange_rate,
  conversion_cost_vnd_per_kg)` và `quantize_money(...)` (`Decimal`,
  `ROUND_HALF_UP`, scale 2 chữ số).
- `backend/app/services/quote_pricing.py`:
  `QuotePricingService.resolve_pricing_provenance(...)` đọc
  `settings.conversion_cost_vnd_per_kg` từ `QuotifySettingsService`, gọi
  `convert_usd_mt_to_vnd_kg(...)`, và trả dict provenance được ghi thẳng vào
  `QuoteLine`.
- `backend/app/models/quote_line.py`: `QuoteLine` đóng băng provenance quy đổi
  trên từng dòng báo giá, gồm `exchange_rate`, `exchange_rate_source`,
  `exchange_rate_source_mode`, `exchange_rate_entered_at`,
  `exchange_rate_manual_reason`, `exchange_rate_actor_id`,
  `conversion_cost_vnd_per_kg`, `price_converted_vnd_per_kg`. Đây là nguồn sự
  thật duy nhất cho provenance quy đổi theo
  `memory-bank/systemPatterns.md#Quotify Pricing And Exchange Rate Pattern` và
  quyết định ở `docs/quotify/quotify-implementation-plan.md`.
- `backend/app/services/quote_service.py`: hàm
  `_resolve_previous_snapshot_pricing(...)` tái sử dụng snapshot
  tỷ giá/nguồn/chi phí của dòng cũ khi bản điều chỉnh giữ nguyên
  `received_date` (theo bug pattern `2026-07-30: Bản điều chỉnh cùng ngày có
  thể bị ghi đè snapshot tỷ giá`). Hàm này gọi lại `convert_usd_mt_to_vnd_kg`
  với `conversion_cost` lấy từ dòng cũ, chưa có khái niệm thuế.
- `backend/app/services/quote_query_service.py`: `SELECT` và map
  `conversion_cost_vnd_per_kg` cho danh sách báo giá.
- `backend/app/schemas/quote.py`, `backend/app/schemas/quote_list.py`: response
  schema của dòng báo giá có field `conversion_cost_vnd_per_kg`.
- `backend/app/services/audit_log.py`: allowlist sanitizer metadata có key
  `conversion_cost_vnd_per_kg`.
- Alembic: `20260728_0900_create_quotify_settings.py` (tạo bảng),
  `20260728_0930_seed_default_quotify_settings.py` (seed default),
  `20260728_1000_create_quote_core.py` (tạo cột
  `conversion_cost_vnd_per_kg` trên `quote_lines`).
- Test liên quan: `backend/tests/test_quotify_settings_service.py`,
  `backend/tests/test_quotify_settings_api.py`,
  `backend/tests/test_exchange_rate_service.py`,
  `backend/tests/test_quote_lifecycle.py`,
  `backend/tests/test_quote_query_service.py`,
  `backend/tests/test_quotes_list_api.py`.

### Frontend

- `frontend/src/types/quotify-settings.ts`: `QuotifySettingsDto`,
  `QuotifySettingsDomain`, `ConversionCostUpdatePayload` — chỉ có field
  `conversion_cost_vnd_per_kg` / `conversionCostVndPerKg`.
- `frontend/src/api/quotify-settings.api.ts` +
  `frontend/src/api/quotify-settings.mappers.ts`: gọi
  `GET /quotify-settings`, `PUT /quotify-settings/conversion-cost`.
- `frontend/src/composables/useQuotifySettingsPage.ts`: form Zod chỉ có
  `conversionCostVndPerKg` (mặc định `200`, min `0`, max `999999`).
- `frontend/src/pages/QuotifySettingsPage.vue`: panel "Chi phí quy đổi" với
  một input `InputNumber` duy nhất.
- `frontend/src/types/quotes.ts`, `frontend/src/api/quotes.mappers.ts`: DTO/
  domain của dòng báo giá có `conversion_cost_vnd_per_kg` /
  `conversionCostVndPerKg`.
- `frontend/src/composables/useQuoteEditor.ts`: biến `conversionCost` (mặc
  định `200`, lấy từ `settings.conversionCostVndPerKg` khi bootstrap) và hàm
  `getLinePreviewPrice(...)` tự tính lại công thức
  `(price / 1000) * rate + cost` phía client để preview — đây là bản sao thủ
  công của công thức backend, phải cập nhật đồng bộ.
- `frontend/src/pages/QuoteDetailPage.vue`: hiển thị
  `(Chi phí: {{ formatMoney(slotProps.data.conversionCostVndPerKg) }} VNĐ/KG)`
  trong dòng USD/MT.
- Test liên quan: `frontend/tests/unit/quotify-settings.mappers.spec.ts`,
  `frontend/tests/unit/QuotifySettingsPage.spec.ts`,
  `frontend/tests/unit/useQuotifySettingsPage.spec.ts`,
  `frontend/tests/unit/quotes.mappers.spec.ts`,
  `frontend/tests/unit/useQuoteEditor.spec.ts`,
  `frontend/tests/unit/useQuotesPage.spec.ts`.

### Tài liệu cần cập nhật cùng lúc

- `CONTEXT.md`: định nghĩa "Chi phí quy đổi" và "Giá quy đổi" phải viết lại
  cho đúng công thức và thuật ngữ mới; cần thêm mục "Thuế nhập khẩu" và
  "Chi phí làm hàng".
- `memory-bank/systemPatterns.md` (mục `Quotify Pricing And Exchange Rate
  Pattern`): công thức `(Giá USD/MT / 1000) * tỷ giá + chi phí quy đổi` phải
  đổi thành công thức mới có thuế nhập khẩu.
- `docs/quotify/quotify-implementation-plan.md`: các đoạn tham chiếu "chi phí
  quy đổi mặc định 200 VNĐ/KG" (Phase 4) nên có chú thích trỏ sang refactor
  này để tránh đọc nhầm là còn nguyên trạng.

## Các Lựa Chọn Đã Cân Nhắc

1. **Giữ tên cột/field `conversion_cost_vnd_per_kg`, chỉ đổi nhãn UI thành
   "Chi phí làm hàng".**
   Ưu điểm: không cần đổi tên cột DB, ít rủi ro. Nhược điểm: tên field/code
   không còn khớp nghĩa nghiệp vụ ("chi phí quy đổi" cũ đã bị thay bằng khái
   niệm khác), gây khó hiểu cho agent/dev đọc sau này, đi ngược
   `memory-bank/projectRules.md#Rule 21` (tài liệu tiếng Việt phải chính xác)
   và tinh thần `CONTEXT.md` là bảng thuật ngữ chuẩn.
2. **Đổi tên cột/field thành `processing_cost_vnd_per_kg` ("Chi phí làm
   hàng") xuyên suốt backend + frontend, thêm cột mới
   `import_tax_rate_percent` cho thuế nhập khẩu.** (Khuyến nghị — xem dưới)
3. **Thêm bảng `quotify_settings` version theo thời gian (lưu lịch sử thay đổi
   cấu hình) thay vì singleton.**
   Vượt phạm vi: `memory-bank/systemPatterns.md` đã chốt rõ Phase 4 chỉ có
   singleton hiện hành, còn provenance lịch sử được đóng băng trên
   `QuoteLine`, không phải trên bảng cấu hình. Việc thêm bảng lịch sử cấu hình
   là một thay đổi kiến trúc riêng, không thuộc phạm vi refactor công thức
   giá lần này.

Kế hoạch dưới đây chọn **Lựa chọn 2**: đổi tên cho đúng thuật ngữ mới, thêm
cột mới cho thuế nhập khẩu, giữ nguyên mô hình singleton settings và mô hình
đóng băng provenance trên `QuoteLine`.

## Phạm Vi

**Trong phạm vi:**

- Thêm tham số "Thuế nhập khẩu" (`%`, mặc định `0%`) vào cấu hình quy đổi.
- Đổi tên tham số "Chi phí quy đổi" thành "Chi phí làm hàng" (`VNĐ/KG`, mặc
  định `200`), giữ nguyên giá trị mặc định.
- Cập nhật công thức tính giá quy đổi cho dòng `USD/MT` ở cả backend
  (`convert_usd_mt_to_vnd_kg`) và frontend preview
  (`useQuoteEditor.getLinePreviewPrice`).
- Đóng băng thêm `import_tax_rate_percent` trên từng `QuoteLine` tại thời điểm
  nhập/điều chỉnh, theo đúng pattern provenance hiện có của
  `conversion_cost_vnd_per_kg`/`exchange_rate`.
- Cập nhật toàn bộ API, schema, mapper, composable, UI, audit metadata
  allowlist, và test liên quan tới hai tham số này.
- Cập nhật `CONTEXT.md` và `memory-bank/systemPatterns.md` cho đúng thuật ngữ
  và công thức mới.
- Migration Alembic thêm cột mới, có default an toàn để dữ liệu cũ không bị
  tính sai lại (`import_tax_rate_percent` cũ = `0.00` cho toàn bộ dòng đã có).

**Ngoài phạm vi:**

- Không đổi cách tính cho dòng `VND/KG` (giá quy đổi vẫn bằng giá gốc, không
  có tỷ giá, thuế hoặc chi phí làm hàng).
- Không thêm lịch sử thay đổi cấu hình (settings history/versioning).
- Không đổi permission (`quotify_settings.read` / `quotify_settings.update`
  giữ nguyên, dùng chung cho cả hai tham số).
- Không đổi luồng resolve tỷ giá Vietcombank (`ExchangeRateService`,
  `VietcombankExchangeRateClient`), chỉ đổi phần cộng chi phí/thuế sau khi có
  tỷ giá.
- Không tính lại (`backfill`) giá quy đổi cho các `QuoteVersion`/`QuoteLine`
  đã tồn tại; dữ liệu lịch sử giữ nguyên giá đã đóng băng theo đúng nguyên tắc
  provenance hiện có.
- Không đổi cơ chế "bản điều chỉnh giữ nguyên `received_date` thì tái sử dụng
  snapshot cũ" — chỉ mở rộng snapshot đó để mang theo cả thuế nhập khẩu.

## Quy Ước Đặt Tên Mới

| Khái niệm | Field backend (Python/DB) | Field frontend (camelCase) | Đơn vị | Mặc định |
| --- | --- | --- | --- | --- |
| Thuế nhập khẩu | `import_tax_rate_percent` | `importTaxRatePercent` | `%` | `0.00` |
| Chi phí làm hàng (tên cũ: Chi phí quy đổi) | `processing_cost_vnd_per_kg` | `processingCostVndPerKg` | `VNĐ/KG` | `200.00` |

Áp dụng nhất quán cho: `QuotifySetting`, `QuoteLine`, các schema Pydantic, DTO/
domain TypeScript, API path, tên hàm service, tên biến composable, và nhãn UI
tiếng Việt (`Thuế nhập khẩu`, `Chi phí làm hàng`).

## Kế Hoạch Commit (Từng Bước Nhỏ, Luôn Chạy Được)

1. **Migration + model `QuotifySetting`**: thêm cột `import_tax_rate_percent`
   (`Numeric(5,2)`, `CheckConstraint >= 0`, `server_default '0.00'`) và đổi
   tên cột `conversion_cost_vnd_per_kg` thành `processing_cost_vnd_per_kg`
   trên bảng `quotify_settings` (một migration `alter_column` rename, không
   drop/create lại để không mất dữ liệu hiện có). Cập nhật
   `backend/app/models/quotify_setting.py`.
2. **Service tầng settings**: cập nhật
   `backend/app/services/quotify_settings_service.py` — đổi hằng số thành
   `DEFAULT_IMPORT_TAX_RATE_PERCENT = Decimal("0.00")` và
   `DEFAULT_PROCESSING_COST_VND_PER_KG = Decimal("200.00")`; đổi
   `update_conversion_cost(...)` thành `update_quotify_settings(...)` nhận cả
   hai tham số, có validate riêng cho từng tham số (thuế `0-100%`, chi phí
   `>= 0`). Cập nhật `backend/tests/test_quotify_settings_service.py`.
3. **Schema + API settings**: cập nhật
   `backend/app/schemas/quotify_settings.py` (`QuotifySettingsResponse` có cả
   hai field; đổi `ConversionCostUpdateRequest` thành
   `QuotifySettingsUpdateRequest` với `import_tax_rate_percent` và
   `processing_cost_vnd_per_kg`) và
   `backend/app/api/v1/quotify_settings.py` (đổi route
   `PUT /quotify-settings/conversion-cost` thành
   `PUT /quotify-settings`, cập nhật audit action thành
   `quotify_settings.updated` với `changes` cho cả hai field khi field đó có
   thay đổi). Cập nhật `backend/tests/test_quotify_settings_api.py`.
4. **Audit sanitizer allowlist**: thêm `import_tax_rate_percent`,
   `processing_cost_vnd_per_kg` vào allowlist trong
   `backend/app/services/audit_log.py`, xóa key
   `conversion_cost_vnd_per_kg` nếu không còn được ghi ở nơi khác. Cập nhật
   test sanitizer liên quan.
5. **Công thức tính giá lõi**: đổi
   `backend/app/services/exchange_rate_service.py#convert_usd_mt_to_vnd_kg`
   sang nhận thêm `import_tax_rate_percent`, tính
   `(original_price_usd_per_mt / 1000) * (1 + import_tax_rate_percent / 100) *
   exchange_rate + processing_cost_vnd_per_kg`, quantize một lần ở cuối. Cập
   nhật `backend/tests/test_exchange_rate_service.py` với case thuế `0%`
   (khớp công thức cũ) và thuế `> 0%`.
6. **`QuoteLine` + migration**: thêm cột
   `import_tax_rate_percent` (`Numeric(5,2)`, nullable, giống cách
   `conversion_cost_vnd_per_kg` đang nullable) và đổi tên cột
   `conversion_cost_vnd_per_kg` thành `processing_cost_vnd_per_kg` trên bảng
   `quote_lines`. Cập nhật `backend/app/models/quote_line.py`.
7. **`QuotePricingService`**: cập nhật
   `backend/app/services/quote_pricing.py#resolve_pricing_provenance` để đọc
   cả hai tham số từ `QuotifySettingsService`, truyền vào
   `convert_usd_mt_to_vnd_kg(...)`, và trả thêm key
   `import_tax_rate_percent` trong dict provenance.
8. **`QuoteService` snapshot reuse**: cập nhật
   `backend/app/services/quote_service.py#_resolve_previous_snapshot_pricing`
   để mang theo `import_tax_rate_percent` của dòng cũ khi tái sử dụng snapshot
   (giữ nguyên `received_date`), và tất cả nơi gán
   `conversion_cost_vnd_per_kg=pricing[...]` vào `QuoteLine` phải đổi tên field
   và thêm gán `import_tax_rate_percent=pricing[...]`. Cập nhật
   `backend/tests/test_quote_lifecycle.py`, đặc biệt các test đã có cho bug
   pattern "bản điều chỉnh cùng ngày giữ snapshot tỷ giá".
9. **`QuoteQueryService` + schema list/detail**: cập nhật
   `backend/app/services/quote_query_service.py`,
   `backend/app/schemas/quote.py`, `backend/app/schemas/quote_list.py` để
   `SELECT` và trả về `import_tax_rate_percent` /
   `processing_cost_vnd_per_kg`. Cập nhật
   `backend/tests/test_quote_query_service.py`,
   `backend/tests/test_quotes_list_api.py`.
10. **Frontend type + mapper cấu hình**: cập nhật
    `frontend/src/types/quotify-settings.ts` (đổi tên field, thêm thuế) và
    `frontend/src/api/quotify-settings.mappers.ts`. Cập nhật
    `frontend/tests/unit/quotify-settings.mappers.spec.ts`.
11. **Frontend API client cấu hình**: cập nhật
    `frontend/src/api/quotify-settings.api.ts` — đổi `updateConversionCost`
    thành `updateQuotifySettings`, gọi `PUT /quotify-settings` với payload có
    cả hai field.
12. **Frontend composable + trang cấu hình**: cập nhật
    `frontend/src/composables/useQuotifySettingsPage.ts` (thêm field Zod cho
    `importTaxRatePercent`, đổi tên field chi phí) và
    `frontend/src/pages/QuotifySettingsPage.vue` (thêm input "Thuế nhập khẩu
    (%)", đổi nhãn "Chi phí quy đổi VNĐ/KG" thành "Chi phí làm hàng VNĐ/KG").
    Cập nhật `frontend/tests/unit/useQuotifySettingsPage.spec.ts`,
    `frontend/tests/unit/QuotifySettingsPage.spec.ts`.
13. **Frontend type + mapper dòng báo giá**: cập nhật
    `frontend/src/types/quotes.ts`, `frontend/src/api/quotes.mappers.ts` để
    thêm `import_tax_rate_percent` / `importTaxRatePercent` và đổi tên field
    chi phí. Cập nhật `frontend/tests/unit/quotes.mappers.spec.ts`.
14. **Frontend preview công thức trong editor**: cập nhật
    `frontend/src/composables/useQuoteEditor.ts` — thêm biến
    `importTaxRatePercent` lấy từ settings khi bootstrap, sửa
    `getLinePreviewPrice(...)` theo đúng công thức mới. Cập nhật
    `frontend/tests/unit/useQuoteEditor.spec.ts` với case thuế `0%` và
    `> 0%`.
15. **Frontend hiển thị chi tiết báo giá**: cập nhật
    `frontend/src/pages/QuoteDetailPage.vue` để hiển thị cả "Thuế nhập khẩu"
    và "Chi phí làm hàng" trong phần chú thích dòng `USD/MT`, thay cho dòng
    `(Chi phí: ... VNĐ/KG)` hiện tại.
16. **Tài liệu**: cập nhật `CONTEXT.md` (định nghĩa thuật ngữ mới, xoá định
    nghĩa cũ của "Chi phí quy đổi" nếu không còn dùng, thêm "Thuế nhập khẩu"
    và "Chi phí làm hàng"), `memory-bank/systemPatterns.md` (công thức mới
    trong mục `Quotify Pricing And Exchange Rate Pattern`), và chú thích liên
    quan trong `docs/quotify/quotify-implementation-plan.md`.
17. **Đóng task theo `AGENTS.md`**: cập nhật `memory-bank/activeContext.md`,
    `memory-bank/progress.md`, và ghi journal vào `.agent-memory/inbox/` theo
    lệnh `scripts/agent-task-close.sh` sau khi toàn bộ commit trên đã merge và
    được kiểm chứng.

Mỗi commit ở trên phải để lại repo ở trạng thái build/test được — không có
commit nào đổi backend model mà chưa đổi migration tương ứng trong cùng
commit đó.

## Quyết Định Kỹ Thuật

- **Đơn vị lưu trữ**: `import_tax_rate_percent` lưu dạng phần trăm thập phân
  (ví dụ `5.00` nghĩa là `5%`), không lưu dạng tỷ lệ `0.05`, để nhất quán với
  cách hiển thị UI và tránh nhầm khi đọc dữ liệu thô trong DB. Công thức phải
  tự chia `/100` khi tính.
- **Kiểu dữ liệu**: tiếp tục dùng `Decimal` + `ROUND_HALF_UP` + scale 2 chữ số
  cho mọi giá trị tiền và tỷ giá, theo đúng
  `memory-bank/systemPatterns.md#Quotify Pricing And Exchange Rate Pattern`.
  `import_tax_rate_percent` cũng dùng `Decimal`, scale 2 chữ số
  (`Numeric(5,2)` đủ cho khoảng `0.00` đến `999.99`, thực tế nghiệp vụ chỉ cần
  `0-100`).
- **Rounding**: chỉ quantize một lần ở bước cuối của
  `convert_usd_mt_to_vnd_kg(...)`, không quantize từng bước trung gian, giữ
  nguyên nguyên tắc rounding hiện có.
- **Đóng băng theo dòng báo giá**: `import_tax_rate_percent` phải được đóng
  băng trên `QuoteLine` tại thời điểm resolve provenance, cùng cơ chế với
  `exchange_rate` và `processing_cost_vnd_per_kg` hiện tại. Không đọc lại
  `QuotifySetting` khi hiển thị dữ liệu lịch sử.
- **Đổi tên có backward-compat ở DB, không backward-compat ở API**: dùng
  `op.alter_column(..., new_column_name=...)` trong Alembic để giữ dữ liệu,
  nhưng API response đổi tên field ngay (không giữ field cũ song song), vì
  Quotify chưa có client ngoài ngoài chính frontend trong repo này và
  `memory-bank/techContext.md` không ghi nhận consumer API bên ngoài.
- **Một endpoint cập nhật cả hai tham số**: `PUT /quotify-settings` nhận cả
  `import_tax_rate_percent` và `processing_cost_vnd_per_kg` trong một request,
  vì UI hiển thị cả hai trong cùng một form "Cấu hình quy đổi" và không có
  nhu cầu nghiệp vụ sửa riêng lẻ. Audit event ghi `changes` chỉ cho field thực
  sự thay đổi giá trị.
- **Không backfill giá quy đổi cũ**: các `QuoteLine` đã tồn tại giữ nguyên
  `price_converted_vnd_per_kg` đã đóng băng; cột `import_tax_rate_percent` cho
  các dòng cũ backfill giá trị `0.00` để nếu có logic nào vô tình đọc lại
  công thức mới trên dữ liệu cũ thì kết quả vẫn khớp với giá đã lưu (vì thuế
  `0%` không đổi công thức).

## Quyết Định Kiểm Thử

- **Nguyên tắc**: test chỉ kiểm hành vi bên ngoài (input -> giá quy đổi/response
  API), không kiểm chi tiết cài đặt nội bộ như tên biến private.
- **Backend — mở rộng test đã có**:
  - `backend/tests/test_exchange_rate_service.py`: thêm case
    `import_tax_rate_percent = 0` (khớp kết quả công thức cũ, dùng để chốt
    không breaking change) và case `import_tax_rate_percent > 0` (ví dụ `5%`)
    với số liệu tính tay để chốt công thức mới đúng.
  - `backend/tests/test_quotify_settings_service.py`,
    `backend/tests/test_quotify_settings_api.py`: thêm case cập nhật riêng
    từng field, cập nhật cả hai field cùng lúc, validate âm/vượt `100%` bị từ
    chối, và audit metadata có đủ `changes` cho field thay đổi.
  - `backend/tests/test_quote_lifecycle.py`: thêm case tạo dòng `USD/MT` khi
    `import_tax_rate_percent > 0` để chốt `price_converted_vnd_per_kg` đúng;
    giữ nguyên và bổ sung case bản điều chỉnh cùng `received_date` phải mang
    theo đúng `import_tax_rate_percent` cũ (mở rộng test đã có cho bug pattern
    "Bản điều chỉnh cùng ngày có thể bị ghi đè snapshot tỷ giá").
  - `backend/tests/test_quote_query_service.py`,
    `backend/tests/test_quotes_list_api.py`: assert response có field mới.
- **Frontend — mở rộng test đã có**:
  - `frontend/tests/unit/quotify-settings.mappers.spec.ts`,
    `frontend/tests/unit/useQuotifySettingsPage.spec.ts`,
    `frontend/tests/unit/QuotifySettingsPage.spec.ts`: cập nhật fixture theo
    field mới, thêm case validate thuế `0-100`.
  - `frontend/tests/unit/quotes.mappers.spec.ts`: cập nhật fixture DTO/domain
    dòng báo giá có field mới.
  - `frontend/tests/unit/useQuoteEditor.spec.ts`: thêm case preview giá với
    thuế `> 0%`, đảm bảo preview client khớp số với backend (tính tay theo
    công thức mới).
- **Prior art**: các file test trên đã có sẵn cấu trúc fixture cho
  `conversion_cost_vnd_per_kg` — chỉ cần mở rộng theo field mới, không cần
  dựng lại bộ test.
- **Xác minh tích hợp bắt buộc theo `memory-bank/projectRules.md#Rule 14`**:
  sau khi đổi migration + model, phải chạy `alembic upgrade head` thật trong
  Docker dev, mở trang `/quotify-settings` bằng tài khoản có quyền
  `quotify_settings.update`, lưu cả hai giá trị, tạo một báo giá `USD/MT` mới
  và xác nhận `Giá quy đổi` hiển thị đúng theo công thức mới — không chỉ dựa
  vào unit test.
- Chạy tối thiểu: `uv run pytest` (backend, targeted rồi full),
  `uv run ruff check .`, `uv run mypy .`, `npm run lint`, `npm run typecheck`,
  `npm run test:unit`, và `npx vite build`; nếu có thời gian, chạy thêm
  `make docker-test-e2e` cho luồng nhập báo giá.

## Ngoài Phạm Vi (Nhắc Lại)

- Không đổi permission, RBAC, hoặc route tỷ giá Vietcombank.
- Không thêm bảng lịch sử cấu hình quy đổi.
- Không backfill lại giá đã đóng băng của báo giá cũ.
- Không đổi công thức cho dòng `VND/KG`.
- Không đổi cơ chế báo giá quá khứ/nhập tay tỷ giá.

## Ghi Chú Thêm

- Vì `import_tax_rate_percent` mặc định `0%` giống hành vi cũ, có thể triển
  khai và deploy các commit 1-9 (backend) trước, xác minh không có regression
  giá quy đổi cho dữ liệu hiện tại, rồi mới mở UI nhập thuế ở commit 10-15.
  Đây là điểm rollback an toàn nếu phát hiện vấn đề giữa chừng: tắt hiển thị
  input "Thuế nhập khẩu" ở UI (ẩn field, giữ mặc định `0`) mà không cần revert
  schema/migration.
- Cần rà lại toàn bộ `docs/quotify/Requirements.txt` và
  `docs/quotify/quotify-implementation-plan.md` sau khi merge để các đoạn mô
  tả "chi phí quy đổi 200 VNĐ/KG" không còn gây hiểu nhầm là chưa tách thuế.
