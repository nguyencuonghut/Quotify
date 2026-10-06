# Kế Hoạch Chi Tiết Giai Đoạn 1D: Độ Mới Của Giá Theo Vật Tư (Bảng Dashboard Và Nhắc Qua Telegram)

## Trạng Thái

BẢN NHÁP ĐÃ CHỐT PHẦN NGHIỆP VỤ (bản 1, soạn 2026-10-06). Sáu quyết định nghiệp vụ đã chốt (mục "Câu Hỏi Đã Chốt"). **Bốn điểm còn lại (Q7 đến Q10) là đề xuất, chờ xác nhận**; kế hoạch đã ghi sẵn giá trị mặc định để slice nào không phụ thuộc thì làm được ngay. **Chưa có dòng code nào.**

Kế hoạch này nối tiếp [plan-telegram-giai-doan-1c-giao-dien-ban-tin-van-hanh.md](plan-telegram-giai-doan-1c-giao-dien-ban-tin-van-hanh.md) (1A, 1B, 1C đã chạy trên production từ 2026-10-06) và tái dùng hạ tầng Telegram của 1B và 1C. Đây là nhu cầu mới phát sinh sau khi 1C lên production, không có trong kế hoạch cha [plan-telegram-bien-dong-gia-va-chatbot-ai.md](plan-telegram-bien-dong-gia-va-chatbot-ai.md) ban đầu; chatbot AI (Giai đoạn 2) không thuộc kế hoạch này.

Cách soạn:
- Vai trò: Trưởng phòng Mua kiêm chuyên gia phân tích dữ liệu cùng người dùng thảo luận nhu cầu, rồi đối chiếu với số liệu thật trên DB dev (Phụ lục A).
- Local skill `to-issues`: chia lát cắt dọc (tracer bullet), mỗi slice đi qua đủ các tầng cần thiết, tự xác minh được, có loại **HITL** (cần người quyết hoặc thao tác ngoài code) hoặc **AFK** (agent làm và merge được), "chặn bởi" và tiêu chí chấp nhận. Không đăng issue lên tracker nào.
- Local skill `tdd`: trong mỗi slice, test đầu tiên là **tracer bullet**, sau đó từng hành vi nhỏ; phần SQL, khóa, ràng buộc kiểm trên PostgreSQL thật.
- Local agent: hai agent đọc song song ngày 2026-10-06 (backend: dashboard, bảng cấu hình theo vật tư, người nhận, ràng buộc bảng tin; frontend: cấu trúc trang Dashboard, phân quyền, hộp thoại ngưỡng, kiểu dáng, e2e).

## Mục Tiêu

Hiện tab "Tổng quan" của Dashboard chỉ cho biết **ai** nhập bao nhiêu phiếu trong tuần. Admin và Manager chưa biết **vật tư nào** đã có giá mới, vật tư nào chưa, và mỗi vật tư được cập nhật bao nhiêu lần. Mục đích cuối cùng (đã chốt): **nhắc người nhập nhập cho đủ giá**.

1. **Bảng "Độ mới của giá theo vật tư"** trong tab Tổng quan, đồng bộ với bộ chọn tuần có sẵn: mỗi dòng một vật tư với số lần cập nhật, số nhà cung cấp, ngày nhận giá gần nhất, số ngày chưa có giá mới và trạng thái.
2. **Danh sách theo dõi và chu kỳ kỳ vọng theo vật tư**, để "chưa cập nhật" có nghĩa: 60% vật tư trên dev chưa từng có giá nên nếu không có danh sách theo dõi thì bảng toàn dòng "chưa cập nhật" vô nghĩa. Mặc định tính từ dữ liệu thật; quản lý chỉnh được từng vật tư.
3. **Nhắc qua Telegram** (đề xuất, chờ xác nhận ở Q7 và Q8) gửi cho Manager và cho những User gần đây đã nhập vật tư đó, khi vật tư quá hạn chưa có giá mới.

## Ngoài Scope

- Xuất Excel của bảng, so sánh xu hướng tuần này với tuần trước (đã chốt: không cần, câu trả lời 6).
- Quyền mới (đã chốt Phương án A: dùng lại `price_alerts.manage`).
- Loại ngày lễ và Tết khỏi ngày làm việc: giữ như 1C (QĐ-11, backlog); `working_days.py` chỉ loại thứ Bảy và Chủ nhật.
- Tự động đề xuất đưa vật tư mới vào danh sách theo dõi (chỉ làm tay qua trang cấu hình; xem rủi ro RF-8).
- Công tắc nhắc riêng trong tùy chọn cá nhân (đề xuất không làm, Q10).

## Căn Cứ Đã Xác Minh (2026-10-06)

Đọc trực tiếp code và dữ liệu ngày 2026-10-06. Chỗ nào lệch với giả định ban đầu được ghi rõ.

**Backend:**

| Mục | Hiện trạng |
|---|---|
| Tuần của Dashboard | `get_weekly_entry_activity` chuẩn hóa `week_start` về thứ Hai (`value - timedelta(days=value.weekday())`), mặc định là hôm nay theo `Asia/Ho_Chi_Minh`; khoảng `[thứ Hai 00:00 +07, thứ Hai kế 00:00)`, `week_end = thứ Hai + 6` |
| **Lệch cần lưu ý** | Bảng tuần hiện tại lọc theo `Quote.created_at` (**giờ nhập**), không phải `received_date`, và không kiểm `confirmed_at IS NOT NULL`. Các truy vấn khác của Dashboard (`_build_common_filters`) lọc theo `QuoteVersion.received_date` và có đủ ba điều kiện: `status = 'confirmed'`, `confirmed_at IS NOT NULL`, `Quote.cancelled_at IS NULL` |
| Route Dashboard | `GET /api/v1/dashboard/quotify/...` (entry-kpis, price-trends, weekly-entry-activity), quyền `dashboard.read` (role `user` có quyền này) |
| Kiểm thử Dashboard | `tests/test_quotify_dashboard_service.py`, `tests/test_quotify_dashboard_api.py` dùng `FakeDbSession` và kiểm chuỗi SQL biên dịch; **không có** test PostgreSQL thật cho Dashboard |
| Bảng `materials` | `id, code, name, material_type_id, status ('active' hoặc 'inactive'), note`; chưa có cột theo dõi hay chu kỳ |
| Mẫu cấu hình theo vật tư | `PriceAlertMaterialThreshold` (khóa chính `material_id`, `updated_by_id`, CHECK). **Không mở rộng bảng này**: ba cột ngưỡng bị ép "cùng null hoặc cùng có giá trị" và `list_materials` nối mọi vật tư với nó. Dùng bảng mới |
| API cấu hình theo vật tư | `/price-alert-settings/materials` (GET danh sách `limit`, `offset`, `search`; `PUT/DELETE /{material_id}`), ghi bằng `require_permission("price_alerts.manage")`, audit qua `AuditLogService.log_event` rồi `commit` |
| Quyền | `price_alerts.manage` và `price_alerts.receive_all` gán cho `manager` và `admin` (migration `20261004_1300`) |
| Head Alembic | Một head, hiện là `20261006_0900`; `tests/test_alembic_heads.py` bắt buộc một head |
| Người nhận | `resolve_recipients(kind)` chỉ có `change` và `anomaly`, nhận **một** vật tư. Các nhóm: `admin` (chỉ khi `admin_receive_all`), `manager` (có `price_alerts.receive_all`), `staff` (`quotes.created_by_id` của phiếu đã chốt, chưa hủy, có dòng vật tư đó với `received_date` trong `staff_lookback_days` = 90). Phải có user hoạt động, `TelegramAccount` hoạt động, không phải tài khoản seed; `user_alert_preferences.is_enabled = false` thì không nhận; `PRICE_ALERT_RECIPIENT_EMAILS` giới hạn pilot |
| Bảng `price_alert_messages` | Ràng buộc chặn `kind='freshness'`: **đúng hai** cái, `ck_price_alert_messages_kind` (`kind IN ('change','anomaly','digest')`) và `ck_price_alert_messages_material_required` (`kind = 'digest' OR material_id IS NOT NULL`). `scan_run_id` và `material_id` nullable; `audience`, `digest_kind` nullable; `kind` là `String(10)` nên `'freshness'` (9 ký tự) vừa |
| Idempotency | `uq_price_alert_messages_unit (user_id, material_id, scan_run_id, kind)` **không** bảo vệ khi `material_id` và `scan_run_id` null (NULL khác nhau), nên cần chỉ mục duy nhất một phần riêng |
| Mẫu cron bản tin | `PriceAlertDigestService.run_once`: trả `not_due` nếu chưa tới giờ, khóa `pg_try_advisory_xact_lock` (khóa quét `...004`, bản tin `...006`, nên khóa mới `...007`), `last_digest_local_date` trong `price_alert_scan_state` (một cột đã dùng cho bản tin, nên nhắc giá cần cột riêng), chèn tin `pending` bằng `on_conflict_do_nothing` |
| Sender | `_claim_one` lọc `kind.in_(("change","anomaly","digest"))`: **quên thêm `freshness` thì tin kẹt `pending` mãi**. `_build` rẽ nhánh theo kind; `PriceAlertMessageEvent` chỉ nối tới `price_alert_events`, nên nội dung nhắc giá cần bảng nối riêng |
| Tiêu thụ `kind` khác | `price_alert_replay`, `price_alert_review_service`, `price_alert_digest`, `_insert_summary` lọc theo `audience` hoặc `digest_kind`; tin nhắc giá để cả hai null thì không lọt vào |
| Ngày làm việc | `services/working_days.py`: `is_working_day` (thứ Hai đến thứ Sáu), `working_days_between(start, end)` đếm ngày làm việc trong `(start, end]`; không có hàm cộng ngày làm việc |
| Dọn dữ liệu | `PriceAlertMaintenanceService.cleanup` xóa tin quá 180 ngày bất kể kind (bảng nối dùng `ON DELETE CASCADE`) |

**Frontend (từ agent khảo sát):**

| Mục | Hiện trạng |
|---|---|
| `DashboardPage.vue` | `Tabs` lazy; tab Tổng quan có hero và `dashboard-page__weekly-panel`: `DatePicker` `selectedWeek`, `Select` người dùng, nút "Lọc" và "Xóa lọc", thẻ thống kê, biểu đồ theo người, `DataTable` (Người nhập, Số phiếu, Lần nhập gần nhất, Trạng thái) |
| Composable | `useDashboardPage`; `applyWeeklyEntryFilters`, `resetWeeklyEntryFilters`, `bootstrap` là nơi gọi tải dữ liệu theo tuần; `dashboard.page.spec.ts` mock toàn bộ `useDashboardPage` và stub PrimeVue |
| Danh mục vật tư | Đã có trong lookup, kèm `materialTypeId`, `materialTypeName`, `materialTypeCode` (dùng cho bộ lọc theo loại) |
| Phân quyền | `permissionStore.can('price_alerts.manage')` đã dùng ở `/price-alert-settings` |
| Trang cấu hình | `PriceAlertSettingsPage` + `usePriceAlertMaterialThresholds.ts` (schema zod, hộp thoại sửa ngưỡng, cột "Thao tác" dạng nút icon); specs `price-alert-settings.page.spec.ts`, `usePriceAlertMaterialThresholds.spec.ts`, `price-alert-settings.mappers.spec.ts` |
| Kiểu dáng | Không `<style>` trong `.vue`; SCSS toàn cục đăng ký ở `styles/main.scss`; `npm run lint` chạy `check-no-scoped-style.mjs`; token `--app-*`; mobile bắt buộc, mẫu thẻ mobile là `QuotesPage` (`.quotes-page__table-wrapper` và `.quotes-page__mobile-list`, mốc 1280 và 768); dòng cảnh báo mẫu `.dashboard-page__weekly-row--warning` |
| Kiểm thử | vitest đơn vị; Playwright e2e giả API bằng `page.route` và cookie `quotify_logged_in` |

**Bài học từ 1B và 1C ảnh hưởng 1D:**
- Tài khoản seed (`AUTH_SEED_ADMIN_EMAIL`) không bao giờ nhận tin hay sinh tin; phiếu thử phải do tài khoản không phải seed nhập.
- Mọi `UPDATE` hoặc `DELETE` hàng loạt cần test có ít nhất một hàng không bị ảnh hưởng (hotfix `9efc03a`).
- Sau `resetForm` của vee-validate lỗi không hiện lần lưu sau: dùng `setValues(values, false)` và `setErrors({})`.
- Khi tham số hóa một hàm dùng chung phải `grep` mọi nơi gọi, kể cả callback.

## Định Nghĩa Nghiệp Vụ

| Thuật ngữ | Định nghĩa |
|---|---|
| Phiếu hợp lệ | Phiên bản báo giá (`quote_versions`) có `status = 'confirmed'`, `confirmed_at` khác null, và phiếu cha `quotes.cancelled_at` là null |
| **Một lần cập nhật** của vật tư X trong tuần W | Một phiên bản **phiếu hợp lệ** có ít nhất một dòng của X và `received_date` nằm trong tuần W. Đếm **số phiên bản khác nhau**, không đếm dòng (đã chốt, câu trả lời 3) |
| Tuần W | Thứ Hai đến Chủ nhật theo giờ Việt Nam, chọn bằng bộ chọn tuần có sẵn (đã chốt, câu trả lời 4) |
| Mốc xét `as_of` | `min(hôm nay theo giờ Việt Nam, chủ nhật của tuần W)`. Tuần quá khứ xét tại Chủ nhật của tuần đó, nên xem lại tuần cũ ra đúng trạng thái lúc ấy |
| Ngày nhận gần nhất | `max(received_date)` của mọi phiếu hợp lệ có dòng X và `received_date <= as_of` (toàn thời gian, không giới hạn trong tuần) |
| Tuổi (số ngày chưa có giá) | `as_of - ngày nhận gần nhất`, tính theo ngày lịch; không âm |
| Theo dõi | Vật tư có cờ `is_watched = true` trong bảng cấu hình mới, kèm `expected_interval_days` (chu kỳ kỳ vọng, 1 đến 365 ngày) |
| Trạng thái dòng | `updated` (Đã cập nhật): có ít nhất một lần cập nhật trong tuần. `on_time` (Đúng hạn): không có lần nào trong tuần, tuổi ≤ chu kỳ. `overdue` (Quá hạn): tuổi > chu kỳ. `never` (Chưa có giá): đã theo dõi nhưng chưa từng có giá tới `as_of` |
| Dòng hiển thị | Vật tư **đang hoạt động** (`materials.status = 'active'`) mà (đang theo dõi) hoặc (có ít nhất một lần cập nhật trong tuần). Vật tư không theo dõi và không có cập nhật thì không hiện (đó là phần "nhiễu" 60% chưa từng có giá) |
| Hạn nhắc | `due_date = ngày nhận gần nhất + chu kỳ`; quá hạn khi hôm nay > `due_date`. `k` = số ngày làm việc trong `(due_date, hôm nay]` |

**Cách tính chu kỳ mặc định** (đồng ý "theo giá trị trung bình của dữ liệu thật", câu trả lời 2): với mỗi vật tư lấy các **ngày có cập nhật khác nhau** trong 90 ngày gần nhất; khoảng cách trung bình giữa hai ngày liên tiếp (`(ngày cuối - ngày đầu) / (số ngày - 1)`):

| Khoảng cách trung bình | Chu kỳ gán |
|---|---|
| ≤ 5 ngày | 7 ngày |
| > 5 và ≤ 12 ngày | 14 ngày |
| > 12 ngày | 30 ngày |

Danh sách theo dõi mặc định: vật tư đang hoạt động có **từ 3 ngày cập nhật trở lên** trong 90 ngày. Trên dev: 38 vật tư, chia 17 (7 ngày), 19 (14 ngày), 2 (30 ngày) (Phụ lục A). Các mốc cố ý thô; trưởng phòng siết chặt riêng cho vật tư chủ lực (ví dụ Ngô hạt cập nhật trung bình 1,5 ngày một lần nhưng mặc định 7 ngày) ngay trên trang cấu hình.

## Nguyên Tắc Bắt Buộc

Như 1B và 1C, thêm:
1. Mọi slice có commit riêng, build và test không hỏng; production không đổi hành vi nhìn thấy được cho tới Slice 8.
2. Mọi migration additive, viết tay, không `--autogenerate`, không `downgrade` trên production.
3. Nhắc Telegram mặc định **tắt** (`freshness_enabled = false`); bật là một bước HITL riêng sau khi quản lý đã duyệt danh sách theo dõi.
4. Frontend tuân thủ `AGENTS.md` và `memory-bank/projectRules.md` (không `<style>`, mobile, nhãn tiếng Việt cố định, không hiện `detail` của server); xác minh bằng trình duyệt thật hoặc e2e.
5. Test PostgreSQL thật cho mọi SQL tổng hợp và ràng buộc; dữ liệu thử phải ghi nhận đã quét (`record_scanned_version`) khi chạm engine 1B và có cột hoặc hàng không bị ảnh hưởng cho thao tác hàng loạt.
6. Không thêm khóa metadata audit chứa `token`, `secret`, `session`.

## Quyết Định Kỹ Thuật Cho 1D

| Mã | Chủ đề | Quyết định |
|---|---|---|
| F1 | **Mốc thời gian của "cập nhật"** | Dùng `QuoteVersion.received_date` (ngày nhận báo giá), **không** dùng `created_at` như bảng tuần hiện tại. Lý do: độ mới của giá là chuyện giá có hiệu lực ngày nào; nhập bù hoặc nhập import cũ (`confirmed_at` là lúc import, `received_date` là ngày cũ) không bị tính nhầm vào tuần này; khớp biểu đồ giá theo ngày nhận và tiêu chí của người nhận tin 1B. **Hệ quả cần ghi trên giao diện:** hai bảng cùng tab có thể lệch số khi phiếu nhập trễ (bảng trên đếm theo giờ nhập). Chú thích dưới bảng: "Tính theo ngày nhận báo giá" |
| F2 | Bản sửa phiếu | Bản cũ chuyển `superseded` nên không còn được đếm; bản mới được đếm theo `received_date` của nó. Sửa phiếu không đếm đôi |
| F3 | Bảng cấu hình theo dõi | Bảng mới `price_freshness_materials(material_id PK FK materials ON DELETE CASCADE, is_watched bool not null, expected_interval_days int not null CHECK 1..365, updated_by_id FK users ON DELETE SET NULL, created_at, updated_at)`. Không có hàng nghĩa là không theo dõi. Bảng ngưỡng 1B giữ nguyên |
| F4 | API đọc bảng | `GET /api/v1/dashboard/quotify/material-freshness?week_start=YYYY-MM-DD`, quyền **`price_alerts.manage`** (Phương án A, câu trả lời 5). Trả `{week_start, week_end, as_of_date, summary, items}` không phân trang (dưới 200 dòng, vì cả hệ thống 95 đến 122 vật tư). `summary`: `watched_count`, `updated_count`, `on_time_count`, `overdue_count` (gồm `never`) tính **chỉ trên vật tư đang theo dõi** nên cộng đúng bằng `watched_count`, thêm `unwatched_updated_count` |
| F5 | Mỗi `item` | `material_id, material_code, material_name, material_type_id, material_type_name, is_watched, expected_interval_days (null nếu không theo dõi), update_count, supplier_count, last_received_date (null nếu chưa có), age_days (null nếu chưa có), status, last_enterer_id, last_enterer_label` (người tạo phiếu `quotes.created_by_id` của phiên bản gần nhất, cùng quy tắc xác định "người nhập" của 1B; hiển thị trên web phụ thuộc Q9) |
| F6 | API cấu hình | Mở rộng mỗi mục của `GET /price-alert-settings/materials` thêm `freshness: {is_watched, expected_interval_days} \| null`; thêm `PUT /price-alert-settings/materials/{material_id}/freshness` (`{is_watched, expected_interval_days}`) và `DELETE` cùng đường dẫn (xóa hàng, idempotent). **Tách khỏi endpoint ngưỡng** để `DELETE` của ngưỡng không xóa cấu hình theo dõi. Quyền `price_alerts.manage`; audit `price_alerts.freshness_updated` (có `changes[]`); 404 khi không có vật tư, 422 khi chu kỳ ngoài 1 đến 365 |
| F7 | Nạp danh sách mặc định | **Không** nạp trong migration (dữ liệu production bị ảnh hưởng bởi import cũ). Lệnh `python -m app.price_freshness_seed` mặc định `--dry-run` (in danh sách đề xuất và xuất CSV để trưởng phòng duyệt), `--apply` chỉ chèn hàng **chưa tồn tại** (`ON CONFLICT DO NOTHING`), không bao giờ ghi đè hàng quản lý đã sửa hoặc đã tắt |
| F8 | Giao diện bảng | Component `MaterialFreshnessTable.vue` (kèm composable, api, mappers, types riêng) gắn trong tab Tổng quan **dưới** panel theo tuần, chỉ hiện khi `permissionStore.can('price_alerts.manage')`; gọi tải lại trong `applyWeeklyEntryFilters`, `resetWeeklyEntryFilters`, `bootstrap`; bộ lọc cục bộ: trạng thái và loại vật tư (lọc phía client vì dưới 200 dòng); mặc định sắp xếp: Quá hạn trước, rồi theo tuổi giảm dần; thẻ trạng thái màu (`Tag` severity success, info hoặc warning, danger); dòng quá hạn tô nổi như `.dashboard-page__weekly-row--warning`; khung mobile dạng thẻ như QuotesPage |
| F9 | Giao diện cấu hình | Trong bảng "Ngưỡng theo vật tư" của `/price-alert-settings` thêm hai cột "Theo dõi" và "Chu kỳ (ngày)" và nút icon thứ hai ở cột "Thao tác" mở hộp thoại nhỏ (`ToggleSwitch` + `InputNumber` + "Bỏ cấu hình"), lưu riêng bằng F6. Cập nhật schema zod, mapper và ba spec liên quan |
| F10 | Loại tin nhắc | Tin mới `kind = 'freshness'` (không dùng lại `kind = 'digest'` để khỏi nới CHECK `digest_kind` và khỏi lẫn vào ba loại digest có sẵn). Migration: mở rộng `ck_price_alert_messages_kind`, đổi `ck_price_alert_messages_material_required` thành `kind IN ('digest','freshness') OR material_id IS NOT NULL`, chỉ mục duy nhất một phần `uq_price_alert_messages_freshness (user_id, local_date) WHERE kind = 'freshness'` (một tin mỗi người mỗi ngày làm khóa idempotent), bảng nối `price_alert_message_materials(message_id FK CASCADE, material_id FK CASCADE, overdue_days int, interval_days int, last_received_date date, last_enterer_id FK users SET NULL, PK (message_id, material_id))` để **nội dung được chụp lúc xếp tin** và sender dựng tin xác định |
| F11 | Người nhận nhắc | Hàm mới `resolve_freshness_recipients` (nhận **danh sách** vật tư quá hạn, trả `người nhận -> các vật tư`), dùng chung điều kiện hợp lệ của 1B: user hoạt động, `TelegramAccount` hoạt động, không phải tài khoản seed, `user_alert_preferences.is_enabled` khác false, giới hạn pilot. **Manager** (có `price_alerts.receive_all`) nhận mọi vật tư đến hạn nhắc; **User** nhận vật tư mà họ là người tạo phiếu (`quotes.created_by_id`, như `_staff_ids` của 1B) có phiên bản hợp lệ chứa vật tư đó với `received_date` trong `staff_lookback_days` gần nhất (một truy vấn theo lô, không gọi theo từng vật tư); **admin** chỉ khi `admin_receive_all`. Người thuộc nhiều nhóm nhận **một** tin gộp. Mức tối thiểu `min_level` không áp dụng (chỉ dành cho biến động giá) |
| F12 | Lịch và nhịp nhắc (**đề xuất, chờ xác nhận, Q7**) | Cron `send_price_alert_freshness` chạy mỗi giờ phút 20 (sau cron bản tin phút 10), giờ Việt Nam; chỉ làm việc vào **ngày làm việc** khi giờ địa phương ≥ `freshness_hour_local` (mặc định 9) và `last_freshness_local_date` chưa phải hôm nay (nên worker tắt lúc 09:00 vẫn gửi bù trong ngày). Nhịp **không lưu trạng thái**: vật tư quá hạn được nhắc khi `k = 1`, rồi mỗi 3 ngày làm việc (`k = 1, 4, 7, 10, 13`), tối đa 5 lần (hằng số trong code); cập nhật giá sẽ tự đặt lại chuỗi. Không gửi khi không có gì đến hạn nhắc. Khóa advisory mới `7_620_261_007` |
| F13 | Dạng tin (**đề xuất, chờ xác nhận, Q8**) | **Tin riêng**, không gộp vào bản tin 08:00 (bản tin 08:00 chỉ gồm thay đổi mức Nhẹ và thường rỗng). HTML thuần, có âm báo, không nút; xem Phụ lục C |
| F14 | Cờ và cấu hình | Thêm `price_alert_settings.freshness_enabled` (mặc định false) và `freshness_hour_local` (mặc định 9, CHECK 0 đến 23); `price_alert_scan_state.last_freshness_local_date` (date, nullable). Cron chạy khi **cả** `is_enabled` (công tắc tổng) **và** `freshness_enabled` bật, nên tắt công tắc tổng vẫn dừng được mọi thứ. Nhịp (3 ngày) và trần (5 lần) là hằng số, đổi bằng code nếu chốt khác. `PUT /price-alert-settings` nhận thêm hai trường **tùy chọn** (bỏ qua nghĩa là giữ nguyên, để client cũ không bị gãy) |
| F15 | Quan sát | Hai gauge tính khi scrape (cache 15 giây như 1C): `quotify_price_freshness_watched_materials`, `quotify_price_freshness_overdue_materials` (tại hôm nay). Không thêm luật cảnh báo mới (luật "tin `pending` quá 10 phút" đã bao cả loại mới). Mở rộng `check-price-alert-readiness.sh` kiểm bảng và cột mới; runbook mục 15 |
| F16 | Phát hành | **Một đợt** như 1C: deploy khi xong Slice 1 đến 7; `freshness_enabled` vẫn **tắt**; quản lý dùng bảng web ít nhất một tuần và chỉnh danh sách theo dõi; sau đó bật nhắc trong nhóm pilot (còn `PRICE_ALERT_RECIPIENT_EMAILS`), rồi mở rộng cùng thời điểm bỏ giới hạn pilot |

## Câu Hỏi Đã Chốt (2026-10-06)

| Mã | Câu hỏi | Kết quả chốt |
|---|---|---|
| Q1 | Mục tiêu của bảng | **Nhắc người nhập nhập cho đủ giá**; cảnh báo Telegram cho Manager và cho User gần đây đang nhập vật tư đó |
| Q2 | Danh sách theo dõi và chu kỳ kỳ vọng | Đồng ý như đề xuất; cấu hình mặc định theo giá trị trung bình của dữ liệu thật (F7, bảng chu kỳ ở trên) |
| Q3 | "Số lần cập nhật" | Số **phiên bản phiếu hợp lệ** chứa vật tư trong kỳ, không đếm dòng |
| Q4 | Kỳ xem | Đồng bộ theo bộ chọn tuần hiện có |
| Q5 | Phạm vi quyền (diễn đạt lại cho dễ hiểu: dùng lại quyền có sẵn hay thêm quyền mới) | **Phương án A**: dùng lại `price_alerts.manage` cho cả xem bảng mới lẫn sửa danh sách theo dõi (đúng Admin và Manager, không migration quyền) |
| Q6 | Phụ trợ (xuất Excel, xu hướng so tuần trước) | Không cần |

## Câu Hỏi Còn Mở (đề xuất, chờ xác nhận)

| Mã | Câu hỏi | Đề xuất mặc định (đã ghi vào kế hoạch) | Nếu đổi thì sao |
|---|---|---|---|
| Q7 | **Giờ gửi và nhịp nhắc** | 09:00 ngày làm việc; nhắc khi vật tư vừa quá hạn rồi mỗi 3 ngày làm việc nếu vẫn chưa có giá, tối đa 5 lần | Nhắc hằng ngày: người nhận dễ tắt tin hoặc phớt lờ (mệt mỏi cảnh báo). Chỉ nhắc một lần: ít phiền nhưng dễ bị quên. Đổi giờ: sửa `freshness_hour_local` trên giao diện; đổi nhịp hoặc trần: một dòng code |
| Q8 | **Tin riêng hay gộp vào bản tin 08:00** | Tin riêng, vì bản tin 08:00 chỉ gồm thay đổi mức Nhẹ và thường rỗng (không gửi khi rỗng), gộp sẽ làm hai logic lệ thuộc nhau | Gộp: ít tin hơn mỗi sáng nhưng phải sửa lại bản tin 1C và nội dung thành hai phần |
| Q9 | **Cột "Người nhập gần nhất" trên bảng web** | Có (backend trả sẵn); nếu không có thì trưởng phòng thấy vật tư quá hạn mà không biết hỏi ai | Bỏ cột: gọn hơn, chỉ ẩn ở giao diện, không đổi backend |
| Q10 | **Công tắc riêng cho tin nhắc giá trong tùy chọn cá nhân** | Không; dùng chung công tắc `is_enabled` của thông báo giá | Có: thêm cột `user_alert_preferences` và một ô trong panel Hồ sơ (thêm một slice nhỏ) |

## Slice 0: Chuẩn Bị, Đo Baseline Và Duyệt Mốc Chu Kỳ Trên Dữ Liệu Production

**Loại:** HITL (chạy truy vấn chỉ đọc trên VPS và người duyệt) | **Chặn bởi:** không | **Cỡ:** nhỏ

### Mục tiêu

Biết trạng thái xuất phát của code và kiểm chứng các mốc chu kỳ (7, 14, 30 ngày; từ 3 ngày cập nhật trong 90 ngày) trên **dữ liệu thật của production** trước khi cố định chúng (dev có thêm dữ liệu import nên có thể lệch).

### Việc cần làm

1. Chạy baseline: `make backend-check` và `make frontend-check`; ghi các lỗi cũ (theo tên test và nhóm lỗi) vào `memory-bank/progress.md` và Phụ lục B.
2. Chạy hai truy vấn chỉ đọc ở Phụ lục B trên production (qua `docker compose exec -T postgres psql ...` trong `/opt/quotify`); ghi kết quả vào Phụ lục A cột "Production".
3. Trưởng phòng xem số vật tư đề xuất theo dõi và chu kỳ; nếu lệch lớn so với dev thì chỉnh mốc **trước** Slice 4.

### Tiêu chí chấp nhận

- [ ] Baseline được ghi lại, kể cả các test cũ đang lỗi.
- [ ] Phụ lục A có số liệu production; mốc chu kỳ được xác nhận hoặc chỉnh.

### Rollback

Không có thay đổi sản phẩm.

---

## Slice 1: Bảng Cấu Hình Theo Dõi Và API Đọc Độ Mới Của Giá (Tracer Backend)

**Loại:** AFK | **Chặn bởi:** Slice 0 (chỉ phần mốc chu kỳ; phần code làm song song được) | **Cỡ:** vừa

### Mục tiêu

Có một endpoint trả đúng, kiểm bằng PostgreSQL thật, bảng độ mới của giá theo vật tư cho một tuần; chưa có giao diện.

### Việc cần làm

1. Migration (nối sau head `20261006_0900`, số revision đặt theo ngày làm): tạo `price_freshness_materials` (F3). Model `PriceFreshnessMaterial` đăng ký trong `models/__init__.py`.
2. Service `quotify_material_freshness_service.py` (hoặc thêm vào service Dashboard nếu hợp hơn): ba truy vấn tổng hợp (đếm phiên bản khác nhau và số nhà cung cấp theo vật tư trong tuần theo `received_date`; ngày nhận gần nhất và người nhập gần nhất tới `as_of`; danh sách vật tư hoạt động nối cấu hình), rồi ghép trạng thái bằng **hàm thuần** `classify(update_count, is_watched, interval, age_days)`.
3. Schema `schemas/quotify_material_freshness.py` và route `GET /dashboard/quotify/material-freshness` (F4, F5), quyền `price_alerts.manage`, đăng ký trong `api/v1/router.py` theo mẫu route Dashboard hiện có.
4. Chuẩn hóa `week_start` về thứ Hai giống `get_weekly_entry_activity` (dùng chung hàm chuẩn hóa nếu có, không sao chép).

### Thứ tự test (tracer trước)

1. **Tracer (PostgreSQL thật, `tests/integration/test_material_freshness_db.py`):** vật tư X (theo dõi, chu kỳ 7) có hai phiếu hợp lệ trong tuần từ hai nhà cung cấp → `update_count = 2`, `supplier_count = 2`, trạng thái `updated`; vật tư Y (theo dõi, chu kỳ 14) lần cuối nhận giá cách 20 ngày → `overdue`, `age_days = 20`, `update_count = 0`; vật tư Z không theo dõi và không có cập nhật → không có trong `items`.
2. Một phiên bản có hai dòng cùng vật tư (hai kỳ giao hàng) → `update_count = 1` (đếm phiên bản, không đếm dòng; Q3).
3. Loại trừ: phiên bản `draft`, phiếu đã hủy, phiên bản `superseded` sau khi sửa phiếu (chỉ bản mới được đếm, không đếm đôi, F2), phiên bản `confirmed_at` null.
4. Biên tuần theo `received_date`: thứ Hai và Chủ nhật tính vào tuần; thứ Hai kế tiếp không; phiếu nhập muộn (`created_at` ở tuần sau, `received_date` trong tuần) vẫn tính vào tuần nhận (F1).
5. Tuần quá khứ: `as_of = chủ nhật`, phiếu có `received_date` sau chủ nhật không được tính làm "ngày nhận gần nhất"; tuổi tính từ chủ nhật. Tuần hiện tại: `as_of = hôm nay`; `received_date` ở tương lai không làm tuổi âm.
6. `never`: vật tư theo dõi chưa từng có giá → `last_received_date` và `age_days` null.
7. Vật tư `inactive` không hiện dù đang theo dõi; vật tư không theo dõi nhưng có cập nhật hiện với `is_watched = false`, `expected_interval_days = null`, trạng thái `updated`.
8. `summary`: `watched_count = updated_count + on_time_count + overdue_count`; `unwatched_updated_count` đúng.
9. Người nhập gần nhất: người tạo phiếu (`quotes.created_by_id`) của phiên bản có `received_date` lớn nhất; hai phiên bản cùng ngày: quyết định xác định theo `confirmed_at` giảm dần.
10. API (kiểu `FakeDbSession` có sẵn của Dashboard): 403 với người chỉ có `dashboard.read` (role `user`), 200 với `price_alerts.manage`; `week_start` là thứ Tư → chuẩn hóa về thứ Hai; ngày sai định dạng → 422.
11. Kiểm đột biến thủ công: bỏ điều kiện `cancelled_at IS NULL`, bỏ lọc `status = 'confirmed'`, đổi `received_date` thành `created_at` → test tương ứng phải đỏ.

### Tiêu chí chấp nhận

- [ ] Tracer và các test trên đều xanh trên PostgreSQL thật; test đột biến phát hiện.
- [ ] `tests/test_alembic_heads.py` xanh (một head).
- [ ] Baseline không xấu hơn.

### Rollback

Gỡ route hoặc quay về code cũ; bảng mới là additive và không ai đọc. Không `downgrade` migration.

---

## Slice 2: Bảng "Độ Mới Của Giá Theo Vật Tư" Trên Tab Tổng Quan (Frontend)

**Loại:** AFK | **Chặn bởi:** Slice 1 | **Cỡ:** vừa

### Mục tiêu

Admin và Manager mở Dashboard, chọn tuần và thấy bảng độ mới của giá, đồng bộ với bộ chọn tuần có sẵn; người khác không thấy bảng.

### Việc cần làm

1. `types/material-freshness.ts` (`Dto` snake_case, `Domain` camelCase), `api/material-freshness.api.ts` (`apiRequest` với `accessToken`), `api/material-freshness.mappers.ts` (nhãn trạng thái tiếng Việt: "Đã cập nhật", "Đúng hạn", "Quá hạn", "Chưa có giá"; định dạng ngày `vi-VN` theo múi giờ cấu hình; mô tả tuổi "N ngày").
2. `composables/useMaterialFreshness.ts`: tải theo `weekStart`, trạng thái đang tải và lỗi (thông báo cố định, không dùng `detail` của server), lọc phía client theo trạng thái và loại vật tư, sắp xếp mặc định (F8). Chặn phản hồi cũ ghi đè phản hồi mới (bài học 1C).
3. `components/dashboard/MaterialFreshnessTable.vue`: thẻ tóm tắt (Đang theo dõi, Đã cập nhật, Đúng hạn, Quá hạn, ghi chú "k vật tư không theo dõi có cập nhật"), bộ lọc, `DataTable` (`responsive-layout="scroll"`) với cột Vật tư, Loại, Số lần, Số NCC, Ngày nhận gần nhất, Số ngày, Chu kỳ, Trạng thái, và cột Người nhập gần nhất nếu Q9 giữ; khung mobile dạng thẻ; chú thích "Tính theo ngày nhận báo giá. Quản lý danh sách theo dõi ở Cấu hình thông báo giá" kèm liên kết.
4. Gắn vào `DashboardPage.vue` dưới panel theo tuần, bọc `v-if="permissionStore.can('price_alerts.manage')"`; gọi tải lại trong `applyWeeklyEntryFilters`, `resetWeeklyEntryFilters`, `bootstrap` của `useDashboardPage`.
5. SCSS toàn cục `styles/pages/_dashboard-freshness.scss` (đăng ký trong `main.scss`), token `--app-*`, dòng quá hạn tô nổi như dòng cảnh báo có sẵn; mốc 1280 và 768.
6. Tùy chọn (nếu gọn): thêm `freshness?: {status, materialTypeId}` (trường **tùy chọn**) vào snapshot của `dashboard-view.store` để giữ bộ lọc khi đổi tab.

### Thứ tự test (tracer trước)

1. **Tracer (vitest):** mapper chuyển DTO mẫu thành nhãn tiếng Việt đúng cho cả bốn trạng thái và ngày; composable gọi API với `week_start` đã chọn.
2. Composable: lọc theo trạng thái và loại; sắp xếp Quá hạn trước theo tuổi giảm dần; lỗi hiện thông báo cố định; phản hồi cũ không ghi đè phản hồi mới.
3. Component: không có quyền → không render; có quyền → render; bốn thẻ tóm tắt và dòng `never` hiển thị "Chưa có giá"; trạng thái rỗng.
4. `dashboard.page.spec.ts`: stub component con; xác nhận gọi tải lại khi bấm "Lọc" và "Xóa lọc" (bảng đi theo tuần).
5. e2e Playwright giả API (`page.route`, `quotify_logged_in`): Admin thấy bảng; người không có `price_alerts.manage` không thấy; đổi tuần gọi lại API với `week_start` mới; khung mobile 390×844 hiện thẻ và không cuộn ngang trang; chụp ảnh màn hình và **xem bằng mắt** (bài học 1C: cột thao tác bị che ở 1280 px).

### Tiêu chí chấp nhận

- [ ] Bảng đúng theo tuần đã chọn; ẩn với người không có quyền; tối ưu mobile.
- [ ] `make frontend-check` không xấu hơn baseline (so theo tên test); không có `<style>`.
- [ ] Xem bằng trình duyệt thật hoặc ảnh e2e và sửa các lỗi bố cục thấy được.

### Rollback

Gỡ component khỏi `DashboardPage.vue`; backend không đổi.

---

## Slice 3: Sửa Danh Sách Theo Dõi Trên Trang Cấu Hình Thông Báo Giá (Backend Và Frontend)

**Loại:** AFK | **Chặn bởi:** Slice 1 | **Cỡ:** vừa

### Mục tiêu

Quản lý bật hoặc tắt theo dõi và đặt chu kỳ riêng cho từng vật tư ngay trên `/price-alert-settings`; thay đổi có audit và hiện ngay trong bảng độ mới của giá.

### Việc cần làm

1. Backend: mở rộng `list_materials` (nối thêm `price_freshness_materials`, thêm trường `freshness`), `set_freshness` bằng `pg_insert ... on_conflict_do_update`, `clear_freshness` idempotent; route `PUT` và `DELETE` `/price-alert-settings/materials/{material_id}/freshness` (F6); audit `price_alerts.freshness_updated` có `changes[]` (giá trị cũ và mới) rồi `commit`.
2. Frontend: cập nhật `types`, `mappers`, `api`, `usePriceAlertMaterialThresholds.ts` (schema zod chu kỳ nguyên 1 đến 365 khi đang theo dõi; lỗi tiếng Việt), `PriceAlertSettingsPage.vue`: hai cột "Theo dõi" (`Tag` Có hoặc Không) và "Chu kỳ (ngày)", nút icon thứ hai ở cột "Thao tác" mở hộp thoại nhỏ (`ToggleSwitch`, `InputNumber locale="vi-VN"`, "Bỏ cấu hình"); dùng `setValues(values, false)` và `setErrors({})` thay cho `resetForm`.
3. Nhãn nhật ký: thêm `price_alerts.freshness_updated` vào `audit-logs.mappers.ts` và bộ lọc `AuditLogsPage.vue`.

### Thứ tự test (tracer trước)

1. **Tracer (PostgreSQL thật):** `PUT` đặt `is_watched = true`, chu kỳ 14 cho một vật tư → bản ghi được lưu, `GET` danh sách trả đúng `freshness`, audit có `changes[]`.
2. Chu kỳ 0 hoặc 366 → 422; vật tư không tồn tại → 404; người không có `price_alerts.manage` → 403.
3. `PUT` lần hai đổi chu kỳ ghi đè đúng hàng (không tạo hàng thứ hai); `DELETE` xóa hàng và gọi lại vẫn 200; **ngưỡng của vật tư đó không bị ảnh hưởng** khi `DELETE` freshness và ngược lại (có hàng đối chứng, bài học hotfix `9efc03a`).
4. Tìm kiếm và phân trang của danh sách vẫn đúng khi nối bảng mới (không nhân đôi dòng).
5. Frontend (vitest): schema zod, mapper, composable lưu thành công và lỗi 409 hoặc 422 hiện thông báo cố định, đóng hộp thoại sau khi lưu; cập nhật ba spec hiện có (`price-alert-settings.page.spec.ts`, `usePriceAlertMaterialThresholds.spec.ts`, `price-alert-settings.mappers.spec.ts`).
6. e2e Playwright giả API: mở hộp thoại, bật theo dõi, lưu, thấy cột đổi; khung mobile.

### Tiêu chí chấp nhận

- [ ] Sửa và bỏ cấu hình hoạt động, có audit, không ảnh hưởng ngưỡng.
- [ ] Spec cũ cập nhật, baseline không xấu hơn; xem bằng trình duyệt thật hoặc ảnh e2e.

### Rollback

Gỡ route và cột giao diện; bảng cấu hình còn nguyên dữ liệu nhưng không ai đọc.

---

## Slice 4: Lệnh Nạp Danh Sách Theo Dõi Mặc Định Từ Dữ Liệu Thật

**Loại:** AFK (code và test) rồi HITL (chạy thật trên production lúc deploy) | **Chặn bởi:** Slice 1 | **Cỡ:** nhỏ

### Mục tiêu

Quản lý không phải bật tay hàng chục vật tư; có danh sách đề xuất để duyệt, nạp đúng một lần, không ghi đè lựa chọn của quản lý.

### Việc cần làm

1. `app/price_freshness_seed.py` (mẫu `app.price_alert_replay`): tính cho mỗi vật tư hoạt động số ngày cập nhật khác nhau và khoảng cách trung bình trong 90 ngày (hàm thuần `suggest_interval(mean_gap)` cho ba mốc ở mục "Định Nghĩa Nghiệp Vụ"); `--dry-run` (mặc định) in bảng và xuất CSV; `--apply` chèn bằng `ON CONFLICT DO NOTHING`; `--min-days` (mặc định 3) và `--window-days` (mặc định 90) để chỉnh theo kết quả Slice 0.
2. Ghi một dòng audit hệ thống khi `--apply`.

### Thứ tự test (tracer trước)

1. **Tracer (PostgreSQL thật):** vật tư có 4 ngày cập nhật cách đều 3 ngày → đề xuất chu kỳ 7; vật tư có 2 ngày cập nhật → không đề xuất; vật tư `inactive` → không đề xuất.
2. Hàm thuần theo biên: khoảng cách trung bình 5,0 → 7; 5,01 → 14; 12,0 → 14; 12,01 → 30.
3. `--dry-run` không ghi gì; `--apply` chèn đúng số hàng; **chạy lần hai không đổi gì**.
4. Hàng quản lý đã sửa (chu kỳ 3) hoặc đã tắt (`is_watched = false`) không bị ghi đè hay bật lại khi `--apply` lại (có hàng đối chứng).
5. Phiếu hủy, bản nháp, bản `superseded` không được tính vào số ngày cập nhật.

### Tiêu chí chấp nhận

- [ ] Lệnh idempotent, không ghi đè; dry-run xuất danh sách duyệt được.
- [ ] Chạy thử trên dev, danh sách khớp Phụ lục A (38 vật tư, 17, 19, 2).

### Rollback

Xóa các hàng đã nạp bằng SQL có điều kiện (`updated_by_id IS NULL AND created_at >= <thời điểm nạp>`); không ảnh hưởng gì khác.

---

## Slice 5: Động Cơ Nhắc Cập Nhật Giá Qua Telegram (Backend)

**Loại:** AFK (thử thật với Telegram là HITL) | **Chặn bởi:** Slice 1 (cấu hình theo dõi), Q7 và Q8 (đã có mặc định) | **Cỡ:** lớn

### Mục tiêu

Mỗi ngày làm việc, đúng giờ cấu hình, Manager và những User gần đây đã nhập vật tư quá hạn nhận **một** tin gom các vật tư của mình đến hạn nhắc; không gửi khi không có; không lặp; không phiền người ngoài danh sách.

### Việc cần làm

1. Migration (additive, viết tay): cột `price_alert_settings.freshness_enabled` (mặc định false) và `freshness_hour_local` (mặc định 9, CHECK 0 đến 23); `price_alert_scan_state.last_freshness_local_date`; mở rộng `ck_price_alert_messages_kind` và `ck_price_alert_messages_material_required`; chỉ mục duy nhất một phần `uq_price_alert_messages_freshness`; bảng nối `price_alert_message_materials` (F10, F14).
2. `services/price_freshness_reminder.py`: truy vấn vật tư đang theo dõi, hoạt động, quá hạn tại hôm nay (dùng lại truy vấn của Slice 1); hàm thuần `reminder_due(k)` (nhịp F12); gọi `resolve_freshness_recipients` (F11, thêm vào `price_alert_recipients.py`); chèn tin `pending` kèm hàng bảng nối bằng `on_conflict_do_nothing`; đặt `last_freshness_local_date` trong cùng giao dịch với khóa advisory `7_620_261_007`.
3. `services/price_freshness_formatter.py` (hàm thuần): dựng tin (Phụ lục C), sắp xếp theo `tuổi / chu kỳ` giảm dần, tối đa 30 dòng rồi "và N vật tư nữa, xem trên web", thoát HTML.
4. `price_alert_sender.py`: thêm `freshness` vào `_claim_one`; nhánh dựng nội dung từ bảng nối trước nhánh digest dự phòng; nếu không còn dòng nào thì `_SkipError`/`_FailError("no_content")` giống các nhánh khác. Gửi có âm báo, không nút.
5. `worker.py`: hàm `send_price_alert_freshness` (trả sớm khi không `telegram_enabled`, không `is_enabled` hoặc không `freshness_enabled`), đăng ký trong `WorkerSettings.functions` và `cron(send_price_alert_freshness, minute=20, second=0)`.

### Thứ tự test (tracer trước)

1. **Tracer (PostgreSQL thật, mẫu `test_price_alert_digest_db.py`):** một Manager và một User (đã nhập vật tư A), hai vật tư quá hạn A và B (B do người khác nhập), chạy job lúc 09:20 thứ Ba → Manager có một tin với hai hàng bảng nối (A và B), User có một tin với một hàng (A), `last_freshness_local_date` là hôm nay.
2. Chạy lại cùng ngày: không tạo thêm tin (idempotent; chỉ mục duy nhất giữ ngay cả khi bỏ cột `last_freshness_local_date`).
3. Trước giờ cấu hình: `not_due`; worker tắt lúc 09:00 rồi bật lúc 11:30: gửi bù trong ngày.
4. Cuối tuần: không gửi; thứ Hai ngay sau thứ Sáu quá hạn: `k = 1` nên gửi.
5. Nhịp theo `reminder_due(k)`: `k = 1, 4, 7, 10, 13` gửi; `k = 2, 3, 5, 6, 14` không gửi; cập nhật giá đặt lại chuỗi (vật tư không còn quá hạn thì không có tin).
6. Không có vật tư đến hạn nhắc: không tạo tin.
7. Người nhận: người tắt `is_enabled`, tài khoản seed, user bị khóa hoặc chưa liên kết Telegram, người ngoài danh sách pilot, admin không bật `admin_receive_all`: không nhận. Người vừa là Manager vừa đã nhập vật tư: một tin duy nhất, hợp nhất danh sách.
8. Vật tư không theo dõi, vật tư `inactive`, phiếu hủy hoặc bản nháp của User: không gây tin hay làm User trở thành người nhận. `staff_lookback_days` hết hạn (nhập từ 100 ngày trước): User không nhận, Manager vẫn nhận.
9. `is_enabled = false` hoặc `freshness_enabled = false`: job không làm gì (hai test riêng).
10. Sender với transport giả: tin được nhận (`_claim_one` có `freshness`), nội dung đúng thứ tự, HTML được thoát, quá 30 dòng cắt đúng "và N vật tư nữa", đánh dấu `sent`; tin `freshness` **không** lọt vào truy vấn nguồn của bản tin 08:00, duyệt giá bất thường hay replay (có test dựng sẵn một tin `freshness` rồi chạy các luồng đó).
11. Formatter (hàm thuần): giới hạn dòng, thoát HTML, sắp xếp, không có tên vật tư rỗng.
12. Đăng ký cron: phút 20, múi giờ Việt Nam (test `next_cron`, mẫu `test_the_digest_cron_runs_every_hour_at_minute_ten_in_vietnam_time`).
13. Kiểm đột biến thủ công: bỏ điều kiện loại tài khoản seed, bỏ `WHERE` của một `UPDATE` hàng loạt nếu có, bỏ chỉ mục duy nhất → test tương ứng phải đỏ.

### Cách xác minh thật (HITL)

Trên dev, bật `freshness_enabled`, đặt `freshness_hour_local` về giờ hiện tại, tạo ngữ cảnh có một vật tư quá hạn do tài khoản không phải seed đã nhập; chờ cron phút 20; kiểm tin đến điện thoại (nội dung, thứ tự, liên kết, âm báo), Manager và User nhận khác nhau.

### Tiêu chí chấp nhận

- [ ] Tin thật đến điện thoại đúng nội dung và đúng người; không gửi khi rỗng.
- [ ] Idempotent, gửi bù trong ngày, nhịp theo `k` có test PostgreSQL thật.
- [ ] Không ảnh hưởng ba loại tin cũ; baseline không xấu hơn.

### Rollback

Đặt `freshness_enabled = false` (hiệu lực ở lần cron kế tiếp, tối đa một giờ) hoặc `is_enabled = false` (công tắc tổng). **Nếu phải quay về image cũ:** sender cũ không nhận loại `freshness` nên tin chưa gửi sẽ kẹt `pending` (làm kêu luật "tin pending quá 10 phút"); trước đó chạy `UPDATE price_alert_messages SET status = 'skipped', status_reason = 'rolled_back' WHERE kind = 'freshness' AND status = 'pending'`. Không `downgrade` migration.

---

## Slice 6: Công Tắc Và Giờ Nhắc Trên Trang Cấu Hình (Backend Và Frontend)

**Loại:** AFK | **Chặn bởi:** Slice 5 | **Cỡ:** nhỏ

### Mục tiêu

Quản lý bật hoặc tắt nhắc giá và đổi giờ gửi mà không cần SQL.

### Việc cần làm

1. Backend: `GET/PUT /price-alert-settings` trả và nhận thêm `freshness_enabled`, `freshness_hour_local` (**tùy chọn** khi PUT, bỏ qua là giữ nguyên); kiểm 0 đến 23; ghi audit `price_alerts.settings_updated` như hiện có.
2. Frontend: thẻ mới "Nhắc cập nhật giá" trên `/price-alert-settings` (công tắc, giờ gửi, ghi chú ngắn về nhịp "nhắc khi quá hạn rồi mỗi 3 ngày làm việc, tối đa 5 lần" và về việc người nhận chỉ là người đã bật Telegram), schema zod, nhãn audit (`freshness_enabled`, `freshness_hour_local`).
3. Cảnh báo trên giao diện: nhắc giá chỉ chạy khi công tắc tổng "Thông báo giá" đang bật.

### Thứ tự test (tracer trước)

1. **Tracer (PostgreSQL thật):** `PUT` với `freshness_enabled = true` và `freshness_hour_local = 10` → lưu đúng, `GET` trả đúng, audit có `changes[]`.
2. `PUT` không gửi hai trường → giữ nguyên giá trị cũ; giờ 24 → 422.
3. Frontend (vitest): schema, mapper nhãn, lưu thành công và lỗi; e2e Playwright giả API: bật, đổi giờ, lưu; khung mobile.

### Tiêu chí chấp nhận

- [ ] Bật, tắt, đổi giờ làm việc từ giao diện; client cũ không gãy.
- [ ] Xem bằng trình duyệt thật hoặc ảnh e2e; baseline không xấu hơn.

### Rollback

Gỡ thẻ giao diện; công tắc vẫn đặt được bằng SQL.

---

## Slice 7: Quan Sát, Tuân Thủ Và Runbook

**Loại:** AFK | **Chặn bởi:** Slice 5 | **Cỡ:** nhỏ

### Mục tiêu

Theo dõi được tính năng đang chạy và có hướng dẫn phát hành, quay lại, kiểm sau phát hành.

### Việc cần làm

1. Hai gauge của F15 trong `price_alert_metrics.py` (truy vấn đếm nhẹ, cache 15 giây, cô lập lỗi, chỉ phát khi `is_enabled`).
2. `scripts/compliance/check-price-alert-readiness.sh`: thêm kiểm bảng `price_freshness_materials`, cột `freshness_enabled` và head Alembic.
3. Runbook mục 15 (theo mục 14): sao lưu, build ba service, bảo trì, migrate hai migration, `up -d`, chạy `price_freshness_seed` dry-run rồi apply, kiểm sau deploy, bật nhắc theo bước, rollback (gồm câu lệnh `UPDATE` của Slice 5), truy vấn giám sát (tin `freshness` theo trạng thái, số vật tư theo dõi, số vật tư quá hạn).

### Thứ tự test (tracer trước)

1. **Tracer (PostgreSQL thật):** có 3 vật tư theo dõi, 1 quá hạn → gauge trả 3 và 1; không có cấu hình → 0.
2. Gauge không phát khi `is_enabled = false`; lỗi truy vấn không làm hỏng `/metrics`.
3. Script tuân thủ chạy xanh với DB mới migrate và đỏ khi thiếu bảng (kiểm trên dev).

### Tiêu chí chấp nhận

- [ ] `/metrics` có hai gauge mới đúng số; script tuân thủ kiểm được cấu hình mới.
- [ ] Runbook mục 15 đủ lệnh và có phần rollback.

### Rollback

Gỡ gauge và mục runbook; không ảnh hưởng chức năng.

---

## Slice 8: Phát Hành 1D Lên Production

**Loại:** HITL (thao tác trên VPS) | **Chặn bởi:** Slice 1 đến 7 (một đợt duy nhất) | **Cỡ:** nhỏ

### Mục tiêu

Đưa tính năng lên production an toàn, kèm kiểm bằng dữ liệu thật, rồi bật nhắc có kiểm soát.

### Việc cần làm

1. Theo runbook mục 15: backup, `git pull`, build `backend`, `worker`, `frontend` khi site còn chạy, bật chế độ bảo trì (`docker/nginx/maintenance.conf`), migrate (hai migration additive), tạo lại ba service, tắt bảo trì.
2. Chạy `price_freshness_seed` ở chế độ `--dry-run`; trưởng phòng duyệt danh sách và chu kỳ; chạy `--apply`.
3. Kiểm sau deploy: Admin và Manager thấy bảng ở tab Tổng quan, đổi tuần ra số hợp lý, đối chiếu một vật tư với dữ liệu phiếu thật; User thường **không** thấy bảng; trang cấu hình sửa được theo dõi; gauge ở `/metrics`.
4. **Giữ `freshness_enabled = false` ít nhất một tuần**: quản lý dùng bảng web, chỉnh danh sách theo dõi và chu kỳ cho sát thực tế.
5. Bật nhắc (HITL): đặt `freshness_enabled = true` (trong nhóm pilot nếu còn `PRICE_ALERT_RECIPIENT_EMAILS`); kiểm tin đầu tiên trên điện thoại thật; theo dõi tải tin tuần đầu.
6. Cập nhật runbook, `memory-bank/`, tài liệu này; chạy `agent-task-close.sh`.

### Tiêu chí chấp nhận

- [ ] Bảng chạy trên production bằng tài khoản người thật; chức năng cũ không đổi.
- [ ] Một tin nhắc thật đến đúng người (và không đến người ngoài danh sách pilot khi còn giới hạn).
- [ ] Token không có trong log worker; số đo `quotify_price_freshness_*` đúng.

### Rollback

Tắt `freshness_enabled` hoặc `is_enabled` (hiệu lực trong một giờ); gỡ bảng khỏi giao diện bằng cách quay về image trước (build lại từ commit cũ), kèm câu lệnh `UPDATE` của Slice 5 nếu có tin `pending`. Schema additive, không `downgrade`.

---

## Slice 9: Chỉnh Danh Sách Và Nhịp Theo Dữ Liệu Thật (Sau 3 Đến 4 Tuần)

**Loại:** HITL | **Chặn bởi:** Slice 8 và 3 đến 4 tuần chạy thật | **Cỡ:** nhỏ

### Mục tiêu

Giảm cờ giả và tin thừa, bổ sung vật tư bị bỏ sót.

### Việc cần làm

1. Đo: số tin `freshness` theo tuần, tỉ lệ tin theo sau là cập nhật giá trong 3 ngày làm việc, vật tư nhận nhắc nhiều lần liên tiếp mà không bao giờ cập nhật.
2. Quyết định với quản lý: bỏ vật tư không còn mua khỏi danh sách theo dõi; siết hoặc nới chu kỳ; đổi nhịp hoặc trần; thêm vật tư mới đã có cập nhật nhưng chưa được theo dõi (nhìn dòng `is_watched = false` trong bảng); xem lại Q10 nếu có phàn nàn về số tin.
3. Nếu cần đổi nhịp hoặc trần thì đổi hằng số trong code (có test).

### Tiêu chí chấp nhận

- [ ] Có số liệu và quyết định được ghi lại; thay đổi nào đổi hành vi đều có test.

### Rollback

Hoàn lại cấu hình hoặc hằng số trước đó.

---

## Thứ Tự Và Phụ Thuộc

```
S0 (baseline + duyệt mốc) ─┐
                           S1 (bảng + API đọc, tracer) ─┬─ S2 (bảng Dashboard) ───────────┐
                                                        ├─ S3 (sửa theo dõi trên cấu hình)┤
                                                        ├─ S4 (nạp mặc định từ dữ liệu) ──┼─ S8 (một lần deploy)
                                                        └─ S5 (động cơ nhắc) ─┬─ S6 (cờ + giờ trên UI) ─┤
                                                                              └─ S7 (quan sát + runbook) ┘
S9 (chỉnh theo dữ liệu thật) sau S8, 3 đến 4 tuần
```

S2, S3, S4, S5 làm song song được (khác file, cùng chặn bởi S1). Mỗi slice merge riêng được và không làm hỏng build hay test; production không đổi hành vi nhìn thấy được cho tới Slice 8. Thứ tự đề xuất để có giá trị sớm nhất: S0, S1, S2 (xem được bảng), rồi S3 và S4 (chỉnh được danh sách), rồi S5, S6, S7.

## Ma Trận Kiểm Thử

| Lớp | Nội dung | Slice |
|---|---|---|
| Hàm thuần (TDD) | `classify` trạng thái, `suggest_interval`, `reminder_due(k)`, formatter tin nhắc, mapper nhãn | 1, 2, 4, 5 |
| PostgreSQL thật | Đếm phiên bản khác nhau, biên tuần theo `received_date`, loại phiếu hủy, nháp và `superseded`; `as_of` của tuần quá khứ; nạp mặc định idempotent và không ghi đè; người nhận và nhịp nhắc; chỉ mục duy nhất; `PUT` và `DELETE` cấu hình; gauge | 1, 3, 4, 5, 6, 7 |
| API kiểu Dashboard (`FakeDbSession`) | Quyền `price_alerts.manage` (403 với `dashboard.read`), chuẩn hóa tuần, 422 | 1 |
| Sender với transport giả | Tin nhắc đến đúng người, `_claim_one` có loại mới, không lọt vào luồng khác | 5 |
| Đơn vị frontend (vitest) | Composable, mapper, component, `dashboard.page.spec.ts`, ba spec cấu hình | 2, 3, 6 |
| Playwright e2e | Bảng theo tuần, ẩn theo quyền, sửa theo dõi, công tắc nhắc, khung mobile 390×844 | 2, 3, 6 |
| Cron và múi giờ | `next_cron` phút 20 giờ Việt Nam | 5 |
| Migration | Một head Alembic; additive; kiểm trên DB tạm | 1, 5 |
| Vận hành | `make production-readiness-check`, gauge | 7 |
| Thử thật | Tin nhắc lên điện thoại; đối chiếu bảng với phiếu thật | 5, 8 |

## Rủi Ro Và Cách Giảm

| Mã | Rủi ro | Giảm |
|---|---|---|
| RF-1 | Danh sách theo dõi hoặc chu kỳ sai gây nhắc thừa, người dùng phớt lờ hoặc tắt tin | Mặc định lấy từ dữ liệu thật và có người duyệt trước khi nạp (S0, S4); nhịp thưa (mỗi 3 ngày làm việc), tối đa 5 lần mỗi chuỗi; một tin gom mỗi người mỗi ngày; tắt được bằng cờ; S9 chỉnh theo dữ liệu thật |
| RF-2 | Dữ liệu import và nhập bù làm lệch chu kỳ mặc định | Tính theo `received_date` và số **ngày** khác nhau (không đếm dòng); đo lại trên dữ liệu production (S0); quản lý chỉnh từng vật tư |
| RF-3 | Hai bảng cùng tab dùng hai mốc thời gian (giờ nhập và ngày nhận) nên số lệch với phiếu nhập trễ | Chú thích dưới bảng "Tính theo ngày nhận báo giá"; ghi rõ ở F1 và runbook; không đổi bảng tuần cũ |
| RF-4 | Tuần lễ và Tết tính là ngày làm việc nên có nhắc vô nghĩa | Giữ như 1C (QĐ-11, backlog); tắt `freshness_enabled` trong tuần nghỉ nếu cần |
| RF-5 | Sửa phiếu hoặc nhập muộn làm số lần cập nhật của một tuần cũ thay đổi sau khi xem | Chấp nhận có chủ ý (bảng phản ánh dữ liệu hiện tại); bản sửa không đếm đôi (F2) |
| RF-6 | Phương án A gộp quyền xem bảng với quyền sửa cấu hình thông báo; sau này muốn cho người chỉ-xem sẽ phải thêm quyền | Chấp nhận (khớp đúng Admin và Manager hiện tại); thêm quyền sau là một migration nhỏ và không phá cái đã có |
| RF-7 | Đổi ràng buộc `CHECK` trên bảng tin đang chạy production | Migration additive, bảng nhỏ, khóa ngắn; kiểm trên DB tạm có dữ liệu cũ; kế hoạch rollback ghi rõ tin `pending` loại mới kẹt khi quay về image cũ |
| RF-8 | Vật tư mới chưa được theo dõi nên không bao giờ bị nhắc (điểm mù) | Vật tư không theo dõi nhưng có cập nhật vẫn hiện trên bảng (`unwatched_updated_count`); S9 rà soát định kỳ; đề xuất tự động gợi ý để lại backlog |
| RF-9 | Quên thêm `freshness` vào `_claim_one` làm tin kẹt `pending` | Test sender chạy từ tin `pending` loại mới tới `sent` (Slice 5, test 10); luật cảnh báo "tin pending quá 10 phút" đã có |
| RF-10 | Tin nhắc lọt vào luồng bản tin, duyệt giá bất thường hoặc replay | `audience` và `digest_kind` để null; test dựng sẵn tin `freshness` rồi chạy các luồng đó (Slice 5, test 10) |
| RF-11 | Vật tư ngừng mua nhưng vẫn quá hạn nên bị nhắc mãi | Trần 5 lần mỗi chuỗi; quản lý bỏ theo dõi hoặc vật tư chuyển `inactive`; S9 |
| RF-12 | Người đã nhập vật tư từ nhiều tháng trước vẫn nhận nhắc | Dùng `staff_lookback_days` (90 ngày, chỉnh được trên trang cấu hình); Manager luôn nhận, User chỉ nhận vật tư mình đã nhập gần đây |
| RF-13 | Người tạo phiếu bị xóa hoặc khóa | Người nhận phải là user hoạt động có liên kết Telegram hoạt động (điều kiện sẵn của 1B); Manager vẫn nhận nên không bị bỏ sót |
| RF-14 | `PUT /price-alert-settings` thêm trường làm gãy client cũ lúc deploy | Hai trường mới là **tùy chọn**; deploy backend và frontend cùng đợt trong bảo trì |
| RF-15 | Frontend có test lỗi sẵn che lỗi mới | Slice 0 ghi baseline; so sánh theo tên test, không theo tổng số |
| RF-16 | Truy vấn tổng hợp chậm khi dữ liệu lớn | Hiện 21 nghìn dòng, truy vấn đếm nhẹ có chỉ mục trên `received_date` và `material_id`; đo ở Slice 1, thêm chỉ mục nếu cần (additive) |

## Lệnh Chuẩn

```bash
# Backend (thư mục backend)
INTEGRATION_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:55432/app \
  uv run pytest <file> -q --no-cov -p no:cacheprovider
uv run ruff check <file> --output-format concise
uv run mypy app --cache-dir=/dev/null

# Frontend
make frontend-check            # lint (gồm kiểm không có <style>), format:check, vue-tsc, vitest
npm --prefix frontend run test:e2e

# Danh sách theo dõi mặc định (Slice 4)
docker compose exec -T backend python -m app.price_freshness_seed            # dry-run
docker compose exec -T backend python -m app.price_freshness_seed --apply    # nạp

# Giám sát dev
bash scripts/ops/price-alert-dev-state.sh [số ngày]
```

## Phụ Lục A: Số Liệu Thật (DB Dev, 2026-10-06; Cột Production Điền Ở Slice 0)

Số liệu dev **có lẫn dữ liệu import hàng loạt** nên chỉ mang tính chỉ dẫn.

| Chỉ số | Dev | Production |
|---|---|---|
| Số vật tư | 122 | (điền) |
| Có cập nhật trong 7 ngày gần nhất | 6 | (điền) |
| Có cập nhật trong 30 ngày | 41 | (điền) |
| Có cập nhật trong 90 ngày | 49 | (điền) |
| Chưa từng có giá | 73 (60%) | (điền) |
| Đã từng có giá nhưng quá 30 ngày chưa cập nhật | 8 | (điền) |
| Trung vị số lần cập nhật trong 30 ngày (trong số vật tư có cập nhật) | 5 (lớn nhất 35) | (điền) |
| Vật tư có đúng 1 ngày cập nhật trong 90 ngày | 7 | (điền) |
| Vật tư có đúng 2 ngày | 4 | (điền) |
| **Vật tư có từ 3 ngày (đề xuất theo dõi)** | **38** | (điền) |
| Khoảng cách trung bình giữa hai ngày cập nhật: trung vị, trung bình, p25, p75 | 5,5; 6,1; 3,7; 7,8 ngày | (điền) |
| Chia theo chu kỳ gán (7, 14, 30 ngày) | 17, 19, 2 | (điền) |

Theo loại vật tư (dev):

| Loại | Số vật tư | Có cập nhật | Số lần trung bình |
|---|---|---|---|
| Nguyên liệu | 60 | 22 | 6,0 |
| Vi lượng | 39 | 14 | 10,3 |
| Premix | 13 | 5 | 2,4 |
| Bao bì | 6 | 0 | không có |

Vật tư cập nhật dày nhất (dev, khoảng cách trung bình giữa hai ngày cập nhật): Ngô hạt 1,5 ngày (58 ngày cập nhật), Khô đậu tương 2,1, Fermented Soybean Meal 2,5, Threonine 2,7.

Nhận xét: sáu mươi phần trăm vật tư chưa từng có giá và nhóm Bao bì không có cập nhật nào, nên "chưa cập nhật" chỉ có nghĩa khi có danh sách theo dõi; ngay trong danh sách mặc định mốc chu kỳ cố ý thô.

## Phụ Lục B: Truy Vấn Chỉ Đọc (Chạy Ở Slice 0 Trên Production)

Chạy trong `/opt/quotify` bằng `docker compose exec -T postgres psql -U <user> -d <db>`; chỉ đọc.

```sql
-- B.1 Tổng quan độ mới của giá theo vật tư
with base as (
  select m.id as material_id, m.status, qv.received_date, qv.id as version_id, q.id as quote_id
  from materials m
  left join quote_lines ql on ql.material_id = m.id
  left join quote_versions qv on qv.id = ql.quote_version_id
    and qv.status = 'confirmed' and qv.confirmed_at is not null
  left join quotes q on q.id = qv.quote_id and q.cancelled_at is null
  where qv.id is null or q.id is not null
), per as (
  select material_id, status,
    max(received_date) as last_update,
    count(distinct case when received_date >= current_date - 6 then version_id end) as v7,
    count(distinct case when received_date >= current_date - 29 then version_id end) as v30,
    count(distinct case when received_date >= current_date - 89 then version_id end) as v90,
    count(distinct version_id) as v_all
  from base group by 1, 2
)
select 'materials' k, count(*)::text v from per
union all select 'updated_7d', count(*)::text from per where v7 > 0
union all select 'updated_30d', count(*)::text from per where v30 > 0
union all select 'updated_90d', count(*)::text from per where v90 > 0
union all select 'never_updated', count(*)::text from per where v_all = 0
union all select 'stale_over_30d_but_ever', count(*)::text from per where v_all > 0 and v30 = 0;

-- B.2 Ngày cập nhật khác nhau và khoảng cách trung bình trong 90 ngày (cơ sở của chu kỳ mặc định)
with days as (
  select distinct m.id as material_id, qv.received_date as d
  from materials m
  join quote_lines ql on ql.material_id = m.id
  join quote_versions qv on qv.id = ql.quote_version_id
    and qv.status = 'confirmed' and qv.confirmed_at is not null
  join quotes q on q.id = qv.quote_id and q.cancelled_at is null
  where m.status = 'active' and qv.received_date >= current_date - 89
), per as (
  select material_id, count(*) as n_days,
         case when count(*) > 1
              then (max(d) - min(d))::numeric / (count(*) - 1) end as mean_gap
  from days group by 1
)
select 'with_update_90d' k, count(*)::text v from per
union all select 'n_days>=3', count(*)::text from per where n_days >= 3
union all select 'tier7 (gap<=5)', count(*)::text from per where n_days >= 3 and mean_gap <= 5
union all select 'tier14 (5<gap<=12)', count(*)::text from per where n_days >= 3 and mean_gap > 5 and mean_gap <= 12
union all select 'tier30 (gap>12)', count(*)::text from per where n_days >= 3 and mean_gap > 12;
```

Baseline code (Slice 0, điền sau): backend pytest, ruff, mypy, bandit; frontend lint, `vue-tsc`, vitest (kể cả bốn lỗi cũ đã ghi ở Phụ lục B của kế hoạch 1C). Quy tắc so sánh: theo **tên test và nhóm lỗi**, không theo tổng số.

## Phụ Lục C: Bản Mẫu Giao Diện Và Tin Nhắn

Bảng trên tab Tổng quan (Admin và Manager), tuần 05/10 đến 11/10:

```
Độ mới của giá theo vật tư            [Trạng thái ▾] [Loại vật tư ▾]
Đang theo dõi 38 | Đã cập nhật 21 | Đúng hạn 11 | Quá hạn 6   (+3 vật tư không theo dõi có cập nhật)

Vật tư          Loại        Số lần  Số NCC  Nhận gần nhất  Số ngày  Chu kỳ  Trạng thái      Người nhập gần nhất
Khô đậu tương   Nguyên liệu    7      3      10/10             0       7    Đã cập nhật     Nguyễn Văn A
Lysine          Vi lượng       0      0      18/09            18      14    Quá hạn         Trần Thị B
Bao bì 25kg     Bao bì         0      0      —                 —      30    Chưa có giá     —
Tính theo ngày nhận báo giá. Quản lý danh sách theo dõi ở Cấu hình thông báo giá.
```

Tin nhắc (minh họa; Manager nhận đủ, User chỉ nhận vật tư mình đã nhập; có âm báo, không nút):

```
⏰ Vật tư chưa có giá mới (3) · 09:00 07/10
• Lysine — 18 ngày (chu kỳ 14) · Trần Thị B
• Khô đậu tương — 8 ngày (chu kỳ 7) · Nguyễn Văn A
• Threonine — 15 ngày (chu kỳ 14) · Lê Văn C
Xem chi tiết trên web
```
