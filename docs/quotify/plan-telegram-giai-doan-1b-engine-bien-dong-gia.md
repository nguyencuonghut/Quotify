# Kế Hoạch Triển Khai Giai Đoạn 1B: Engine Biến Động Giá Và Thông Báo Telegram

## Trạng Thái

BẢN ĐÃ CHỐT (bản 4, 2026-10-04: Q1 đến Q7 và L1 đến L28 đã chốt; **Slice 0 đã xong**, kể cả kiểm production chỉ đọc). Sẵn sàng bắt đầu Slice 1. Ngày soạn: 2026-10-04. **Chưa có dòng code nào của 1B.** Giai đoạn 1A (liên kết tài khoản Telegram) đã chạy trên production từ 2026-10-04.

Kế hoạch này là phần triển khai chi tiết của Giai đoạn 1B trong
[plan-telegram-bien-dong-gia-va-chatbot-ai.md](plan-telegram-bien-dong-gia-va-chatbot-ai.md)
(Mục 3 D1 đến D12, Mục 4.1 đến 4.8, Mục 7). Các quyết định thiết kế ở tài liệu đó đã chốt (QĐ-1 đến QĐ-19; QĐ-20 là chu kỳ quét 30 giây, xem L27). Chỗ kế hoạch này kiểm chứng lại, điều chỉnh hoặc bổ sung dựa trên code và dữ liệu thật được liệt kê ở mục "Độ Lệch Và Bổ Sung So Với Tài Liệu Cha". Các điều cần người dùng quyết nằm ở mục "Câu Hỏi Cần Bạn Quyết" (Q1 đến Q7, đã chốt 2026-10-04), mỗi câu có đề xuất.

Cách soạn:
- Local skill `to-issues`: chia lát cắt dọc (tracer bullet). Mỗi slice đi qua đủ các tầng cần thiết, tự xác minh được, có loại **HITL** (cần người quyết định hoặc thao tác ngoài code) hoặc **AFK** (agent làm và merge được), "chặn bởi" và tiêu chí chấp nhận. Không đăng issue lên tracker nào.
- Local skill `tdd`: trong mỗi slice, test đầu tiên là **tracer bullet** (hành vi chính đi hết đường), sau đó mới tới từng hành vi nhỏ. Test đo hành vi qua giao diện công khai; phần SQL, khóa, savepoint phải kiểm trên PostgreSQL thật (lớp `integration` của 1A), không bằng session giả.
- Local agent: 4 agent đọc và đo song song ngày 2026-10-04: (1) vòng đời version báo giá trong code, (2) worker, cấu hình, quyền và bot, (3) kiểm chứng dữ liệu dev và phát lại engine, (4) khả thi vẽ biểu đồ. Cộng với các thí nghiệm Telegram do tác giả chạy với bot dev thật (Phụ lục A). Số liệu baseline đo trên cây git sạch.

## Mục Tiêu

Cuối Giai đoạn 1B, trên dev rồi production (cờ tắt rồi bật dần):
- Khi một version báo giá được chốt, hệ thống tự phát hiện biến động giá theo bộ ba quy tắc R1/R2/R3 (D2), phân mức Nhẹ, Trung bình, Lớn theo ngưỡng của từng vật tư (D4), chống lặp và gộp tin (D5).
- Người đúng (trưởng phòng, nhân viên đã nhập vật tư đó, admin nếu tự bật) nhận tin Telegram gồm **ảnh biểu đồ 14 ngày** kèm caption ngắn và một tin chi tiết. Giọng trung tính, không khuyến nghị mua bán.
- Giá nghi nhập sai (D12) bị loại khỏi tính toán và gửi thành thẻ có nút **Giá đúng** hoặc **Nhập sai** cho trưởng phòng; nút xử lý được trong chat.
- Cấu hình (ngưỡng, ghi đè theo vật tư, bật/tắt, tùy chọn cá nhân) qua **API** (giao diện web là 1C).
- Có chế độ **dry-run replay** trên DB dev để đo tải tin và kiểm engine trước khi gửi thật.

**Hoàn thành khi (định lượng, mục 1B của tài liệu cha, đã siết lại bằng số đo thật):**
1. Replay trên DB dev bằng engine thật khớp **engine tham chiếu độc lập** (`docs/quotify/analysis-1b/`) trong ±15% cho cấu hình D6 (Phụ lục C): khoảng 30,2 tin theo chuỗi mỗi tuần, 16,9 tin gộp theo vật tư, 6,8 tin Trung bình và Lớn, 19,1 tin theo đơn vị D5(b) (7,6 Trung bình và Lớn). Không có tin sai hướng.
2. Ba ví dụ của D2 và các biên ngưỡng (2,5 / 5 / 10, và 4,996) đúng; test thuộc tính |R2| ≥ |R1| khi tăng, |R3| ≥ |R1| khi giảm xanh.
3. Các điểm bất thường của B.7 được gắn cờ đúng; các điểm đúng của Khô cọ và Tryptophan không bị gắn cờ giả khi mô phỏng nút "Giá đúng" (đợt β).
4. Tin mẫu đúng định dạng trên Telegram thật (ảnh 900 x 500, caption không quá 1.024 ký tự, tin chi tiết không quá 4.096), nút Giá đúng và Nhập sai chạy được vòng khứ hồi (đợt β).
5. Chạy thật cron trên dev: quét an toàn (khóa, chồng lấp, cô lập lỗi) có test trên PostgreSQL thật; không gửi trùng khi thử lại.

## Phát Hành Hai Đợt (đề xuất, Q3)

| Đợt | Slice | Nội dung | Cổng |
|---|---|---|---|
| **1B-α** | 0 đến 11 | Biến động giá (mức Trung bình và Lớn gửi ngay; mức Nhẹ chỉ lưu), người nhận, gộp tin, ảnh biểu đồ, gửi tin, dry-run, API cấu hình. **Chưa có** giá bất thường và nút bấm | G1: replay đạt (Slice 10), rồi pilot trên production |
| **1B-β** | 12 đến 15 | Giá bất thường (D12), xử lý nút bấm (`callback_query`), nhắc, hết hạn, dọn dữ liệu | G2: replay có mô phỏng "Giá đúng" đạt (Slice 12), rồi pilot |

Lý do tách: giá bất thường là phần rủi ro nhất (tham chiếu bị "nhiễm độc", Phụ lục C), cần số đo riêng; đợt α không đổi `allowed_updates` của webhook và không có nút bấm, nên deploy đơn giản hơn. Mỗi đợt phát hành độc lập, cờ tắt mặc định.

## Ngoài Scope (làm ở 1C hoặc sau)

- Giao diện web: trang `/price-alert-settings`, tùy chọn cá nhân trong Hồ sơ, trang xem xét điểm bất thường (1C). Ở 1B chỉ có API.
- **Bản tin tổng hợp 08:00** cho mức Nhẹ (1C). Ở 1B sự kiện mức Nhẹ được **lưu và đánh dấu `digest_queued`, không gửi** (Q1).
- Hạn mức Redis, metric `quotify_*` và cảnh báo watermark trễ (1C). Ở 1B chỉ có bảng `price_alert_scan_runs` và log.
- Chatbot, LLM (Giai đoạn 2). Cảnh báo ngay lúc nhập (USD gõ vào ô VNĐ/KG) và loại ngày lễ, Tết khỏi ngày làm việc (backlog).
- Sửa 4 spec E2E cũ đang lỗi, `DELETE /users/{id}` 500, `npm audit`, alert rules `fastapivue_*` (nợ có sẵn).

## Căn Cứ Đã Xác Minh (2026-10-04)

### Từ code (backend)

| Điều | Kết luận | Nguồn |
|---|---|---|
| `confirmed_at` | Gán **phía ứng dụng**, `datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))` (aware +07:00), chỉ ghi ở hai chỗ: `create_quote(confirm_immediately=True)` và `confirm_version`; **chỉ ghi một lần** (reactivate, cancel không đổi). Gán **trước** commit; service chỉ `flush`, commit ở route | `services/quote_service.py:221,615` |
| Mọi đường tạo version `confirmed` | `POST .../versions/{vid}/confirm`; `delete_confirmed_line` (tự tạo rồi chốt bản điều chỉnh); import xlsx qua worker (`create_quote(confirm_immediately=True)`, commit mỗi 200 nhóm, **`confirmed_at` gán ở đầu nhóm**). Không còn đường nào khác, và chưa có đường Telegram nào tạo phiếu | `api/v1/quotes.py`, `services/quote_backfill_import.py:426-455,563-572` |
| Version điều chỉnh | Con trỏ **từ version cũ sang mới**: `superseded_by_version_id` (`quote_service.py:620`). **Backend không sao chép dòng**: nó ghi đúng `lines_data` do client gửi; "snapshot đầy đủ" là hợp đồng với frontend. Không có cột dòng gốc (`source_line_id`); `id` dòng mới là uuid mới và `line_order` đánh lại | `quote_service.py:379-426`, `models/quote_line.py` |
| Cột và index | `confirmed_at` **không có index**. `received_date` nằm ở `quote_versions` (không ở `quote_lines`). Có `ix_quote_lines_material_delivery_created`. Không có `source_line_id`. `quotes.created_by_id` có thể NULL (FK `SET NULL`) | `models/quote*.py`, migration `20260729_0800` |
| Nhận biết import | `AUTH_SEED_ADMIN_EMAIL` chỉ được `QuotifyDashboardService` dùng, thuộc tính private, so sánh chuỗi thô, **không có helper dùng lại**. Import dùng **id của người tải file**, không ép tài khoản seed | `quotify_dashboard_service.py:27-30,72-75,187`, `worker.py:564`, `job_admin.py:81` |
| Ngày làm việc | **Không có** hàm ngày làm việc. Có `get_business_today()` (ngày VN, `exchange_rate_service.py:106`) và `Settings.app_timezone` (`core/config.py:22`) | grep toàn `app/` |
| `delivery_month` | Backend **không ép ngày 01**, truy vấn so `==`; trong dữ liệu dev hiện 0/21.102 dòng khác ngày 01 | `quote_service.py:41-42` |
| Điều kiện lọc chuẩn | `status='confirmed' AND confirmed_at IS NOT NULL AND quotes.cancelled_at IS NULL` (dashboard); danh sách phiếu mặc định còn gồm draft | `quotify_dashboard_service.py:234-238`, `quote_query_service.py:89-104` |
| Worker | `WorkerSettings` chỉ có 1 cron (`poll_and_run_scheduled_backups`), **không có `timezone`** (arq 0.26.3 hỗ trợ, mặc định theo hệ thống tức UTC). Không có advisory lock ở đâu trong `app/`. Worker **chưa dựng `TelegramClient`** và **chưa gọi `configure_logging`** (log INFO của `app.*` không in, OTel ở worker vô hiệu). Redis chỉ lấy host và port | `worker.py:1003-1021`, `arq/worker.py:299-300` |
| Compose | Worker dev không tự reload (không `--watch`); worker prod không healthcheck, không `restart`. **`worker-test` không ép tắt Telegram**: nếu `.env` bật bot thật thì test có thể gửi tin thật | `docker-compose*.yml` |
| Quyền | `BASE_PERMISSION_CODES` phải là list literal (test kiểm bằng `ast`); `test_permission_inventory.py` chỉ bắt lời gọi `require_permission("hằng chuỗi")`. **Không migration nào** từng `INSERT INTO permissions`; `permissions.id` UUID không có default, `code` có unique index; `gen_random_uuid()` có sẵn trên PostgreSQL 16 (đã kiểm). Role `manager` chỉ có trong DB thật (có trên dev), không có trong seed. Frontend `can()` không bypass admin | `auth/seed_data.py`, `tests/test_permission_inventory.py`, `stores/permission.store.ts` |
| Audit | Khóa lạ bị `[REDACTED]`, đệ quy vào `changes[]`; khóa chứa `token`, `session`, `secret` luôn bị che (kể cả `token_usage`). Mẫu `changes[]` ở `api/v1/quotify_settings.py:41-70` | `services/audit_log.py:15-25,189-229` |
| Decimal | Một helper `quantize_money` (HALF_UP, scale 2); **không** có helper phần trăm. Làm tròn trước khi phân mức sẽ đẩy 4,996% lên 5,00% | `exchange_rate_service.py:87-88` |
| Bot hiện tại | Chỉ xử lý `message` và `my_chat_member`. Client chưa có `send_photo`, `answer_callback_query`, `edit_message_text`; `_call` ép JSON (không multipart). `allowed_updates` có **hai bản sao** (`telegram_poller.py:32`, `telegram_cli.py:37`). Rate limiter chỉ áp cho `message`. Dedupe chỉ theo `update_id` (không chống hai người bấm cùng lúc) | `app/integrations/telegram.py`, `app/services/telegram_update_*.py` |
| Fake test | `telegram_fakes.py` và `fake_telegram_server.py` chỉ đọc JSON, chưa hiểu multipart hay `sendPhoto` | `tests/telegram_fakes.py:112` |
| Mẫu test | Service quote dùng session giả nhưng không bắt được lỗi SQL; mẫu tốt cho 1B là `tests/integration/` (DB tạm trên PostgreSQL thật), nhưng **chưa có helper dựng phiếu, nhà cung cấp, vật tư** | `tests/integration/db_helpers.py` |

### Từ dữ liệu DB dev (đo bằng truy vấn chỉ đọc)

| Chỉ tiêu | Số liệu |
|---|---|
| Quy mô | 3.434 phiếu (3 hủy), 3.478 version (confirmed 3.412, superseded 41, draft 25), 21.102 dòng (confirmed chưa hủy 20.893), 361 chuỗi, 49 vật tư có dòng confirmed. Không version confirmed nào thiếu `confirmed_at` |
| Seed admin (import) | 2.847 phiếu, 19.139 dòng; **toàn bộ chốt trong 40 giây ngày 19/08/2026 15:35:43** |
| Người thật | 562 phiếu và version confirmed, 1.754 dòng, 7 người (697, 293, 271, 206, 159, 67, 61 dòng) |
| Độ trễ ngày làm việc (người thật) | 0: 178 version/598 dòng · 1: 55/209 · 2: 28/96 · 3: 22/127 · 4: 12/34 · 5 trở lên: 267/690. **D6 (không quá 3): 283 version, 1.030 dòng** (565 nhập thật + 465 nhập lùi) |
| Hoạt động 60 ngày | Người thật: 292 chuỗi, 49 vật tư; đủ điều kiện D6: 283 version, 198 chuỗi, 46 vật tư. Chốt cuối tuần: 17,3% version đủ điều kiện D6 (6,1% chỉ với nhập thật). Giờ chốt không bó trong giờ hành chính |
| Cuối tuần | `received_date` thứ Bảy hoặc Chủ Nhật: 0,65% dòng toàn kỳ, **2,7% dòng của người thật** |
| Bản điều chỉnh | 41 cặp (137 dòng cũ, 148 dòng mới): 78 không đổi, 24 đổi giá, 46 thêm, 35 bỏ. **Dòng ứng viên 70/148 (47%)**; 18/41 cặp không có dòng ứng viên. `line_order` không ổn định; khóa 4 trường (kèm currency, unit) làm sửa VND/KG thành USD/MT thành "thêm và bỏ" nên khóa phải là (vật tư, kỳ giao hàng). Dữ liệu import có 1.853 nhóm (version, vật tư, kỳ) trùng nhau, người thật 0 nhóm |
| "Người nhập" | `quote_versions.created_by_id` luôn bằng `quotes.created_by_id` (0/3.478 lệch; 41/41 bản điều chỉnh do chính người tạo phiếu): khác biệt D8 và D12 chưa từng được kiểm bằng dữ liệu thật |
| Hiệu năng | Daily-min chuỗi lớn nhất (577 dòng, 197 điểm): 3,4 ms toàn vòng đời, 0,65 ms cửa sổ 30 ngày. Quét `confirmed_at` trong 7 phút: 0,3 ms (Seq Scan trên 3.478 version). **Chưa cần index `quote_versions(confirmed_at)`** |

### Từ Telegram thật (bot dev `@HHQuotifyBot`, các thí nghiệm "từ chối", không gửi gì vào chat)

Văn bản 4.097 ký tự: 400 `message is too long`. HTML có `<` hoặc `&` thô: 400 `can't parse entities` (lỗi cuối cùng). `callback_data` 65 byte hoặc chuỗi tiếng Việt 72 byte: 400 `BUTTON_DATA_INVALID`. Nút inline không có `callback_data` hay `url`: 400. Caption 1.025 ký tự: 400. `answerCallbackQuery` với id giả: 400 (hết hạn). `editMessageText` tin không tồn tại: 400. Theo tài liệu chính thức (Bot API 10.3): ảnh tối đa 10 MB, rộng cộng cao không quá 10.000, tỷ lệ tối đa 20, caption và văn bản tính sau khi parse entity. Các thí nghiệm "dương" (gửi thật, nút bấm khứ hồi, giới hạn tốc độ 40 tin) đã chạy ngày 2026-10-04 ở Slice 0, kết quả ở Phụ lục A. Điểm đáng chú ý nhất: `answerCallbackQuery` bị từ chối sau khoảng 15 giây (L22).

### Từ thử nghiệm biểu đồ (matplotlib, môi trường tạm, Python 3.12 như image)

Khả thi, không cần apt hay font: matplotlib 3.11.2 cùng numpy, pillow... đều có wheel (không biên dịch). DejaVu Sans đi kèm đủ **146/146** ký tự tiếng Việt dựng sẵn; **emoji KHÔNG hiển thị được trong ảnh** (ra ô vuông), nên ảnh dùng `▲`/`▼` còn emoji chỉ nằm trong caption và tin văn bản. Chi phí thật: **+130 MB** site-packages (tài liệu cha ghi 60 đến 100 MB), +82 MB nén; layer của `uv sync` tăng +274 MB vì uv cache nằm lại (thêm `--no-cache` thì chỉ +137 MB). Vẽ 61 đến 91 ms mỗi ảnh (PNG 900 x 500 khoảng 54 KB), font cache dưới 1 giây (tài liệu cha ghi "vài giây"), RSS worker 104 MB sau 30 ảnh, đỉnh 150 MB khi 5 ảnh đồng thời, không rò rỉ sau 300 ảnh; 200 ảnh đồng thời qua `to_thread` không lỗi. Mypy strict báo 7 lỗi `no-untyped-call` ở `matplotlib.dates`: tránh bằng `date.toordinal()`, `FixedLocator`, `FuncFormatter`. Phương án Pillow thuần: nhẹ hơn (20 MB, 44 ms, 51 MB RAM) nhưng phải nhúng font và tự vẽ trục. Ảnh mẫu: `analysis-1b/chart_prototype.png`.

### Baseline repo (không được xấu hơn)

| Hạng mục | Giá trị |
|---|---|
| pytest | 559 pass khi có DB (gồm 51 test tích hợp); 508 pass và 51 skip khi không có DB |
| ruff | 62 lỗi có sẵn (`ruff check .`) |
| mypy (`app`) | 13 lỗi ở 5 file cũ (`quotes.py`, `catalog_import.py`, `quote_backfill_import.py`, `quote_export_service.py`, `worker.py`) |
| bandit (`-r app`) | 16 phát hiện (15 Low, 1 Medium) |
| Frontend | 1B không sửa frontend; baseline Vitest 247 pass và đúng 4 lỗi cũ, ESLint 69, Prettier 74 file, vue-tsc 0 |
| Alembic | head `20261004_1100`, một head |

## Độ Lệch Và Bổ Sung So Với Tài Liệu Cha

Các điểm dưới đây được kiểm chứng bằng code và dữ liệu thật. Những chỗ tài liệu cha **sai về sự kiện** sẽ được sửa ở Slice 0; những chỗ là **quyết định thiết kế mới** nằm ở mục L1 đến L28.

| # | Tài liệu cha ghi | Thực tế và xử lý |
|---|---|---|
| 1 | Alembic head `20260824_1000` (Mục 1.1, 4.5) | Head là `20261004_1100`. Migration 1B đặt `down_revision = "20261004_1100"` |
| 2 | D2 mục 5: version mới là snapshot đầy đủ do hệ thống sao chép | Backend không sao chép; frontend gửi lại toàn bộ dòng. Cách tìm dòng ứng viên viết lại ở **L1** |
| 3 | D6 và B.8: "220 / 373 / 522 dòng trễ ≤ 1 / 3 / 7" | Đó là **ngày lịch** và chỉ cho dòng nhập lùi. Theo **ngày làm việc** và cho mọi dòng người thật: ≤ 3 là 283 version và 1.030 dòng. Bảng tải ở B.8 thay bằng Phụ lục C |
| 4 | D6: import dùng tài khoản seed admin | Import dùng id **người tải file**; "tài khoản seed" chỉ là quy ước. Phải kiểm production có ai khác tải import không (Slice 0, **L17**) |
| 5 | RR-4, RR-20: chỉ so dòng đổi giá với version nguồn | Thiếu bẫy: (a) nguồn bị thay thế **trước khi cron quét** thì các dòng không đổi của nó không bao giờ phát tin; (b) đổi `received_date` làm điểm giá chuyển ngày và tính lại tỷ giá USD/MT; (c) trùng khóa dòng trong một version; (d) `currency`, `unit` lưu không chuẩn hóa chữ hoa. Xử lý ở **L1**, **L2** |
| 6 | Mục 4.1: quét theo `confirmed_at`, chồng lấp 5 phút | Với import, `confirmed_at` gán đầu nhóm và commit sau tối đa 200 nhóm, thời gian chưa đo; dùng bảng version đã quét (**L2**) để không phụ thuộc hoàn toàn vào chồng lấp. Phải so thứ tự `(confirmed_at, id)` |
| 7 | D12: "khoảng 1,6 điểm bất thường mỗi tuần" | Là cận dưới. Phát lại theo thời gian thực gắn cờ **43 điểm (6,8 mỗi tuần)** vì tham chiếu bị nhiễm độc bởi lần nhập sai đầu tiên (ví dụ Threonine 18.100, sau sửa 25.600). Sau gộp cụm khoảng 2,6 tin mỗi tuần. Đợt β phải đo lại với mô phỏng "Giá đúng" (**Q4**) |
| 8 | Mục 4.3: matplotlib thêm 60 đến 100 MB, font cache vài giây, font tiếng Việt chưa xác minh | +130 MB, dưới 1 giây, font đủ; emoji không vẽ được (**L11**) |
| 9 | Mục 4.8: Prometheus; worker không tự reload | Đúng; bổ sung: worker chưa có logging app, chưa có `TelegramClient`, `worker-test` có thể gửi tin thật (**L8**, **L20**) |
| 10 | Mục 1.2: dashboard loại seed admin khỏi thống kê theo người | Chỉ ở KPI theo người và hoạt động tuần; tổng số phiếu và biểu đồ giá vẫn tính dữ liệu import. Điều kiện loại phải NULL-safe (`quotes.created_by_id` có thể NULL) |
| 11 | RR-19: alert rules "còn tên cũ" | Rule dùng metric `fastapivue_*` mà code không còn phát (`quotify_*`): ít nhất 2 rule không bao giờ khớp |
| 12 | Mục 1.5: chỉ enqueue SAU commit | `create_export_job` vi phạm (enqueue trước commit); 1B không bắt chước |

## Nguyên Tắc Bắt Buộc

Kế thừa nguyên tắc của 1A và bổ sung riêng cho 1B:

1. **Additive, tắt mặc định.** Chỉ thêm bảng, cột nullable, file, route. Không sửa migration cũ, không đổi hành vi API cũ. Hai cờ độc lập (L13); phát hành ở trạng thái tắt.
2. **Không sửa `quotes.py` hay `quote_service.py`.** Phát hiện bằng cron quét (thiết kế 4.1), không móc vào route.
3. **Service chỉ `flush`; route hoặc job `commit` rồi mới gửi Telegram.** Lỗi gửi không bao giờ đổi kết quả nghiệp vụ. Không enqueue trước commit.
4. **Tiền và phần trăm là `Decimal`**, không `float`. Phân mức trên giá trị **chưa làm tròn**.
5. **Ngày địa phương là `Asia/Ho_Chi_Minh`.** `confirmed_at` đọc ra là aware (UTC từ asyncpg): luôn `astimezone(VN)` trước khi lấy ngày; không gọi `.date()` trực tiếp.
6. **Authz ở tầng bot.** Service không kiểm quyền, nên nút bấm (`callback_query`) phải tự kiểm `price_alerts.receive_all` hoặc admin, và người dùng `ACTIVE`.
7. **Không lộ bí mật.** Token bot không vào log, audit, response; audit không ghi `telegram_user_id`; khóa audit không chứa `token`, `secret`, `session`.
8. **TDD theo `tdd` skill.** Mỗi slice mở bằng test tracer. Lõi thuần (ngày làm việc, phân mức, quy tắc) test không cần DB. Mọi thứ có SQL, khóa, savepoint, `ON CONFLICT` phải có test tích hợp trên PostgreSQL thật. Telegram luôn qua `httpx.MockTransport` hoặc server giả, không gọi Telegram thật trong test tự động.
9. **Xác minh thật** bằng `curl`, `psql`, worker thật trên dev, và bot dev thật cho các bước HITL. Không sửa lan: không `ruff format .`, `ruff check --fix .` trên file cũ; không làm xấu baseline.
10. **Tiếng Việt có dấu** cho mọi chuỗi hiển thị và tài liệu. Tiền `10,200.00 VNĐ/KG`, ngày `DD/MM/YYYY`, kỳ giao hàng `MM/YYYY`, giờ VN. Giọng trung tính, không khuyến nghị mua bán.
11. **Cuối mỗi slice có kiến thức bền vững:** cập nhật `memory-bank/`, chạy `agent-task-close.sh` (ít nhất ở Slice 5, 11, 15).

## Quyết Định Kỹ Thuật Cho 1B

Mỗi điểm có mặc định, dựa trên số đo ở mục Căn Cứ. **Trạng thái: đề xuất của tác giả, chờ xác nhận ở Slice 0** (người dùng đã ủy quyền cho agent chốt các quyết định kỹ thuật của 1A, tài liệu này giữ cùng cách làm nhưng chỉ gắn nhãn "đã chốt" khi người dùng đồng ý).

| # | Quyết định | Mặc định |
|---|---|---|
| L1 | Dòng ứng viên của bản điều chỉnh (thay D2 mục 5) | Theo **chuỗi** (vật tư, `date_trunc('month', delivery_month)`), so **tập đa** (multiset) `price_converted_vnd_per_kg`. Ứng viên là dòng của bản mới có giá không còn trong tập đa của bản nguồn (cùng chuỗi). Ba ngoại lệ: (a) `received_date` của bản mới khác bản nguồn thì **mọi dòng** là ứng viên (điểm giá đổi ngày, tỷ giá USD/MT tính lại); (b) bản nguồn chưa từng được quét (L2) thì mọi dòng là ứng viên; (c) version đầu của phiếu (không có nguồn) thì mọi dòng là ứng viên. Không dùng `line_order`, không dùng khóa kèm currency/unit. Đọc giá đã lưu, không tính lại từ `price_original` |
| L2 | Bảng `price_alert_scanned_versions` | Mỗi version đã được quét ghi một dòng (kể cả khi không sinh sự kiện): `version_id`, `scanned_at`, `is_trigger_source`, độ trễ ngày làm việc, `scan_run_id`. Dùng để: biết nguồn đã quét hay chưa (L1 b), chống quét lại, báo cáo. Dọn sau 180 ngày. UNIQUE trên sự kiện vẫn là lớp chống trùng thứ hai |
| L3 | Chọn version cần quét | `status='confirmed' AND confirmed_at > watermark − 5 phút AND phiếu chưa hủy AND version_id chưa có trong scanned_versions`, sắp `(confirmed_at, id)`. Watermark chỉ giới hạn truy vấn, **không** là cơ chế chống bỏ sót duy nhất. Không quét theo `updated_at` (đổi khi version bị `superseded`). Watermark tiến tới `confirmed_at` lớn nhất đã xử lý |
| L4 | Index | **Không thêm** `quote_versions(confirmed_at)` ở 1B (đo 0,3 ms ở 3,5 nghìn version, tuyến tính; 100 lần dữ liệu vẫn cỡ 30 ms). Xét lại ở 1C khi có số liệu production |
| L5 | Ngày làm việc | Module thuần `services/working_days.py`: `is_working_day`, `working_days_between(start, end)` (đếm ngày làm việc trong `(start, end]`), `reference_window(day, n=7)` (lùi bỏ thứ Bảy, Chủ Nhật). Thứ Bảy, Chủ Nhật không đếm; ngày lễ và Tết chưa loại (QĐ-11). Điểm nhận cuối tuần vẫn là điểm tham chiếu |
| L6 | Điểm giá (daily-min) | Hàm `get_daily_min_series(session, material_id, delivery_month, date_from, date_to, exclude_line_ids)` trong `services/daily_min_series.py`, SQL `GROUP BY received_date, MIN(price_converted_vnd_per_kg)`, điều kiện chuẩn của dashboard, chuẩn hóa `date_trunc('month')`. Trả thêm id dòng và version của điểm thấp nhất. Chatbot ở giai đoạn 2 dùng lại hàm này |
| L7 | Phân mức | `percent = (mới − ref) / ref × 100` bằng `Decimal`, **không quantize** trước khi so; biên `≥ 2,5`, `≥ 5`, `> 10` (D4). Hiển thị mới làm tròn HALF_UP 2 chữ số. Bảo vệ `ref = 0` và giá không dương (import không kiểm dương) |
| L8 | Worker | (a) Dựng `TelegramClient.from_settings` ở `startup`, đóng ở `shutdown`; (b) gọi `configure_logging` ở `startup` (hiện thiếu, nên log INFO không in và bộ che token không áp dụng); (c) cron `poll_price_alerts` mỗi 30 giây (`second={0, 30}`, L27); (d) đặt `timezone = ZoneInfo(settings.app_timezone)` cho `WorkerSettings` và có test; (e) `pg_try_advisory_xact_lock` suốt lần quét, vì `cron(unique=True)` chỉ chống trùng theo mốc giờ, không chống chạy chồng; (f) mỗi version trong một savepoint |
| L9 | `allowed_updates` | Gom thành **một hằng** dùng chung cho poller và CLI, thêm `callback_query` (đợt β). Webhook production đang đăng ký danh sách cũ nên **sau deploy đợt β phải chạy lại `telegram_webhook.py set --yes`** (nếu không Telegram không gửi `callback_query`). Test đang ghim danh sách cũ ở 3 file, phải cập nhật |
| L10 | Client Telegram mở rộng | Thêm `send_photo(chat_id, png, caption, reply_markup)` (multipart: `files` cho ảnh, `data` cho trường còn lại, `reply_markup` là chuỗi JSON), `answer_callback_query`, `edit_message_text`, `edit_message_reply_markup`. Kiểm caption ≤ 1.024 và văn bản ≤ 4.096 trước khi gọi. Giữ `from None` khi lỗi mạng. Lỗi `message is not modified` là bình thường, không thử lại |
| L11 | Biểu đồ | matplotlib, **API hướng đối tượng** (`Figure` + `FigureCanvasAgg`, không `pyplot`), chạy trong `asyncio.to_thread`. Nhúng đường dẫn tới DejaVu Sans đi kèm gói (`FontProperties(fname=...)`), không phụ thuộc font hệ thống. **Không emoji trong ảnh** (dùng `▲`, `▼`); emoji chỉ ở caption và tin văn bản. Tránh `matplotlib.dates` (lỗi mypy strict). Đặt `MPLCONFIGDIR=/tmp/mpl`. Bọc sau hàm `render_price_chart(spec) -> bytes` để đổi sang Pillow sau nếu cần. Pin phiên bản trong `uv.lock` |
| L12 | Danh sách người nhận thử (pilot) | Biến môi trường `PRICE_ALERT_RECIPIENT_EMAILS` (rỗng nghĩa là không giới hạn). Khi có giá trị, **chỉ** người trong danh sách nhận tin; người khác được ghi trạng thái `skipped` (lý do `pilot`). Dùng ở dev và ở giai đoạn đầu trên production, an toàn hơn chỉ dựa vào việc "ít người đã liên kết Telegram" |
| L13 | Hai cờ | `TELEGRAM_ENABLED` (môi trường) là điều kiện cần; `price_alert_settings.is_enabled` (DB) là điều kiện đủ. Chuyển `false → true` đặt `watermark_confirmed_at` và `enabled_since` bằng thời điểm bật **mỗi lần**, để dữ liệu cũ không sinh tin. Cron kiểm cờ ở đầu mỗi lần chạy nên tắt có hiệu lực trong vòng 30 giây |
| L14 | Quyền | Hai mã cho 1B: `price_alerts.receive_all`, `price_alerts.manage` (`chatbot.manage` để 2A). Thêm vào `BASE_PERMISSION_CODES` (list literal). **Migration quyền tự `INSERT`** vào `permissions` (`gen_random_uuid()`, `ON CONFLICT (code) DO NOTHING`) rồi gán cho `manager` **và `admin`** (`ON CONFLICT DO NOTHING`, chịu được thiếu role). Gán `admin` để giao diện 1C hiện trang (frontend `can()` không bypass admin; backend vẫn bypass). Có test migration trên DB có và không có role `manager`, và chạy trước seed |
| L15 | Audit | `price_alerts.settings_updated`, `price_alerts.threshold_updated` (kèm `changes[]`, mọi giá trị `str()`), `price_alerts.anomaly_reviewed`, `price_alerts.scan_completed` (chỉ khi có sự kiện). Thêm khóa vào allow-list, test giữ khóa và vẫn che khóa chứa `token`, `secret`, `session`. Không audit từng tin gửi |
| L16 | Người nhận | D7 đến D10 giữ nguyên. Chỉ gửi cho người dùng `ACTIVE` có liên kết Telegram `active` (không `blocked`). D8 dựa `quotes.created_by_id`; D12 dựa `quote_versions.created_by_id` (hiện luôn bằng nhau, nên test phải **tạo dữ liệu khác nhau** để kiểm hai định nghĩa). Mọi phép loại tài khoản seed phải NULL-safe (`IS DISTINCT FROM`) |
| L17 | Nhận biết import | Quy ước đã chốt (Q7): tài khoản seed (`AUTH_SEED_ADMIN_EMAIL`) là admin hệ thống, chỉ quản trị và import, không bao giờ nhập tay; phiếu do tài khoản này tạo là import (D6) và tài khoản này không nhận tin. Import dùng id người tải file nên quy ước chỉ đúng khi mọi import đều do tài khoản này tải: **Slice 0 kiểm production** (`import_jobs.created_by_id`) và kiểm tài khoản này không có phiếu nhập tay. Đo trên dev (2026-10-04): 4 job import đều do tài khoản seed tải; 2.847 phiếu của tài khoản seed đều tạo trong một ngày (19/08, ngày import); 587 phiếu của 9 người thật từ 20/08 đến 02/10. **Production (kiểm 2026-10-04) khớp dev:** 4 job import đều do tài khoản seed tải; 2.847 phiếu của tài khoản seed đều tạo ngày 19/08; 595 phiếu của 7 người thật từ 20/08 đến 04/10. Vi phạm quy ước về sau (người khác import) không có cơ chế chặn riêng ở 1B; trần 10 phút của L27(d) giới hạn thiệt hại. Không có đánh dấu riêng |
| L18 | Mức Nhẹ ở 1B | Tạo sự kiện và tin trạng thái `digest_queued`, **không gửi** (bản tin 08:00 là 1C). Tính là "đã gửi" cho chống lặp D5(a). Người đặt mức tối thiểu "Nhẹ" vì thế chưa nhận gì ở 1B (Q1) |
| L19 | Dọn dữ liệu | Cron hằng ngày xóa sự kiện, tin, lần quét, version đã quét cũ hơn 180 ngày. Có test không xóa tin còn `pending` hay thẻ còn `pending` |
| L20 | Hạ tầng test | `worker-test` ép `TELEGRAM_ENABLED=false` và token rỗng (như `backend-test` đã làm ở 1A); `scripts/fake_telegram_server.py` và `tests/telegram_fakes.py` hiểu multipart (`sendPhoto`), `answerCallbackQuery`, `editMessageText`, `editMessageCaption`, `editMessageReplyMarkup`, trả `message_id`. Thêm helper dựng vật tư, nhà cung cấp, phiếu, version, dòng vào `tests/integration/db_helpers.py` |
| L21 | Quan sát | `price_alert_scan_runs` (số version quét, sự kiện, tin tạo, tin gửi, lỗi; **chỉ ghi khi lần quét có việc hoặc có lỗi**, L27), nhịp tim `price_alert_scan_state.last_run_at`, và log INFO của worker (lần quét rỗng chỉ log DEBUG). Có truy vấn giám sát chỉ đọc trong runbook, trong đó `last_run_at` cũ hơn 2 phút khi cờ đang bật nghĩa là cron hoặc worker hỏng. Metric Prometheus và cảnh báo watermark trễ là 1C |
| L22 | `callback_query` ở bot | Rate limit **bucket riêng** theo `from.id` (cùng cơ chế in-memory); **luôn** gọi `answerCallbackQuery` (kể cả khi từ chối hay bị giới hạn) để nút không quay mãi, và gọi **trong 5 giây** kể từ lúc nhận update, trước các thao tác tốn thời gian (Telegram từ chối câu trả lời sau khoảng 15 giây: trả lời sau 14 giây vẫn được, sau 17 giây thì 400 `query is too old`, Phụ lục A). Nếu việc xử lý chưa xong thì trả lời ngay bằng "Đang xử lý" rồi sửa tin khi xong; nhánh lỗi "độc" cũng phải trả lời được callback (hiện trả `[]` khi không có `message`) |
| L23 | Hai người bấm cùng lúc | Cập nhật nguyên tử: `UPDATE price_alert_events SET review_status=:s, reviewed_by_id=:u, reviewed_at=now() WHERE id=:id AND review_status='pending' RETURNING ...`; ai được 1 dòng thì thắng (dedupe theo `update_id` không đủ vì hai lần bấm là hai update) |
| L24 | Sửa tin sau khi bấm | Tin có ảnh sửa bằng `editMessageCaption` (`editMessageText` trả 400 `there is no text in the message to edit`), tin văn bản bằng `editMessageText`; bỏ bàn phím bằng `reply_markup` `{"inline_keyboard": []}`; lỗi 400 `message is not modified` (bấm lặp hoặc sửa trùng nội dung) là **thành công**, không phải lỗi. Sửa tin của **người bấm**: ghi người xử lý, thời điểm, kết quả và bỏ bàn phím. Tin của trưởng phòng khác giữ nguyên cho tới khi họ bấm; khi bấm vào thẻ đã xử lý thì `answerCallbackQuery` báo "đã được xử lý bởi ..." và sửa tin của họ về trạng thái cuối |
| L25 | Gửi tin | At-least-once, `lease_until` giảm gửi trùng. Mỗi tin: gửi ảnh rồi tin chi tiết. 429: chờ `retry_after`; 403: `mark_blocked` theo **tài khoản** (`telegram_accounts.chat_id`); 400: lỗi cuối, không thử lại; lỗi mạng: thử lại có backoff. Bỏ qua tin ở trạng thái cuối; không bỏ qua `sending` còn hạn `lease_until` |
| L26 | Dry-run replay | Lệnh `python -m app.price_alert_replay` chạy engine thật trên DB, **trong một giao dịch không bao giờ commit**, không gửi Telegram, in số liệu theo tuần (chuỗi, gộp, Trung bình và Lớn, D5(b)). Tùy chọn `--ignore-trigger-source` (bỏ D6) để thấy nhiều dữ liệu hơn trên dev |
| L27 | Chu kỳ quét 30 giây (đã chốt 2026-10-04) | Giữ **cron quét + watermark** và đổi chu kỳ từ 2 phút (tài liệu cha 4.1) xuống **30 giây** (`second={0, 30}`). Độ trễ từ lúc chốt đến lúc có sự kiện tối đa 30 giây cộng thời gian xử lý; đến tin Telegram khoảng 45 giây vì cron gửi chạy lệch pha `second={15, 45}` (L25). Tính toán vẫn là đúng điều người dùng mô tả (chốt xong thì so với cửa sổ 7 ngày làm việc rồi gửi), chỉ khác là do cron nhặt thay vì route gọi. Không móc vào route confirm vì ba đường chốt (route, `delete_confirmed_line`, import commit từng 200 nhóm) và vì mất kết nối Redis sau commit sẽ làm mất sự kiện; **nâng cấp gần thời gian thực** (enqueue job ngay sau commit, giữ cron làm lưới an toàn; hoặc outbox bằng trigger DB) để dành cho 1C nếu 30 giây không đủ. Hệ quả: **(a)** chỉ ghi `price_alert_scan_runs` khi lần quét có ≥ 1 version hoặc có lỗi, nếu không sẽ có khoảng 2.880 dòng rỗng mỗi ngày; thay vào đó mọi lần quét có lấy được khóa đều cập nhật `price_alert_scan_state.last_run_at` (một UPDATE trên bảng singleton, thêm cột ở migration 1). **(b)** Khóa advisory vẫn bắt buộc: lần quét có thể kéo dài hơn 30 giây khi import lớn, và `cron(unique=True)` của arq chỉ chống trùng theo mốc thời gian (job id là `tên:mốc ms`); lần chạy không lấy được khóa thoát ngay, không ghi gì. **(c)** Độ chồng lấp watermark giữ **5 phút** (do độ trễ commit của import, không phụ thuộc chu kỳ). **(d)** Chia nhỏ lần quét làm trần D5(d) "30 tin mỗi lần quét" kém tác dụng khi có đợt nhập hàng loạt, nên thêm **trần thứ hai: 30 tin gửi ngay cho một người trong 10 phút gần nhất** (đếm từ `price_alert_messages`, hằng số trong code; vượt thì `digest_queued` và gom vào tin tóm tắt như D5(d)); số liệu thật (tối đa 7 tin mỗi lần quét, 14 tin mỗi ngày) không chạm trần này. **(e)** Số liệu D5(b) đo lại với ô quét 30 giây: 19,1 tin mỗi tuần (trước 18,9), Trung bình và Lớn vẫn 7,6 (Phụ lục C) |
| L28 | Tài khoản thử trên dev (người dùng đề xuất 2026-10-04) | Tạo một tài khoản **Manager** riêng trên dev (role `manager` và `user`, giống 9 trưởng phòng hiện có; không phải tài khoản seed và không mượn tài khoản của người thật) qua trang Người dùng. Dùng cho cả hai việc: **nhập liệu và chốt phiếu thử** (người thật nên là nguồn kích hoạt hợp lệ theo D6) và **nhận Telegram** (liên kết Telegram của bạn vào tài khoản này, thay cho liên kết của tài khoản seed). Một tài khoản đủ cho đợt α vì trưởng phòng nhận mọi vật tư từ mức Trung bình (D7); quy tắc D8 (nhân viên chỉ nhận vật tư mình đã nhập) không kiểm được bằng tài khoản này mà do test tích hợp phủ. Đợt β cần thêm **một tài khoản nhân viên** (role `user`) làm người nhập, để kiểm "trưởng phòng khác người nhập" (thẻ có nút và thẻ không nút). **Luật khi một người vừa là trưởng phòng vừa là người nhập:** nhận **một** thẻ, loại có nút (một tin cho mỗi người nhận, D5(b)). Tài khoản nằm trong DB dev nên mất khi khôi phục DB từ dump; thao tác tạo lại ghi trong hướng dẫn kiểm dev. `PRICE_ALERT_RECIPIENT_EMAILS` trên dev chỉ gồm email tài khoản này |

## Câu Hỏi Cần Bạn Quyết

Mỗi câu có đề xuất; nếu bạn trả lời "theo đề xuất" thì tác giả chốt như đề xuất. **Kết quả 2026-10-04:** Q1 đến Q6 chốt theo đề xuất; Q7 chốt như ghi ở dòng Q7.

| # | Câu hỏi | Đề xuất | Hệ quả nếu khác |
|---|---|---|---|
| Q1 (đã chốt) | **Mức Nhẹ ở 1B**: lưu mà chưa gửi (chờ bản tin 08:00 ở 1C), hay gửi riêng từng tin ngay? | Lưu, chưa gửi (L18). Mức Nhẹ chiếm phần lớn sự kiện (118/190 theo chuỗi trong replay); gửi riêng sẽ tăng đáng kể khối lượng tin | Gửi riêng: tải tin mỗi nhân viên tăng, cần trần riêng, ngược với D5(c) |
| Q2 (đã chốt) | **Bản điều chỉnh sửa muộn**: D6 tính trễ theo `received_date` (bản điều chỉnh mang `received_date` cũ), nên sửa giá sau hơn 3 ngày làm việc **không phát tin** (vẫn là điểm tham chiếu). Giữ vậy? | Giữ (đơn giản, tránh bão tin khi sửa hàng loạt phiếu cũ) | Tính trễ theo ngày chốt bản điều chỉnh: sửa lỗi cũ cũng phát tin; dễ ồn khi chỉnh dữ liệu lịch sử |
| Q3 (đã chốt) | **Tách hai đợt phát hành** α (biến động) và β (giá bất thường, nút bấm)? | Tách (xem mục Phát Hành Hai Đợt) | Một đợt: rủi ro lớn hơn, deploy phải đổi `allowed_updates` ngay |
| Q4 (đã chốt) | **Giá bất thường (D12)**: replay thời gian thực gắn cờ 43 điểm (6,8 mỗi tuần), nhiều điểm do tham chiếu bị nhiễm độc bởi lần nhập sai đầu tiên. Giữ ngưỡng 30% và 30 ngày, rồi chỉnh theo dry-run **có mô phỏng nút "Giá đúng"** ở Slice 12? | Giữ mặc định, chỉ phát hành β khi dry-run đạt | Nâng ngưỡng (40%, 50%) bỏ sót lỗi nhập sai thật (ví dụ USD gõ vào ô VNĐ/KG lệch khoảng 96%) |
| Q5 (đã chốt) | **Ai nhận tin trong giai đoạn pilot trên production?** (L12) | Chỉ chủ dự án và 1 đến 2 trưởng phòng, qua `PRICE_ALERT_RECIPIENT_EMAILS`, vài tuần đầu (phải là tài khoản người thật, không phải tài khoản seed; Q7) | Bỏ pilot: tin đến mọi người đã liên kết ngay khi bật |
| Q6 (đã chốt) | **Thêm `--no-cache` vào `uv sync` của Dockerfile production** (giảm 137 MB layer, bù cho matplotlib)? Thay đổi Dockerfile production ngoài phạm vi tính năng | Làm, như một slice nhỏ riêng có rollback dễ (Slice 8) | Không làm: image production tăng thêm khoảng 274 MB |
| Q7 (đã chốt, khác đề xuất ban đầu) | **Tài khoản riêng cho import** thay vì dùng tài khoản seed admin hay admin thật? | **Không cần tài khoản riêng.** Tài khoản admin hệ thống (`AUTH_SEED_ADMIN_EMAIL`) chỉ để quản trị và import, **không bao giờ nhập tay** vì không phải nhân sự phòng Mua. Vậy "tài khoản seed" chính là "tài khoản import" (L17) | Quy ước này phải đúng mãi: nếu admin hệ thống nhập tay thì phiếu đó bị loại khỏi nguồn kích hoạt; nếu người khác import thì bị coi là nhập tay (RR-38) |

## Mô Hình Dữ Liệu (migration additive, viết tay, không `--autogenerate`)

Định nghĩa đầy đủ các bảng nằm ở Mục 4.5 của tài liệu cha. Chỗ khác ở 1B:

- **Thêm** bảng `price_alert_scanned_versions` (L2):

```
price_alert_scanned_versions
  version_id UUID PK, FK quote_versions CASCADE
  scanned_at timestamptz NOT NULL default now()
  is_trigger_source bool NOT NULL
  trigger_delay_working_days smallint NULL
  scan_run_id UUID NULL FK price_alert_scan_runs SET NULL
```

- **Thêm** cột `price_alert_scan_state.last_run_at timestamptz NULL` (L27): nhịp tim của cron quét, cập nhật mỗi lần chạy lấy được khóa, kể cả khi không có version nào.
- Giữ nguyên các bảng `price_alert_settings` (singleton), `price_alert_scan_state` (singleton), `price_alert_scan_runs`, `price_alert_material_thresholds`, `price_alert_events`, `price_alert_messages`, `price_alert_message_events`, `user_alert_preferences` như tài liệu cha. `price_alert_events.attached_to_event_id`, `review_status`, `reminded_at` chỉ dùng từ đợt β nhưng tạo cùng bảng để tránh migration sửa bảng.
- **Chia migration theo slice** (mỗi migration một head nối tiếp từ `20261004_1100`, đặt tên `YYYYMMDD_HHMM_<mô_tả>.py`):
  1. Slice 1: `price_alert_settings`, `price_alert_scan_state`, `price_alert_scan_runs`, `price_alert_scanned_versions`, `price_alert_material_thresholds`, `user_alert_preferences`.
  2. Slice 1: migration quyền (L14), tách riêng để rollback dữ liệu quyền không đụng bảng.
  3. Slice 5: `price_alert_events`.
  4. Slice 7: `price_alert_messages`, `price_alert_message_events`.
- Mọi FK ghi rõ `ON DELETE` (tài liệu cha, Mục 4.5). Mọi model đăng ký ở `app/models/__init__.py` và `app/db/base.py`. Kiểm `alembic heads` còn đúng một head sau mỗi migration; viết test upgrade và downgrade trên DB tạm.
- **Production:** chỉ `upgrade`, không `downgrade` (bảng mới tương thích code cũ).

## Hợp Đồng API (đóng băng ở Slice 1, chưa có giao diện nên đây là hợp đồng cho 1C)

Prefix `/api/v1`. Số thập phân trả dạng **chuỗi** (như `quotify-settings`). Lỗi `detail` có thể tiếng Anh; giao diện 1C map theo mã.

| Endpoint | Quyền | Thành công | Lỗi |
|---|---|---|---|
| `GET /price-alert-settings` | `price_alerts.manage` | 200: `is_enabled`, `reference_working_days`, `light_from_percent`, `medium_from_percent`, `large_over_percent`, `anomaly_percent`, `anomaly_lookback_days`, `max_trigger_delay_working_days`, `staff_lookback_days`, `dedupe_window_days`, `immediate_cap_per_scan`, `digest_hour_local`, `enabled_since`, `updated_at`, `updated_by_id` | 401, 403 |
| `PUT /price-alert-settings` | `price_alerts.manage` | 200 (đối tượng như trên). Thay toàn bộ trường cấu hình; chuyển `is_enabled` `false → true` đặt watermark (L13) trong cùng giao dịch; audit `price_alerts.settings_updated` kèm `changes[]` | 422 nếu vi phạm `0 < nhẹ < trung bình < lớn < bất thường` hoặc ngoài khoảng; 401, 403 |
| `GET /price-alert-settings/materials?limit&offset&search` | `price_alerts.manage` | 200 `{items, total}`; mỗi mục: `material_id`, `code`, `name`, `override` (`null` hoặc 4 ngưỡng), `effective` (4 ngưỡng đang áp dụng). `limit ≤ 100` | 401, 403 |
| `PUT /price-alert-settings/materials/{material_id}` | `price_alerts.manage` | 200 `{material_id, override, effective}`. Ghi đè đủ ba ngưỡng; `anomaly_percent` tùy chọn (`null` dùng mặc định). Hiệu lực từ lần quét kế tiếp, không báo lại dữ liệu cũ; audit `price_alerts.threshold_updated` | 404 vật tư; 422 (không tăng dần, hoặc ngưỡng bất thường không lớn hơn ngưỡng Lớn hiệu lực) |
| `DELETE /price-alert-settings/materials/{material_id}` | `price_alerts.manage` | 204, idempotent (bỏ ghi đè, về mặc định) | 401, 403 |
| `GET /users/me/alert-preferences` | đăng nhập | 200 `{is_enabled, min_level, effective_min_level, admin_receive_all}`; `min_level` `null` nghĩa là mặc định theo vai trò (trưởng phòng Trung bình, nhân viên Nhẹ) | 401 |
| `PUT /users/me/alert-preferences` | đăng nhập | 200 như trên. `admin_receive_all=true` chỉ admin được đặt | 403 nếu người không phải admin đặt `admin_receive_all`; 422 mức không hợp lệ |

Khi `TELEGRAM_ENABLED=false`: các `GET` vẫn trả 200 (giữ hợp đồng, như 1A), các `PUT` vẫn lưu được cấu hình nhưng engine không chạy.

## Bộ Tin Nhắn (tiếng Việt có dấu, HTML; duyệt ở Slice 0 và Slice 8)

Dữ liệu động luôn qua `escape_html`. Phần định dạng đầy đủ và ví dụ số liệu ở Mục 4.2 của tài liệu cha; 1B chốt thêm:

| Tình huống | Nội dung |
|---|---|
| Ảnh biểu đồ | Tiêu đề trong ảnh dạng `▲ TĂNG TRUNG BÌNH · Ngô hạt` hoặc `▼ GIẢM LỚN · ...` (**không emoji trong ảnh**); dải màu theo mức; 900 x 500 |
| Caption (≤ 1.024 ký tự) | `🔺🟠 TĂNG TRUNG BÌNH · Ngô hạt` / `Giá thấp nhất hôm nay: 8,150.00 VNĐ/KG (02/10/2026)` / `Kỳ 12/2026: +5.57% so với giá thấp nhất 7 ngày làm việc` |
| Tin chi tiết (≤ 4.096) | Theo Mục 4.2: lý do chính, "So sánh khác" (chỉ khi khác điểm tham chiếu), vùng tham chiếu, dòng CNF khi nguồn USD/MT (QĐ-8), chú thích "điểm giá có thể thuộc nhà cung cấp khác với lần trước", liên kết `https://quotify.honghafeed.com.vn/quotes/<id>` |
| Quá dài | Nhiều kỳ giao hàng vượt ngưỡng: cắt có chú thích "còn N kỳ nữa, xem trên web"; không bao giờ vượt 4.096 ký tự |
| Vượt trần (30 mỗi lần quét, hoặc 30 trong 10 phút cho mỗi người, L27) | Một tin tóm tắt "còn N thay đổi, xem trên web" (D5(d)) |
| Thẻ giá bất thường (β) | Theo Mục 4.2; trưởng phòng có hai nút `✅ Giá đúng` và `❌ Nhập sai` (`callback_data` `pa:ok:<uuid>` và `pa:no:<uuid>`, khoảng 42 byte, dưới 64) |
| Thẻ cho người nhập (β) | Cùng nội dung, **không nút**, thay bằng "Vui lòng kiểm tra và sửa phiếu nếu nhập sai." kèm liên kết |
| Sau khi bấm (β) | Sửa tin: `✅ Đã xác nhận giá đúng bởi <tên> lúc <HH:mm DD/MM/YYYY>` hoặc `❌ Đã đánh dấu nhập sai bởi <tên> ...`, bỏ nút |
| Bấm vào thẻ đã xử lý (β) | `answerCallbackQuery` dạng cảnh báo: "Thẻ này đã được xử lý bởi <tên>" |
| Người không có quyền bấm (β) | `answerCallbackQuery`: "Bạn không có quyền xử lý thẻ này" |
| Thẻ đã hết hạn (β) | "Thẻ này đã hết hạn. Điểm giá vẫn bị loại khỏi tính toán." |

## Lệnh Chuẩn

```bash
# Backend: từng công cụ riêng cho file mới (stack dev đang chạy)
cd backend
uv run pytest tests/test_price_alert_*.py -q --no-cov
INTEGRATION_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:55432/app uv run pytest -m integration -q --no-cov
uv run pytest -q --no-cov                                    # toàn bộ, so với baseline
uv run ruff check --no-cache <file mới> && uv run ruff format --no-cache --diff <file mới>
uv run mypy <file mới>
uv run bandit -c pyproject.toml -r app                        # so với 16 phát hiện

# Migration và worker trên dev
make migrate
docker compose restart worker                                 # worker dev KHÔNG tự reload code
docker compose --profile telegram up -d telegram-poller      # nhận tin Telegram (bước HITL)

# Dry-run replay (Slice 5)
docker compose exec backend uv run python -m app.price_alert_replay --weeks 8 --ignore-trigger-source

# Xem trạng thái engine (chỉ đọc)
docker compose exec postgres psql -U postgres -d app -c "select * from price_alert_scan_runs order by started_at desc limit 5"
```

Ghi chú: `ruff` có thể báo `Permission denied` ở `.ruff_cache` (do Docker); dùng `--no-cache`. `mypy` dùng `--cache-dir` tạm.

---

## Slice 0: Chuẩn Bị Và Chốt Điều Kiện

**Loại:** HITL | **Chặn bởi:** không | **Cỡ:** nhỏ

### Mục tiêu

Chốt các quyết định còn mở, kiểm các giả định chỉ production mới trả lời được, đo các hành vi Telegram cần gửi thật, và đồng bộ tài liệu trước khi viết code.

### Việc cần làm

1. **Chốt L1 đến L26** (Q1 đến Q7, L27 và L28 đã được người dùng chốt ngày 2026-10-04; người dùng trả lời "theo đề xuất" hoặc sửa). Ghi kết quả vào mục "Quyết Định Kỹ Thuật".
2. **Kiểm production, chỉ đọc**, trên VPS (`/opt/quotify`, nhớ `-f docker-compose.prod.yml`, database là `quotify`):
   - Role `manager` có tồn tại không và tên chính xác: `select name from roles order by 1`.
   - Số người dùng theo role và trạng thái.
   - Ai đã tải import: `select ij.entity_type, ij.task_name, u.email, count(*) from import_jobs ij left join users u on u.id = ij.created_by_id group by 1,2,3` (L17, Q7).
   - Phiếu theo người tạo: `select u.email, count(*) from quotes q join users u on u.id = q.created_by_id group by 1 order by 2 desc`. Với tài khoản seed, kiểm thêm theo ngày (`group by q.created_at::date`): phải chỉ có các ngày import, không có phiếu nhập tay rải rác (Q7, L17).
   - Tài khoản nào đang liên kết Telegram (`telegram_accounts` nối `users`, so với `AUTH_SEED_ADMIN_EMAIL`): tài khoản seed không nhận tin (L16), nên người trong nhóm pilot (Q5) phải liên kết bằng tài khoản người thật.
   - `delivery_month` khác ngày 01 và `confirmed_at` thiếu: hai truy vấn đếm.
   - Số người đã liên kết Telegram: `select count(*) from telegram_accounts where status = 'active'`.
3. **Tạo tài khoản Manager thử trên dev (L28)** qua trang Người dùng (bạn tự đặt mật khẩu, không dán vào chat), rồi liên kết Telegram của bạn vào tài khoản đó trên trang Hồ sơ (hủy liên kết hiện có của tài khoản seed trước). Dùng làm người nhận cho các thí nghiệm bên dưới nếu muốn thử tin thật theo đường nghiệp vụ.
4. **Thí nghiệm "dương" với bot dev** (cần bạn đồng ý nhận khoảng 8 tin thử, và 40 tin cho mục f). Dùng script tạm, không chạm poller sản phẩm. Ghi vào Phụ lục A:
   - (a) `sendPhoto` PNG 900 x 500 kèm caption và bàn phím inline 2 nút: hiển thị đúng không.
   - (b) Bấm nút: `callback_query` đến qua `getUpdates` khi `allowed_updates` có `callback_query` (kiểm `id`, `from`, `message.message_id`, `data`).
   - (c) `answerCallbackQuery`, `editMessageText`, `editMessageReplyMarkup` sau khi bấm; `message is not modified`.
   - (d) `callback_data` đúng 64 byte có được chấp nhận; caption đúng 1.024 ký tự và tin đúng 4.096 ký tự được chấp nhận.
   - (e) Hết hạn của `answerCallbackQuery` (bấm nút rồi đợi quá lâu mới trả lời).
   - (f) **T6:** 40 tin liên tiếp tới chat riêng: có 429 không, `retry_after` bao nhiêu.
5. **Đồng bộ tài liệu:** sửa tài liệu cha theo các dòng 1 đến 4 của mục "Độ Lệch" (head, D2 mục 5, D6 đơn vị, nhận biết import); thêm thuật ngữ giá vào `CONTEXT.md` (Điểm giá, Chuỗi, Cửa sổ tham chiếu, Ngày làm việc, Biến động giá, Mức biến động, Ngưỡng cảnh báo, Nguồn kích hoạt, Giá bất thường, Sự kiện, Tin, Bản tin tổng hợp, Trưởng phòng, kèm cột "Tránh"); ghi chú phạm vi ở `Requirements.txt` mục 3.9 (thông báo trung tính, không tự kết luận) và "Nhật ký thay đổi" của `quotify-implementation-plan.md`.

### Tiêu chí chấp nhận

- [x] L1 đến L26 được chốt. Q1 đến Q7, L27, L28 và L1 đến L26 đã chốt 2026-10-04.
- [x] Tài khoản Manager thử trên dev tồn tại ("Quản lý phòng Mua", role `manager`, đang hoạt động) và đã liên kết Telegram (kiểm DB 2026-10-04). Còn lại: đưa email vào `PRICE_ALERT_RECIPIENT_EMAILS` của `.env` dev khi Slice 1 thêm biến này.
- [x] Kết quả kiểm production đã ghi (2026-10-04, mục "Kết quả kiểm production" bên dưới): role trưởng phòng là `manager`; mọi import do tài khoản seed tải; tài khoản seed chỉ có phiếu ngày import; production chưa có liên kết Telegram nào đang hiệu lực.
- [x] Phụ lục A điền xong các mục (a) đến (f) (2026-10-04). Nếu kết quả khác giả định (ví dụ giới hạn tốc độ) thì sửa quyết định liên quan trước Slice 8.
- [x] Tài liệu cha, `CONTEXT.md`, `Requirements.txt`, `quotify-implementation-plan.md` được cập nhật (chờ bạn commit).

### Kết quả kiểm production (chỉ đọc, 2026-10-04)

Truy vấn nằm ở `docs/quotify/analysis-1b/sql/slice0_production_check.sql`.

| Điều kiểm | Kết quả | Hệ quả |
|---|---|---|
| Tên role | `admin`, `manager`, `user` | Migration quyền gán cho `manager` đúng tên (RR-41 giải quyết) |
| Người dùng | 1 tài khoản seed (admin) và 9 người thật, đều `active` | Giống dev. Trên dev 9 người này là 7 `user` và 2 `manager` (mỗi người một role); production không kiểm riêng từng người, sẽ thấy số dòng gán quyền khi chạy migration ở Slice 11 |
| Người tải import | 4 job (vật tư, nhà cung cấp, 2 lần nhập lùi báo giá) đều do tài khoản seed | Quy ước Q7 đúng (L17) |
| Phiếu của tài khoản seed | 2.847 phiếu, tất cả tạo ngày 2026-08-19 | Không có phiếu nhập tay rải rác (RR-38) |
| Phiếu của người khác | 595 phiếu của 7 người, từ 20/08 đến 04/10/2026 (dev có 587 phiếu đến 02/10) | Dev chỉ cũ hơn vài ngày; số liệu Phụ lục C giữ nguyên |
| `delivery_month` khác ngày 01 | 0 | Khóa chuỗi theo tháng an toàn (L1) |
| Version `confirmed` thiếu `confirmed_at` | 0 | Truy vấn quét L3 không bỏ sót vì thiếu mốc |
| Liên kết Telegram | 1 liên kết, của tài khoản seed, đã thu hồi (lần thử khi go-live 1A) | **Chưa ai trên production liên kết Telegram.** Trước pilot (Q5) người nhận phải liên kết bằng tài khoản người thật (không phải tài khoản seed) |

### Rollback

Không có (chỉ đọc và tài liệu).

---

## Slice 1: Dữ Liệu Nền, Quyền Và API Cấu Hình Chung

**Loại:** AFK | **Chặn bởi:** Slice 0 | **Cỡ:** vừa

### Mục tiêu

Người có quyền `price_alerts.manage` đọc và ghi cấu hình chung, bật tính năng (đặt watermark) bằng API. Quyền được cấp cho `manager` và `admin` bằng migration. Hợp đồng API được đóng băng cho 1C.

### Việc cần làm

1. **Migration 1** (L2, tài liệu cha 4.5): `price_alert_settings` (singleton, CHECK như tài liệu cha, hàng mặc định tự chèn bằng migration giống `quotify_settings`), `price_alert_scan_state` (singleton, có cột `last_run_at`, L27), `price_alert_scan_runs`, `price_alert_scanned_versions`, `price_alert_material_thresholds`, `user_alert_preferences`. Viết tay, `down_revision = "20261004_1100"`. Đăng ký model ở `models/__init__.py` và `db/base.py`.
2. **Migration 2 (quyền, L14):** tự `INSERT` hai mã vào `permissions` rồi gán cho `manager` và `admin`, chịu được thiếu role; `downgrade` xóa đúng các dòng đó.
3. Thêm hai mã vào `BASE_PERMISSION_CODES` (list literal). Thêm khóa audit vào allow-list (L15).
4. `services/price_alert_settings_service.py` và `schemas/price_alerts.py`, `api/v1/price_alerts.py` với `GET` và `PUT /price-alert-settings` theo hợp đồng. Chuyển `is_enabled` `false → true` đặt `watermark_confirmed_at` và `enabled_since` (L13). Audit `price_alerts.settings_updated` kèm `changes[]`. Đăng ký router. Không sửa `quotify_settings`.

### Thứ tự test (tracer trước)

1. **Tracer (API, mock session như `test_quotify_settings_api.py`):** người có `price_alerts.manage` gọi `PUT` bật tính năng → 200, giá trị lưu, audit được ghi (metadata có `changes[]`, mọi giá trị là chuỗi), `GET` trả lại.
2. **Tích hợp DB thật:** `false → true` đặt watermark bằng thời điểm bật; `true → true` không đổi watermark; `true → false → true` đặt lại.
3. 403 khi thiếu quyền, 401 khi chưa đăng nhập. 422 khi `0 < nhẹ < trung bình < lớn < bất thường` bị vi phạm hoặc ngoài khoảng.
4. **Migration quyền** (DB tạm, chạy `alembic upgrade`): có role `manager` thì được gán hai quyền; không có thì ghi 0 dòng và không lỗi; chạy trước seed vẫn tạo `permissions`; chạy hai lần không lỗi; `admin` được gán; `downgrade` dọn sạch.
5. `test_permission_inventory.py` qua. `test_audit_log_service.py`: khóa mới được giữ, khóa chứa `token` vẫn bị che.
6. Upgrade rồi downgrade từng migration trên DB tạm, `alembic heads` đúng một head.

### Cách xác minh thật

```bash
make migrate && docker compose exec backend uv run alembic downgrade -2 && make migrate && docker compose exec backend uv run alembic heads
docker compose exec postgres psql -U postgres -d app -c "select code from permissions where code like 'price_alerts.%'" -c "select r.name, p.code from role_permissions rp join roles r on r.id=rp.role_id join permissions p on p.id=rp.permission_id where p.code like 'price_alerts.%'"
# đăng nhập bằng tài khoản có quyền (không in mật khẩu), rồi:
curl -s -X PUT localhost:8000/api/v1/price-alert-settings -H "Authorization: Bearer $AT" -H 'Content-Type: application/json' -d '{...}'
```

### Tiêu chí chấp nhận

- [x] Hợp đồng `GET`/`PUT /price-alert-settings` đóng băng như mục Hợp Đồng API (chờ bạn commit làm căn cứ cho 1C). Phần ngưỡng theo vật tư và tùy chọn cá nhân của hợp đồng làm ở Slice 6.
- [x] `manager` và `admin` có quyền mới trên dev sau `make migrate` (kể cả khi chưa chạy seed; có test migration).
- [x] Bật tính năng đặt watermark và ghi audit; cron chưa tồn tại nên chưa có tác dụng phụ.
- [x] Baseline không xấu hơn; mọi file mới sạch ruff, mypy, bandit.

### Kết quả (2026-10-04, nhánh `feat/telegram-1b-alpha`)

- **Code mới:** `models/price_alert.py` (sáu model), hai migration `20261004_1200` và `20261004_1300`, `schemas/price_alerts.py`, `services/price_alert_settings_service.py`, `api/v1/price_alerts.py` (đăng ký ở router). Sửa tối thiểu: `models/__init__.py`, `db/base.py`, `auth/seed_data.py` (hai mã quyền), `tests/integration/db_helpers.py` (thêm `create_material`, `create_confirmed_quote_version`), `tests/integration/conftest.py` (fixture `empty_database_url`).
- **Test mới (74):** 30 API (service giả: hợp đồng, 401/403, 422, audit), 34 PostgreSQL thật (watermark bật/tắt/bật lại, hai lần bật đồng thời, CHECK, singleton, FK `CASCADE`/`SET NULL`), 7 migration trên DB trống (quyền có/thiếu `manager`, chạy trước seed, tái sử dụng quyền đã có, chạy lại, downgrade, vòng upgrade/downgrade/upgrade), 1 một head, 1 audit giữ `changes[]`, 1 quyền không cấp cho role `user`. Đã chạy thử đột biến (bỏ `FOR UPDATE`, đặt watermark mỗi lần, bỏ `updated_by_id`): cả ba bị test bắt.
- **Baseline:** pytest 633 pass (559 + 74, có DB); ruff 62, mypy 13, bandit 16 (không đổi, không lỗi ở file mới).
- **Xác minh thật trên dev:** `make migrate`, `downgrade -2`, `make migrate` đúng một head `20261004_1300`; `manager` và `admin` có cả hai quyền; bằng token của tài khoản Manager thử: `GET` 200, `PUT` bật đặt `enabled_since`, đổi ngưỡng giữ nguyên `enabled_since`, ngưỡng sai thứ tự và ngoài khoảng trả 422, không đăng nhập trả 401. Đã dọn dữ liệu thử theo đúng ID (3 dòng audit, watermark, người sửa cuối).
- **Quyết định bổ sung trong lúc làm:** (a) khoảng hợp lệ của các trường số (ngày làm việc tham chiếu 1 đến 30; số ngày xét bất thường 1 đến 365; trễ tối đa của nguồn kích hoạt 0 đến 30; số ngày nhân viên 1 đến 365; cửa sổ chống lặp 0 đến 90; trần mỗi lần quét 1 đến 500; giờ bản tin 0 đến 23; phần trăm Nhẹ/Trung bình/Lớn ≤ 100) được ghi cả ở schema (422) lẫn CHECK của DB; (b) `PUT` không có thay đổi thì không ghi audit và không đổi người sửa cuối; (c) hai hàng mặc định có id cố định `...0a1` (cấu hình) và `...0a2` (trạng thái quét); (d) quyền tạo kèm `description` tiếng Việt.
- **Phát hiện:** test cũ `test_unlinking_revokes_the_account_and_is_audited` thỉnh thoảng fail ngẫu nhiên vì kiểm chuỗi con "555" trong `repr` có UUID; đã sửa (xem `bugPatterns.md`).
- **Còn lại cho slice sau:** các endpoint ngưỡng theo vật tư và `users/me/alert-preferences` (Slice 6); thêm khóa audit cho `threshold_updated`, `anomaly_reviewed`, `scan_completed` (Slice 6, 13, 5).

### Rollback

`PUT is_enabled=false`. Dev: `alembic downgrade -2`. Production: không downgrade, để bảng.

---

## Slice 2: Ngày Làm Việc Và Điểm Giá (Daily-Min)

**Loại:** AFK | **Chặn bởi:** Slice 1 | **Cỡ:** vừa

### Mục tiêu

Có hai khối nền tảng kiểm thử được độc lập: tính ngày làm việc và cửa sổ tham chiếu (hàm thuần), và hàm điểm giá của một chuỗi trong khoảng ngày (SQL).

### Việc cần làm

1. `services/working_days.py` (L5): `is_working_day`, `working_days_between`, `reference_window(day, n)`. Hàm thuần, không đụng DB.
2. `services/daily_min_series.py` (L6): `get_daily_min_series(...)` trả danh sách điểm `(received_date, price, line_id, version_id)`, điều kiện chuẩn của dashboard, `date_trunc('month', delivery_month)`, tham số `exclude_line_ids`.
3. Helper dựng dữ liệu cho test tích hợp trong `tests/integration/db_helpers.py`: vật tư, nhà cung cấp, phiếu, version, dòng (có `status`, `received_date`, `confirmed_at`, `created_by_id`, `price_converted_vnd_per_kg`).

### Thứ tự test (tracer trước)

1. **Tracer (thuần):** điểm mới thứ Sáu 02/10/2026 thì cửa sổ 7 ngày làm việc là 23/09 đến 01/10.
2. Điểm mới thứ Hai, thứ Bảy, Chủ Nhật; cửa sổ vắt qua cuối tuần; `working_days_between(thứ Sáu, thứ Hai) = 1`; không đếm thứ Bảy, Chủ Nhật; cùng ngày = 0.
3. **Tích hợp (PostgreSQL thật):** chuỗi có nhiều dòng trong một ngày thì điểm là giá thấp nhất; hai nhà cung cấp cùng ngày vẫn một điểm.
4. Loại version `draft` và `superseded`, phiếu đã hủy; `exclude_line_ids` loại đúng dòng và **tính lại** điểm của ngày (ví dụ Threonine 15/09: loại dòng 970 thì điểm là 26.000); ngày hết dòng thì không có điểm.
5. `delivery_month` không phải ngày 01 vẫn gom đúng chuỗi.
6. `received_date` cuối tuần vẫn là điểm. Ngày tính theo `received_date`, không theo giờ chốt.
7. Đối chiếu với truy vấn gốc trên dữ liệu dev (kết quả giống nhau).

### Cách xác minh thật

So sánh `get_daily_min_series` với truy vấn SQL độc lập cho 5 chuỗi lớn nhất trên DB dev; `EXPLAIN ANALYZE` không vượt vài mili giây (đo hiện tại 0,65 đến 3,4 ms).

### Tiêu chí chấp nhận

- [x] Hàm thuần có test biên đầy đủ; hàm SQL có test tích hợp và khớp truy vấn gốc trên dev.
- [x] Không sửa dashboard (hai nơi có thể lệch nhau; ghi nhận ở rủi ro RR-42).
- [ ] Baseline không xấu hơn.

### Kết quả (2026-10-04)

- **Code:** `services/working_days.py` (`is_working_day`, `working_days_between` đếm `(start, end]`, `reference_window(day, working_days=7)` trả `[start, end]` với `end = day - 1` nên điểm cuối tuần nằm giữa vẫn là điểm tham chiếu), `services/daily_min_series.py` (`get_daily_min_series(session, *, material_id, delivery_month, start, end, exclude_line_ids)` trả `DailyMinPoint(received_date, price, line_id, version_id)`; điều kiện như dashboard gồm `confirmed`, `confirmed_at` không NULL, phiếu chưa hủy; tie-break giá, `confirmed_at`, id). Helper `create_priced_line` ở `db_helpers.py`.
- **Test mới (42):** 28 hàm thuần, 11 tích hợp. pytest 675 pass; ruff 62, mypy 13, bandit 16 không đổi.
- **Dev:** 5 chuỗi lớn nhất (460 đến 577 dòng, 191 đến 203 điểm) khớp truy vấn SQL độc lập; khoảng 9 ms cho toàn lịch sử (cửa sổ 7 ngày nhỏ hơn nhiều).
- **Rà soát bằng agent độc lập:** thêm điều kiện `confirmed_at` không NULL (thiếu so với dashboard), tie-break xác định, test hòa giá, test giá quy đổi khác giá gốc, test ngày chốt khác ngày nhận, `working_days` mặc định 7. Chưa làm: bọc `date_trunc` trên cột `delivery_month` làm mất index (đo 9 ms, chấp nhận; xét lại ở 1C).
- Tên tham số là `start`/`end` (L6 ghi `date_from`/`date_to`); Slice 3 dùng đúng tên này.

### Rollback

Xóa các file mới (chưa có tham chiếu từ nơi khác).

---

## Slice 3: Lõi Đánh Giá Biến Động (R1, R2, R3)

**Loại:** AFK | **Chặn bởi:** Slice 2 | **Cỡ:** vừa

### Mục tiêu

Hàm thuần nhận điểm mới, các điểm tham chiếu trong cửa sổ và ngưỡng, trả về kết quả đánh giá: hướng, mức, lý do chính, các phần trăm, vùng tham chiếu, dòng "so sánh khác". Không đụng DB, không đụng Telegram.

### Việc cần làm

1. `services/price_alert_rules.py`: `evaluate_change(new_point, prior_points, thresholds) -> ChangeEvaluation | None` (D2, D4, L7). Kết quả là dataclass đóng băng, giá trị `Decimal`.
2. Quy tắc nhất quán hướng: hướng theo R1; R2 chỉ áp dụng khi R1 tăng, R3 chỉ khi R1 giảm; mức là mức cao nhất của các quy tắc áp dụng; hòa `|%|` ưu tiên R1; không in dòng phụ nếu trùng điểm tham chiếu với lý do chính; cần ít nhất 1 điểm trước; giá bằng điểm trước thì không có tin; bảo vệ `ref = 0`.

### Thứ tự test (tracer trước)

1. **Tracer:** ví dụ 1 của D2 (7,900 · 7,720 · 7,800 → 8,150) cho Tăng Trung bình, lý do chính R2 (+5,57%), dòng phụ R1 (+4,49%).
2. Ví dụ 2 (giảm, R3 là lý do chính, −10,58%, mức Lớn) và ví dụ 3 (hướng ngược: R2 bỏ qua, R3 trùng điểm tham chiếu nên không in dòng phụ, mức Nhẹ).
3. Biên: đúng 2,5 là Nhẹ, đúng 5 là Trung bình, đúng 10 là Trung bình, 10,0001 là Lớn, 2,4999 không gửi; **4,996% là Nhẹ** (không làm tròn trước khi so).
4. Hòa `|%|` thì lý do chính là R1. Chỉ 1 điểm trước. Giá bằng điểm trước. `ref = 0`. Giá không dương.
5. **Thuộc tính:** khi tăng thì `|R2| ≥ |R1|`; khi giảm thì `|R3| ≥ |R1|`; hướng của kết quả luôn bằng dấu của R1; mức của kết quả không thấp hơn mức của từng quy tắc áp dụng (dùng `hypothesis` nếu dự án đã có, nếu chưa thì sinh ngẫu nhiên với hạt giống cố định).
6. Ngưỡng ghi đè theo vật tư thay đổi mức đúng như kỳ vọng.

### Tiêu chí chấp nhận

- [x] Ba ví dụ D2, các biên và thuộc tính đều xanh.
- [x] Hàm không import `sqlalchemy`, `httpx`, hay đọc thời gian hệ thống.
- [x] File mới sạch ruff, mypy (strict), bandit; baseline không xấu hơn.

### Kết quả (2026-10-04)

- `services/price_alert_rules.py`: `PricePoint`, `Thresholds`, `ChangeEvaluation`, `evaluate_change(new_point, prior_points, thresholds)`. Hàm thuần (có test kiểm import chỉ gồm thư viện chuẩn và không đọc giờ hệ thống).
- 32 test: ba ví dụ D2, mọi biên, hòa |%|, hòa giá min/max, đối chiếu một cài đặt độc lập trên 3.000 chuỗi ngẫu nhiên (hạt giống cố định, không dùng `hypothesis` vì dự án chưa có). pytest 707 pass; ruff 62, mypy 13 và bandit 16 không đổi.
- **Rà soát agent độc lập đã bổ sung:** chỉ dùng điểm trước ngày điểm mới; trùng ngày thì lấy giá thấp nhất để kết quả không phụ thuộc thứ tự; điểm giá 0 bị bỏ có chủ ý (L7); thêm test R2 ở biên và các trường ngày. Thứ tự ngưỡng không kiểm trong hàm vì đã kiểm ở API cấu hình và CHECK của DB (Slice 1).

### Rollback

Xóa file mới.

---

## Slice 4: Nguồn Kích Hoạt Và Dòng Ứng Viên

**Loại:** AFK | **Chặn bởi:** Slice 2 | **Cỡ:** vừa (có thể làm song song với Slice 3)

### Mục tiêu

Biết **version nào được quét** và **dòng nào của nó tham gia đánh giá**: nguồn kích hoạt (D6), dòng ứng viên của bản điều chỉnh (L1), version đã quét (L2).

### Việc cần làm

1. `services/price_alert_candidates.py`: (a) `select_versions_to_scan(session, watermark, now)` theo L3; (b) `is_trigger_source(version, seed_user_id, max_delay)` (D6: không phải tài khoản seed, **NULL-safe**, trễ không quá 3 ngày làm việc tính từ `received_date` đến **ngày VN** của `confirmed_at`, phiếu chưa hủy); (c) `select_candidate_lines(...)` (L1) là hàm thuần nhận hai danh sách dòng.
2. Ghi `price_alert_scanned_versions` (L2) khi đã xử lý (làm ở Slice 5, hàm ghi để đây).

### Thứ tự test (tracer trước)

1. **Tracer (tích hợp):** phiếu do người thật tạo, chốt cùng ngày: `select_versions_to_scan` trả version đó và `is_trigger_source` là đúng.
2. Tài khoản seed bị loại; `created_by_id` NULL **không** bị loại nhầm; người khác nhưng cùng là admin vẫn được xem là người thật.
3. Trễ 0, 3 (được), 4 (không); nhập thứ Sáu chốt thứ Hai là trễ 1; chốt lúc 23:30 giờ VN (nằm ngày UTC khác) tính đúng ngày VN.
4. Version không phải nguồn vẫn được trả về để làm điểm tham chiếu và để đánh giá bất thường (cờ `is_trigger_source=false`).
5. **Bản điều chỉnh:** chỉ dòng đổi giá và dòng thêm là ứng viên; dòng bỏ không tạo ứng viên; **tập đa**: hai dòng cùng giá trong bản nguồn mà bản mới còn một dòng, và trường hợp trùng khóa trong một version; `received_date` đổi thì mọi dòng là ứng viên; bản nguồn chưa quét thì mọi dòng là ứng viên; version đầu thì mọi dòng là ứng viên; `delete_confirmed_line` (cùng giá còn lại) thì không có ứng viên.
6. Phiếu đã hủy bị bỏ qua; phiếu hủy rồi kích hoạt lại không phát tin quá khứ.

### Tiêu chí chấp nhận

- [x] Mọi trường hợp của L1, L3 và D6 có test (thuần hoặc PostgreSQL thật).
- [x] Số version đủ điều kiện D6 trên DB dev khớp số đo (283 version và 1.030 dòng, theo `received_date` đến ngày chốt) khi chạy hàm trên dữ liệu thật.
- [x] Baseline không xấu hơn.

### Kết quả (2026-10-04)

- `services/price_alert_candidates.py`: `select_versions_to_scan` (L3), `trigger_delay_working_days` và `is_trigger_source` (D6, giờ VN, NULL-safe), `select_candidate_lines` (L1, hàm thuần), `resolve_candidate_lines`, `record_scanned_version` (L2, idempotent). Helper test `create_quote_shell`, `create_version_with_lines`.
- 30 test mới (20 thuần, 10 PostgreSQL thật). pytest 737 pass; ruff 62, mypy 13, bandit 16 không đổi. Đột biến (bỏ trừ tập đa, bỏ overlap 5 phút, bỏ đổi múi giờ VN) đều bị test bắt.
- **Dev:** chạy trên dữ liệu thật cho đúng **283 version nguồn kích hoạt và 1.030 dòng**, khớp số đo.
- **Rà soát agent độc lập đã bổ sung:** một version mới có thể thay thế nhiều version cũ (`confirm_version` lặp qua danh sách), nên nguồn được lấy là tập mọi version trỏ về nó: chỉ so tập đa khi mọi nguồn đã quét và cùng `received_date`; test biên overlap nghiêm ngặt; test phiếu hủy rồi kích hoạt lại không phát lại version chốt trước watermark (nhờ L3, cần watermark của Slice 5 để đúng).
- **Lưu ý cho Slice 5:** `resolve_candidate_lines` đọc nguồn bằng truy vấn riêng, nên lần quét phải chạy dưới khóa advisory (L8e) và cùng một giao dịch; D6 mục 3 (phiếu chưa hủy) chỉ xét lúc chọn version.

### Rollback

Xóa file mới.

---

## Slice 5: Quét An Toàn, Sự Kiện, Cron Và Dry-Run Replay

**Loại:** AFK | **Chặn bởi:** Slice 3, Slice 4 | **Cỡ:** lớn (vẫn là một lát cắt: từ version được chốt đến dòng sự kiện trong DB)

### Mục tiêu

Chốt một version trên dev thì sau tối đa một chu kỳ quét (30 giây) có **dòng sự kiện** đúng trong DB (chưa gửi Telegram). Có lệnh dry-run để đo tải trên dữ liệu thật mà không ghi gì.

### Việc cần làm

1. **Migration 3:** `price_alert_events` (tài liệu cha 4.5, gồm các cột β). Model và đăng ký.
2. `services/price_alert_scan.py`: `PriceAlertScanService.run_once(now)` (L3, L8): kiểm cờ (L13), `pg_try_advisory_xact_lock`, chọn version, mỗi version một `begin_nested()`, lọc ứng viên, lấy điểm tham chiếu (`get_daily_min_series`, cửa sổ 7 ngày làm việc), `evaluate_change`, chống lặp 14 ngày và leo thang (D5(a)), ghi `price_alert_events` bằng `INSERT ... ON CONFLICT DO NOTHING`, ghi `price_alert_scanned_versions` và, chỉ khi quét ≥ 1 version hoặc có lỗi, `price_alert_scan_runs` (L27); luôn cập nhật `scan_state.last_run_at`; tiến watermark. Lỗi một version ghi vào `scan_runs` và bỏ qua.
3. `worker.py`: cron `poll_price_alerts` mỗi 30 giây, `second={0, 30}` (L8, L27), `timezone = ZoneInfo(settings.app_timezone)`; **không** gửi Telegram ở slice này.
4. `app/price_alert_replay.py` (L26): chạy engine trên DB trong giao dịch không bao giờ commit, in số liệu theo tuần.
5. `worker-test` ép `TELEGRAM_ENABLED=false` và token rỗng (L20).

### Thứ tự test (tracer trước)

1. **Tracer (tích hợp):** dựng chuỗi có 3 điểm trước, chốt version mới có giá +5,57% so với đáy, gọi `run_once` → đúng một dòng `price_alert_events` (`kind='change'`, mức Trung bình, tăng, lý do R2, các trường giá và ngày đúng), một dòng `scanned_versions`, một dòng `scan_runs`, watermark tiến.
2. Chạy lại `run_once` không tạo sự kiện thứ hai (idempotent). Lần chạy không có version nào **không** tạo dòng `scan_runs` nhưng cập nhật `last_run_at`. Chạy hai tiến trình cùng lúc (hai kết nối): chỉ một tiến trình quét, tiến trình kia thoát.
3. **Chồng lấp:** version có `confirmed_at` sớm hơn watermark nhưng commit muộn vẫn được quét. **Cô lập lỗi:** một version có giá 0 không chặn các version khác và watermark vẫn tiến; lỗi được ghi.
4. **Bật cờ sau vài tuần:** dữ liệu cũ hơn thời điểm bật không sinh sự kiện. Tắt cờ thì cron không làm gì.
5. Chống lặp: cùng (chiều, mức) trong 14 ngày bị bỏ; leo thang hoặc đổi chiều thì tạo sự kiện mới; mức Nhẹ được tính là đã gửi. Bản điều chỉnh có nguồn chưa quét. `delete_confirmed_line` không sinh sự kiện.
6. `WorkerSettings.timezone` bằng múi giờ VN; hàm cron được đăng ký với `second={0, 30}`, mặc định `unique`.
7. **Dry-run:** chạy xong số dòng các bảng `price_alert_*` không đổi (giao dịch bị hủy); in bảng theo tuần.

### Cách xác minh thật

```bash
docker compose restart worker       # worker dev không tự reload code
# bật tính năng bằng API (Slice 1), chốt một phiếu thử trên giao diện bằng tài khoản Manager thử (L28; phiếu của tài khoản seed bị loại khỏi nguồn kích hoạt, Q7), đợi khoảng 40 giây
docker compose exec postgres psql -U postgres -d app -c "select kind, level, direction, rule, percent_change, price_new, price_ref from price_alert_events order by created_at desc limit 5" -c "select * from price_alert_scan_runs order by started_at desc limit 3" -c "select last_run_at, watermark_confirmed_at from price_alert_scan_state"
docker compose exec backend uv run python -m app.price_alert_replay --weeks 8
```

Chạy replay với D6 và so với Phụ lục C (khoảng 30,2 / 16,9 / 6,8 mỗi tuần).

### Tiêu chí chấp nhận

- [x] Chốt phiếu thật trên dev sinh đúng sự kiện sau tối đa một chu kỳ quét (30 giây), không trùng.
- [x] Để worker chạy 1 giờ không có phiếu mới: không có dòng `scan_runs` nào được thêm, `last_run_at` luôn mới hơn 1 phút (L27).
- [x] Hai tiến trình quét song song chỉ một chạy (test trên PostgreSQL thật).
- [x] Replay chạy xong, không để lại dữ liệu, và số liệu nằm trong ±15% của Phụ lục C (cổng chính thức ở Slice 10).
- [x] `worker-test` không còn dùng được Telegram thật. Baseline không xấu hơn.
- [x] Chạy `agent-task-close.sh`, cập nhật `memory-bank/`.

### Kết quả (2026-10-04)

- **Code mới:** migration `20261004_1400` và model `PriceAlertEvent` (có cột `sequence_number` tự tăng để biết sự kiện nào mới nhất khi cùng `created_at`); `services/price_alert_scan.py` (`PriceAlertScanService.run_once`, `scan_versions`, `load_thresholds`, `get_seed_user_id`); cron `poll_price_alerts` ở `worker.py` (`second={0, 30}`, `timezone` VN, `configure_logging` ở `startup`); `app/price_alert_replay.py`; `worker-test` ép tắt Telegram.
- **Thiết kế đã chốt khi làm:** service chỉ `flush`, cron `commit`, replay `rollback`; khóa advisory kiểu transaction giữ đến lúc commit; một version lỗi vẫn được đánh dấu đã quét (không lặp mỗi 30 giây), lỗi nằm ở `scan_runs`; sự kiện chỉ tạo khi chính version đó giữ giá thấp nhất của ngày (báo giá thứ hai không hạ giá thấp nhất thì không có sự kiện); chống lặp so với sự kiện gần nhất của chuỗi (cùng chiều và mức trong cửa sổ, mức Nhẹ tính là đã gửi); watermark không vượt `now`; `last_run_at` cập nhật mỗi lần lấy được khóa, bảng `scan_runs` chỉ có dòng khi có việc.
- **Test mới (36):** 23 PostgreSQL thật cho quét (tracer đủ trường, idempotent, cờ tắt, hai kết nối, chồng lấp 5 phút, cô lập lỗi kể cả lỗi DB, bật cờ sau vài tuần, chống lặp và cửa sổ, leo thang, đổi chiều, bản điều chỉnh, ghi đè ngưỡng, giới hạn batch, replay), 7 cho worker (múi giờ VN, `second={0,30}`, cách nhau 30 giây, task). pytest 766 pass; ruff 62, mypy 13, bandit 16 không đổi. Đột biến (bỏ kiểm chủ sở hữu giá thấp nhất ngày, đổi `<=`, bỏ so mức, watermark `min`, bỏ kiểm nguồn kích hoạt) đều bị bắt.
- **Replay trên dev (nhiều ngày thật, D6 bật):** 207 sự kiện theo chuỗi (32,9 mỗi tuần), 115 vật tư-ngày (18,3), 56 Trung bình và Lớn (8,9). So với engine tham chiếu **không có chặn bất thường** (đúng với đợt α): 218 / 116 / 57, lệch dưới 5%. So với Phụ lục C (có chặn bất thường, đợt β): 30,2 / 16,9 / 6,8, lệch +9% / +8% / +31%; phần chênh Trung bình và Lớn là các điểm bất thường sẽ bị loại ở đợt β. Cổng ±15% chính thức ở Slice 10 nên so với số không chặn bất thường cho đợt α.
- **Thật trên dev:** worker khởi động có `poll_price_alerts` và cron; bật cờ rồi `last_run_at` tiến đúng :00 và :30, không có dòng `scan_runs` nào khi rảnh.
- **Rà soát agent độc lập đã xử lý:** thứ tự "sự kiện gần nhất" không phụ thuộc UUID ngẫu nhiên (cột tự tăng); test UNIQUE giờ thật sự chỉ còn chỉ mục chặn; lỗi DB trong savepoint không làm hỏng lô; nhánh đánh dấu lỗi không làm thoát cả lần quét; replay có `lock_timeout` 5 giây và `statement_timeout` 120 giây, đếm đúng phần từ `since`; watermark bị chặn bởi `now`.
- **Giới hạn đã biết của replay:** chỉ tính version `confirmed` hiện tại (bỏ các version sau đó bị thay thế), nên số liệu là xấp xỉ; replay xóa rồi hoàn tác các bảng sự kiện trong giao dịch (giữ khóa ngắn); khi 1C thêm bảng tin có FK, cần đổi sang lọc theo tập version.

### Rollback

`PUT is_enabled=false` hoặc tắt `TELEGRAM_ENABLED`. Dev: `alembic downgrade -1`. Production: không downgrade.

---

## Slice 6: Người Nhận, Tùy Chọn Cá Nhân Và Ghi Đè Ngưỡng Theo Vật Tư

**Loại:** AFK | **Chặn bởi:** Slice 1 (dùng song song được với Slice 5) | **Cỡ:** vừa

### Mục tiêu

Biết **ai** nhận tin của một vật tư (D7 đến D10, L12, L16) và cấu hình được ngưỡng theo vật tư và tùy chọn cá nhân bằng API.

### Việc cần làm

1. `services/price_alert_recipients.py`: `resolve_recipients(session, material_id, event_level, kind, now)`.
2. API (hợp đồng ở mục trên): `GET/PUT/DELETE /price-alert-settings/materials...`, `GET/PUT /users/me/alert-preferences`. Audit `price_alerts.threshold_updated`.
3. Engine đọc ngưỡng hiệu lực (ghi đè theo vật tư hoặc mặc định) khi phân mức.

### Thứ tự test (tracer trước)

1. **Tracer (tích hợp):** một trưởng phòng đã liên kết Telegram nhận sự kiện mức Trung bình của một vật tư bất kỳ.
2. Trưởng phòng không nhận mức Nhẹ theo mặc định; nhân viên nhận vật tư mình đã nhập trong 90 ngày, không nhận vật tư chưa nhập, không nhận nếu phiếu đã hủy, version `superseded` hay nháp, không nhận nếu ngoài 90 ngày; admin chỉ nhận khi bật `admin_receive_all`; tài khoản seed bị loại (NULL-safe).
3. Loại người dùng không `ACTIVE`, người chưa liên kết, liên kết `blocked`; `min_level` cá nhân; cờ tắt cá nhân; **danh sách pilot** (`PRICE_ALERT_RECIPIENT_EMAILS`) giữ đúng người, người khác `skipped` lý do `pilot`.
4. **Hai định nghĩa người nhập:** dựng dữ liệu `quotes.created_by_id` khác `quote_versions.created_by_id` (dữ liệu thật chưa từng khác) và kiểm D8 dùng cột nào, D12 dùng cột nào.
5. API: ghi đè đủ ba số, từ chối không tăng dần hoặc ngưỡng bất thường không lớn hơn ngưỡng Lớn hiệu lực; `DELETE` idempotent; đổi ngưỡng không báo lại dữ liệu cũ; `admin_receive_all` bị từ chối cho người không phải admin; audit `changes[]`.

### Tiêu chí chấp nhận

- [x] Bảng người nhận D7 đến D10 có test đủ từng dòng.
- [x] API ngưỡng và tùy chọn đóng băng như hợp đồng.
- [x] Baseline không xấu hơn.

### Kết quả (2026-10-04)

- **Người nhận** (`services/price_alert_recipients.py`, `resolve_recipients`): trưởng phòng (quyền `price_alerts.receive_all`) nhận mọi vật tư từ Trung bình; nhân viên nhận vật tư mình là `quotes.created_by_id` trong 90 ngày (phiếu hủy, version nháp hoặc `superseded` không tính), từ Nhẹ; admin chỉ khi bật `admin_receive_all` (kiểm admin **trước** quyền vì migration cho admin cả `receive_all`); tài khoản seed bị loại NULL-safe; chỉ người `ACTIVE` có liên kết `active`; cờ cá nhân và `min_level`; thẻ bất thường (`kind='anomaly'`) bỏ qua mức tối thiểu, chỉ trưởng phòng, admin đã bật và người nhập (version) nhận; danh sách pilot `PRICE_ALERT_RECIPIENT_EMAILS` (cấu hình mới, ví dụ ở hai file `.env`) giữ đúng người, người khác trả `skipped` lý do `pilot`. Trưởng phòng đồng thời là người nhập chỉ nhận một mục (L28).
- **API** (do một agent làm trong worktree riêng, đã gộp): `GET/PUT/DELETE /price-alert-settings/materials`, `GET/PUT /users/me/alert-preferences`; audit `price_alerts.threshold_updated`; `anomaly_percent` null so với ngưỡng mặc định; `DELETE` idempotent; route `/users/me/alert-preferences` đăng ký trước `/users/{id}` (có test thứ tự). Mức tối thiểu hiệu lực mặc định là Trung bình cho người có `receive_all` hoặc role `manager` (và admin), còn lại Nhẹ.
- **Engine đọc ngưỡng hiệu lực** đã có từ Slice 5 (`load_thresholds`), có test.
- **Test mới (77):** 25 người nhận và cấu hình, 52 API ngưỡng và tùy chọn. pytest 843 pass; ruff 62, mypy 13, bandit 16 không đổi. Đột biến (admin kiểm sau trưởng phòng, bỏ loại seed, bỏ cửa sổ 90 ngày) đều bị bắt. Kiểm thật trên dev bằng token Manager thử: danh sách vật tư 22 mục có `effective`, tùy chọn mặc định Trung bình, người không phải admin đặt `admin_receive_all` bị 403.
- **Ghi nhận:** `PUT` tùy chọn cá nhân không ghi audit (hợp đồng không yêu cầu).

### Rollback

Như Slice 1.

---

## Slice 7: Gộp Tin Và Chống Lặp Theo Người Nhận

**Loại:** AFK | **Chặn bởi:** Slice 5, Slice 6 | **Cỡ:** vừa

### Mục tiêu

Từ các sự kiện sinh ra **tin** đúng đơn vị D5(b): một tin cho mỗi người nhận, mỗi vật tư, mỗi lần quét, kèm quy tắc leo thang, trần và mức Nhẹ chờ bản tin.

### Việc cần làm

1. **Migration 4:** `price_alert_messages`, `price_alert_message_events`. Model và đăng ký.
2. `services/price_alert_messages.py`: gộp sự kiện theo (người nhận, vật tư, lần quét); `UNIQUE (user_id, material_id, scan_run_id, kind)`; trạng thái `pending`, `suppressed`, `digest_queued`, `skipped`; trần 30 tin mỗi lần quét **và** 30 tin gửi ngay cho một người trong 10 phút gần nhất (L27), cùng tin tóm tắt; mức Nhẹ thành `digest_queued` (L18).
3. `run_once` (Slice 5) gọi thêm bước này cùng giao dịch ngắn (Giai đoạn 1 của thiết kế 4.1).

### Thứ tự test (tracer trước)

1. **Tracer:** hai kỳ giao hàng của cùng vật tư vượt ngưỡng trong một lần quét tạo **một** tin cho trưởng phòng, liên kết hai sự kiện.
2. Cùng ngày, lần quét sau không leo thang thì `suppressed`; leo thang (mức cao hơn mức cao nhất đã gửi trong ngày, hoặc đổi chiều) thì tạo tin bổ sung.
3. Vượt 30 tin trong một lần quét: tin thứ 31 trở đi `digest_queued` và một tin tóm tắt "còn N thay đổi"; mức Nhẹ luôn `digest_queued`. **Trần cửa sổ (L27):** hai lần quét cách nhau 30 giây, mỗi lần 20 tin cho cùng một người: tin thứ 31 của cửa sổ 10 phút trở đi `digest_queued`; sau 10 phút trần được tính lại.
4. Chạy lại cùng lần quét không tạo tin trùng (UNIQUE và `ON CONFLICT`).
5. Người nhận bị `skipped` (không còn đủ điều kiện) được ghi rõ lý do.

### Tiêu chí chấp nhận

- [x] Replay (Slice 5) in thêm số tin theo đơn vị D5(b), khớp Phụ lục C trong ±15% (19,1 mỗi tuần, 7,6 Trung bình và Lớn).
- [x] Không có tin sai hướng trong replay.
- [x] Baseline không xấu hơn.

### Kết quả (2026-10-04)

- **Code mới:** migration `20261004_1500` (`price_alert_messages` có `sequence_number` tự tăng và `status_reason`; `price_alert_message_events`; UNIQUE `(user_id, material_id, scan_run_id, kind)` và chỉ mục một phần cho tin tóm tắt), model, `services/price_alert_messages.py` (`PriceAlertMessageService.build_for_run`), `run_once` gọi bước này trong savepoint, worker truyền danh sách pilot, replay chạy theo từng ô 30 giây (mỗi ô một `scan_run`) và in số tin theo trạng thái.
- **Quy tắc đã làm:** gộp sự kiện theo (người nhận, vật tư, lần quét), hướng và mức theo kỳ có mức cao nhất; cùng ngày VN chỉ có tin mới khi mức cao hơn mức cao nhất đã có hoặc đổi chiều so với tin gần nhất, nếu không thì `suppressed`; Nhẹ thành `digest_queued` (lý do `light`); trần theo lần quét và trần 30 tin trong 10 phút cho mỗi người (mức cao xử lý trước), phần vượt thành `digest_queued` (lý do `cap`) kèm **một** tin tóm tắt `kind='digest'` trong mỗi cửa sổ 10 phút; người ngoài danh sách pilot ghi `skipped` (lý do `pilot`); chạy lại cùng lần quét không tạo tin trùng.
- **Test mới (15):** tracer hai kỳ giao hàng một tin, Nhẹ, cùng ngày (suppressed, leo thang, đổi chiều), ngày mới, trần theo lần quét có ưu tiên mức cao, trần 10 phút và tính lại sau 11 phút, hai lần quét 20 tin chia sẻ một trần và một tin tóm tắt, tin bị trần cắt không chặn sự kiện sau, ngày VN lúc 00:30, pilot, idempotent, lỗi bước tin không làm hỏng lần quét. pytest toàn bộ xanh; ruff 62, mypy 13, bandit 16 không đổi. Đột biến (leo thang, trần 10 phút, trần theo lần quét, ưu tiên mức, Nhẹ, một tin tóm tắt, loại tin bị trần) đều bị bắt.
- **Replay trên dev (người nhận là Manager thử):** 65 tin gửi ngay và 3 tin bị chặn cùng ngày trong 6,29 tuần, so với tham chiếu không chặn bất thường 63 tin Trung bình và Lớn theo đơn vị D5(b): lệch khoảng 3%. Không lần nào chạm trần.
- **Rà soát agent độc lập đã xử lý:** bước tin nằm trong savepoint (nếu không, một lỗi sẽ rollback cả lần quét và lặp mãi mỗi 30 giây); tin tóm tắt không sinh mỗi 30 giây; tin bị trần cắt không còn làm sự kiện sau bị `suppressed`; ghi `message_events` theo lô; thêm test ngày VN và cộng dồn giữa hai lần quét.
- **Chấp nhận có chủ ý (ghi lại):** hướng của tin gộp lấy theo kỳ có mức cao nhất (giống engine tham chiếu), hai kỳ cùng mức khác hướng chỉ lưu hướng kỳ sớm nhất, chi tiết từng kỳ nằm ở `message_events`; `local_date` theo giờ quét chứ không theo giờ chốt (lệch chỉ khi quét qua nửa đêm VN); mỗi nhóm vẫn gọi `resolve_recipients` riêng (đủ nhanh với tải thật 7 tin mỗi lần quét, tối ưu nếu import lớn ở 1C); người ngoài pilot mỗi nhóm một dòng `skipped` (phình bảng nếu pilot kéo dài, bảng được dọn sau 180 ngày); `scan_run_id` có thể NULL sau khi dọn `scan_runs` (không còn bảo vệ UNIQUE cho dòng cũ, không có luồng ghi nào dùng NULL).

### Rollback

Như Slice 5.

---

## Slice 8: Soạn Tin, Biểu Đồ Và Gửi Ảnh

**Loại:** AFK (có bước duyệt bằng mắt, HITL) | **Chặn bởi:** Slice 0 (kết quả thí nghiệm), Slice 7 | **Cỡ:** vừa

### Mục tiêu

Dựng được **nội dung** một tin hoàn chỉnh từ một bản ghi tin: ảnh biểu đồ, caption ngắn và tin chi tiết đúng định dạng, và client Telegram gửi được ảnh. Chưa gửi tự động.

### Việc cần làm

1. `services/price_alert_formatter.py`: caption (≤ 1.024 ký tự), tin chi tiết (≤ 4.096), `escape_html`, dòng CNF theo QĐ-8, dòng "So sánh khác" chỉ khi khác điểm tham chiếu, chú thích nhà cung cấp, liên kết chi tiết; cắt có chú thích khi nhiều kỳ giao hàng.
2. `services/price_alert_chart.py` (L11): `render_price_chart(spec) -> bytes`, `Figure` + `FigureCanvasAgg`, `asyncio.to_thread`, font DejaVu nhúng đường dẫn, không emoji, không `matplotlib.dates`. Thêm `matplotlib` vào `pyproject.toml` và `uv.lock` (pin phiên bản).
3. `integrations/telegram.py` (L10): `send_photo`, `answer_callback_query`, `edit_message_text`, `edit_message_reply_markup`. Cập nhật `tests/telegram_fakes.py` và `scripts/fake_telegram_server.py` hiểu multipart và các method mới (L20).
4. **Dockerfile (Q6, nếu được duyệt):** thêm `--no-cache` vào `uv sync` ở stage production; đặt `MPLCONFIGDIR=/tmp/mpl`. Build thử image production, đo dung lượng và kiểm `python -c "import matplotlib"`.

### Thứ tự test (tracer trước)

1. **Tracer:** từ một bản ghi tin dựng sẵn (ví dụ 1 của D2), formatter sinh đúng caption và tin chi tiết khớp mẫu ở tài liệu cha **từng ký tự**; chart trả về PNG giải mã được, 900 x 500.
2. Formatter: dòng CNF có và không có (USD/MT cả hai bên, một bên, VND/KG); dòng phụ in và không in; ký tự `<`, `&` trong tên vật tư được escape; nhiều kỳ giao hàng vượt 4.096 thì cắt có chú thích; caption không vượt 1.024.
3. Chart: tiêu đề tiếng Việt có dấu và `▲`/`▼`; **không** có glyph thiếu (không cảnh báo `Glyph ... missing`); cùng đầu vào cho cùng băm; chạy 5 ảnh đồng thời qua `to_thread` không lỗi.
4. `send_photo` qua `httpx.MockTransport`: yêu cầu là multipart, có trường `photo`, `caption`, `parse_mode`, `reply_markup` là **chuỗi JSON**; caption vượt 1.024 bị từ chối trước khi gọi; lỗi mạng ném lại đã làm sạch, không lộ token.
5. `edit_message_text` xử lý `message is not modified` như không lỗi.

### Cách xác minh thật (HITL)

Xuất vài ảnh mẫu (Trung bình tăng, Lớn giảm, Nhẹ, ngày cuối tuần, vật tư tên dài) ra thư mục tạm và **xem bằng mắt**; bạn duyệt thẩm mỹ và câu chữ. `docker build --target prod` kiểm dung lượng.

### Tiêu chí chấp nhận

- [ ] Ảnh mẫu và câu chữ được bạn duyệt (chờ bạn).
- [x] `send_photo` và các method mới có test và fake tương ứng; test cũ của 1A vẫn xanh.
- [x] `uv.lock` chỉ thêm các gói của matplotlib (không nâng gói cũ); image production build được.
- [x] Baseline không xấu hơn; mypy strict sạch cho file mới.

### Kết quả (2026-10-04)

- **Làm song song:** client Telegram và biểu đồ do hai agent làm trong worktree riêng (cherry-pick `548de83`, `5903844`); formatter, bộ dựng dữ liệu tin và CNF do tôi làm; một agent độc lập rà soát toàn bộ.
- **Client** (`integrations/telegram.py`): `send_photo` (multipart, `reply_markup` là chuỗi JSON, caption > 1.024 bị chặn trước khi gọi mạng), `answer_callback_query`, `edit_message_text`, `edit_message_caption` (tin ảnh không dùng được `editMessageText`), `edit_message_reply_markup`; lỗi `message is not modified` trả `False` thay vì raise; fake server và `Outbox` hiểu multipart và các method mới. Lỗi mạng vẫn `from None`, không lộ token.
- **Biểu đồ** (`services/price_alert_chart.py`): `ChartSpec`, `render_price_chart` (`Figure` + `FigureCanvasAgg`, `asyncio.to_thread`, khóa toàn module vì cache font của matplotlib không an toàn đa luồng, PNG 900 x 500 xác định, không emoji, DejaVu nhúng, không glyph thiếu, `$` được thoát). `matplotlib==3.11.2`; `uv.lock` chỉ thêm 9 gói, không nâng gói cũ. Import +91 MB RSS, khoảng 0,06 giây mỗi ảnh.
- **Formatter** (`services/price_alert_formatter.py`): caption (≤ 1.024) và tin chi tiết (≤ 4.096) khớp mẫu 4.2 **từng ký tự**; dòng phụ chỉ khi khác điểm tham chiếu; CNF theo QĐ-8 (có chú thích "chênh lệch do tỷ giá" khi CNF đứng yên hoặc ngược chiều); nhiều kỳ giao hàng thì một khối mỗi kỳ, đánh dấu hướng từng kỳ khi khác hướng, cắt có chú thích; cắt không bao giờ chẻ giữa thực thể HTML và luôn giữ liên kết; tên vật tư qua `escape_html`. `price_alert_message_view.py`: `load_message_view` và `load_chart_spec` dựng dữ liệu từ sự kiện đã lưu.
- **Engine ghi CNF** (`price_alert_scan.py`): `cnf_price_new` khi dòng mới là USD/MT, `cnf_price_ref` và `cnf_date_ref` chỉ khi dòng tham chiếu cũng là USD/MT.
- **Dockerfile (Q6):** `uv sync --frozen --no-dev --no-cache` và `MPLCONFIGDIR` ở stage production. Image production dựng được: 692 MB, `import matplotlib` và vẽ một ảnh chạy trong container. Cấu hình mới `APP_PUBLIC_URL` (liên kết trong tin).
- **Test mới:** 51 (formatter 22, chart 15, client 7 và fake 3, CNF 1, dựng dữ liệu tin 3). pytest 907 pass; ruff 62, mypy 13, bandit 16 không đổi.
- **Rà soát độc lập đã xử lý:** cắt không chẻ thực thể HTML; khối đầu quá dài vẫn giữ liên kết và không vượt giới hạn; chú thích tỷ giá khi CNF đứng yên; thoát `$` trong chữ của biểu đồ.
- **Ghi nhận cho Slice 9:** `load_chart_spec` trả `None` khi không có dữ liệu giá, nên đường gửi phải có nhánh chỉ gửi tin văn bản; biểu đồ tính lại daily-min lúc vẽ (có thể lệch nhãn nếu có dòng thấp hơn xuất hiện sau khi quét) và chưa loại dòng bị gắn cờ (đợt β); câu "Giá thấp nhất hôm nay" giữ theo mẫu 4.2 dù điểm mới có thể trễ tới 3 ngày làm việc.
- **Chờ bạn duyệt bằng mắt (HITL):** 5 ảnh mẫu ở `docs/quotify/analysis-1b/slice8-samples/` (Trung bình tăng, Lớn giảm, Nhẹ, cuối tuần, tên dài; phụ đề trong ảnh mẫu là chuỗi thử glyph, không phải câu chữ thật) và câu chữ caption và tin chi tiết ở trên.

### Rollback

Hoàn nguyên `pyproject.toml`, `uv.lock`, Dockerfile; xóa file mới.

---

## Slice 9: Gửi Tin Trong Worker

**Loại:** AFK (có bước thử với Telegram thật, HITL) | **Chặn bởi:** Slice 8 | **Cỡ:** vừa

### Mục tiêu

Tin ở trạng thái `pending` được **gửi thật** tới Telegram: ảnh rồi tin chi tiết, có thử lại và xử lý lỗi, không làm đổi kết quả nghiệp vụ.

### Việc cần làm

1. `worker.py` (L8): dựng `TelegramClient` ở `startup`, đóng ở `shutdown`; gọi `configure_logging`.
2. `services/price_alert_sender.py` (L25): chọn tin `pending` đến hạn, lấy `lease_until`, gửi ảnh rồi tin chi tiết, đặt `sent` hoặc `failed`, lưu `telegram_message_id`; phân loại lỗi 429, 403, 400 và lỗi mạng. Cron `send_price_alerts` chạy lệch pha với cron quét, `second={15, 45}` (L27), là job riêng để một lần gửi chậm không làm trễ lần quét; chống chạy chồng bằng `lease_until` của từng tin, không bằng khóa advisory.
3. 403: `mark_blocked` theo tài khoản của tin (`telegram_account_id`).

### Thứ tự test (tracer trước)

1. **Tracer (server giả):** một tin `pending` được gửi: nhận một `sendPhoto` rồi một `sendMessage`, tin chuyển `sent`, lưu `message_id`.
2. 429: chờ `retry_after` rồi gửi lại. 403: tài khoản thành `blocked`, tin `skipped`. 400 (HTML sai): `failed`, không thử lại. Lỗi mạng: thử lại có backoff, đến hạn thì `failed`.
3. Hai worker cùng lấy: `lease_until` ngăn gửi trùng; tin `sending` còn hạn bị bỏ qua, hết hạn thì nhận lại.
4. Gửi lỗi **không** đổi sự kiện hay tin đã commit. Tin ở trạng thái cuối không bị gửi lại.
5. Log và exception không chứa token; `startup` dựng client một lần và `shutdown` đóng nó.

### Cách xác minh thật (HITL)

**Chuẩn bị:** hiện liên kết Telegram duy nhất trên dev là của tài khoản seed, mà tài khoản seed không nhận tin (L16, Q7). Dùng tài khoản Manager thử của L28 (đã chuẩn bị ở Slice 0; mỗi tài khoản Telegram chỉ liên kết một người dùng, nên liên kết cũ của tài khoản seed phải được hủy). `PRICE_ALERT_RECIPIENT_EMAILS` chỉ gồm tài khoản đó; dùng chính nó nhập và chốt phiếu thử gây biến động Trung bình rồi mở Telegram: ảnh và tin chi tiết hiện đúng, bấm liên kết mở được phiếu. Kiểm `grep` token trong log của worker bằng 0.

### Tiêu chí chấp nhận

- [ ] Một tin thật tới Telegram của bạn đúng định dạng (ảnh, caption, tin chi tiết).
- [ ] Mọi nhánh lỗi có test; không gửi trùng khi hai worker chạy.
- [ ] Token không có trong log.
- [ ] Baseline không xấu hơn.

### Rollback

Tắt cờ; dừng worker.

---

## Slice 10: Cổng G1, Replay Và Pilot Trên Dev

**Loại:** HITL | **Chặn bởi:** Slice 9 | **Cỡ:** nhỏ

### Mục tiêu

Chứng minh engine đạt tiêu chí "Hoàn thành khi" 1, 2 và 5 trên dữ liệu thật trước khi đụng production; chốt các tham số mặc định.

### Việc cần làm

1. Chạy `price_alert_replay` 8 tuần ở hai chế độ (D6 và `--ignore-trigger-source`), so với Phụ lục C và với engine tham chiếu (`analysis-1b/`). Giải thích mọi chênh lệch trên 15%.
2. Rà mẫu tin: lấy 10 sự kiện ngẫu nhiên, đối chiếu thủ công con số trong tin với dữ liệu gốc.
3. Chạy cron thật trên dev vài ngày với danh sách pilot; theo dõi `price_alert_scan_runs`, lỗi, số tin.
4. Chốt bảng "Tham số mặc định của 1B" (tài liệu cha, Mục 3) và ghi vào Phụ lục C.

### Tiêu chí chấp nhận

- [ ] Số liệu replay trong ±15% của tham chiếu; không tin sai hướng.
- [ ] Mẫu 10 sự kiện đối chiếu đúng 100%.
- [ ] Cron thật chạy nhiều ngày không lỗi quét, không trùng.
- [ ] Tham số mặc định được chốt và ghi lại.

### Rollback

Tắt cờ.

---

## Slice 11: Đưa Đợt α Lên Production

**Loại:** HITL (thao tác trên VPS) | **Chặn bởi:** Slice 10 | **Cỡ:** nhỏ

### Mục tiêu

Production chạy engine với cờ tắt, rồi bật cho nhóm pilot, không ảnh hưởng dữ liệu hiện có.

### Việc cần làm (theo runbook mục 9 và 12, thêm mục 13 cho 1B)

1. Backup (`export POSTGRES_DB=quotify` trước khi chạy `backup-postgres.sh`, kiểm file).
2. `git pull`, so `.env` với `.env.production.example`; thêm `PRICE_ALERT_RECIPIENT_EMAILS` (nhóm pilot, Q5).
3. Build `backend` và `worker` (**không** build frontend: 1B không đổi giao diện). Kiểm dung lượng image so với Dockerfile.
4. `run --rm backend uv run alembic upgrade head` (bốn migration, đều thêm bảng hoặc dữ liệu quyền). Kiểm số liệu cũ không đổi.
5. `up -d backend worker`, `restart reverse-proxy`. Kiểm `/health`, `/ready`, đăng nhập, các chức năng cũ; `docker compose logs worker` không có lỗi khi khởi động, không có token.
6. Kiểm quyền: người dùng `manager` và `admin` đã có quyền mới (`select ... role_permissions`); kiểm tên role trưởng phòng thật.
7. Bật bằng API (cần token của người có `price_alerts.manage`; đăng nhập bằng `curl`, không dán mật khẩu vào chat): `PUT /price-alert-settings` với `is_enabled=true` (đặt watermark = bây giờ).
8. Theo dõi `price_alert_scan_runs` và log; đợi một phiếu thật được chốt; kiểm tin đến đúng người trong danh sách pilot.
9. Sau vài tuần ổn định: bỏ giới hạn pilot theo Q5.

### Tiêu chí chấp nhận

- [ ] Migration chạy, dữ liệu cũ nguyên vẹn, chức năng cũ bình thường.
- [ ] Một tin thật tới người trong nhóm pilot; không có tin tới người ngoài nhóm.
- [ ] Token không có trong log worker; `scan_runs` không có lỗi.
- [ ] Runbook mục 13 viết xong; chạy `agent-task-close.sh`.

### Rollback (đúng thứ tự)

1. `PUT /price-alert-settings` với `is_enabled=false` (hiệu lực trong 30 giây) hoặc `TELEGRAM_ENABLED=false` rồi recreate backend và worker, `restart reverse-proxy`.
2. Giữ nguyên schema (additive, tương thích code cũ). Không `alembic downgrade` trên production.

---

## Slice 12: Giá Bất Thường (Đợt β)

**Loại:** AFK | **Chặn bởi:** Slice 11 | **Cỡ:** lớn

### Mục tiêu

Dòng giá nghi nhập sai bị phát hiện ở mức dòng, **loại khỏi tính toán**, và sinh thẻ cho đúng người (D12). Có số đo dry-run với mô phỏng nút "Giá đúng" (cổng G2).

### Việc cần làm

1. `services/price_alert_anomaly.py`: phát hiện mức dòng (lệch ≥ 30% so với trung vị các điểm hợp lệ trước trong 30 ngày lịch; trung vị số chẵn là trung bình hai điểm giữa; cần ít nhất 1 điểm; chỉ 1 điểm tham chiếu thì "độ tin cậy thấp"; điểm đầu chuỗi không bị gắn cờ), tạo sự kiện `kind='anomaly'`, `review_status='pending'`.
2. Loại dòng bị gắn cờ trước khi tính daily-min và làm điểm tham chiếu (`exclude_line_ids` của Slice 2); điểm sau cùng mặt bằng (lệch dưới 2,5% so với điểm `pending`) gắn vào thẻ; từ 3 cờ trong một ngày địa phương gộp thành một tin tóm tắt (tối đa 10 điểm).
3. Người nhận: trưởng phòng (`receive_all`) nhận thẻ có nút; **người nhập** (`quote_versions.created_by_id`) nhận thẻ không nút; người vừa là trưởng phòng vừa là người nhập nhận **một** thẻ có nút (L28); seed admin không nhận; người không `ACTIVE` bỏ qua; tin bất thường không chịu mức tối thiểu nhưng chịu cờ bật/tắt cá nhân và pilot.
4. Chế độ replay mô phỏng "Giá đúng" (chính sách mô phỏng ghi rõ, ví dụ chấp nhận điểm bị cờ nếu có từ 2 điểm sau trong khoảng 2,5% so với nó).

### Thứ tự test (tracer trước)

1. **Tracer (tích hợp):** ví dụ Threonine 15/09: dòng 970 bị gắn cờ, daily-min của ngày được tính lại thành 26.000, sự kiện bất thường được tạo, và **không** sinh tin biến động cho điểm đó.
2. Điểm đầu chuỗi không bị cờ; chỉ 1 điểm tham chiếu thì cờ "độ tin cậy thấp"; trung vị số chẵn; ngưỡng 30% theo vật tư.
3. `pending` gắn các điểm sau cùng mặt bằng vào cùng thẻ; sau khi duyệt, các điểm gắn kèm được đánh giá lại độc lập.
4. Gộp cụm từ 3 cờ cùng ngày; ví dụ cụm 15/09/2026 (6 điểm) ra một tin.
5. Người nhận đúng (đặc biệt người nhập khác người tạo phiếu), người nhập NULL hay không hoạt động thì bỏ qua.
6. Khô cọ: điểm đúng 5.172 không bị gắn cờ giả khi điểm sai 187 đã `rejected`; Tryptophan tương tự (trong replay mô phỏng).

### Tiêu chí chấp nhận (cổng G2)

- [ ] Replay có mô phỏng "Giá đúng": các điểm bất thường của B.7 được gắn cờ, các điểm sai tham chiếu (Khô cọ, Tryptophan) không còn sinh cờ giả; số thẻ mỗi tuần và số tin bất thường sau gộp cụm được ghi vào Phụ lục C và nằm trong mức người dùng chấp nhận (Q4).
- [ ] Baseline không xấu hơn.

### Rollback

Tắt cờ; sự kiện bất thường đang `pending` không ảnh hưởng tính toán khi cờ tắt.

---

## Slice 13: Nút Bấm (`callback_query`)

**Loại:** AFK (có bước thử với Telegram thật, HITL) | **Chặn bởi:** Slice 12 | **Cỡ:** vừa

### Mục tiêu

Trưởng phòng bấm **Giá đúng** hoặc **Nhập sai** trong Telegram và hệ thống xử lý đúng, an toàn, một lần.

### Việc cần làm

1. `telegram_update_service.py`: parse `callback_query` (`id`, `from.id`, `message.chat.id`, `message.message_id`, `data`), nhánh xử lý, authz (L22: người dùng `ACTIVE`, `price_alerts.receive_all` hoặc admin, qua `AuthService.get_active_user` rồi `has_permission`), outbound mới (`answerCallbackQuery`, `editMessageText`, `editMessageCaption`) và `runner` gửi chúng; `answerCallbackQuery` đi **trước** việc cập nhật DB nặng và trong 5 giây (L22).
2. Cập nhật nguyên tử (L23), sửa tin (L24), ghi audit `price_alerts.anomaly_reviewed` (không chứa `telegram_user_id`).
3. Gom `ALLOWED_UPDATES` (L9) thêm `callback_query`; cập nhật các test đang ghim danh sách cũ.
4. Rate limit bucket riêng; nhánh lỗi "độc" vẫn trả lời callback.

### Thứ tự test (tracer trước)

1. **Tracer (PostgreSQL thật, server giả):** trưởng phòng bấm Giá đúng: thẻ chuyển `accepted`, dòng hợp lệ trở lại, `answerCallbackQuery` được gọi, tin được sửa, bàn phím bị bỏ.
2. Nhập sai: thẻ `rejected`, dòng vẫn bị loại.
3. Người không có quyền bấm: bị từ chối, `answerCallbackQuery` báo lỗi, không đổi trạng thái. Người không `ACTIVE`.
4. **Hai người bấm cùng lúc** (hai kết nối): đúng một người thắng, người kia nhận "đã được xử lý bởi ...".
5. **Thứ tự và thời hạn:** server giả ghi thứ tự gọi: `answerCallbackQuery` đến trước khi tin bị sửa; khi cập nhật DB chậm hoặc lỗi thì callback vẫn được trả lời trong 5 giây. Bấm lặp liên tiếp (Telegram gửi mỗi lần bấm là một `callback_query` riêng): lần sau nhận "đã được xử lý", sửa tin trùng (400 `message is not modified`) không làm lỗi. Bấm thẻ đã xử lý hoặc hết hạn; `callback_data` lạ hoặc sai định dạng; id sự kiện không tồn tại.
6. Giới hạn tốc độ vẫn trả lời callback; callback gây lỗi vẫn trả lời callback.
7. `ALLOWED_UPDATES` dùng chung ở poller và CLI và có `callback_query`.

### Cách xác minh thật (HITL)

Gửi một thẻ thật tới Telegram của bạn trên dev (poller bật), bấm cả hai nút, kiểm trạng thái trong DB, tin được sửa, audit. Thử bấm lần hai.

### Tiêu chí chấp nhận

- [ ] Vòng khứ hồi hai nút chạy với bot dev thật.
- [ ] Hai người bấm cùng lúc chỉ một thắng (test PostgreSQL thật).
- [ ] Mọi callback đều được trả lời. Baseline không xấu hơn.

### Rollback

Tắt cờ; webhook vẫn nhận `callback_query` nhưng không còn thẻ để bấm.

---

## Slice 14: Nhắc, Hết Hạn Và Dọn Dữ Liệu

**Loại:** AFK | **Chặn bởi:** Slice 13 | **Cỡ:** nhỏ

### Mục tiêu

Thẻ không bị bỏ quên: nhắc một lần, hết hạn đúng hạn; dữ liệu cũ được dọn.

### Việc cần làm

1. Cron hằng giờ nhắc thẻ `pending` sau 2 ngày làm việc (một lần, đặt `reminded_at`), hết hạn sau 7 ngày làm việc (`expired`, dòng vẫn bị loại, ngừng nhắc). Cron hằng ngày dọn dữ liệu cũ hơn 180 ngày (L19).
2. Đăng ký cron với `timezone` VN.

### Thứ tự test (tracer trước)

1. **Tracer:** thẻ `pending` quá 2 ngày làm việc nhận đúng một lời nhắc; chạy lại không nhắc lần hai.
2. Quá 7 ngày làm việc: `expired`, dòng vẫn bị loại khỏi tính toán, thẻ ghi "hết hạn".
3. Tính ngày làm việc qua cuối tuần.
4. Dọn dữ liệu: xóa đúng bản ghi cũ hơn 180 ngày, **không** xóa thẻ `pending` hay tin chưa gửi.

### Tiêu chí chấp nhận

- [ ] Các nhánh nhắc, hết hạn, dọn có test; cron chạy đúng giờ VN trên dev.
- [ ] Baseline không xấu hơn.

### Rollback

Như Slice 12.

---

## Slice 15: Cổng G2 Và Đưa Đợt β Lên Production

**Loại:** HITL | **Chặn bởi:** Slice 14 | **Cỡ:** nhỏ

### Việc cần làm

1. Hồi quy toàn bộ; xác nhận cổng G2 (Slice 12). Cập nhật runbook mục 13 cho đợt β.
2. Deploy như Slice 11 (backup với `POSTGRES_DB=quotify`, `git pull`, build `backend` và `worker`, migrate nếu có migration mới, `up -d`, `restart reverse-proxy`).
3. **Bước riêng của β:** chạy lại `telegram_webhook.py set --yes` để đăng ký `allowed_updates` có `callback_query` (L9), rồi `telegram_webhook.py info` và kiểm `allowed_updates` thật sự gồm `callback_query`.
4. Thử bằng nhóm pilot: một thẻ bất thường thật, bấm nút, kiểm audit và trạng thái. Kiểm token không có trong log.
5. Sau vài tuần ổn định, bỏ giới hạn pilot.

### Tiêu chí chấp nhận

- [ ] Webhook production báo `allowed_updates` có `callback_query`; nút chạy trên production với nhóm pilot, có audit.
- [ ] Chức năng cũ và đợt α không đổi; token không có trong log.
- [ ] Chạy `agent-task-close.sh`; memory-bank và tài liệu cha cập nhật.

### Rollback (đúng thứ tự)

Tắt cờ như Slice 11. Không cần hoàn nguyên `allowed_updates`. Không `downgrade`.

---

## Thứ Tự Và Phụ Thuộc

```
S0 ─► S1 ─┬─► S2 ─┬─► S3 ─┐
          │       └─► S4 ─┴─► S5 ─┐
          └──────────► S6 ────────┴─► S7 ─► S8 ─► S9 ─► S10 ─► S11   (đợt α)
                                                                 │
                                         S12 ─► S13 ─► S14 ─► S15      (đợt β, sau S11)
```

S3 và S4 làm song song được. S6 chỉ cần S1 nên có thể làm song song với S2 đến S5. Mỗi slice merge riêng được và không làm hỏng build hay test của repo; production không đổi hành vi nhìn thấy được cho tới Slice 11 (cờ tắt, và 1B không đổi giao diện).

## Ma Trận Kiểm Thử

| Lớp | Slice | Cách |
|---|---|---|
| Hàm thuần (ngày làm việc, quy tắc, phân mức, ứng viên) | 2 đến 4 | pytest thuần; thuộc tính cho R1 đến R3 |
| PostgreSQL thật (lớp `integration`) | 2, 4 đến 7, 12 đến 14 | daily-min, quét, khóa advisory, savepoint, `ON CONFLICT`, UNIQUE, chồng lấp watermark, hai kết nối tranh chấp |
| API (mock session, `dependency_overrides`) | 1, 6 | quyền, 422, audit, hợp đồng |
| Migration | 1, 5, 7 | DB tạm: upgrade, downgrade, một head; quyền có và không có role `manager`, chạy trước seed |
| Telegram (httpx `MockTransport` hoặc server giả) | 8, 9, 13 | multipart, 429, 403, 400, lease, `callback_query`; không gọi Telegram thật |
| Dry-run replay | 5, 7, 10, 12 | đối chiếu engine tham chiếu độc lập (Phụ lục C) |
| Verify thật (bot dev, worker thật, trình duyệt khi cần) | 8, 9, 13 | HITL |
| Hồi quy | mỗi slice | pytest đầy đủ (kể cả `-m integration`), ruff, mypy, bandit so với baseline |

## Rủi Ro Và Cách Giảm

Đánh số tiếp từ tài liệu cha (RR-1 đến RR-27).

| # | Rủi ro | Cách giảm | Slice |
|---|---|---|---|
| RR-28 | `worker-test` có thể dùng bot thật từ `.env` dev | Ép `TELEGRAM_ENABLED=false` và token rỗng (L20) | 5 |
| RR-29 | Nguồn bị thay thế trước khi cron quét: dòng không đổi của nó không bao giờ phát tin | Bảng version đã quét và ngoại lệ (b) của L1 | 4, 5 |
| RR-30 | Import commit sau tối đa 200 nhóm, `confirmed_at` gán đầu nhóm: có thể vượt biên chồng lấp 5 phút | Version đã quét (L2); đo thời lượng lô khi bật trên production; D6 loại import khỏi nguồn kích hoạt | 5, 11 |
| RR-31 | Tham chiếu bị "nhiễm độc" bởi lần nhập sai đầu tiên: 43 điểm gắn cờ (6,8 mỗi tuần) | Chỉ phát hành β sau dry-run mô phỏng "Giá đúng" (Q4) | 12 |
| RR-32 | Tải tin cao hơn dự kiến, đặc biệt mức Nhẹ | Mức Nhẹ chưa gửi ở 1B (Q1), trần 30 tin, pilot (L12), theo dõi 30 đến 60 ngày | 10, 11 |
| RR-33 | matplotlib: +130 MB, RSS worker 104 đến 150 MB, vẽ mỗi ảnh 61 đến 91 ms trên luồng nền | `to_thread`, ghim phiên bản, `--no-cache` (Q6), `MPLCONFIGDIR=/tmp/mpl`, hàm bọc để đổi sang Pillow | 8 |
| RR-34 | Worker chưa có logging và `timezone`: giờ cron lệch 7 tiếng, log INFO không in | `configure_logging` ở `startup`, `timezone` VN, test | 5, 9 |
| RR-35 | Webhook production giữ `allowed_updates` cũ nên nút bấm "chết" | Bước `set --yes` bắt buộc ở Slice 15, kiểm `info` | 13, 15 |
| RR-36 | Callback quay mãi hoặc bị từ chối `query is too old` (ngưỡng đo được khoảng 15 giây) vì xử lý chậm, hàng đợi poller dồn, DB khóa | Luôn `answerCallbackQuery` trong 5 giây, trước việc nặng; bucket riêng (L22) | 13 |
| RR-37 | Tin gửi cả cuối tuần và ngoài giờ (17% version đủ điều kiện được chốt cuối tuần) | Theo QĐ-7 (không có khung giờ yên lặng); người dùng tự tắt tiếng chat; cờ bật/tắt cá nhân | 11 |
| RR-38 | Quy ước "admin hệ thống không bao giờ nhập tay" (Q7) bị vi phạm: phiếu nhập tay của tài khoản seed bị loại nhầm khỏi nguồn kích hoạt, hoặc người khác import nên bị coi là nhập tay | Kiểm production ở Slice 0; ghi quy ước vào runbook; trần 10 phút cho mỗi người (L27d) giới hạn thiệt hại | 0 |
| RR-39 | Gửi tin là at-least-once nên hiếm khi trùng | `lease_until`, UNIQUE, chấp nhận (RR-27) | 9 |
| RR-40 | `confirmed_at` là aware UTC khi đọc: `.date()` sai ngày trong khung 00:00 đến 07:00 giờ VN | Luôn `astimezone(VN)`; test chốt 23:30 và 00:30 | 4 |
| RR-41 | Migration quyền gắn với tên role `manager`, tên thật trên production chưa kiểm | Kiểm ở Slice 0; migration chịu được thiếu role; có thể gán thủ công | 0, 1 |
| RR-42 | Hai cách tính min/max khác nhau (backend `summary` trên mọi dòng, frontend trên daily-min): tin và dashboard có thể lệch | Tin dùng daily-min và ghi rõ "vùng tham chiếu"; không sửa dashboard | 2, 8 |
| RR-43 | Làm tròn trước khi phân mức đẩy 4,996% lên mức Trung bình | `Decimal` không quantize trước khi so (L7), có test | 3 |
| RR-44 | Không có test hay helper dựng phiếu trên DB thật | Thêm helper ở Slice 2 trước mọi test tích hợp | 2 |
| RR-45 | Cron quét 30 giây cạnh job import dài: tranh `max_jobs` của arq (mặc định 10); lần quét kéo dài quá 30 giây làm lần sau chạy chồng | Job quét ngắn; khóa advisory làm lần chạy chồng thoát ngay; đo khi import chạy; xét `max_jobs` | 5, 11 |
| RR-46 | Chia nhỏ lần quét (30 giây) làm trần "30 tin mỗi lần quét" kém tác dụng khi có đợt nhập hàng loạt của người không phải tài khoản seed | Trần thứ hai: 30 tin trong 10 phút cho mỗi người (L27); nguồn kích hoạt D6; quy ước tài khoản import (Q7) | 7, 11 |
| RR-47 | Cron 30 giây tạo khoảng 2.880 lần chạy mỗi ngày: dòng `scan_runs` rỗng làm phình bảng, log INFO ồn, tải thăm dò thừa | Chỉ ghi `scan_runs` khi có việc hoặc lỗi; nhịp tim ở `scan_state.last_run_at`; lần rỗng log DEBUG; đo 0,3 ms mỗi truy vấn chọn version (L4) | 5 |

## Phụ Lục A: Kết Quả Kiểm Chứng Thực Nghiệm Với Telegram

Bot dev `@HHQuotifyBot`. Các thí nghiệm "từ chối" không gửi tin vào chat.

| # | Nội dung | Kết quả | Ngày |
|---|---|---|---|
| T6 | 40 tin liên tiếp tới chat riêng, gửi tuần tự (mục f) | **Không có 429.** 40 tin trong 19,3 giây (khoảng 2 tin mỗi giây, trung vị 419 ms mỗi tin). Giới hạn thật nằm xa tải 1B (tối đa 30 tin trong 10 phút cho mỗi người, L27d); vẫn xử lý 429 theo `retry_after` (L25) | 2026-10-04 |
| T7a | Văn bản 4.097 ký tự | 400 `message is too long` | 2026-10-04 |
| T7b | `parse_mode=HTML` với `<` và `&` thô | 400 `can't parse entities: Unsupported start tag ...` và `Can't find end tag corresponding to start tag "i"`: lỗi cuối cùng, không thử lại, bắt buộc `escape_html` | 2026-10-04 |
| T8a | `callback_data` 65 byte ASCII | 400 `BUTTON_DATA_INVALID` | 2026-10-04 |
| T8b | `callback_data` tiếng Việt 54 ký tự (72 byte UTF-8) | 400 `BUTTON_DATA_INVALID`: giới hạn tính theo **byte** | 2026-10-04 |
| T8c | Nút inline không có `callback_data` hay `url` | 400 `Text buttons are not allowed in the inline keyboard` | 2026-10-04 |
| T9a | Caption `sendPhoto` 1.025 ký tự | 400 `message caption is too long` | 2026-10-04 |
| T9b | Ảnh: kích thước, tỷ lệ | Theo tài liệu chính thức Bot API 10.3: tối đa 10 MB, rộng cộng cao không quá 10.000, tỷ lệ rộng trên cao tối đa 20. Ảnh dự kiến 900 x 500, khoảng 54 KB nằm xa các giới hạn | 2026-10-04 |
| T10a | `answerCallbackQuery` id giả | 400 `query is too old and response timeout expired or query ID is invalid` | 2026-10-04 |
| T10b | `editMessageText` tin không tồn tại | 400 `message can't be edited` | 2026-10-04 |
| (a) | `sendPhoto` multipart PNG 900 x 500 (55 KB) kèm caption HTML và bàn phím 2 nút (`reply_markup` là chuỗi JSON trong form) | Gửi được; người dùng xác nhận ảnh rõ nét, tiêu đề và caption tiếng Việt đúng | 2026-10-04 |
| (b) | Bấm nút: `callback_query` | Đến qua `getUpdates` khi `allowed_updates` có `callback_query`. Có `id`, `from` (`id`, `first_name`, `last_name`, `language_code`, `is_bot`), `message` (đủ `chat.id`, `message_id`), `data`, `chat_instance`. `data` nguyên vẹn (42 byte cho `pa:ok:<uuid>`; 64 byte cũng nguyên vẹn) | 2026-10-04 |
| (c) | Sau khi bấm: `answerCallbackQuery`, sửa tin | `answerCallbackQuery` chạy (khoảng 0,9 giây); gọi lần hai cho cùng một lần bấm vẫn `ok`. `editMessageCaption` (tin ảnh) và `editMessageText` (tin văn bản) chạy; `editMessageText` trên tin ảnh: 400 `there is no text in the message to edit`. Sửa y hệt: 400 `message is not modified: specified new message content and reply markup are exactly the same...`. `editMessageReplyMarkup` bỏ nút chạy, lặp lại: 400 `message is not modified` | 2026-10-04 |
| (d) | `callback_data` đúng 64 byte; caption đúng 1.024; văn bản đúng 4.096 | Cả ba được chấp nhận và hiển thị đủ (người dùng xác nhận) | 2026-10-04 |
| (e) | Hết hạn của `answerCallbackQuery` (trả lời trễ sau lần bấm) | Trễ 0 đến 2, 5, 8, 11, 14 giây: `ok`. Trễ 17 giây, 20 giây, 60 giây: 400 `query is too old and response timeout expired or query ID is invalid`. **Ngưỡng khoảng 15 giây.** Bấm liên tiếp cách nhau 2 đến 3 giây: Telegram gửi mỗi lần bấm là một `callback_query` riêng, không bị gộp hay chặn | 2026-10-04 |

## Phụ Lục B: Danh Sách File Dự Kiến

**Tạo mới (backend):** các migration (bốn migration nối tiếp từ `20261004_1100`), `app/models/price_alert.py`, `app/schemas/price_alerts.py`, `app/api/v1/price_alerts.py`, `app/services/working_days.py`, `daily_min_series.py`, `price_alert_rules.py`, `price_alert_candidates.py`, `price_alert_scan.py`, `price_alert_recipients.py`, `price_alert_messages.py`, `price_alert_formatter.py`, `price_alert_chart.py`, `price_alert_sender.py`, `price_alert_anomaly.py`, `price_alert_settings_service.py`, `app/price_alert_replay.py`; test tương ứng cho từng file; helper dựng dữ liệu ở `tests/integration/db_helpers.py`.

**Sửa tối thiểu (backend và hạ tầng):** `app/worker.py` (cron, `timezone`, `startup`/`shutdown`), `app/api/v1/router.py`, `app/models/__init__.py`, `app/db/base.py`, `app/auth/seed_data.py`, `app/services/audit_log.py`, `app/core/config.py` (`PRICE_ALERT_RECIPIENT_EMAILS`), `app/integrations/telegram.py`, `app/services/telegram_update_service.py`, `telegram_update_runner.py`, `telegram_poller.py`, `telegram_cli.py` (hằng `ALLOWED_UPDATES`), `tests/telegram_fakes.py`, `scripts/fake_telegram_server.py`, `pyproject.toml`, `uv.lock`, `docker/backend/Dockerfile` (Q6), `docker-compose.test.yml`, `.env.example`, `.env.production.example`, `docs/runbooks/deploy-vps-production.md` (mục 13).

**Frontend:** không có (giao diện cấu hình, tùy chọn cá nhân và trang xem xét điểm bất thường là 1C).

**Không đụng:** `app/services/quote_service.py`, `app/api/v1/quotes.py`, `app/services/quotify_dashboard_service.py`, `app/models/quote*.py`, `frontend/**`, `docker-compose.prod.yml`, `docker/nginx/prod.conf`.

**Tài liệu bền vững:** tài liệu cha, `CONTEXT.md`, `Requirements.txt`, `quotify-implementation-plan.md`, `memory-bank/*`, `.agent-memory` (qua `agent-task-close.sh`), `docs/quotify/analysis-1b/`.

## Phụ Lục C: Số Liệu Phát Lại Tham Chiếu (DB dev, 2026-10-04)

Engine tham chiếu độc lập (`docs/quotify/analysis-1b/py/engine.py`, `partA.py`, `partB*.py`). Kiểm chứng: cấu hình B.7 tái hiện đúng **4.532 điểm, 1.540 điểm bị báo, R1/R2/R3 = 430/638/472, 16 điểm bất thường (13 chuỗi, 7 vật tư), 19,4 tin/tuần theo chuỗi (tài liệu cha 19,5), 7,8 theo vật tư (7,8), 2,9 Trung bình và Lớn (2,9)**.

Phát lại theo thời điểm chốt (`confirmed_at`), chia cho 6,29 tuần hoạt động (20/08 đến 02/10/2026). Tin D5(b) gộp theo **ô quét 30 giây** (L27; bản phân tích đầu dùng ô 2 phút cho 18,9 mỗi tuần, chênh +1%; các cột còn lại không phụ thuộc chu kỳ). Các cột là mỗi tuần:

| Kịch bản | Theo chuỗi | Gộp theo vật tư | Trung bình và Lớn (gộp) | Tin D5(b) (Trung bình và Lớn) |
|---|---|---|---|---|
| Trễ ≤ 0 ngày làm việc | 18,8 | 11,5 | 4,1 | 12,1 (4,1) |
| Trễ ≤ 1 | 25,1 | 14,8 | 5,9 | 16,2 (6,4) |
| **Trễ ≤ 3, loại tài khoản seed (D6)** | **30,2** | **16,9** | **6,8** | **19,1 (7,6)** |
| Trễ ≤ 7 | 31,7 | 17,5 | 7,2 | 20,0 (8,0) |
| Mọi dòng của người thật | 38,3 | 19,1 | 8,3 | 23,4 (9,7) |
| Chỉ `is_backfilled=false` | 18,5 | 11,0 | 4,0 | 11,6 (4,0) |

Chi tiết kịch bản D6:
- Theo tuần ISO 34 đến 40, tin D5(b): 5, 38, 10, 20, 11, 19, 17 (Trung bình và Lớn: 2, 17, 3, 10, 4, 8, 4). Tuần cao nhất 38 tin. Ngày cao nhất 14 tin (27/08 và 08/09). Một lần quét (ô 30 giây) cao nhất 7 tin gộp và 15 sự kiện theo chuỗi, đều là một đợt nhập duy nhất; thấp xa trần 30. Chu kỳ ngắn hơn không làm đợt nhập tách thành nhiều tin vì mỗi đợt chốt trong vài giây.
- Theo mức (theo chuỗi, sau chống lặp): Nhẹ 118, Trung bình 49, Lớn 23; tăng 109, giảm 81; lý do chính R1 126, R2 39, R3 25. Chống lặp loại 55/245 sự kiện. Vật tư nhiều tin nhất: Ngô hạt 11, Cám gạo chiết ly 10, Lysine 99% 9.
- Người nhận (ước lượng D8): trung bình 1,94 nhân viên mỗi tin. Mỗi người một tuần: người nhiều nhất 7,6 tin tức thời (Trung bình và Lớn) và 16,4 tin nếu tính cả mức Nhẹ (hai trưởng phòng là 7,6/16,4 và 7,6/9,2); nhân viên nhiều nhất 4,3/9,4; thấp nhất 0,2/0,5.
- Bất thường (D12, mức dòng, trung vị 30 ngày, **bất thường bị loại vĩnh viễn**, không mô phỏng "Giá đúng"): 47 dòng, 43 điểm (6,8 mỗi tuần), 28 chuỗi, 11 vật tư; sau gộp cụm khoảng 16 tin, 2,6 mỗi tuần cho trưởng phòng. Chặn bất thường giảm khoảng 13% tin theo chuỗi và 24% Trung bình và Lớn.
- So với B.8 của tài liệu cha (28,2 / 17,7 / 7,3): +7%, −5%, −7%, trong ±30%.

Giới hạn: chu kỳ quét 30 giây được xấp xỉ bằng ô 30 giây theo `confirmed_at` (không mô phỏng giờ chạy thật của cron); không có người bấm nút; danh sách người nhận là ước lượng; dữ liệu là DB dev, không phải production. Slice 0 nên chạy lại bộ truy vấn `analysis-1b/sql/` trên bản sao production (chỉ đọc) để so.
