# Kế hoạch: Thông báo biến động giá qua Telegram và Chatbot AI

> **Trạng thái:** ĐANG HOÀN THIỆN. **Giai đoạn 1A (nền tảng liên kết tài khoản Telegram) đã có code và chạy trên dev** (xem mục "Kết Quả Triển Khai" của kế hoạch 1A); Slice 7 (production) chưa làm. Từ 1B trở đi (tính biến động, gửi tin, chatbot) chưa có dòng code nào. Các quyết định D1 đến D12 đã chốt. Các tham số mặc định ở mục 3 ("Tham số mặc định của 1B") chưa được xác nhận từng giá trị.
> **Ngày soạn:** 2026-10-03. **Cập nhật:** 2026-10-04 (áp dụng kết quả rà soát độc lập và quyết định Q1 đến Q4).
> **Phạm vi:** Bước 1 (thông báo biến động giá qua Telegram) và Bước 2 (nâng cấp thành chatbot AI).
> **Nguyên tắc nền:** Production đã chạy. Mọi thay đổi chỉ được **additive** (thêm bảng, thêm cột nullable, thêm file). Không sửa migration cũ, không đổi hành vi API cũ.

Tài liệu liên quan:
- [plan-telegram-giai-doan-1a-nen-tang-lien-ket.md](plan-telegram-giai-doan-1a-nen-tang-lien-ket.md): kế hoạch triển khai chi tiết Giai đoạn 1A (chia slice).
- [plan-telegram-giai-doan-1b-engine-bien-dong-gia.md](plan-telegram-giai-doan-1b-engine-bien-dong-gia.md): kế hoạch triển khai chi tiết Giai đoạn 1B (chia slice, bản nháp 2026-10-04). Kiểm chứng lại tài liệu này với code và dữ liệu thật; các chỗ lệch (head Alembic, D2 mục 5, đơn vị của D6, nhận biết import) được liệt kê ở mục "Độ Lệch Và Bổ Sung" của kế hoạch 1B và sẽ được sửa ở Slice 0 của 1B.
- [review-telegram-plan-rasoat-2026-10-03.md](review-telegram-plan-rasoat-2026-10-03.md): kết quả rà soát độc lập tài liệu này và trạng thái áp dụng từng mục.

Nguồn: 4 agent đọc toàn bộ tài liệu `.md`, backend (model, service, API, worker) và frontend; các phép backtest bằng script chạy trên DB dev (Phụ lục B); 3 agent rà soát độc lập ngày 2026-10-03. Mục nào chưa kiểm chứng được ghi **[CHƯA XÁC MINH]**.

**Quy ước trong tài liệu.**
- Số trong văn xuôi và bảng dùng dấu phẩy thập phân kiểu Việt (ví dụ 4,49%). Số trong khối mẫu tin nhắn và ví dụ dữ liệu theo quy ước hiển thị của sản phẩm (ví dụ `7,900.00 VNĐ/KG`, `+5.57%`).
- "Vật tư" là thuật ngữ chuẩn (CONTEXT.md). "Điểm giá" là giá thấp nhất trong ngày của một chuỗi.
- **Ký hiệu:** `R1`, `R2`, `R3` là các **quy tắc** tính biến động (D2). `RR-1` đến `RR-n` là các **rủi ro** (Mục 6). `QĐ-n` là quyết định đã chốt (Mục 0.1). `H1` đến `H15` là các câu hỏi đã trả lời (Mục 9.1). `K1` đến `K19` là quyết định kỹ thuật của kế hoạch 1A.

**Mục lục:** 0 Tóm tắt · 0.1 Quyết định đã chốt · 1 Nền tảng · 2 Phạm vi và thuật ngữ · 3 Quyết định D1 đến D12 (nhóm A: D1 đến D6 và D12; nhóm B: D7 đến D10; nhóm C: D11) · 4 Bước 1 · 5 Bước 2 · 6 Rủi ro · 7 Kế hoạch theo giai đoạn · 8 Khuyến nghị production · 9 Câu hỏi đã trả lời và điểm còn mở · 10 Phụ lục A: tập tin · Phụ lục B: backtest.

---

## 0. Tóm tắt điều hành

1. **Cập nhật 2026-10-04:** phần liên kết tài khoản Telegram (Giai đoạn 1A) đã có code, tắt mặc định bằng `TELEGRAM_ENABLED=false`. Phần thông báo biến động giá (1B trở đi), LLM, OCR và PDF **chưa có** trong repo. Hai tài liệu kế hoạch (tài liệu này và kế hoạch 1A) là nơi mô tả.
2. Hạ tầng tái dùng được: worker **arq + Redis** (đã có cron), pattern adapter `httpx` (Vietcombank), `EmailService` (mẫu "thông báo không làm hỏng nghiệp vụ"), cơ chế audit, nginx đã proxy `/api/`. Truy vấn daily-min theo chuỗi **chưa có** (`QuotifyDashboardService` chỉ trả điểm thô và tóm tắt), phải viết hàm mới (mục 4.3).
3. Điểm mới cần thêm: bảng liên kết Telegram, bảng sự kiện, tin và quét, bảng cấu hình ngưỡng, engine tính biến động, bộ vẽ biểu đồ ảnh phía server, webhook nhận tin từ Telegram.
4. **Bước 1 đã cần nhận tin từ Telegram.** Để liên kết tài khoản an toàn bằng mã `/start <mã liên kết>`, bot phải nhận được update. Vì vậy webhook (hoặc long-polling) phải có ngay ở Bước 1.
5. Các gói thuê bao tiêu dùng (ChatGPT, Gemini, Claude trả phí theo tháng) **không** cấp quyền gọi API. Chatbot cần API key riêng tính phí theo token. Đã chốt: dev dùng Google AI Studio (gói miễn phí), production chưa chọn nhà cung cấp (D11).
6. Chatbot hỏi đáp dùng **tool-calling với các hàm cố định**, không cho AI tự sinh SQL. Điều này đáp ứng "chỉ READ" và "cấm SQL nguy hiểm" bằng thiết kế.
7. **Điều kiện gửi tin đã chốt:** bộ ba quy tắc R1/R2/R3 so với 7 ngày làm việc liền trước (D2, D3), ngưỡng 2,5 / 5 / 10% cấu hình được theo từng vật tư (D4). **Nguồn kích hoạt** là version không do tài khoản seed admin tạo và có độ trễ không quá 3 ngày làm việc (D6, QĐ-16). **Tin** gộp theo vật tư trong một lần quét, chỉ gửi bổ sung khi leo thang (D5, QĐ-17). **Giá bất thường** có vòng đời riêng (D12, QĐ-18). Trưởng phòng được sửa ngưỡng và bật/tắt tính năng (QĐ-19).
8. **Tải tin thật cao hơn con số backtest.** 82,5% dòng trong 12 tháng là dữ liệu import một lần, dữ liệu nhập thật chỉ có 6,3 tuần. Với nguồn kích hoạt theo D6 mới, ước lượng khoảng 17,7 tin gộp mỗi tuần (7,3 tin Trung bình và Lớn), cao hơn 7,8 và 2,9 của backtest (Phụ lục B.8). Cần dry-run ở chế độ replay trước khi chốt các trần.
9. Việc tiếp theo: Slice 7 của kế hoạch 1A (đưa lên production, thao tác trên VPS), rồi soạn kế hoạch 1B riêng theo mẫu 1A. Kết quả kiểm chứng với Telegram thật (T2, T3, T5, T5b) nằm ở Phụ lục A của kế hoạch 1A.

---

## 0.1 Quyết định đã chốt

| # | Ngày | Quyết định | Chi tiết |
|---|---|---|---|
| QĐ-1 | 2026-10-03 | Điều kiện gửi tin là **bộ ba quy tắc** R1 (so với điểm giá gần nhất), R2 (so với giá thấp nhất), R3 (so với giá cao nhất) của 7 ngày làm việc liền trước. **R2 chỉ áp dụng khi R1 tăng, R3 chỉ khi R1 giảm, hướng của tin theo R1** (xem QĐ-12). Chỉ quan tâm giá, **không phân biệt nhà cung cấp** | D2 |
| QĐ-2 | 2026-10-03 | Cửa sổ tham chiếu là **7 ngày làm việc**, loại trừ thứ Bảy và Chủ Nhật | D3 |
| QĐ-3 | 2026-10-03 | Có loại thông báo riêng cho **giá bất thường** (nghi nhập sai). Vòng đời chi tiết ở QĐ-18 | D12 |
| QĐ-4 | 2026-10-03 | Ba khoảng % (Nhẹ, Trung bình, Lớn) **cấu hình được theo từng vật tư**. Mặc định 2,5 / 5 / 10%. **Admin và trưởng phòng** được sửa | D4 |
| QĐ-5 | 2026-10-03 | LLM: **dev dùng API key Google AI Studio (Gemini), gói miễn phí**. Nhà cung cấp production chưa chọn, thiết kế adapter đa nhà cung cấp | D11, 5.5 |
| QĐ-6 | 2026-10-03 | Chính sách dữ liệu: **cho phép** gửi nội dung báo giá, ảnh và PDF sang hệ thống bên thứ ba | D11 |
| QĐ-7 | 2026-10-03 | Phạm vi bot: **chỉ chat riêng**, **chỉ tiếng Việt có dấu**, **không có khung giờ yên lặng** | 4.4, 4.8, 5.1 |
| QĐ-8 | 2026-10-03 | Tin nhắn **hiển thị thêm giá CNF (USD/MT)** cho dòng nhập USD | 4.2 |
| QĐ-9 | 2026-10-03 | Chatbot nhập liệu **luôn tạo nháp rồi mới chốt**. **Ghi nhận nguồn nhập qua Telegram**: **icon bot ở cột "Trạng thái"** của danh sách báo giá, kèm **ô tick lọc** theo nguồn Telegram | 4.5, 4.9, 5.3 |
| QĐ-10 | 2026-10-03 | **Admin hệ thống quản lý chi phí LLM**, trần ngân sách khoảng **2.000.000 VNĐ mỗi tháng**. Cảnh báo ngân sách gửi **qua email admin** | 5.6 |
| QĐ-11 | 2026-10-03 | Chưa loại ngày lễ và Tết khỏi ngày làm việc | D3 |
| QĐ-12 | 2026-10-03 | Giá bất thường chỉ chấp nhận bằng nút **Giá đúng** (không tự động). Người nhận: **trưởng phòng và người nhập**. Hướng tin theo bước nhảy cuối (R1) | D2, D12 |
| QĐ-13 | 2026-10-03 | **Không tính biến động % trên CNF**: chuỗi USD/MT cũng chỉ tính % trên VNĐ/KG | D1, 4.2 |
| QĐ-14 | 2026-10-03 | Đồng ý các đề xuất **D5 đến D10**: chống spam (chỉ gửi khi chiều hoặc mức đổi, gộp tin theo vật tư, mức Nhẹ vào bản tin 08:00, trần số tin mỗi lần quét), trưởng phòng nhận tin của mọi vật tư (mặc định từ mức Trung bình), nhân viên nhận tin của vật tư mình đã nhập trong 90 ngày, admin chỉ nhận khi bật tùy chọn, mỗi người có cờ bật/tắt và mức tối thiểu. **Phần nguồn kích hoạt của D6 đã được thay bằng QĐ-16** | D5 đến D10 |
| QĐ-15 | 2026-10-03 | Chuỗi so sánh là **(vật tư, kỳ giao hàng)**, **không gộp nhiều kỳ giao hàng**. Giá so sánh là `price_converted_vnd_per_kg` của version `confirmed`, phiếu chưa hủy | D1 |
| QĐ-16 | 2026-10-04 | **Nguồn kích hoạt (thay D6 cũ):** version không do **tài khoản seed admin** tạo (nhận biết import bằng tài khoản này) **và** có độ trễ không quá **3 ngày làm việc** từ `received_date` đến ngày chốt. Không còn dùng `is_backfilled` làm điều kiện | D6 |
| QĐ-17 | 2026-10-04 | **Đơn vị tin (D5b):** một tin cho mỗi người nhận, mỗi vật tư, mỗi lần quét. Cùng ngày chỉ gửi bổ sung khi **leo thang** hoặc đổi chiều. Ảnh kèm caption ngắn, chi tiết các kỳ giao hàng gửi bằng tin văn bản ngay sau. Không sửa tin cũ | D5 |
| QĐ-18 | 2026-10-04 | **Vòng đời giá bất thường:** loại ở mức dòng rồi tính lại daily-min; cửa sổ gắn cờ 30 ngày; gộp cụm; người nhập nhận tin không có nút; chỉ người có `price_alerts.receive_all` và admin bấm được; có nhắc và hết hạn. Cảnh báo ngay lúc nhập (USD gõ vào ô VNĐ/KG) tách thành tính năng riêng, ngoài phạm vi 1A đến 1C | D12 |
| QĐ-19 | 2026-10-04 | **Quyền:** `price_alerts.manage` cho admin **và trưởng phòng, gồm cả bật/tắt tính năng**; cấp bằng migration tự chèn quyền (phương án a); giao diện cấu hình ở **trang mới** `/price-alert-settings`, không cấp `quotify_settings.read` cho trưởng phòng; cờ môi trường là điều kiện cần, cờ DB là điều kiện đủ | 4.6, 4.9 |
| QĐ-20 | 2026-10-04 | **Chu kỳ quét 30 giây** (thay 2 phút), giữ cơ chế cron quét + watermark chồng lấp 5 phút + khóa advisory; chỉ ghi `scan_runs` khi có việc, nhịp tim ở `scan_state.last_run_at`; thêm trần 30 tin trong 10 phút cho mỗi người. Chi tiết ở kế hoạch 1B, L27 | 4.1, D5(d) |

---

## 1. Hiểu biết nền tảng về dự án (đã xác minh từ code)

### 1.1 Stack và hạ tầng

| Thành phần | Chi tiết |
|---|---|
| Backend | Python 3.12, FastAPI 0.136, SQLAlchemy 2 async + asyncpg, Alembic, Pydantic v2, `uv` |
| Worker | arq 0.26 + Redis 7. Chỉ có 1 cron (`poll_and_run_scheduled_backups`, mỗi phút). Chạy `arq app.worker.WorkerSettings` |
| DB | Postgres 16. Một role duy nhất (`postgres`). Alembic head hiện tại: `20261004_1100` (sau hai migration Telegram 1A; số liệu cũ `20260824_1000` đã lỗi thời) |
| Frontend | Vue 3.5 + TS, Pinia, PrimeVue 4, Chart.js, vee-validate + zod, SCSS tập trung (cấm `<style>` trong `.vue`) |
| Deploy | VPS, build qua SSH, **không CI/CD**. Migrate bằng `docker compose -f docker-compose.prod.yml run --rm backend uv run alembic upgrade head` **trước** `up -d`. Sau `up -d` phải `restart reverse-proxy` |
| Domain | `quotify.honghafeed.com.vn`, HTTPS 443 (certbot). Nginx route `/api/` → backend nên webhook đi qua được mà không sửa nginx |
| Thư viện thiếu | Không có SDK Telegram, SDK LLM, matplotlib/Pillow, thư viện đọc PDF |

Phân tầng backend: `api/v1/*` (route, kiểm quyền, ownership, audit, **commit**) → `services/*` (logic, chỉ `flush`, **không kiểm quyền**) → `models/*`. Thư mục `repositories/` rỗng.

### 1.2 Mô hình dữ liệu giá

- Giá chỉ nằm ở `quote_lines`: `price_original` + `currency` (VND/USD) + `unit` (KG/MT), và **`price_converted_vnd_per_kg`** (giá chuẩn hóa VNĐ/KG, đóng băng lúc confirm).
- Chỉ hỗ trợ 2 cặp: `VND/KG` và `USD/MT`. Công thức USD/MT: `(giá/1000) × (1 + thuế%) × tỷ giá + chi phí làm hàng`.
- Chuỗi tự nhiên của một vật tư: **(`material_id`, `delivery_month`)**. `delivery_month` luôn là ngày 01 của tháng trong dữ liệu thật, nhưng backend **không ép** (bẫy RR-1 ở Mục 6).
- Phiên bản: `draft → confirmed → superseded`. Mỗi phiếu tối đa 1 draft. Phân tích hiện có chỉ dùng `status='confirmed'` AND `confirmed_at IS NOT NULL` AND `quotes.cancelled_at IS NULL`.
- Ba mốc thời gian khác nhau: `received_date` (ngày nhận, Date, ngày nghiệp vụ), `confirmed_at` (lúc dữ liệu có hiệu lực), `delivery_month` (kỳ giao hàng).
- "Người nhập phiếu" = `quotes.created_by_id` (bất biến, nguồn KPI). `quote_versions.created_by_id` là người tạo từng version (trưởng phòng tạo bản điều chỉnh thì là trưởng phòng). Hai nơi trong code dùng hai định nghĩa khác nhau.
- **Không có bảng gán nhân viên ↔ vật tư phụ trách.** "Vật tư mình nhập" phải suy ra từ `quotes.created_by_id × quote_lines.material_id`.
- Dashboard loại tài khoản seed admin (`AUTH_SEED_ADMIN_EMAIL`, dùng cho import) khỏi thống kê theo người.

**Quy mô.** Có hai nguồn dữ liệu, mỗi con số trong tài liệu ghi rõ nguồn:

| Chỉ tiêu | Dump `backups/postgres_20261003T060900.sql.gz` (chưa xác minh là production) | DB dev hiện tại (khôi phục từ dump Downloads 2026-10-02) |
|---|---|---|
| Phiếu | 3.067 | 3.434 (3 phiếu đã hủy) |
| Version | 3.086 | 3.478 (confirmed 3.412, superseded 41, draft 25) |
| Dòng giá | 19.969 | 21.102 (confirmed chưa hủy: 20.893) |
| Vật tư | 119 (36 có báo giá) | 122 (51 có dòng giá) |
| Nhà cung cấp | 311 | 321 |
| Người dùng | 12 (admin 1, user 8, manager 3) | 10 (admin 1, user 7, manager 2) |
| Chuỗi (vật tư, kỳ giao hàng) | 261 | 361 |
| Version nhập lùi (`is_backfilled`) | 3.026 / 3.086 | 3.279 / 3.478 (94,3%) |

Backtest (Phụ lục B) chạy trên DB dev. Trung vị mỗi chuỗi có 4 điểm giá (daily-min), tối đa 44 kỳ giao hàng cho một vật tư trong toàn kỳ (20 trong 12 tháng), trung vị 5 kỳ giao hàng mỗi vật tư.

### 1.3 Role và quyền

- Seed chỉ có `admin` (bypass mọi quyền theo tên role) và `user` (21 quyền).
- **"Trưởng phòng" trên dữ liệu thật là role `manager`** (không phải role hệ thống, tạo tay ngày 2026-08-25): quyền của `user` + `quotes.correct_user_quotes`. Số người dùng theo role xem bảng ở 1.2 (dump `backups/`: manager 3; DB dev hiện tại: manager 2).
- Code **không** hard-code tên `manager`, chỉ dùng permission `quotes.correct_user_quotes`. Role không phải hệ thống có thể bị đổi tên hoặc xóa, nên không nên gắn logic thông báo vào tên role: dùng permission.
- `seed_auth_rbac.py` chỉ cập nhật role `admin` và `user`. Role `manager` **không** được seed. Tiền lệ `20260729_0810_restrict_quotify_settings_user_role.py` chỉ chạy `DELETE FROM role_permissions` (không có `INSERT`). Bảng `permissions` chỉ được điền bởi `AuthSeedService._ensure_permissions`, mà runbook chạy migrate **trước** seed, nên một migration chỉ gán quyền sẽ chạy rỗng. Migration cấp quyền phải tự chèn các dòng `permissions` (xem 4.6, QĐ-19).
- `test_permission_inventory.py` bắt buộc mọi permission dùng trong code phải có trong `BASE_PERMISSION_CODES`.
- Auth: access JWT 30 phút (bộ nhớ) + refresh cookie httpOnly. Bot Telegram không có JWT, nên phải gọi service trực tiếp trong tiến trình và **tự kiểm quyền** (xem RR-3).

### 1.4 Logic biểu đồ và biến động hiện có

- Backend chỉ trả điểm thô và `summary` min/max/avg (`QuotifyDashboardService`). **Chưa có** hàm tính % biến động theo thời gian, ngưỡng, hay phân loại tăng/giảm.
- Frontend (`useDashboardPage.ts`) tự gom: mỗi ngày nhận giữ **1 điểm = giá thấp nhất trong ngày** (daily-min), MIN/MAX/AVG tính trên chuỗi daily-min. Điểm đã chốt mua tô đỏ.
- Backend `summary` tính min/max/avg trên **mọi dòng**, khác với frontend (trên daily-min). Hai nơi hiện **không nhất quán**. Tin Telegram phải chọn một và ghi rõ.
- Chart.js chỉ chạy ở frontend. Muốn gửi ảnh biểu đồ qua Telegram phải **vẽ lại phía server** bằng thư viện mới.

### 1.5 Quy tắc dự án phải tuân thủ

- Tài liệu tiếng Việt **phải có dấu**. Tiền hiển thị `10,200.00 VNĐ/KG` (cấm `đ/KG`, `₫`). Ngày `DD/MM/YYYY`, kỳ giao hàng `MM/YYYY`, giờ `Asia/Ho_Chi_Minh`.
- Chỉ **enqueue job SAU khi commit**. Lỗi gửi thông báo **không được** làm đổi kết quả nghiệp vụ (bug 27/07). Retry phải idempotent.
- Audit metadata có **allow-list** (`ALLOWED_AUDIT_METADATA_KEYS`): key lạ bị thay bằng `[REDACTED]`, key chứa `token/secret/session/credential` luôn bị che.
- Tiền dùng `Decimal`, `ROUND_HALF_UP`, scale 2. Không dùng float.
- Hệ thống **không tự kết luận mua đúng/sai** (Requirements 3.9). Giọng thông báo phải trung tính.
- TDD, verify bằng `curl`/browser thật (unit test với fake session không bắt được `MissingGreenlet`), E2E chuẩn là `make docker-test-e2e`. Đóng task bằng `scripts/agent-task-close.sh` và cập nhật `memory-bank/`.
- Hiện có nợ kỹ thuật cũ: ESLint 12 lỗi, Prettier 74 file lệch, vài test frontend fail baseline. Không sửa lan trong PR tính năng, nhưng code mới phải sạch.

---

## 2. Xung đột với phạm vi đã ghi trong tài liệu

Tài liệu hiện **tuyên bố ngoài phạm vi** các mục gần với yêu cầu mới:

| Tài liệu | Nội dung đang ghi | Ảnh hưởng |
|---|---|---|
| `quotify-implementation-plan.md` dòng ~29-36 | Ngoài phạm vi: "Email nhắc người chưa nhập báo giá", "Mô hình dự báo giá, AI recommendation", "Dashboard nâng cao" | Cần cập nhật bằng văn bản trước khi code |
| `Requirements.txt` mục 3.4 | "Không gửi email nhắc nhở" | Như trên |
| `Requirements.txt` mục 3.9 | "Hệ thống không tự kết luận quyết định mua là đúng hay sai" | Thông báo và chatbot phải giữ giọng trung tính, không "nên mua/bán" |

**Việc cần làm trước khi code (Slice 0 của 1A):** ghi vào "Nhật ký thay đổi" của kế hoạch, cập nhật `CONTEXT.md` và nêu rõ chatbot **không đưa khuyến nghị mua/bán**. Thuật ngữ cần thêm vào `CONTEXT.md` (gộp từ hai tài liệu kế hoạch):

| Thuật ngữ | Nghĩa |
|---|---|
| **Điểm giá** | Giá thấp nhất trong ngày (daily-min) của một chuỗi, giữa mọi nhà cung cấp |
| **Chuỗi** | Cặp (vật tư, kỳ giao hàng) |
| **Cửa sổ tham chiếu** | 7 ngày làm việc liền trước ngày của điểm mới |
| **Ngày làm việc** | Thứ Hai đến thứ Sáu (chưa loại ngày lễ, Tết) |
| **Biến động giá**, **Mức biến động**, **Ngưỡng cảnh báo** | Kết quả của R1/R2/R3 và ba mức Nhẹ, Trung bình, Lớn |
| **Nguồn kích hoạt** | Version đủ điều kiện sinh thông báo (D6) |
| **Giá bất thường** | Dòng giá lệch lớn so với trung vị, nghi nhập sai (D12) |
| **Sự kiện** và **Tin** | Sự kiện là một kết quả đánh giá cho một chuỗi. Tin là một thông báo Telegram gộp các sự kiện của một vật tư cho một người nhận |
| **Bản tin tổng hợp** | Tin gửi 08:00 giờ VN chứa các sự kiện mức Nhẹ |
| **Trưởng phòng** | Người có permission `price_alerts.receive_all` (thực tế là role `manager`) |
| **Liên kết Telegram**, **Đường dẫn liên kết**, **Mã liên kết**, **Hủy liên kết**, **Đổi tài khoản Telegram** | Xem kế hoạch 1A |

---

## 3. Quyết định D1 đến D12

Nhóm A (D1 đến D6 và D12) định nghĩa biến động giá. D12 nằm sau D6 vì cùng thuộc nhóm này. Nhóm B (D7 đến D10) là người nhận. Nhóm C (D11) là chatbot.

### Nhóm A: Định nghĩa biến động giá

**D1. Giá nào để so sánh? (ĐÃ CHỐT, QĐ-15)**
- `price_converted_vnd_per_kg`, chuỗi **(vật tư, kỳ giao hàng)**, chỉ version `confirmed`, phiếu chưa hủy.
- **Không phân biệt nhà cung cấp** (QĐ-1): điểm giá của một ngày là giá thấp nhất trong ngày giữa mọi nhà cung cấp.
- **Chuỗi USD/MT cũng chỉ tính % trên VNĐ/KG** (QĐ-13), không thêm quy tắc tính % trên CNF.
- Dòng USD/MT bị ảnh hưởng bởi tỷ giá: cùng giá USD nhưng tỷ giá đổi vẫn thành "biến động". Chấp nhận được vì giá VNĐ/KG mới là thứ phòng Thu Mua mua thật. Tin ghi rõ "giá quy đổi" và có dòng CNF (4.2) để người đọc nhận ra biến động do tỷ giá.
- **Không gộp nhiều kỳ giao hàng vào một chuỗi** vì giá kỳ xa khác kỳ gần (QĐ-15).
- Một điểm giá có thể thuộc nhà cung cấp khác với điểm trước. Đo trên dữ liệu: 70,6% điểm bị báo có nhà cung cấp rẻ nhất khác với điểm trước (Phụ lục B.8). Tin phải ghi điều này (D5).

**D2. Điều kiện biến động (ĐÃ CHỐT, QĐ-1): bộ ba quy tắc so với 7 ngày làm việc liền trước.**

Định nghĩa:
- **Điểm giá** của một ngày là giá thấp nhất trong ngày (daily-min) của chuỗi, sau khi loại các dòng bị gắn cờ bất thường (D12).
- **Điểm mới** là điểm của ngày đang xét. **Các điểm trước** là các điểm nằm trong cửa sổ 7 ngày làm việc (D3), không gồm điểm mới.
- Một chuỗi và một ngày chỉ được **đánh giá lại** khi điểm giá của ngày đó thay đổi so với lần đánh giá trước. Báo giá thứ hai trong ngày không làm đổi daily-min thì không sinh sự kiện.

| Quy tắc | So giá mới với | Áp dụng khi |
|---|---|---|
| **R1** | Điểm giá trước **gần nhất** | luôn luôn |
| **R2** | Giá **thấp nhất** của các điểm trước | giá mới **tăng** so với R1 |
| **R3** | Giá **cao nhất** của các điểm trước | giá mới **giảm** so với R1 |

Cách kết hợp:
1. **Hướng** của tin theo hướng của R1 (bước nhảy cuối). Giá mới bằng đúng điểm trước thì không có tin.
2. **Mức** của tin là mức cao nhất trong các quy tắc áp dụng, tính theo ngưỡng của vật tư (D4). **Lý do chính** là quy tắc cho mức cao nhất. Về mặt toán học, khi tăng thì |R2| ≥ |R1| (đáy không lớn hơn điểm gần nhất), khi giảm thì |R3| ≥ |R1|. Vì vậy R1 chỉ có thể là lý do chính khi |%| bằng nhau, tức điểm gần nhất chính là đáy hoặc đỉnh (430/1.540 lần trong backtest). **Khi |%| bằng nhau thì ưu tiên R1.** Các quy tắc còn lại hiển thị như thông tin phụ, và **không in dòng phụ nếu nó trùng điểm tham chiếu với lý do chính**.
3. Cần **ít nhất 1 điểm trước** trong cửa sổ, nếu không thì không gửi.
4. Điểm đã bị gắn "giá bất thường" (D12) và còn ở trạng thái `pending` hoặc `rejected` không được dùng làm điểm tham chiếu và không sinh tin biến động. Điểm đã được "Giá đúng" hợp lệ trở lại.
5. **Dòng ứng viên của version điều chỉnh.** Version mới chứa đầy đủ dòng của phiếu, nhưng **backend không sao chép** từ version cũ: frontend gửi lại toàn bộ dòng, và dòng không có khóa nguồn (`source_line_id`). Chỉ các dòng **mới thêm hoặc đổi giá** so với version nguồn (`superseded_by_version_id`) mới tham gia đánh giá; cách tìm chúng (so tập đa giá theo chuỗi, ba ngoại lệ) định nghĩa ở kế hoạch 1B, L1. `delete_confirmed_line` tạo version mới nhưng không có dòng nào đổi giá: có thể làm daily-min của ngày đổi nhưng **không phát tin**.

**Vì sao điều chỉnh so với cách hiểu theo chữ.** Nếu mỗi quy tắc chạy độc lập rồi lấy mức cao nhất, backtest cho thấy khoảng 20% tin (403/1.986, loại 82 điểm có R1 = 0) có nhãn tăng/giảm ngược với bước nhảy cuối. Quy tắc nhất quán hướng loại bỏ mâu thuẫn này, khối lượng tin gần như không đổi (19,5 so với 20,3 tin/tuần theo chuỗi). Đã được xác nhận (QĐ-12).

Ví dụ (giá thấp nhất mỗi ngày, VNĐ/KG, điểm mới là thứ Sáu 02/10/2026, cửa sổ là 23/09 đến 01/10):

| | Các điểm trước | Điểm mới | R1 | R2 / R3 | Kết quả |
|---|---|---|---|---|---|
| **1. Tăng** | 23/09: 7,900 · 25/09: **7,720** · 30/09: 7,800 | 8,150 | +4,49% (so với 7,800) | R2: **+5,57%** (so với đáy 7,720) | 🔺🟠 **Tăng Trung bình**, lý do chính R2 |
| **2. Giảm** | 24/09: **10,400** · 28/09: 10,000 · 30/09: 9,800 | 9,300 | −5,10% (so với 9,800) | R3: **−10,58%** (so với đỉnh 10,400) | 🔻🔴 **Giảm Lớn**, lý do chính R3 |
| **3. Hướng ngược** | 25/09: 9,000 · 30/09: 10,000 | 9,600 | −4,00% (so với 10,000) | R2 **bỏ qua** vì R1 là giảm (R2 sẽ là +6,67%). R3 cũng −4,00% và trùng điểm tham chiếu với R1 nên không in dòng phụ | 🔻🟡 **Giảm Nhẹ**, lý do chính R1 |

Ví dụ 3 cho thấy lý do cần quy tắc nhất quán hướng: giá đã giảm so với lần trước nên tin phải là "giảm", dù giá vẫn cao hơn đáy tuần.

**Các phương án đã so sánh** (định nghĩa ở đầu Phụ lục B): A, B, C, MIN, MM. Bộ ba quy tắc bắt được cú đảo chiều mà A bỏ sót. Không có dòng "xu hướng 14 ngày" (A) trong tin: đã loại khỏi phạm vi.

**D3. Cửa sổ tham chiếu (ĐÃ CHỐT, QĐ-2): 7 ngày làm việc.**
- Cửa sổ là 7 ngày làm việc (thứ Hai đến thứ Sáu) liền trước ngày của điểm mới, theo `received_date`, múi giờ `Asia/Ho_Chi_Minh`. **Thứ Bảy và Chủ Nhật không được đếm.**
- Cách tính: lùi từng ngày từ ngày liền trước, bỏ qua thứ Bảy và Chủ Nhật, cho đến khi đủ 7 ngày làm việc. Cửa sổ là khoảng từ ngày thứ 7 đó đến ngày liền trước, tức **9 đến 11 ngày lịch**. Ví dụ điểm mới thứ Sáu 02/10/2026 thì cửa sổ là 23/09 đến 01/10.
- Điểm giá nhận vào cuối tuần (0,7% số dòng, 1,3% số điểm trong 12 tháng gần nhất) vẫn được dùng làm điểm tham chiếu nếu nằm trong khoảng.
- **Ngày lễ và Tết chưa được loại trừ ở v1** (QĐ-11). Kỳ nghỉ dài làm cửa sổ thưa điểm, nhưng không sinh tin sai vì quy tắc cần có ít nhất 1 điểm trước.
- Mốc **kích hoạt** là `confirmed_at` (lúc version có hiệu lực).
- Biểu đồ gửi kèm hiển thị 14 ngày lịch để người mua thấy bức tranh rộng, và tô sáng vùng tham chiếu 7 ngày làm việc.

**D4. Biên ngưỡng (ĐÃ CHỐT, QĐ-4): mặc định 2,5 / 5 / 10%, cấu hình được theo từng vật tư.**
- Mặc định toàn hệ thống, tính theo `|%|` bằng `Decimal`, **không làm tròn trước khi so** (4,996% hiển thị "5.00%" nhưng xếp mức Nhẹ):
  - Nhẹ: `2,5 ≤ x < 5`
  - Trung bình: `5 ≤ x ≤ 10`
  - Lớn: `x > 10`
  - Dưới 2,5%: không gửi.
- Tên cột phản ánh đúng phép so: `light_from_percent` (≥), `medium_from_percent` (≥), `large_over_percent` (>).
- **Ghi đè theo vật tư:**
  - Theo **vật tư** (không theo kỳ giao hàng).
  - Ghi đè đủ **cả ba số** hoặc không ghi đè. Điều kiện `0 < Nhẹ < Trung bình < Lớn < ngưỡng bất thường`.
  - Vật tư không có ghi đè dùng mặc định.
  - Thay đổi có hiệu lực từ lần quét kế tiếp, **không báo lại** dữ liệu cũ.
  - Mọi thay đổi ghi audit (`changes[]`, old/new).
  - Ai được sửa: **admin và trưởng phòng** (permission `price_alerts.manage`, QĐ-4, QĐ-19).
- **Vì sao cần ghi đè** (Phụ lục B.7): mức dao động khác nhau theo vật tư. Trung vị |%| của các điểm bị báo: Khô đậu tương 4,3% (P90 8,0%), Ngô hạt 3,3% (P90 5,2%), Methionine 4,9% (P90 13,7%). Riêng Khô đậu tương chiếm khoảng 52% số điểm bị báo, nên là ứng viên đầu tiên cho ngưỡng cao hơn.

**D5. Chống spam và đơn vị tin (ĐÃ CHỐT, QĐ-14 và QĐ-17).**

Khối lượng tin là vấn đề thật: daily-min giữa các nhà cung cấp dao động nhiều, và tải thật cao hơn backtest (Phụ lục B.8). Quy tắc:

- **(a) Chống lặp theo chuỗi:** chỉ gửi khi **(chiều, mức) khác lần đã gửi gần nhất của chuỗi đó trong 14 ngày lịch**. Sự kiện mức Nhẹ nằm trong bản tin tổng hợp được tính là "đã gửi".
- **(b) Đơn vị tin (QĐ-17).** Phân biệt hai thực thể:
  - **Sự kiện** (`price_alert_events`): một kết quả đánh giá cho một chuỗi, một ngày.
  - **Tin** (`price_alert_messages`): một thông báo Telegram cho **một người nhận**, **một vật tư**, **một lần quét**, gộp mọi sự kiện của các kỳ giao hàng thuộc vật tư đó.
  - Cùng ngày địa phương, một lần quét sau chỉ gửi **tin bổ sung** khi có sự kiện **leo thang** (mức cao hơn mức cao nhất đã gửi trong ngày cho vật tư đó, hoặc đổi chiều). Nếu không leo thang thì ghi nhận sự kiện với trạng thái `suppressed`, không gửi. **Không sửa tin đã gửi.**
  - Ảnh biểu đồ vẽ kỳ giao hàng có mức cao nhất. Caption ảnh **ngắn** (tối đa 1.024 ký tự theo giới hạn Telegram): tiêu đề, mức, giá mới, lý do chính. **Chi tiết các kỳ giao hàng gửi bằng một tin văn bản** (tối đa 4.096 ký tự) ngay sau ảnh. Khi các kỳ khác hướng, tiêu đề theo kỳ có mức cao nhất và khối chi tiết ghi hướng từng kỳ.
  - Mỗi tin ghi "điểm giá có thể thuộc nhà cung cấp khác với lần trước" (D1).
  - Tính idempotent bằng `UNIQUE (user_id, material_id, scan_run_id, kind)` trên `price_alert_messages`.
- **(c) Mức Nhẹ vào bản tin tổng hợp** 08:00 giờ VN. Mức Trung bình và Lớn gửi ngay (khoảng 7,3 tin gộp mỗi tuần theo ước lượng ở B.8, cao hơn 2,9 của backtest). Nếu worker tắt lúc 08:00 thì bản tin được gửi ở lần chạy kế tiếp trong cùng ngày (nhớ bằng `last_digest_local_date`).
- **(d) Trần gửi ngay mỗi lần quét** (mặc định 30 tin). Vượt trần thì gửi một tin tóm tắt "còn N thay đổi, xem trên web", phần còn lại chuyển trạng thái `digest_queued`.
- **(e)** Có thể nâng ngưỡng Nhẹ của các vật tư dao động mạnh bằng cấu hình theo vật tư (D4).

**D6. Nguồn kích hoạt thông báo (ĐÃ CHỐT, QĐ-16; thay thế phần nguồn dữ liệu của QĐ-14).**

Một version `confirmed` là **nguồn kích hoạt** khi đồng thời:
1. **Không do import:** `quotes.created_by_id` khác tài khoản seed admin (`AUTH_SEED_ADMIN_EMAIL`). Import báo giá cũ và import danh mục đều dùng tài khoản này.
2. **Trễ không quá 3 ngày làm việc:** số ngày làm việc (thứ Hai đến thứ Sáu) từ `received_date` đến ngày chốt (ngày của `confirmed_at` theo giờ VN) không quá 3. Chốt cùng ngày là trễ 0.
3. Phiếu chưa hủy.

Version không phải nguồn kích hoạt **vẫn được dùng làm điểm tham chiếu** (và vẫn được đánh giá bất thường để gắn cờ, D12), chỉ không sinh tin biến động. `is_backfilled` **không còn** là điều kiện.

Lý do thay đổi (Phụ lục B.8):
- `is_backfilled` chỉ được kiểm khi tạo hoặc sửa bản nháp (`_validate_backfill`), **không kiểm lúc chốt**: bản nháp tạo hôm trước rồi chốt hôm nay vẫn có `is_backfilled=false` dù `received_date` đã cũ. Ngược lại, phiếu nhập trễ 1 ngày cũng bị ép `true`.
- Trong 12 tháng chỉ 565 dòng (5,8%) là nhập thật, 82,5% là import (8.082 dòng, cùng tạo ngày 19/08/2026 bằng tài khoản seed). Điều kiện `is_backfilled=false` giữ lại khoảng 38% khối lượng tin của dữ liệu nhân viên thật. Dữ liệu nhân viên nhập lùi có 1.151 dòng, trong đó 220 dòng trễ không quá 1 ngày **lịch**, 373 dòng không quá 3 ngày lịch, 522 dòng không quá 7 ngày lịch. Đó là ngày lịch và chỉ cho dòng nhập lùi; theo **ngày làm việc** và cho mọi dòng người thật, trễ ≤ 3 là 283 version và 1.030 dòng (kế hoạch 1B, Phụ lục C thay bảng tải ở B.8).
- Ngưỡng trễ 3 ngày làm việc tránh bão tin do import mà không bỏ phí tin trễ vài ngày.

Giới hạn:
- Nhận biết import chỉ qua tài khoản seed admin, không có đánh dấu riêng, và import dùng **id người tải file** chứ không ép tài khoản seed. Quy ước đã chốt (kế hoạch 1B, Q7, L17): admin hệ thống chỉ quản trị và import, không bao giờ nhập tay, nên tài khoản seed là tài khoản import; Slice 0 kiểm production để xác nhận. Không cần tài khoản riêng cho import.
- Khi bật cờ lần đầu, và **mỗi lần bật lại**, watermark đặt bằng thời điểm bật (4.1) để dữ liệu cũ không sinh tin.
- Ước lượng tải theo điều kiện này và các số cần đo lại ở dry-run replay: Phụ lục B.8.

**D12. Giá bất thường (ĐÃ CHỐT, QĐ-3, QĐ-12, QĐ-18): loại thông báo riêng, nghi nhập sai.**

*Phát hiện.*
- Xét ở **mức dòng báo giá** của version vừa chốt, **kể cả version không phải nguồn kích hoạt** (chỉ để gắn cờ, không sinh tin biến động).
- Một dòng bị gắn cờ khi giá quy đổi lệch từ **30%** (mặc định toàn hệ thống, ghi đè được theo vật tư) so với **trung vị** các điểm giá hợp lệ trước đó của chuỗi trong **30 ngày lịch** (cửa sổ gắn cờ dài hơn cửa sổ tham chiếu để giảm nhiễm độc tham chiếu). Trung vị của số điểm chẵn là trung bình hai điểm giữa. Cần ít nhất 1 điểm hợp lệ trước. Nếu chỉ có đúng 1 điểm tham chiếu thì tin ghi "độ tin cậy thấp".
- Điểm **đầu tiên** của chuỗi chưa có tham chiếu nên không bị gắn cờ được (giới hạn đã biết).

*Tác động lên tính toán.*
- Dòng bị gắn cờ **bị loại trước khi tính daily-min**. Daily-min của ngày được tính lại từ các dòng còn lại. Ví dụ Threonine kỳ 11/2026 ngày 15/09/2026: dòng 970 là min của ngày nhưng cùng ngày có dòng 26.000; sau khi loại dòng 970, điểm giá của ngày là 26.000. Nếu ngày không còn dòng nào thì ngày đó không có điểm.
- Khi cờ ở trạng thái `pending` (chưa duyệt), các điểm sau cùng mặt bằng mới (lệch dưới 2,5% so với điểm đang `pending`) **không sinh tin bất thường mới**. Chúng được **gắn vào thẻ** của điểm đang `pending` (thẻ hiển thị "đã có n điểm xác nhận cùng mức") và tạm bị loại cùng điểm đó. Sau khi thẻ được duyệt, các điểm gắn kèm được đánh giá lại độc lập ở lần quét kế tiếp.
- **Gộp cụm:** từ 3 cờ trở lên trong cùng ngày địa phương được gộp thành **một tin tóm tắt** (liệt kê tối đa 10 điểm, mỗi điểm một hàng nút, phần còn lại xem trên web ở 1C). Ví dụ cụm ngày 15/09/2026 có 6 điểm.

*Vòng đời xem xét.*
- Trạng thái: `pending` → `accepted` (Giá đúng) | `rejected` (Nhập sai) | `expired`.
- **Giá đúng:** dòng hợp lệ trở lại, daily-min tính lại, điểm đó là tham chiếu cho các lần sau. **Không** gửi tin biến động muộn cho chính điểm đó (người xem xét đã biết).
- **Nhập sai:** dòng tiếp tục bị loại. Người nhập sửa phiếu trên web (version điều chỉnh).
- **Nhắc và hết hạn:** nhắc lại một lần sau 2 ngày làm việc nếu còn `pending`. Hết hạn sau 7 ngày làm việc: trạng thái `expired`, dòng vẫn bị loại, ngừng nhắc. Đường xem xét trên web (danh sách điểm chờ duyệt) là hạng mục của 1C.
- Hai trưởng phòng bấm cùng lúc: người đầu thắng, người sau nhận thông báo "đã được xử lý bởi ...". Sau khi bấm, nội dung tin được **sửa** (ghi người xử lý, thời điểm, kết quả) và bỏ nút.

*Người nhận và quyền.*
- **Trưởng phòng** (`price_alerts.receive_all`): nhận tin kèm hai nút **✅ Giá đúng** và **❌ Nhập sai**.
- **Người nhập** (người tạo version chứa dòng bị cờ, `quote_versions.created_by_id`, thường là người gõ sai): nhận tin **không có nút**, chỉ có liên kết sửa phiếu. Nếu người này bị xóa (NULL), không còn hoạt động, hoặc chưa liên kết Telegram thì bỏ qua (trưởng phòng vẫn nhận). Tài khoản seed admin không nhận.
- **Chỉ người có `price_alerts.receive_all` và admin được bấm nút.** Admin không nhận tin mặc định (D9), bấm được nếu có tin.
- Tin bất thường **không chịu mức tối thiểu cá nhân** (D10) nhưng chịu cờ bật/tắt cá nhân. Gửi ngay (không gom vào bản tin).

*Số liệu (Phụ lục B.7, B.8).*
- 12 tháng có 16 điểm bất thường (cận dưới) ở 13 chuỗi thuộc 7 vật tư. Thử ngưỡng 20%, 30%, 40%, 50% cho 17, 16, 15, 14 điểm, nên 30% là mặc định an toàn.
- Trong giai đoạn nhập thật (6,3 tuần): 10 điểm (khoảng 1,6 điểm mỗi tuần) và 5 phiên bản sửa giá từ 30%. Con số 0,3 điểm mỗi tuần là cho 12 tháng toàn dữ liệu import.
- Phần lớn lệch rất lớn (khoảng −96%). 9/16 điểm có tỷ lệ trung vị so với giá mới từ 25,8 đến 29,3, gần tỷ giá USD chia 1.000: dấu hiệu **giá USD/MT gõ vào ô VNĐ/KG**.
- Ví dụ Khô cọ: chuỗi 187 → 5.165 → 5.179 → 9.505 → 5.172. Điểm sai thật là **187** (190 USD gõ vào ô VNĐ/KG). 9.505 là giá **đã được sửa** từ 93.245. Nếu không có tham chiếu 30 ngày và vòng đời `pending`, các điểm đúng (5.172) bị gắn cờ giả và điểm 187 không bị gắn cờ.
- Cụm ngày 15/09/2026: 6 điểm (Threonine, Arginin, Lysine, mỗi vật tư 2 kỳ) cùng lệch khoảng −96%, cộng Khô cọ +2.662%. Ngoài ra Tryptophan (CJ) ngày 08/09 và Arginin ngày 29/09.

*Giới hạn đã biết và ngoài phạm vi.*
- Biến động **thật** nhưng lớn cũng bị gắn cờ (ví dụ Cám mỳ 6,075 → 8,400, +38%; Methionine +71% là bước nhảy thật và bền). Nút "Giá đúng" xử lý trường hợp này. **Không tự động chấp nhận** (QĐ-12).
- Kiểm tra ở mức dòng bổ sung rất ít so với mức điểm (đo được đúng 1 dòng trong 12 tháng bị daily-min "ẩn": Lysine 70% kỳ 09/2026, 23.500, +49%), nhưng việc **loại** ở mức dòng là cần thiết (ví dụ Threonine ở trên).
- **Cảnh báo ngay lúc nhập** (phát hiện USD gõ vào ô VNĐ/KG trên giao diện nhập báo giá) là tính năng riêng, **ngoài phạm vi 1A đến 1C**, ghi vào backlog (Mục 9.2).

### Tham số mặc định của 1B

Các giá trị dưới đây là mặc định đề xuất, **chưa được xác nhận từng giá trị**, cần đo ở dry-run replay rồi chốt.

| Tham số | Mặc định | Ghi chú |
|---|---|---|
| Cửa sổ tham chiếu | 7 ngày làm việc | D3 |
| Độ trễ cho phép của nguồn kích hoạt | 3 ngày làm việc | D6, QĐ-16 |
| Cửa sổ chống lặp theo chuỗi | 14 ngày lịch | D5(a) |
| Trần gửi ngay mỗi lần quét | 30 tin; thêm 30 tin trong 10 phút cho mỗi người (QĐ-20) | D5(d) |
| Chu kỳ quét, độ chồng lấp | 30 giây, 5 phút (đổi từ 2 phút, QĐ-20) | 4.1 |
| Cửa sổ gắn cờ bất thường, ngưỡng | 30 ngày lịch, 30% | D12 |
| Gộp cụm bất thường | từ 3 cờ cùng ngày | D12 |
| Điểm sau gắn vào thẻ pending | lệch dưới 2,5% so với điểm pending | D12 |
| Nhắc, hết hạn thẻ pending | 2 ngày làm việc, 7 ngày làm việc | D12 |
| Nhân viên nhận tin của vật tư mình nhập | 90 ngày (xem D8) | D8 |
| Giờ bản tin tổng hợp | 08:00 giờ VN | D5(c) |
| Lưu giữ sự kiện, tin, lần quét | 180 ngày | 4.5 |

### Nhóm B: Người nhận

**D7. Trưởng phòng (ĐÃ CHỐT, QĐ-14).** Permission mới `price_alerts.receive_all`, cấp cho role `manager` bằng migration dữ liệu (cách làm ở 4.6, QĐ-19). Trưởng phòng nhận tin của **mọi vật tư**. Mức tối thiểu mặc định là Trung bình (D10). Không so tên role.

**D8. Nhân viên nhận vật tư mình đã nhập báo giá (ĐÃ CHỐT, QĐ-14).** Người dùng nhận cảnh báo của vật tư `M` nếu là `quotes.created_by_id` của ít nhất một phiếu chưa hủy có dòng vật tư `M` trong version `confirmed` hiện hành, với `received_date` trong **90 ngày gần nhất** tính đến lúc sinh sự kiện (cấu hình được). Phiếu nháp và version `superseded` không tính. Phiếu import thuộc tài khoản seed admin nên không tính.

**D9. Admin có nhận tất cả không? (ĐÃ CHỐT, QĐ-14).** Admin bypass mọi quyền, nên người nhận được xác định tường minh, không suy từ `role_permissions`. Admin chỉ nhận khi có liên kết Telegram **và** bật tùy chọn `admin_receive_all` (mặc định tắt). Tài khoản seed admin bị loại.

**D10. Tùy chọn từng người (ĐÃ CHỐT, QĐ-14).** Mỗi người có cờ bật/tắt chung và "mức tối thiểu" (Nhẹ, Trung bình, Lớn). `min_level` NULL nghĩa là **mặc định theo vai trò**: trưởng phòng từ Trung bình, nhân viên từ Nhẹ (gom vào bản tin tổng hợp). Tin giá bất thường không chịu mức tối thiểu nhưng chịu cờ bật/tắt chung.

### Nhóm C: Chatbot AI

**D11. Nhà cung cấp LLM và chính sách dữ liệu (QĐ-5, QĐ-6).**
- **Dev:** dùng API key của **Google AI Studio** (Gemini).
- **Production:** chưa chọn nhà cung cấp. Thiết kế `LLMClient` đa nhà cung cấp (OpenAI, Gemini, Anthropic) để đổi bằng cấu hình, chọn sau khi đo chi phí và chất lượng đọc ảnh/PDF tiếng Việt trên dev. Các gói thuê bao tiêu dùng không có API, chạy thật cần API key tính phí theo token (ngân sách ở 5.6).
- **Chính sách dữ liệu (đã chốt):** cho phép gửi nội dung báo giá, ảnh và PDF sang hệ thống bên thứ ba.
- **Dev dùng gói miễn phí (đã chốt, QĐ-5).** Theo hiểu biết hiện có (chưa kiểm chứng), gói miễn phí có thể cho phép Google dùng nội dung gửi lên để cải thiện sản phẩm và có hạn mức thấp **[CẦN XÁC MINH điều khoản và hạn mức hiện hành]**. DB dev chứa dữ liệu thật. Việc gửi dữ liệu sang bên thứ ba đã được phép (QĐ-6), nhưng khi test nên ưu tiên dữ liệu thử hoặc ảnh/PDF mẫu để không phơi bày dữ liệu thật không cần thiết. Không dùng gói miễn phí cho production. Hạn mức thấp cũng làm bài đo chi phí mỗi lượt và thử tải chưa phản ánh production.
- Dù đã được phép, vẫn chỉ gửi nội dung tối thiểu cần để trả lời. Không gửi email, mật khẩu, mã người dùng hay dữ liệu cá nhân không liên quan sang LLM.

---

## 4. Bước 1: Thông báo biến động giá qua Telegram

### 4.1 Luồng tổng thể

```
Nhân viên chốt báo giá ──► quote_versions (confirmed_at gán phía ứng dụng, TRƯỚC khi commit)
                                         │
             cron arq mỗi 30 giây ◄──────┘   quét confirmed_at > watermark − 5 phút
                        │   khóa advisory suốt lần quét
                        ▼
  Giai đoạn 1: giao dịch ngắn, mỗi version một savepoint
    · chọn dòng ứng viên (D2 mục 5) và nguồn kích hoạt (D6)
    · đánh giá bất thường mức dòng (D12), loại dòng bị gắn cờ
    · dựng điểm giá (daily-min) của chuỗi, cửa sổ 7 ngày làm việc (D3)
    · bộ ba quy tắc R1/R2/R3 (D2), phân mức theo ngưỡng của vật tư (D4)
    · chống lặp và leo thang (D5)  ──►  price_alert_events
    · giải quyết người nhận (D7 đến D10)  ──►  price_alert_messages (UNIQUE chống trùng)
                        │ commit
                        ▼
  Giai đoạn 2: ngoài giao dịch DB
    · vẽ PNG bằng matplotlib trong asyncio.to_thread, soạn caption ngắn và tin chi tiết
    · Telegram sendPhoto + sendMessage, trạng thái pending → sending → sent | failed
```

Lý do chọn **cron quét + watermark** thay vì móc vào route confirm:
- Không phải sửa `quotes.py` (an toàn cho code cũ đang chạy).
- Bắt được mọi đường confirm: API `confirm_version`, `delete_confirmed_line` (tự tạo và confirm bản điều chỉnh), `create_quote(confirm_immediately=True)` của import.
- Mất kết nối Redis hay worker tạm dừng không làm mất sự kiện, nếu watermark được quản lý đúng như dưới đây.
- Đổi lại: trễ tối đa khoảng 30 giây cộng thời gian xử lý (chu kỳ đã chốt ở QĐ-20). Chấp nhận được với thông báo giá. Nếu sau này cần gần thời gian thực: enqueue job ngay sau commit, giữ cron làm lưới an toàn, hoặc outbox bằng trigger DB; chưa làm.

**Quy tắc quét an toàn** (watermark có thể bỏ sót version nếu làm ngây thơ):
- `confirmed_at` được gán bằng `datetime.now()` phía ứng dụng **trước** khi commit (`quote_service.py`), và import commit mỗi 200 nhóm. Một version có `confirmed_at` sớm có thể commit muộn hơn lần quét đã đẩy watermark qua nó. Vì vậy quét **chồng lấp**: `confirmed_at > watermark − 5 phút`. Sự trùng lặp do chồng lấp được chặn bởi `UNIQUE` và `INSERT ... ON CONFLICT DO NOTHING` (idempotent).
- **Watermark** nằm ở bảng riêng `price_alert_scan_state` (không chung bảng cấu hình, để cron không giữ khóa dòng làm nghẽn `PUT` cấu hình). Đặt bằng thời điểm chuyển `is_enabled` từ false sang true, **mỗi lần bật**. Chỉ tiến lên đến `confirmed_at` lớn nhất của các version đã xử lý (thành công hoặc lỗi đã được cô lập).
- **Cô lập lỗi:** mỗi version xử lý trong một savepoint. Lỗi một version ghi vào `price_alert_scan_runs` và bỏ qua, không chặn watermark và không làm mất các version khác.
- **Khóa chống chạy chồng:** `pg_try_advisory_xact_lock` suốt lần quét. arq cron `unique=True` chỉ chống trùng theo mốc thời gian, **không** chặn chạy chồng khi lần quét trước chưa xong. Mẫu `poll_and_run_scheduled_backups` commit giữa vòng lặp nên khóa dòng đã nhả, không bắt chước nguyên văn.
- **Tách pha:** giai đoạn 1 chỉ ghi DB và commit ngắn. Giai đoạn 2 gọi Telegram theo từng tin, có `lease_until` để tiến trình khác không gửi trùng. Việc gửi là **at-least-once** (Telegram không có khóa idempotency), nên cần chấp nhận khả năng gửi trùng hiếm khi gặp sự cố giữa chừng.
- **Lọc nguồn kích hoạt trong SQL** (D6), nhưng version không phải nguồn vẫn đi qua đánh giá bất thường và vẫn cho watermark tiến.
- **Dọn dữ liệu:** sự kiện, tin, lần quét cũ hơn 180 ngày bị xóa bằng cron hằng ngày.

**Các trường hợp đặc biệt:**
- Version `superseded` không tham gia tham chiếu (điểm giá lấy từ version hiện hành).
- Bản điều chỉnh sửa giá: chỉ các dòng mới hoặc đổi giá được đánh giá (D2 mục 5), nên không báo kép cho dòng không đổi.
- `delete_confirmed_line` không có dòng nào đổi giá nên không phát tin. Nếu phiếu bị hủy hoặc một dòng bị xóa **sau** khi tin đã gửi thì không có tin thu hồi, đính chính (ghi nhận là giới hạn).

### 4.2 Giao diện tin nhắn

Telegram không có chữ màu. Dùng emoji kép (chiều và mức) và ảnh biểu đồ có dải màu theo mức.

| Mức | Tăng | Giảm | Màu dải trên biểu đồ |
|---|---|---|---|
| Nhẹ (mặc định 2,5-5%) | 🔺🟡 **TĂNG NHẸ** | 🔻🟡 **GIẢM NHẸ** | Vàng |
| Trung bình (mặc định 5-10%) | 🔺🟠 **TĂNG TRUNG BÌNH** | 🔻🟠 **GIẢM TRUNG BÌNH** | Cam |
| Lớn (mặc định >10%) | 🔺🔴 **TĂNG LỚN** | 🔻🔴 **GIẢM LỚN** | Đỏ |

Quy ước màu theo **mức độ biến động**, không theo ý nghĩa thuận lợi hay bất lợi, vì ý nghĩa đó phụ thuộc vị thế của người nhận. Chiều phân biệt bằng mũi tên và chữ. Giọng thông báo trung tính, không khuyến nghị mua bán.

Mỗi thông báo gồm **một ảnh kèm caption ngắn** (tối đa 1.024 ký tự theo giới hạn Telegram) và **một tin văn bản chi tiết** (tối đa 4.096 ký tự) gửi ngay sau ảnh (D5(b)). Dùng ví dụ 1 ở D2.

Caption:

```
🔺🟠 TĂNG TRUNG BÌNH · Ngô hạt
Giá thấp nhất hôm nay: 8,150.00 VNĐ/KG (02/10/2026)
Kỳ 12/2026: +5.57% so với giá thấp nhất 7 ngày làm việc
```

Tin chi tiết (khi gộp theo vật tư thì có một khối cho mỗi kỳ giao hàng vượt ngưỡng, ảnh vẽ kỳ có mức cao nhất):

```
Ngô hạt · kỳ giao hàng 12/2026
Lý do chính: so với giá thấp nhất 7 ngày làm việc
  +5.57%  (7,720.00 · 25/09/2026)
So sánh khác: so với điểm giá gần nhất
  +4.49%  (7,800.00 · 30/09/2026)
Vùng tham chiếu 7 ngày làm việc
  Thấp nhất: 7,720.00 (25/09) · Cao nhất: 7,900.00 (23/09)
CNF (USD/MT): 303.50 (02/10/2026), so với 287.00 (25/09/2026): +5.75%

Lưu ý: điểm giá có thể thuộc nhà cung cấp khác với lần trước.
🔗 Xem chi tiết: https://quotify.honghafeed.com.vn/quotes/<id>
```

Quy tắc hiển thị:
- Vùng tham chiếu (thấp nhất, cao nhất) là của **7 ngày làm việc không gồm điểm mới**, giống đường min và max trên biểu đồ (4.3). Không dùng thống kê "14 ngày qua gồm điểm mới" nữa để hai số khớp nhau.
- **Dòng "So sánh khác" chỉ in khi khác điểm tham chiếu của lý do chính** (D2 mục 2).
- **Hiển thị CNF (QĐ-8).** Khi điểm giá mới là dòng nhập **USD/MT**, tin thêm dòng CNF lấy từ `price_original` (USD/MT). Dòng "so với" chỉ in khi **cả điểm mới và điểm tham chiếu của lý do chính đều là dòng USD/MT**, nếu không thì chỉ in giá CNF của điểm mới. Điều kiện gửi tin và mức độ vẫn tính trên **VNĐ/KG** (D1, QĐ-13). Khi hai bên khác chiều, thêm chú thích ngắn "chênh lệch do tỷ giá". Dòng nhập VND/KG không có dòng CNF.
- Tin không nêu nhà cung cấp vì người dùng chỉ quan tâm giá. Thông tin nhà cung cấp xem ở liên kết chi tiết.
- Khuôn dạng: `10,200.00 VNĐ/KG`, ngày `DD/MM/YYYY`, giờ VN, tiếng Việt có dấu. Tin ghi rõ "giá quy đổi" nếu nguồn là USD/MT. Dữ liệu động qua `html.escape` vì Telegram từ chối chuỗi HTML sai (lỗi 400 "can't parse entities", lỗi terminal, không thử lại).

Tin giá bất thường (D12), gửi cho **trưởng phòng**, dùng dữ liệu thật ngày 15/09/2026:

```
⚠️ GIÁ BẤT THƯỜNG · Threonine
Kỳ giao hàng: 11/2026

Giá nhận 15/09/2026: 970.00 VNĐ/KG
Các giá hợp lệ gần đây (30 ngày): 25,600.00 · 25,435.00 · 25,900.00
Lệch −96.21% so với trung vị 25,600.00

Giá này tạm chưa được dùng để tính biến động.
[✅ Giá đúng]  [❌ Nhập sai]
🔗 Xem phiếu: https://quotify.honghafeed.com.vn/quotes/<id>
```

Cùng nội dung gửi cho **người nhập** nhưng **không có hai nút**, thay bằng câu "Vui lòng kiểm tra và sửa phiếu nếu nhập sai." kèm liên kết. Khi chỉ có 1 giá tham chiếu, thêm dòng "Độ tin cậy thấp: chỉ có 1 giá tham chiếu". Khi từ 3 cờ trở lên trong cùng ngày, gộp thành một tin tóm tắt (D12). `callback_data` của nút tối đa 64 byte, dùng dạng `pa:ok:<uuid sự kiện>` (khoảng 42 byte).

### 4.3 Biểu đồ 14 ngày với vùng tham chiếu

- **Dữ liệu: viết hàm mới** `get_daily_min_series(material_id, delivery_month, date_from, date_to, exclude_line_ids)` (truy vấn `GROUP BY received_date, MIN(price)` theo chuỗi, loại các dòng bị gắn cờ). **Không tái dùng** được các hàm dashboard hiện có: `_get_points` là hàm private, giới hạn 1.000 dòng, join ghi chú và không tính daily-min (daily-min chỉ có ở frontend); `get_price_trends` gọi `_build_purchase_context` theo vòng lặp cho từng điểm đã chốt mua (N+1) và API không lộ `point_limit`. Hiệu năng không phải vấn đề: `EXPLAIN ANALYZE` chuỗi lớn nhất (578 dòng) khoảng 18 ms, dùng `ix_quote_lines_material_delivery_created`. Chatbot (5.2) cũng dùng hàm mới này, không dùng `get_price_trends` (trả tới 500 điểm kèm ghi chú, tốn token).
- Hiển thị: 14 ngày lịch, đường daily-min, hai đường ngang min và max **của vùng tham chiếu 7 ngày làm việc không gồm điểm mới** (gắn nhãn giá, khớp với tin chi tiết), vùng tham chiếu được tô sáng, điểm cuối tô theo màu mức, tiêu đề, nhãn ngày `dd/MM`.
- **Công nghệ: matplotlib** (mặc định cho 1B). Phương án đã xét: Pillow tự vẽ (nhẹ nhưng phải tự vẽ trục, nhãn), dịch vụ ngoài như QuickChart (không thêm dependency nhưng dữ liệu giá rời công ty).
  - Vẽ là CPU đồng bộ, chạy thẳng trong coroutine arq sẽ chặn các job khác trên cùng vòng lặp. Dùng `asyncio.to_thread` và API hướng đối tượng (`Figure`, `FigureCanvasAgg`), **không dùng `pyplot`** (không thread-safe). Lần import đầu xây font cache vài giây.
  - Kéo theo numpy, tăng khoảng 60 đến 100 MB image. Cần font có tiếng Việt (DejaVu Sans hỗ trợ), nhúng vào image **[CHƯA XÁC MINH trong image production]**.
- Vẽ trong **worker**, không vẽ trong request. Phải build lại `backend` và `worker`.

### 4.4 Liên kết tài khoản Telegram

Chi tiết triển khai, hợp đồng API và bộ tin nhắn của bot: [kế hoạch 1A](plan-telegram-giai-doan-1a-nen-tang-lien-ket.md). Phần dưới tóm tắt thiết kế.

Nguyên tắc: **định danh người nhận là `users.id`**, không phải `chat_id`. `telegram_user_id` là khóa liên kết ổn định, `username` chỉ để hiển thị vì người dùng có thể đổi.

Luồng liên kết:
1. Người dùng vào **Hồ sơ** trên web → bấm "Liên kết Telegram".
2. Backend sinh **mã liên kết** (token) ngẫu nhiên dùng một lần, lưu **băm sha256**, hạn 10 phút, trả **đường dẫn liên kết** (deep link) `https://t.me/<tên_bot>?start=<mã>`.
3. Người dùng mở đường dẫn, bấm Start. Telegram gửi update `/start <mã>` tới webhook.
4. Backend xác thực mã, kiểm tra `telegram_user_id` chưa gắn với user khác, tạo liên kết `active`, đánh dấu mã đã dùng, gửi tin xác nhận. Ghi audit.
5. Frontend thấy trạng thái đổi sang "Đã liên kết" (poll vài giây hoặc làm mới khi focus).

Các trường hợp biên:

| Trường hợp | Xử lý |
|---|---|
| Đổi sang tài khoản Telegram mới | Nút "Đổi tài khoản": sinh token mới. Khi tài khoản mới xác nhận, **trong một transaction** thu hồi liên kết cũ (`revoked_at`, lý do `replaced`), tạo liên kết mới. Chat cũ nhận tin "đã hủy liên kết" (nếu còn gửi được). Giữ lịch sử |
| Hủy liên kết từ web | `DELETE /users/me/telegram` thu hồi liên kết |
| Hủy liên kết từ Telegram | Lệnh `/stop` thu hồi liên kết. Người dùng chặn bot (Telegram trả 403 hoặc update `my_chat_member`) thì đánh dấu `blocked`, không thử lại vô hạn |
| Telegram đã gắn với user khác | Từ chối (kể cả khi liên kết kia đang `blocked`), báo hướng dẫn hủy liên kết ở tài khoản kia hoặc gõ `/stop`. Nếu chủ cũ không còn `ACTIVE` thì tự thu hồi liên kết cũ (`owner_inactive`) |
| Đổi `username` Telegram | Không ảnh hưởng. Cập nhật `username` hiển thị lần tin nhắn sau |
| Người dùng bị khóa/vô hiệu | Mỗi lần gửi và mỗi tin nhận đều kiểm tra `User.status = active` |
| Nhắn từ nhóm (group) | Chỉ chấp nhận chat riêng (`chat.type = private`) |
| Xóa user cứng | `DELETE /users/{id}` từng trả 500 khi user có `refresh_tokens` (chưa fix **[CHƯA XÁC MINH đã sửa]**). Khuyến nghị vô hiệu hóa thay vì xóa |

Ràng buộc DB: hai chỉ mục **partial unique** (mẫu `uq_quote_versions_single_draft`) `WHERE status IN ('active','blocked')`: mỗi `telegram_user_id` chỉ có 1 liên kết đang giữ, mỗi `user_id` chỉ có 1 liên kết đang giữ. Gồm cả `blocked` vì tài khoản bị chặn vẫn thuộc người dùng, nếu không thì người khác chiếm `telegram_user_id`, và khi bỏ chặn sẽ vi phạm unique.

Không bắt người dùng gõ mật khẩu Quotify hay `chat_id` vào chat. Không thêm cột Telegram vào `users` vì `PUT /users/{id}` ghi đè toàn bộ.

### 4.5 Mô hình dữ liệu (migration mới, additive)

Head hiện tại là `20261004_1100` (sau 1A). Migration 1B nối tiếp từ đây. Migration mới đặt tên `YYYYMMDD_HHMM_<mô_tả>.py`, `--rev-id` đúng quy ước, viết tay (autogenerate sẽ sinh DROP index giả vì ORM thiếu nhiều index composite). Các migration nối tiếp nhau (một head). Phần Telegram (1A) có định nghĩa chuẩn ở kế hoạch 1A.

**Nhóm Telegram (1A).**

```
telegram_processed_updates          -- chống xử lý trùng (Telegram có thể gửi lại)
  update_id BIGINT PK, received_at timestamptz

telegram_accounts
  id UUID PK
  user_id FK users CASCADE (ix)
  telegram_user_id BIGINT NOT NULL, chat_id BIGINT NOT NULL
  username varchar(64) NULL (lưu không có '@'), first_name varchar(150) NULL
  status varchar(20) CHECK in ('active','revoked','blocked')
  linked_at timestamptz, revoked_at NULL
  revoked_reason varchar(30) NULL CHECK in ('replaced','user_unlink','stop_command','owner_inactive')
  last_seen_at NULL, created_at, updated_at
  UNIQUE PARTIAL (telegram_user_id) WHERE status IN ('active','blocked')
  UNIQUE PARTIAL (user_id)          WHERE status IN ('active','blocked')

telegram_link_tokens
  id UUID PK, user_id FK users CASCADE, token_hash varchar(64) UNIQUE
  expires_at, used_at NULL, created_at
```

**Nhóm biến động giá (1B).** Mọi khóa ngoại của bảng dẫn xuất ghi rõ `ON DELETE` để xóa người dùng hoặc vật tư không bị chặn.

```
price_alert_settings (singleton)    -- KHÔNG nhét vào quotify_settings
  id, singleton_key 'default'
  reference_working_days int default 7                 -- D3
  light_from_percent  numeric(5,2) default 2.50        -- Nhẹ khi |%| >= giá trị
  medium_from_percent numeric(5,2) default 5.00        -- Trung bình khi |%| >= giá trị và <= large_over
  large_over_percent  numeric(5,2) default 10.00       -- Lớn khi |%| > giá trị
  anomaly_percent numeric(5,2) default 30.00           -- D12
  anomaly_lookback_days int default 30
  max_trigger_delay_working_days int default 3         -- D6
  staff_lookback_days int default 90                   -- D8
  dedupe_window_days int default 14                    -- D5(a)
  immediate_cap_per_scan int default 30                -- D5(d)
  digest_hour_local smallint default 8                 -- D5(c)
  is_enabled bool default false                        -- cờ bật, phát hành "tắt" trước
  updated_by_id FK users SET NULL, created_at, updated_at
  CHECK 0 < light_from_percent < medium_from_percent < large_over_percent < anomaly_percent

price_alert_scan_state (singleton)  -- tách khỏi cấu hình
  id, singleton_key 'default'
  watermark_confirmed_at timestamptz NULL              -- đặt = thời điểm bật cờ, mỗi lần bật
  enabled_since timestamptz NULL
  last_digest_local_date date NULL                     -- catch-up bản tin 08:00
  updated_at

price_alert_scan_runs               -- quan sát, thay metric của worker (xem 4.8)
  id UUID PK, started_at, finished_at NULL
  versions_scanned int, events_created int, messages_created int, messages_sent int
  error_count int, last_error varchar(255) NULL

price_alert_material_thresholds     -- D4: ghi đè theo vật tư
  material_id UUID PK FK materials CASCADE
  light_from_percent, medium_from_percent, large_over_percent numeric(5,2) NULL
  anomaly_percent numeric(5,2) NULL                    -- NULL = dùng mặc định
  CHECK: ba cột ngưỡng cùng NULL hoặc cùng NOT NULL
  CHECK: 0 < light_from < medium_from < large_over khi NOT NULL
  CHECK: anomaly_percent > large_over_percent khi cả hai NOT NULL
  (nếu chỉ ghi đè anomaly_percent thì service kiểm tra so với large_over hiệu lực)
  updated_by_id FK users SET NULL, created_at, updated_at

price_alert_events                  -- 1 sự kiện = 1 kết quả đánh giá cho 1 chuỗi, 1 ngày
  id UUID PK, scan_run_id FK SET NULL
  quote_version_id FK quote_versions CASCADE, material_id FK materials CASCADE, delivery_month date
  kind varchar(10) ('change'|'anomaly')
  quote_line_id FK quote_lines SET NULL NULL           -- dòng bị gắn cờ (kind='anomaly')
  direction varchar(4) ('up'|'down')                   -- anomaly: dấu của độ lệch
  level varchar(10) NULL ('light'|'medium'|'large')    -- NULL khi kind='anomaly'
  rule varchar(2) NULL ('R1'|'R2'|'R3')                -- lý do chính; NULL khi kind='anomaly'
  percent_change numeric(8,2)                          -- anomaly: độ lệch so với trung vị
  price_new numeric(12,2), price_ref numeric(12,2)     -- anomaly: price_ref = trung vị
  received_date_new date, received_date_ref date NULL
  window_min numeric(12,2), window_max numeric(12,2)   -- vùng tham chiếu, không gồm điểm mới
  window_min_date date, window_max_date date
  reference_point_count smallint                       -- số điểm tham chiếu (độ tin cậy)
  secondary_rule varchar(2) NULL, secondary_percent numeric(8,2) NULL   -- dòng "So sánh khác"
  secondary_price_ref numeric(12,2) NULL, secondary_date_ref date NULL
  cnf_price_new numeric(12,2) NULL, cnf_price_ref numeric(12,2) NULL, cnf_date_ref date NULL
  review_status varchar(10) NULL ('pending'|'accepted'|'rejected'|'expired')   -- kind='anomaly'
  attached_to_event_id UUID NULL FK price_alert_events SET NULL        -- điểm gắn vào thẻ pending
  reviewed_by_id FK users SET NULL NULL, reviewed_at NULL, reminded_at NULL
  created_at
  UNIQUE PARTIAL (quote_version_id, material_id, delivery_month) WHERE kind='change'
  UNIQUE PARTIAL (quote_version_id, quote_line_id)               WHERE kind='anomaly'
  -- lưu đủ trường để dựng lại tin; không tính lại lúc gửi (dữ liệu có thể đã đổi)

price_alert_messages                -- 1 tin = 1 người nhận, 1 vật tư, 1 lần quét (D5b)
  id UUID PK, user_id FK users CASCADE, telegram_account_id FK telegram_accounts SET NULL
  material_id FK materials CASCADE, local_date date, scan_run_id FK SET NULL
  kind varchar(10) ('change'|'anomaly'|'digest')
  level_max varchar(10) NULL, direction varchar(4) NULL
  status varchar(20) ('pending','sending','sent','failed','suppressed','digest_queued','skipped')
  lease_until timestamptz NULL, attempts int, last_error varchar(255) NULL
  telegram_message_id BIGINT NULL, created_at, sent_at NULL
  UNIQUE (user_id, material_id, scan_run_id, kind)     -- idempotent khi thử lại
  -- skipped: người nhận không còn đủ điều kiện (blocked, không ACTIVE); suppressed: không leo thang

price_alert_message_events          -- một tin gộp nhiều sự kiện
  message_id FK price_alert_messages CASCADE, event_id FK price_alert_events CASCADE, PK (message_id, event_id)

user_alert_preferences              -- tùy chọn cá nhân (D9, D10)
  user_id PK FK users CASCADE
  is_enabled bool default true
  min_level varchar(10) NULL                            -- NULL = mặc định theo vai trò
  admin_receive_all bool default false                  -- D9
  created_at, updated_at
```

Chỉ mục tối thiểu: `price_alert_events(material_id, delivery_month, created_at)`, `price_alert_events(review_status)` có điều kiện `kind='anomaly' AND review_status='pending'`, `price_alert_messages(status, created_at)`, `price_alert_messages(user_id, material_id, local_date)`. Có thể thêm chỉ mục additive `quote_versions(confirmed_at)` khi dữ liệu lớn (hiện 3,5 nghìn version thì chưa cần). Dữ liệu cũ hơn 180 ngày bị dọn (4.1).

**Nhóm Giai đoạn 2** có ở 5.4 (`chat_sessions`, `chat_messages`) và 5.6 (`chatbot_settings`, `llm_usage_events`).

**Thay đổi bảng hiện có (additive, nullable, QĐ-9, Giai đoạn 2B).** Ghi nhận nguồn nhập báo giá:

```
quotes.created_via         varchar(20) NULL   -- 'telegram' | NULL (NULL = web hoặc dữ liệu cũ); nguồn của version đầu tiên
quote_versions.created_via varchar(20) NULL   -- nguồn của từng version
CHECK created_via IS NULL OR created_via IN ('telegram')
```

Không backfill dữ liệu cũ. `QuoteService.create_quote` và `create_version` nhận thêm tham số tùy chọn `created_via` (mặc định `None`). **Icon và bộ lọc đọc `quote_versions.created_via`** của version đang hiển thị ở dòng danh sách (danh sách đã ở cấp version). Các điểm chạm đầy đủ ở 4.9. Khóa audit `channel` thêm vào allow-list.

Mọi bảng mới phải thêm vào `app/models/__init__.py` và `app/db/base.py`.

### 4.6 API và quyền

| Endpoint | Quyền | Ghi chú |
|---|---|---|
| `POST /api/v1/users/me/telegram/link-token` | đăng nhập | 201 `{deep_link, expires_at, expires_in_seconds, bot_username}`. Hạn mức theo người dùng. 503 khi tắt |
| `GET /api/v1/users/me/telegram` | đăng nhập | `{enabled, bot_username, account, pending_link}` |
| `DELETE /api/v1/users/me/telegram/link-token` | đăng nhập | Hủy yêu cầu đang chờ, 204 idempotent |
| `DELETE /api/v1/users/me/telegram` | đăng nhập | Hủy liên kết, 204 idempotent |
| `GET/PUT /api/v1/users/me/alert-preferences` | đăng nhập | Bật/tắt, mức tối thiểu, `admin_receive_all` (chỉ admin) |
| `GET/PUT /api/v1/price-alert-settings` | `price_alerts.manage` | Ngưỡng mặc định, các tham số ở 4.5, **bật/tắt tính năng** |
| `GET /api/v1/price-alert-settings/materials` | `price_alerts.manage` | Danh sách vật tư kèm ngưỡng hiệu lực, phân trang (`limit ≤ 100`), tìm kiếm |
| `PUT /api/v1/price-alert-settings/materials/{material_id}` | `price_alerts.manage` | Ghi đè ba ngưỡng và/hoặc ngưỡng bất thường |
| `DELETE /api/v1/price-alert-settings/materials/{material_id}` | `price_alerts.manage` | Bỏ ghi đè, về mặc định |
| `GET /api/v1/price-alerts/anomalies` (1C) | `price_alerts.receive_all` | Danh sách điểm bất thường chờ duyệt |
| `POST /api/v1/price-alerts/anomalies/{id}/review` (1C) | `price_alerts.receive_all` | `accepted` hoặc `rejected`, cùng logic với nút Telegram |
| `GET/PUT /api/v1/chatbot-settings`, `GET /api/v1/chatbot-usage` (2A) | `chatbot.manage` | Trang "Chi phí chatbot": trần, chi phí theo ngày và theo người dùng |
| `POST /api/v1/telegram/webhook` | **không JWT**, xác thực `X-Telegram-Bot-Api-Secret-Token` | Giai đoạn 1A xử lý nội tuyến (một ghi DB và một cuộc gọi HTTP ngắn). Giai đoạn 2A chuyển xử lý nặng qua arq |

**Permission mới** (QĐ-19): `price_alerts.receive_all` (trưởng phòng), `price_alerts.manage` (admin **và trưởng phòng, gồm cả bật/tắt tính năng**), `chatbot.manage` (chỉ admin, **không** cấp cho trưởng phòng). Phải thêm vào `BASE_PERMISSION_CODES` (để admin nhận qua seed và `test_permission_inventory.py` qua).

**Cấp quyền cho role `manager` bằng migration (phương án a, QĐ-19).** Mẫu `20260729_0810` chỉ `DELETE` nên không dùng làm mẫu. Migration mới phải:
1. `INSERT INTO permissions(id, code) VALUES (gen_random_uuid(), '<mã>') ON CONFLICT (code) DO NOTHING` cho từng mã (`permissions.id` là UUID không có `server_default`; bảng `permissions` chưa có các dòng này vì seed chạy **sau** migrate).
2. `INSERT INTO role_permissions SELECT ... FROM roles, permissions WHERE roles.name = 'manager' AND permissions.code IN (...) ON CONFLICT DO NOTHING`.
3. Chịu được trường hợp DB không có role `manager` (DB test và dev mới): câu lệnh ghi 0 dòng, không lỗi.
4. Có test migration trên DB có và không có role `manager`. `seed_auth_rbac.py` chạy sau vẫn idempotent.

Điểm yếu cần ghi nhận: migration gắn với **tên** role `manager`, trong khi nguyên tắc là không so tên role. Chấp nhận vì không có cách khác cấp quyền cho role không phải role hệ thống.

**Thứ bậc các cờ.** `TELEGRAM_ENABLED` (môi trường) là điều kiện cần. `price_alert_settings.is_enabled` (DB) là điều kiện đủ để bật/tắt tính năng bởi người có `price_alerts.manage`. Tương tự `CHATBOT_ENABLED` và `chatbot_settings.is_enabled` (chỉ admin).

**Xem xét giá bất thường.** Qua nút trong Telegram (update `callback_query` đến cùng webhook, phải gọi `answerCallbackQuery`), và qua endpoint web ở 1C. Chỉ người có `price_alerts.receive_all` (và admin) được bấm (D12). `callback_data` tối đa 64 byte.

**Audit event mới:** `telegram.link_requested`, `telegram.linked`, `telegram.link_rejected`, `telegram.unlinked`, `price_alerts.settings_updated`, `price_alerts.threshold_updated`, `price_alerts.anomaly_reviewed`, `price_alerts.scan_completed` (chỉ ghi khi lần quét có tạo sự kiện), `chatbot.budget_updated`. Thêm key vào `ALLOWED_AUDIT_METADATA_KEYS`, tránh key chứa `token`, `secret`, `session`. Không ghi audit từng tin gửi hàng loạt. Không ghi `telegram_user_id` hay username vào audit (kế hoạch 1A, K2).

### 4.7 Cấu hình

Thêm vào `Settings` (`core/config.py`), theo mẫu có `*_FILE` cho secret (mỗi secret mới phải thêm một dòng ở `model_post_init`, vì `_apply_secret_file` ánh xạ thủ công), và vào `.env.example` + `.env.production.example`:

```
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN / TELEGRAM_BOT_TOKEN_FILE
TELEGRAM_BOT_USERNAME
TELEGRAM_WEBHOOK_SECRET / TELEGRAM_WEBHOOK_SECRET_FILE
TELEGRAM_WEBHOOK_URL                  # URL đầy đủ để setWebhook
TELEGRAM_API_BASE_URL                 # mặc định https://api.telegram.org, đổi khi dùng fake server
TELEGRAM_MODE=webhook|polling         # dev dùng polling
TELEGRAM_HTTP_TIMEOUT_SECONDS=10
RATE_LIMIT_TELEGRAM_LINK_TOKEN=5
```

Secret đi qua `env_file: .env` của backend và worker. **Không** dùng `${TELEGRAM_*:?msg}` trong compose production: `make production-readiness-check` chạy `docker compose config` và sẽ lỗi khi biến trống trong lúc tính năng đang tắt. Secret webhook sinh bằng `openssl rand -hex 32`. Tham số của engine biến động nằm trong DB (4.5), không phải biến môi trường.

### 4.8 Worker

- Thêm cron vào `WorkerSettings.cron_jobs` (cạnh `poll_and_run_scheduled_backups`): `poll_price_alerts` mỗi 30 giây (`second={0, 30}`), `send_price_alert_digest` mỗi giờ (chạy khi đã qua giờ bản tin và `last_digest_local_date` chưa phải hôm nay, nên worker tắt lúc 08:00 vẫn gửi bù cùng ngày), nhắc thẻ bất thường `pending` mỗi giờ, dọn dữ liệu cũ mỗi ngày.
- **Múi giờ.** arq 0.26.3 hỗ trợ `timezone` trong `WorkerSettings`. Đặt `timezone = ZoneInfo("Asia/Ho_Chi_Minh")` (Việt Nam không có DST) và có test, vì mặc định cron chạy theo múi giờ hệ thống (UTC trong container, `hour=8` thành 15:00 giờ VN).
- **Chống chạy chồng:** khóa advisory suốt lần quét (4.1). `SKIP LOCKED` trong mẫu backup không đủ vì commit giữa vòng lặp làm nhả khóa.
- Job gửi tin: bọc `try/except` riêng, thử lại có backoff, xử lý 429 (`retry_after`) và 403 (bot bị chặn thì `mark_blocked`). Lỗi 400 (HTML sai) là lỗi terminal, không thử lại. Chỉ bỏ qua khi trạng thái terminal (`sent`, `failed`, `suppressed`, `skipped`), không bỏ qua trạng thái `sending` còn hạn `lease_until` (bug 27/07).
- **Quan sát.** `prometheus.yml` chỉ scrape `backend:8000/metrics`, nên metric `quotify_*` đặt trong worker không bao giờ xuất hiện. Ghi tổng kết mỗi lần quét vào `price_alert_scan_runs`, để backend phát gauge khi scrape, hoặc chạy `start_http_server` trong `on_startup` của worker và thêm job vào `prometheus.yml`. Thêm cảnh báo khi watermark trễ quá N phút. Lưu ý alert rules hiện còn tên `fastapivue_*` (nợ cũ, RR-19).
- Worker không tự reload code: sau khi sửa phải restart (dev) hoặc build lại `worker` (production).
- **Không có khung giờ yên lặng** (QĐ-7): tin Trung bình, Lớn và giá bất thường gửi ngay mọi giờ. Người dùng tự tắt tiếng chat bot trong Telegram nếu cần. Bản tin tổng hợp mức Nhẹ gửi lúc 08:00 giờ VN.
- **Bot dev và bot production là hai bot khác nhau** (polling và webhook loại trừ nhau, dùng chung token gây lỗi 409). Khôi phục dump production vào dev phải đặt `price_alert_settings.is_enabled=false` và thu hồi `telegram_accounts` (kế hoạch 1A, K16), kẻo worker dev gửi tin thật.

### 4.9 Giao diện web

**Giai đoạn 1.**
- Panel thứ ba trong `ProfilePage.vue` ("Thông báo Telegram"): liên kết, đổi, hủy, ẩn khi tính năng tắt (kế hoạch 1A). Ở 1C thêm tùy chọn cá nhân: bật/tắt, mức tối thiểu, `admin_receive_all` cho admin.
- **Trang mới `/price-alert-settings`** (guard `price_alerts.manage`, thêm vào sidebar). Gồm: bật/tắt tính năng, ngưỡng mặc định và các tham số ở 4.5, và bảng **"Ngưỡng theo vật tư"** (DataTable lazy `limit ≤ 100`, tìm theo tên hoặc mã, cột Nhẹ / Trung bình / Lớn / Bất thường, mặc định hiển thị mờ với nhãn "mặc định", sửa qua Dialog, kiểm tra `0 < Nhẹ < Trung bình < Lớn < Bất thường`, nút "Dùng mặc định"). **Không** đặt trong `QuotifySettingsPage.vue`: route đó yêu cầu `quotify_settings.read` mà role `manager` không có (migration `0810` cố ý gỡ), nên trưởng phòng không vào được. Người thiếu quyền thấy nút ở trạng thái `disabled` kèm `title` giải thích (quy ước dự án).
- Trang xem xét điểm bất thường chờ duyệt (1C).
- Thêm nhãn `telegram.*` và `price_alerts.*` vào `audit-logs.mappers.ts` và các bộ lọc ở `AuditLogsPage.vue`.
- Tuân thủ: không `<style>` trong `.vue`, SCSS mới ở `styles/pages/_price-alert-settings-page.scss` (trang mới) và `_profile-page.scss` (panel), token `--app-*`, responsive, dấu `*` đỏ cho trường bắt buộc, thông báo inline (không Toast), `data-testid` cho test.

**Giai đoạn 2.**
- **Nguồn nhập Telegram (QĐ-9, 2B):** chỉ làm hai thứ trên danh sách báo giá, không làm ở trang chi tiết phiếu.
  - **Icon bot** trong cột "Trạng thái" (cột `version_status`, cạnh các badge Đã xác nhận, Đã hủy), có tooltip "Nhập qua Telegram", chỉ hiển thị khi `createdVia = 'telegram'`. Dùng một trong các icon PrimeIcons 7 có sẵn (`pi-android`, `pi-microchip-ai`, `pi-telegram`; **không có** `pi-robot`). Phải thêm ở **cả bảng desktop và thẻ mobile** của `QuotesPage.vue`.
  - **Ô tick lọc** "Chỉ phiếu nhập qua Telegram" cạnh các bộ lọc "Trạng thái chốt" và "Trạng thái phiếu". Tick là chỉ phiếu nhập qua Telegram, không tick là tất cả (chờ xác nhận).
  - **Điểm chạm backend:** `QuoteFlattenedResponse` (`schemas/quote_list.py`, không phải `QuoteResponse`), hai truy vấn phẳng dựng dict thủ công trong `quote_query_service.py`, `_apply_filters` (dùng chung nên thêm tham số lọc `created_via` một chỗ), **hàm export Excel `query_flattened_quotes_for_export` và endpoint `export_quotes`** (xuất Excel phải tôn trọng bộ lọc trên trang), `GET /quotes`, `schemas/quote.py`, `models/quote.py`, `models/quote_version.py`, `quote_service.py`.
  - **Điểm chạm frontend:** `types/quotes.ts`, `api/quotes.mappers.ts` (thêm `createdVia`), `useQuotesPage.ts`, `quotes-view.store.ts` (kiểu `QuotesViewState` bắt buộc: snapshot `sessionStorage` cũ trả `createdVia = undefined`, các điều kiện kiểu `!== null` sẽ coi là bộ lọc đang bật, cần `?? null`) và `quotes-view.store.spec.ts` (`sampleSnapshot` typed). `quotes.api.ts` **không cần sửa** vì `buildQuotesQueryString` tự đổi camelCase sang snake_case.
- Trang **"Chi phí chatbot"** (chỉ admin, `chatbot.manage`, 2A): chi phí tháng đến hiện tại so với trần, theo ngày, theo người dùng, sửa trần (5.6).

### 4.10 Kiểm thử

- TDD cho phần lõi thuần: hàm tính %, phân mức theo biên D4 (kiểm các giá trị đúng 2,5 / 5 / 10, và 4,996%), chọn điểm tham chiếu, chống lặp và leo thang, giải quyết người nhận. Thêm kiểm thử theo thuộc tính cho tính chất |R2| ≥ |R1| khi tăng và |R3| ≥ |R1| khi giảm.
- Cửa sổ 7 ngày làm việc: điểm mới vào thứ Hai, thứ Sáu, thứ Bảy; cửa sổ vắt qua cuối tuần; điểm nhận cuối tuần.
- Bộ ba quy tắc: ba ví dụ ở D2 làm test mẫu (tăng, giảm, hướng ngược), hòa |%| thì ưu tiên R1, không in dòng phụ trùng, chỉ có 1 điểm trước, giá mới bằng điểm trước.
- **Nguồn kích hoạt (D6):** tài khoản seed bị loại, trễ 0, 3, 4 ngày làm việc, nhập thứ Sáu chốt thứ Hai, version không phải nguồn vẫn là điểm tham chiếu.
- **Quét an toàn (4.1):** watermark không bỏ sót version commit muộn (quét chồng lấp), lỗi một version không chặn watermark, hai tiến trình quét song song chỉ một tiến trình chạy, bật cờ sau vài tuần không sinh tin cũ, bản điều chỉnh chỉ đánh giá dòng đổi giá, `delete_confirmed_line` không sinh tin.
- **Tin (D5b):** gộp theo vật tư trong một lần quét, leo thang cùng ngày gửi bổ sung, không leo thang thì `suppressed`, trần 30 tin, bản tin 08:00 gửi bù.
- Ngưỡng theo vật tư: ghi đè đủ ba số, dùng mặc định khi không ghi đè, từ chối giá trị không tăng dần hoặc ngưỡng bất thường không lớn hơn ngưỡng Lớn, đổi ngưỡng không báo lại dữ liệu cũ.
- **Giá bất thường (D12):** loại ở mức dòng rồi tính lại daily-min (ví dụ Threonine 15/09), cờ `pending` gắn điểm sau vào cùng thẻ, gộp cụm từ 3 cờ, Giá đúng và Nhập sai, người nhập không có nút, người không có `receive_all` bấm bị từ chối, hai người bấm cùng lúc, nhắc và hết hạn, điểm đầu chuỗi không thể bị gắn cờ.
- **Migration cấp quyền:** chạy trên DB có và không có role `manager`, và chạy trước seed.
- **Fake Telegram transport** (không gọi Telegram thật trong unit test, theo tiền lệ fixture Vietcombank). Cố định "hôm nay" bằng monkeypatch.
- Test múi giờ: biên 00:00/24:00 GMT+7, ranh giới cửa sổ 7 ngày làm việc inclusive/exclusive rõ ràng, `timezone` của arq.
- Verify thật: `curl` webhook với secret đúng/sai, chạy cron trên Docker dev, kiểm `MissingGreenlet` (sau `commit` phải `await session.refresh`). E2E-A cho luồng liên kết (kế hoạch 1A).
- `test_permission_inventory.py` và `test_audit_log_service.py` phải qua. Bảng quyền của công cụ chatbot khai báo dạng dữ liệu không được `test_permission_inventory.py` kiểm (chỉ kiểm lời gọi có tham số là hằng chuỗi), cần test riêng.
- **Dry-run replay trên DB dev:** chế độ bỏ qua D6 (dev gần như toàn dữ liệu nhập lùi nên dry-run theo D6 sẽ ra gần như không có tin), chỉ ghi log, không gửi. Dùng để so với ước lượng ở Phụ lục B.8.

---

## 5. Bước 2: Chatbot AI trên Telegram

### 5.1 Kiến trúc

```
Telegram ──► POST /api/v1/telegram/webhook ──► xác thực secret, dedupe update_id, 200 ngay
                                                  │ enqueue arq (queue riêng "bot")
                                                  ▼
                                      process_telegram_update (worker bot)
                                        1. map telegram_user_id → users.id (active)
                                        2. nạp user + permission
                                        3. khóa hội thoại (Redis lock theo chat)
                                        4. nạp lịch sử gần nhất + tóm tắt
                                        5. gọi LLMClient (tool-calling)
                                        6. thực thi TOOL (hàm cố định, kiểm quyền từng tool)
                                        7. lưu tin + token usage, trả lời Telegram
```

- Dùng **queue và service worker riêng** cho bot (cùng image, `command: arq app.worker.BotWorkerSettings`) để cuộc gọi LLM dài không chiếm 10 slot của worker backup/import. Thêm service vào dev, prod và test compose, kiểm tra `check-production-readiness.sh` vẫn qua.
- Dùng **một pool Redis chung**. Không dùng kiểu `create_job_queue` hiện tại (mở pool mới mỗi lần, không đóng) vì mỗi tin nhắn sẽ rò kết nối.
- Chế độ **polling cho dev** (không có URL công khai), **webhook cho prod** (nginx đã proxy `/api/`). Cùng một hàm xử lý update. Nếu dùng polling ở prod thì chỉ được 1 tiến trình (nhiều instance gây lỗi 409).
- Prod chưa xác minh VPS ra được `api.telegram.org` và Telegram gọi được vào `443` **[CHƯA XÁC MINH]**. Cần kiểm tra sớm.
- **Chỉ chat riêng** (QĐ-7): bỏ qua mọi update có `chat.type` khác `private` (nhóm, kênh), không trả lời.
- **Chỉ tiếng Việt có dấu** (QĐ-7): mọi câu trả lời và nút bấm bằng tiếng Việt có dấu, system prompt yêu cầu như vậy. Đề xuất chấp nhận cả câu hỏi gõ không dấu (khớp tên vật tư bằng chuỗi đã bỏ dấu, chuẩn hóa bằng Python `unicodedata`, không cần extension `unaccent`) nhưng luôn trả lời có dấu.
- Khi chuyển xử lý update sang arq (2A): nếu ghi `update_id` vào `telegram_processed_updates` **trước** khi đưa vào hàng đợi mà Redis lỗi thì update bị mất. Dedupe trong worker, hoặc xóa dòng dedupe nếu đưa vào hàng đợi thất bại.
- Bot dev và bot production tách riêng (4.8).

### 5.2 Hỏi đáp và báo cáo (chỉ đọc)

**Tool-calling với hàm cố định**, mỗi hàm tham số hóa, gọi lại service có sẵn:

| Tool | Gọi tới | Quyền cần |
|---|---|---|
| `find_material(name)` | `MaterialAdminService` lookup | `materials.read` |
| `get_price_trend(material, delivery_month, days)` | `get_daily_min_series` (hàm mới, 4.3) | `dashboard.read` |
| `compare_suppliers(material, delivery_month)` | `QuoteQueryService` | `quotes.read` |
| `list_recent_quotes(filters)` | `QuoteQueryService` | `quotes.read` |
| `weekly_entry_activity()` | `QuotifyDashboardService` | `dashboard.read` |
| `get_price_alerts(days)` | `price_alert_events` | `dashboard.read` |

Phòng thủ nhiều lớp để đáp ứng "chỉ READ" và "cấm SQL nguy hiểm":
1. **Không có tool nào ghi hoặc nhận SQL.** AI không có đường tới câu lệnh tự do.
2. Mọi truy vấn của luồng hỏi đáp chạy ở chế độ **chỉ đọc** và có `statement_timeout`. Đã thử `SET TRANSACTION READ ONLY` trên Postgres 16: chạy được, nhưng hiệu lực **chỉ đến hết giao dịch** (mọi `commit` hoặc `rollback` làm mất chế độ), `SET LOCAL statement_timeout` không bind được tham số, và `SELECT ... FOR UPDATE` không chạy trong giao dịch chỉ đọc. Dùng cách cố định: `execution_options(postgresql_readonly=True)` (SQLAlchemy 2.0.50 hỗ trợ cho asyncpg) hoặc sessionmaker riêng với `connect_args={"server_settings": {"default_transaction_read_only": "on", "statement_timeout": "5000"}}`. Rẻ, không cần role mới.
3. Giai đoạn tăng cường (tùy chọn): role Postgres chỉ `SELECT` trên view whitelist (loại `users.password_hash`, `refresh_tokens`, `audit_logs`, `files`) và engine thứ hai cho luồng hỏi đáp. Cần quyền `CREATE ROLE`.
4. Không cung cấp tool đọc `users`, `audit_logs`, `refresh_tokens`, `files`.
5. Giới hạn kích thước kết quả (cap `limit`), không quét `quote_lines` (~20.000 dòng) không filter. Kiểm `EXPLAIN` cho truy vấn mới.
6. Câu trả lời chỉ dựa trên kết quả tool. System prompt yêu cầu từ chối câu hỏi ngoài dữ liệu Quotify. Giọng trung tính, **không khuyến nghị mua/bán**.
7. Chỉ dùng version `confirmed` (danh sách phẳng mặc định còn cả `draft`, phải lọc).

Nếu sau này cần "hỏi tự do" kiểu text-to-SQL thì chỉ làm sau khi có role read-only và view whitelist, kèm trình phân tích câu lệnh chỉ cho phép một câu `SELECT`. Không đề xuất làm ở v1.

Quyền đọc báo giá hiện là toàn cục theo `quotes.read` (không phân quyền theo chủ phiếu), nên nhân viên hỏi bot xem được giá của người khác, giống như xem trên web. Công cụ hỏi đáp về biến động dùng **cùng định nghĩa với D2** (cùng hàm tính), không có định nghĩa riêng.

### 5.3 Nhập liệu bằng văn bản, ảnh hoặc PDF

Nguyên tắc: **AI chỉ trích xuất, hệ thống kiểm tra, người dùng xác nhận, backend tự tính giá.**

```
Tin nhắn/ảnh/PDF ─► lưu file MinIO (private) ─► LLM trích xuất JSON có cấu trúc
   ─► phân giải NCC/vật tư (khớp chính xác → chứa chuỗi; mơ hồ thì HỎI LẠI, không đoán)
   ─► validate luật nghiệp vụ ─► thẻ xác nhận [✅ Tạo nháp] [✏️ Sửa] [❌ Hủy]
   ─► QuoteService.create_quote  (draft, created_by = user đã liên kết)
   ─► [✅ Chốt báo giá] ─► confirm_version (kiểm ownership như API)
```

Điểm bắt buộc:
- **Không tin số LLM trích xuất để tính giá.** Giá quy đổi do `QuotePricingService` tính. Tỷ giá lấy từ Vietcombank hoặc người dùng nhập.
- Luật nghiệp vụ phải giữ: chỉ cặp `VND/KG` và `USD/MT`; NCC phải có trong `supplier_materials` của vật tư; `received_date` không ở tương lai; `received_date` < hôm nay hoặc `delivery_month` < tháng hiện tại thì bắt buộc `is_backfilled`; USD/MT quá khứ bắt buộc tỷ giá nhập tay; ép `delivery_month` về **ngày 01** (RR-1). Quy tắc "tỷ giá là số nguyên" chỉ có trong import (`quote_backfill_import.py`), **không** áp dụng cho đường nhập thường (`QuoteLineCreateRequest` cho phép 2 chữ số thập phân), nên bỏ khỏi danh sách luật phải giữ.
- **Luôn tạo draft, bước chốt là hành động riêng của người dùng** (QĐ-9). Không có cấu hình "chốt ngay". Phiếu và phiên bản tạo qua bot được đánh dấu `created_via = 'telegram'`.
- **Quyền ghi:** `create_quote` cần `quotes.create`, `confirm_version` cần `quotes.update` cộng kiểm ownership. `_ensure_quote_mutation_allowed` đang là hàm private ném `HTTPException` trong `quotes.py` và gọi `has_role(owner, "user")` cứng tên trong `_quote_owner_can_be_corrected_by`. Cần **tách một helper trả kết quả thuần** (bool hoặc exception domain, không phụ thuộc HTTP), giữ nguyên hành vi API. Service **không** tự kiểm quyền (RR-3).
- **Dựng dịch vụ ngoài HTTP** như `worker.import_quote_backfill_task`: `QuotePricingService(ExchangeRateService(VietcombankExchangeRateClient(...)), QuotifySettingsService(session))`. `VietcombankExchangeRateClient` tạo `httpx.AsyncClient` lười và không đóng, nên tạo **một lần** trong `on_startup` của worker bot, không tạo mỗi tin nhắn.
- **Điều kiện chặn bảo mật (kế hoạch 1A, K15).** Liên kết Telegram ở 1A chỉ dựa vào đường dẫn liên kết sống 10 phút, không có bước xác nhận trong chat. Ai có đường dẫn trong thời gian đó có thể gắn Telegram của mình vào tài khoản của chủ đường dẫn, và chatbot (2B) cho phép ghi dữ liệu nhân danh tài khoản đó. **Trước khi bật ghi dữ liệu qua chatbot, bắt buộc có thêm một bước xác nhận trong chat khi liên kết** (ví dụ nút xác nhận kèm tên và email che một phần), và tin nhắn liên kết đã nêu rõ tên. Đây là điều kiện chặn của slice 2B.
- Audit `quotes.quote_created` do route phát chứ không phải service, nên bot phải tự ghi, kèm `channel=telegram` (thêm key vào allow-list).
- Chống tạo trùng: dedupe theo `update_id`, khóa theo chat, và phát hiện trùng hoàn toàn (mẫu `quote_backfill_import.py`).
- Ảnh/PDF: kiểm MIME, magic bytes, kích thước, số trang trước khi gọi LLM (giới hạn chi phí). Hiện upload file nguồn không kiểm các thứ này. Lưu qua `FileAdminService`. MinIO client là đồng bộ trong hàm async nên phải chạy trong worker hoặc `to_thread`.
- **Prompt injection:** nội dung PDF/ảnh là dữ liệu không tin cậy. Tool ghi duy nhất là "tạo nháp", luôn qua thẻ xác nhận. Không có tool xóa, hủy, sửa danh mục.
- Dòng ghi chú nếu có phải sanitize (`nh3`).

### 5.4 Nhớ ngữ cảnh hội thoại

```
chat_sessions   id, telegram_user_id BIGINT, user_id FK users, summary text,
                last_message_at, expires_at          -- khóa phiên theo telegram_user_id kèm user_id hiện tại
chat_messages   id, session_id, role('user'|'assistant'|'tool'), content,
                tool_calls JSON (định dạng TRUNG LẬP, xem 5.5), created_at
(số token và chi phí chỉ lưu ở llm_usage_events, một nguồn, xem 5.6)
```

- Khóa theo **`telegram_user_id`** và gắn `user_id` hiện tại. Khi đổi tài khoản Telegram, phiên mới bắt đầu (không thừa hưởng ngữ cảnh của người khác).
- Cửa sổ ngữ cảnh: N tin gần nhất + bản tóm tắt cuộn. Lệnh `/reset` xóa ngữ cảnh. TTL (đề xuất 30 ngày) và job dọn.
- Dữ liệu hội thoại có PII và nằm trong `pg_dump`/backup. Phải đưa vào chính sách lưu giữ và restore drill. Không lưu secret. Không ghi nội dung hội thoại vào log hoặc audit.
- Redis dùng cho khóa và tốc độ, không phải nguồn sự thật.
- Giới hạn theo người dùng bằng Redis (không dùng `InMemoryRateLimiter`, vì nó khóa theo IP, IP webhook là của Telegram). Có trần chi phí LLM theo tháng (5.6) và giới hạn lượt hỏi mỗi người mỗi ngày.

### 5.5 Lớp adapter LLM

```
class LLMClient(Protocol):
    async def chat(messages, tools, *, system, max_tokens) -> LLMResponse
    async def extract(files/messages, schema) -> dict          # nhập liệu có cấu trúc
```

- Triển khai riêng cho OpenAI, Gemini, Anthropic trong `app/integrations/llm/`, theo mẫu `integrations/vietcombank.py` (httpx inject được để test, timeout/retry typed, exception riêng). Cờ `LLM_PROVIDER` chọn nhà cung cấp, cờ `CHATBOT_ENABLED` để rollback nhanh. **Dev dùng `LLM_PROVIDER=gemini` với key Google AI Studio** (QĐ-5). Production chọn sau.
- `chat_messages` lưu lời gọi công cụ theo **định dạng trung lập** và ánh xạ sang từng nhà cung cấp khi gọi (OpenAI `tool_calls`, Anthropic `tool_use`, Gemini `functionCall` khác định dạng), nếu không thì đổi nhà cung cấp sẽ hỏng lịch sử hội thoại. Đơn giá (5.6) cấu hình theo mô hình đang dùng, đổi nhà cung cấp phải cập nhật.
- Key API là secret (`*_FILE`, có owner và chính sách xoay vòng). Có timeout, giới hạn token, lỗi LLM không được làm hỏng bot (trả lời "tạm thời không xử lý được").
- Test bằng transport giả, không gọi LLM thật. Cần bộ test "đánh giá" nhỏ (golden set) cho trích xuất báo giá tiếng Việt.

### 5.6 Ngân sách và chi phí LLM (QĐ-10)

- **Admin hệ thống quản lý chi phí.** Trần ngân sách khoảng **2.000.000 VNĐ mỗi tháng** (khoảng 75 USD ở tỷ giá ~26.500), cấu hình được.

```
chatbot_settings (singleton)
  is_enabled bool default false
  monthly_budget_vnd numeric(14,0) default 2000000
  warn_percent smallint default 80
  daily_user_limit int default 20             -- số lượt hỏi mỗi người mỗi ngày, chờ đo chi phí mỗi lượt
  input_price_usd_per_mtok  numeric(10,4)     -- đơn giá model đang dùng (cấu hình)
  output_price_usd_per_mtok numeric(10,4)
  fallback_usd_vnd_rate numeric(12,2)         -- khi không lấy được tỷ giá Vietcombank
  alert_email varchar(255) NULL               -- một địa chỉ; NULL = dùng ADMIN_EMAIL_FOR_BACKUPS
  last_warn_month date NULL                   -- tháng đã gửi email cảnh báo 80%
  last_cap_month date NULL                    -- tháng đã gửi email đạt trần
  updated_by_id FK users SET NULL, created_at, updated_at

llm_usage_events                              -- 1 dòng mỗi lần gọi LLM
  id UUID PK, user_id FK users SET NULL, provider, model
  purpose varchar(10) ('qa'|'extract')
  input_tokens int, output_tokens int
  cost_vnd numeric(14,2)
  created_at timestamptz  (ix)
```

- **Cách tính:** số token × đơn giá model × tỷ giá. Đây là **chi phí ước tính**, số chính thức theo hóa đơn của nhà cung cấp.
- **Kiểm tra trước mỗi lần gọi:** tổng chi phí tháng hiện tại (tháng theo giờ VN) so với trần.
  - Từ `warn_percent` (mặc định 80%): **gửi email cảnh báo cho admin**, một lần mỗi tháng (nhớ bằng `last_warn_month`).
  - Từ 100%: **chặn lời gọi LLM** và gửi email thông báo đã đạt trần, một lần mỗi tháng (`last_cap_month`). Bot trả lời "Chatbot tạm dừng vì đã đạt trần ngân sách tháng này. Vui lòng liên hệ quản trị viên." Thông báo biến động giá (Bước 1) **không bị ảnh hưởng** vì không dùng LLM.
  - Chạy song song có thể vượt trần vài lượt gọi, chấp nhận được.
- **Kênh cảnh báo là email admin (QĐ-13).** Thêm `EmailService.send_budget_alert` theo mẫu `send_backup_notification` (SMTP đồng bộ trong `asyncio.to_thread`). Gọi **sau commit**, bọc `try/except` riêng, lỗi gửi mail không được làm đổi kết quả nghiệp vụ. Người nhận là `chatbot_settings.alert_email`, nếu trống thì `ADMIN_EMAIL_FOR_BACKUPS`. **Chống gửi trùng:** cập nhật có điều kiện `UPDATE ... SET last_warn_month = :tháng WHERE last_warn_month IS DISTINCT FROM :tháng RETURNING`, và chỉ ghi tháng khi gửi thành công (nếu ghi trước mà email lỗi thì cả tháng không gửi lại). Khi admin tăng trần giữa tháng thì đặt lại các cờ gửi. **Điều kiện:** SMTP production hiện chỉ có giá trị mẫu trong `.env.production.example` **[CHƯA XÁC MINH có SMTP thật trên VPS]**, cần cấu hình và gửi thử trước khi dựa vào kênh này. Trang quản trị vẫn hiển thị chi phí tháng nhưng không phải kênh cảnh báo chính.
- **Tỷ giá:** tính chi phí dùng tỷ giá cache theo ngày với `fallback_usd_vnd_rate` khi không lấy được, không gọi Vietcombank mỗi lần tính (RR-11).
- **Giới hạn lượt mỗi người mỗi ngày** (Redis) để một người không dùng hết ngân sách.
- **Trang "Chi phí chatbot"** chỉ admin (`chatbot.manage`): chi phí tháng đến hiện tại so với trần, theo ngày, theo người dùng, sửa trần. Mọi thay đổi trần ghi audit.
- **Chưa có số liệu chi phí mỗi lượt.** Cần đo thực tế trên dev với Google AI Studio (số token và chi phí cho hỏi đáp, đọc ảnh, đọc PDF) trước khi chốt model và hạn mức lượt mỗi người.

---

## 6. Rủi ro và điểm dễ làm vỡ code cũ

Mã rủi ro là `RR-n` (khác với quy tắc R1, R2, R3 ở D2).

| # | Rủi ro | Cách xử lý |
|---|---|---|
| RR-1 | `delivery_month` backend **không ép ngày 01** (`_get_first_day_of_month` tồn tại nhưng không được gọi). Dashboard so `==` chính xác | Chuẩn hóa `date_trunc('month')` khi nhóm chuỗi. Bot phải gửi ngày 01 |
| RR-2 | `is_backfilled` chỉ được kiểm khi tạo hoặc sửa bản nháp, **không lúc chốt**; bị ép `true` mỗi khi `received_date` < hôm nay hoặc kỳ giao < tháng hiện tại. Không có nghĩa "import" (94,3% version trong DB dev là nhập lùi, còn import tạo 82,5% dòng) | D6 mới (QĐ-16) không dùng `is_backfilled`: nguồn kích hoạt theo tài khoản seed và độ trễ ngày làm việc |
| RR-3 | **Authz nằm ở tầng API**, service không kiểm quyền và không kiểm ownership. Bot gọi service sẽ **bỏ qua toàn bộ RBAC** nếu không tự thêm | Mọi công cụ và hành động phải kiểm `has_permission` và ownership. Tách helper ownership trả kết quả thuần (5.3) |
| RR-4 | Bản điều chỉnh (`superseded`) và `delete_confirmed_line` đều tạo version confirmed mới là snapshot đầy đủ, dễ sinh cảnh báo kép hoặc giả | D2 mục 5: chỉ đánh giá dòng mới hoặc đổi giá (dùng `superseded_by_version_id`). `delete_confirmed_line` không phát tin. Khóa chống trùng |
| RR-5 | `create_job_queue` mở pool Redis mới mỗi lần, không đóng | Dùng một pool chung khi chuyển webhook sang arq (2A) |
| RR-6 | Token bot nằm trong URL `api.telegram.org/bot<TOKEN>/...`. httpx log URL ở INFO và `HTTPXClientInstrumentor` ghi URL vào span OTel | Hạ log httpx, scrub URL ở Formatter, loại URL khỏi OTel, không `raise_for_status`. Kế hoạch 1A, Slice 1. Verify trên production **[CHƯA XÁC MINH]** |
| RR-7 | Xóa người dùng cứng: `created_by_id` thành NULL (mất người nhận); `DELETE /users/{id}` có thể còn trả 500 (`User.refresh_tokens` không có cascade, phân tích tĩnh, chưa chạy thử). Khóa ngoại bảng mới không ghi `ON DELETE` sẽ chặn xóa | Vô hiệu hóa thay vì xóa. Bỏ qua người dùng không `ACTIVE`. Mọi FK bảng mới ghi rõ `ON DELETE` (4.5) |
| RR-8 | arq cron theo múi giờ hệ thống (UTC) nếu không đặt `timezone` | Đặt `timezone` trong `WorkerSettings` (arq 0.26.3 hỗ trợ) và test (4.8) |
| RR-9 | Rate limiter in-memory khóa theo IP, không xóa key cũ | 1A dùng in-memory khóa theo người dùng (ứng dụng và Telegram), **lệch có chủ đích** so với Redis vì production chạy một tiến trình uvicorn (RR-18). Redis ở 1C hoặc khi có nhiều tiến trình |
| RR-10 | Import backfill đi thẳng `create_quote(confirm_immediately=True)`, không qua route confirm. Cron quét `confirmed_at` bắt cả import | Nguồn kích hoạt loại tài khoản seed (D6), watermark lúc bật cờ, trần gửi ngay |
| RR-11 | Tỷ giá gọi Vietcombank **từng dòng**, không cache. Buổi sáng sớm feed có thể chưa cập nhật nên lỗi | Bot hỏi tỷ giá tay khi lỗi. Cache theo ngày |
| RR-12 | Số liệu tiền dùng `float` ở frontend. Backend dùng `Decimal` | Chỉ tính ở backend bằng `Decimal` |
| RR-13 | `seed_auth_rbac.py` ghi đè quyền role `user` về đúng `USER_ROLE_PERMISSION_CODES` và không đụng role `manager`. Migration kiểu `0810` chỉ `DELETE`, và bảng `permissions` chưa có dòng mới lúc migrate (seed chạy sau) nên migration chỉ gán quyền sẽ **chạy rỗng** | Migration tự chèn `permissions` rồi gán cho `manager`, chịu được thiếu role (4.6, QĐ-19) |
| RR-14 | Hai định nghĩa "người nhập" (`quotes.created_by_id` và `quote_versions.created_by_id`) | D8 (nhân viên nhận tin) dùng `quotes.created_by_id`. D12 (người nhận tin bất thường) dùng `quote_versions.created_by_id` vì lỗi nhập sai thường do người tạo version |
| RR-15 | Phiếu `draft` có trong danh sách phẳng mặc định | Mọi truy vấn của bot lọc `confirmed` |
| RR-16 | `update_draft` luôn tính lại giá, `create_version` không giữ `note` | Cẩn thận khi bot tạo bản điều chỉnh |
| RR-17 | Dữ liệu hội thoại, PII nằm trong backup. Dữ liệu gửi LLM bên thứ ba (đã được phép, QĐ-6) | Chính sách lưu giữ. Chỉ gửi nội dung tối thiểu. Dev dùng gói miễn phí nên ưu tiên dữ liệu thử, xác minh điều khoản của gói (D11) |
| RR-18 | Production chạy 1 tiến trình uvicorn, Redis không mật khẩu và worker bỏ qua `REDIS_URL` | Không đổi Redis sang có mật khẩu mà không sửa worker |
| RR-19 | Nợ kỹ thuật nền (lint, prettier, test baseline, `smoke.spec.ts` lỗi thời, alert rules còn tên `fastapivue_*`) | So với baseline trước khi báo "không lỗi mới". Không sửa lan |
| RR-20 | Watermark bỏ sót version commit muộn (`confirmed_at` gán trước commit), một version lỗi chặn watermark, bão tin khi bật cờ sau nhiều ngày | Quét chồng lấp 5 phút, savepoint từng version, watermark đặt lúc bật cờ, khóa advisory (4.1) |
| RR-21 | Điểm tham chiếu bị "nhiễm độc" bởi điểm sai (Khô cọ, Tryptophan), cờ `pending` sinh tin bất thường lặp lại | Tham chiếu gắn cờ 30 ngày, gắn điểm sau vào thẻ, gộp cụm, hết hạn (D12) |
| RR-22 | **Tải tin thật cao hơn backtest** (dữ liệu nhập thật chỉ 6,3 tuần, 82,5% là import) | Ước lượng ở B.8, dry-run replay, trần gửi ngay, bản tin tổng hợp, theo dõi 30 đến 60 ngày sau khi bật |
| RR-23 | Không ai xử lý thẻ bất thường, hai trưởng phòng bấm cùng lúc, người nhập bị xóa hoặc khóa | Vòng đời nhắc, hết hạn, người đầu thắng (D12), đường xem xét trên web (1C) |
| RR-24 | Bot dev và production dùng chung token gây lỗi 409 và lẫn dữ liệu; khôi phục dump production vào dev mang theo liên kết Telegram thật | Hai bot riêng, đặt `is_enabled=false` và thu hồi liên kết sau khi khôi phục (4.8) |
| RR-25 | matplotlib là CPU đồng bộ, chặn vòng lặp arq | `asyncio.to_thread`, API hướng đối tượng (4.3) |
| RR-26 | Worker không được Prometheus scrape nên metric trong worker không hiện | `price_alert_scan_runs` và gauge phát từ backend, hoặc `start_http_server` trong worker (4.8) |
| RR-27 | Gửi Telegram là at-least-once; tin trả lời của bot là at-most-once (commit xong rồi mới gửi) | Chấp nhận, ghi trong thiết kế. `lease_until` giảm gửi trùng |

### Lệch tài liệu và code đã phát hiện (cần biết trước khi tin tài liệu)

- `memory-bank/progress.md`, `activeContext.md` dừng ở 22/08. Nhiều thay đổi 17-25/08 chưa vào memory-bank: import `.xlsx`, dashboard làm lại, hủy phiếu/xóa dòng, `sequence_number`, tỷ giá lịch sử, `created_by_role`, role correction.
- `Requirements.txt` còn công thức cũ ("Chi phí quy đổi") và "bắt buộc lý do nhập lại" đã bỏ từ 04/08.
- `projectbrief.md`, `README.md` còn mô tả "chỉ có boilerplate".
- `systemPatterns.md` ghi grace refresh token 30s, code là 120s.
- `docs/adr/` không tồn tại.
- Mục 1.2 của tài liệu này từng trộn hai nguồn dữ liệu, nay đã ghi nguồn cho từng con số.

---

## 7. Kế hoạch triển khai theo giai đoạn

Mỗi lát cắt có migration (nếu cần), backend, giao diện (nếu cần), test, tài liệu. Làm theo TDD. Mỗi lát cắt phát hành **tắt** bằng cờ cấu hình, bật dần.

### Giai đoạn 0: Chốt phạm vi và điều kiện (không code)
- Các quyết định D1 đến D12 đã chốt. Việc còn lại và chi tiết nằm ở **Slice 0 của kế hoạch 1A** (đã làm một phần: bot dev và T2, T3, T5, T5b; còn phần hạ tầng production): tạo bot dev, kiểm chứng các điểm Telegram chưa nêu rõ, kiểm hạ tầng production hai chiều (ra `api.telegram.org`, và Telegram vào được `443`), cập nhật `CONTEXT.md`, `Requirements.txt`, `quotify-implementation-plan.md`.
- Kiểm tra DB production: role `manager` có tồn tại không, số người dùng theo role, tên role thật (cần cho migration cấp quyền).

### Giai đoạn 1A: Nền tảng Telegram và liên kết tài khoản
Chi tiết, chia slice, hợp đồng API và tiêu chí chấp nhận: [kế hoạch 1A](plan-telegram-giai-doan-1a-nen-tang-lien-ket.md). Gồm client Telegram an toàn, webhook và polling, chống trùng, liên kết, đổi, hủy tài khoản, panel Hồ sơ, audit, và **triển khai production** (cờ tắt rồi bật).
- **Hoàn thành khi:** một người dùng liên kết, đổi, hủy được tài khoản Telegram trên dev, rồi trên production với một tài khoản thử.

### Giai đoạn 1B: Engine biến động và thông báo
**Kế hoạch chi tiết (bản nháp chờ xác nhận):** [plan-telegram-giai-doan-1b-engine-bien-dong-gia.md](plan-telegram-giai-doan-1b-engine-bien-dong-gia.md), chia 16 slice và hai đợt phát hành (α: biến động giá; β: giá bất thường và nút bấm). Hạng mục tổng quát:
- Migration nhóm biến động giá (4.5) và permission mới, cấp cho `manager` bằng migration tự chèn quyền (4.6).
- Hàm `get_daily_min_series` (4.3) và `PriceAlertService` (hàm thuần, TDD): cửa sổ ngày làm việc, bộ ba quy tắc, nguồn kích hoạt (D6), dòng ứng viên của version điều chỉnh, đánh giá bất thường mức dòng và vòng đời thẻ (D12).
- Cron quét an toàn (4.1), tin gộp (D5b), giải quyết người nhận (D7 đến D10), chống trùng và leo thang.
- Bộ vẽ biểu đồ (matplotlib, `asyncio.to_thread`, font tiếng Việt) và tin: ảnh, caption ngắn, tin chi tiết, gửi và thử lại.
- **Bộ xử lý `callback_query`:** nút Giá đúng và Nhập sai (`answerCallbackQuery`, sửa tin sau khi bấm, người đầu thắng).
- **API cấu hình ở backend** (4.6): `price-alert-settings`, ghi đè theo vật tư, `alert-preferences`, bật/tắt. **Cách bật cờ lần đầu ở 1B khi chưa có giao diện:** gọi API bằng quyền `price_alerts.manage` (giao diện ở 1C).
- **Chế độ dry-run replay** trên DB dev (bỏ qua D6, chỉ ghi log, không gửi) và quan sát (`price_alert_scan_runs`).
- **Hoàn thành khi (đề xuất, định lượng):** dry-run replay đạt: (1) không có tin sai hướng (test thuộc tính và đối chiếu mẫu); (2) số tin gộp mỗi tuần và số tin Trung bình và Lớn trong khoảng ±30% so với ước lượng ở B.8 cho cùng cấu hình; (3) các điểm bất thường ở B.7 được gắn cờ đúng, và các điểm sai tham chiếu (Khô cọ, Tryptophan) không còn sinh cờ giả; (4) tin mẫu đúng định dạng trên Telegram thật (ảnh, caption không quá 1.024 ký tự, tin chi tiết không quá 4.096).

### Giai đoạn 1C: Giao diện cấu hình, bản tin tổng hợp, vận hành
- Trang `/price-alert-settings` (ngưỡng mặc định, ngưỡng theo vật tư, bật/tắt), tùy chọn cá nhân trong Hồ sơ, trang xem xét điểm bất thường.
- Bản tin tổng hợp 08:00: danh sách theo vật tư các sự kiện mức Nhẹ chưa gửi, **không gửi khi rỗng**, vẫn gửi vào cuối tuần nếu có sự kiện, gửi bù trong ngày nếu worker tắt lúc 08:00.
- Hạn mức bằng Redis nếu cần (khi có nhiều tiến trình), metric (`quotify_*`) và cảnh báo watermark trễ, runbook, `.env.production.example`, compliance script.
- Triển khai production: backup, build (`backend`, `frontend`, `worker`), migrate bằng `run --rm`, seed quyền, `up -d`, `restart reverse-proxy`, bật cờ cho một nhóm nhỏ trước.

### Giai đoạn 2A: Hạ tầng chatbot và hỏi đáp
- Migration: `chat_sessions`, `chat_messages`, `chatbot_settings`, `llm_usage_events`, permission `chatbot.manage`.
- Ngân sách LLM (5.6): kiểm tra trần trước mỗi lần gọi, cảnh báo email admin, trang "Chi phí chatbot".
- `LLMClient` + adapter, queue và service worker bot, chuyển xử lý update sang arq, lock và hạn mức bằng Redis.
- Công cụ chỉ đọc (chế độ chỉ đọc cố định, 5.2), bộ test công cụ và quyền, golden set hỏi đáp. Bộ nhớ hội thoại, `/reset`.

### Giai đoạn 2B: Nhập liệu bằng văn bản
- **Điều kiện chặn bảo mật (K15):** bước xác nhận trong chat khi liên kết phải có trước khi bật ghi dữ liệu (5.3).
- Migration `quotes.created_via`, `quote_versions.created_via` (nullable). Icon bot ở cột Trạng thái và ô tick lọc nguồn Telegram (4.9, gồm cả export Excel).
- Trích xuất có cấu trúc, phân giải NCC và vật tư, thẻ xác nhận, `create_quote` (luôn draft, `created_via = 'telegram'`), chốt, audit, idempotency, helper ownership tách khỏi `quotes.py`.

### Giai đoạn 2C: Nhập liệu bằng ảnh và PDF
- Kiểm tra file, lưu MinIO, trích xuất đa mô thức, hỏi lại khi mơ hồ, xử lý nhiều báo giá trong một file.

### Giai đoạn 2D: Tăng cường
- Role Postgres read-only và view whitelist cho luồng hỏi đáp. Rà soát prompt injection, chi phí, quyền riêng tư. Restore drill có dữ liệu hội thoại.

---

## 8. Khuyến nghị triển khai production (additive)

- Production hiện chạy migrate bằng image **mới** trước khi thay container, nên code cũ chạy một lúc trên schema mới. Chỉ thêm bảng và cột nullable. Không đổi tên, không xóa, không downgrade.
- Phát hành mọi tính năng với cờ **tắt**. Thêm bảng và quyền trước, bật sau.
- Theo runbook mục 9: backup bắt buộc trước migrate (`scripts/ops/backup-postgres.sh` và `backup-minio.sh`, kèm `export COMPOSE_FILE=docker-compose.prod.yml`); so `.env.production.example` với `.env` thật khi có biến mới (9.3); build `backend frontend worker` và **cả service worker bot** (9.4); migrate bằng `run --rm backend ... alembic upgrade head` **trước** `up -d` (9.5); seed (9.6) chạy **sau** migrate, nên migration cấp quyền phải tự chèn `permissions` (4.6); `up -d` rồi `restart reverse-proxy` (9.7).
- Không sửa các file lõi nếu tránh được: `http.ts`, `auth.store.ts`, `router/guards.ts`, `useDashboardPage.ts`, `quotes.py`, `quote_service.py`. Ưu tiên file mới. Hàm daily-min mới nằm ở service riêng, không sửa `QuotifyDashboardService`.
- Thêm `telegram_accounts` ở bảng riêng, **không** thêm cột vào `users`.
- **Ngoại lệ có chủ đích** (QĐ-9, 2B): cột `created_via` nullable vào `quotes` và `quote_versions`, tham số tùy chọn `created_via` vào `QuoteService.create_quote` và `create_version`, trường tùy chọn vào `schemas/quote.py`, `schemas/quote_list.py`, tham số lọc `created_via` vào `GET /quotes`, `QuoteQueryService` và hàm export Excel. Hành vi mặc định không đổi. Cần test hồi quy cho các API báo giá, export và danh sách hiện có (`test_quotes_list_api.py`, `test_quotes_export_api.py`, `test_quote_query_service.py`).
- Thay đổi nhỏ bắt buộc ở code cũ: đăng ký router, thêm vào `models/__init__.py` và `db/base.py`, `BASE_PERMISSION_CODES`, allow-list audit, `Settings`, `WorkerSettings` (cron, `timezone`), `core/logging.py`, `core/observability.py`, `services/email.py` (`send_budget_alert`), compose, và tách helper ownership khỏi `quotes.py`.

---

## 9. Câu hỏi đã trả lời và điểm còn mở

### 9.1 Đã trả lời

Mã `H` đánh số các câu hỏi, cột QĐ trỏ tới quyết định tương ứng ở Mục 0.1.

| Mã | Ngày | Câu hỏi | Trả lời | QĐ |
|---|---|---|---|---|
| D1 | 10-03 | Gộp nhiều kỳ giao hàng vào một chuỗi không | Không gộp. Chuỗi là (vật tư, kỳ giao hàng) | QĐ-15 |
| D5 đến D10 | 10-03 | Chống spam, nguồn kích hoạt, người nhận, tùy chọn từng người | Đồng ý các đề xuất (D6 sau đó được thay bằng QĐ-16) | QĐ-14 |
| D11a | 10-03 | Nhà cung cấp LLM | Chưa chốt cho production. Dev dùng API key Google AI Studio | QĐ-5 |
| D11b | 10-03 | Chính sách dữ liệu | Cho phép gửi nội dung báo giá, ảnh, PDF sang bên thứ ba | QĐ-6 |
| D11c | 10-03 | Gói Google AI Studio khi test dev | Dùng gói miễn phí | QĐ-5 |
| H1 | 10-03 | Tin nhắn gửi vào nhóm hay chat riêng | Chỉ chat riêng | QĐ-7 |
| H2 | 10-03 | Ngôn ngữ bot | Chỉ tiếng Việt có dấu | QĐ-7 |
| H3 | 10-03 | Khung giờ yên lặng | Không có | QĐ-7 |
| H4 | 10-03 | Hiển thị CNF cho dòng USD | Có | QĐ-8 |
| H5 | 10-03 | Chatbot nhập liệu có chốt ngay không | Luôn tạo nháp rồi mới chốt | QĐ-9 |
| H6 | 10-03 | Ai quản lý chi phí LLM, có trần không | Admin hệ thống. Trần khoảng 2.000.000 VNĐ mỗi tháng | QĐ-10 |
| H7 | 10-03 | Ghi nhận nguồn nhập qua Telegram | Có | QĐ-9 |
| H8 | 10-03 | Loại ngày lễ và Tết khỏi ngày làm việc | Tạm thời chưa | QĐ-11 |
| H9 | 10-03 | Ai sửa ngưỡng theo vật tư | Admin và trưởng phòng | QĐ-4 |
| H10 | 10-03 | Giá bất thường có tự chấp nhận không | Không, chỉ bằng nút Giá đúng | QĐ-12 |
| H11 | 10-03 | Người nhận tin giá bất thường | Trưởng phòng và người nhập | QĐ-12 |
| H12 | 10-03 | Điều chỉnh hướng tin ở D2 | Đồng ý | QĐ-12 |
| H13 | 10-03 | Vị trí nhãn Telegram, có lọc theo nguồn không | Chỉ icon bot ở cột "Trạng thái". Có ô tick lọc theo nguồn Telegram | QĐ-9 |
| H14 | 10-03 | Biến động % cho chuỗi USD/MT | Không làm, chỉ tính trên VNĐ/KG | QĐ-13 |
| H15 | 10-03 | Kênh gửi cảnh báo ngân sách LLM | Email admin | QĐ-10 |
| Q1 | 10-04 | Nguồn kích hoạt (thay D6) | Không do tài khoản seed admin và trễ không quá 3 ngày làm việc. Nhận biết import bằng tài khoản seed admin | QĐ-16 |
| Q2 | 10-04 | Đơn vị tin | Gộp trong một lần quét, chỉ gửi bổ sung khi leo thang, caption ngắn kèm tin chi tiết | QĐ-17 |
| Q3 | 10-04 | Vòng đời giá bất thường | Đồng ý các đề xuất ở D12 | QĐ-18 |
| Q4 | 10-04 | Quyền và vị trí giao diện cấu hình | Đồng ý. Trưởng phòng được tắt/bật tính năng | QĐ-19 |
| Q5 | 10-04 | Có nên tính biến động ngay khi người dùng chốt phiếu thay vì cron quét | Giữ cron quét + watermark (bắt đủ ba đường chốt, không mất sự kiện khi Redis hỏng, không sửa `quotes.py`), đổi chu kỳ thành 30 giây. Enqueue sau commit hoặc outbox để dành cho 1C nếu cần | QĐ-20 |

### 9.2 Còn mở

**Điểm mở (không chặn việc bắt đầu 1A, chốt trong lúc làm):**

1. **Tham số mặc định của 1B** (bảng ở Mục 3): chốt từng giá trị sau dry-run replay.
2. **Nhà cung cấp LLM cho production.** Chọn sau khi đo chi phí và chất lượng đọc ảnh/PDF tiếng Việt trên dev.
3. **Điều khoản dữ liệu và hạn mức của gói miễn phí Google AI Studio** **[CẦN XÁC MINH]**. Dev chứa dữ liệu thật và hạn mức thấp có thể khiến bài đo chi phí chưa phản ánh production.
4. **Giới hạn lượt hỏi mỗi người mỗi ngày** (mặc định 20), sau khi đo chi phí mỗi lượt.
5. **SMTP production** có thật chưa **[CHƯA XÁC MINH]**, và email nhận cảnh báo ngân sách (một địa chỉ hay nhiều).
6. **Ô tick lọc nguồn Telegram:** tick là chỉ phiếu Telegram, không tick là tất cả (chờ xác nhận).
7. **Chấp nhận câu hỏi gõ không dấu** (đề xuất ở 5.1, chưa xác nhận).
8. **TTL hội thoại** (đề xuất 30 ngày) và job dọn.
9. **Font tiếng Việt** trong image production cho matplotlib **[CHƯA XÁC MINH]**.
10. **Nhận biết import chỉ bằng tài khoản seed admin** (QĐ-16): chưa có đánh dấu riêng. Đã chốt quy ước ở kế hoạch 1B (Q7): tài khoản seed không bao giờ nhập tay, nên không cần tài khoản riêng; vi phạm quy ước làm phiếu nhập tay bị loại nhầm (RR-38 của kế hoạch 1B).
11. **Xóa người dùng cứng:** `DELETE /users/{id}` có thể còn trả 500 (phân tích tĩnh, chưa chạy thử). Khuyến nghị vô hiệu hóa thay vì xóa.
12. **Backlog (ngoài phạm vi 1A đến 1C):** cảnh báo ngay lúc nhập (giá USD/MT gõ vào ô VNĐ/KG) trên giao diện nhập báo giá; loại ngày lễ và Tết khỏi ngày làm việc (QĐ-11).

---

## 10. Phụ lục A: tập tin sẽ chạm vào

**File mới, backend (dự kiến):**
- `backend/alembic/versions/2026MMDD_HHMM_*.py` (một migration cho mỗi lát cắt, nối tiếp nhau)
- `app/models/`: `telegram_processed_update.py`, `telegram_account.py`, `telegram_link_token.py`, `price_alert.py` (các bảng nhóm biến động giá), `chat.py`
- `app/schemas/`: `telegram.py`, `price_alert.py`, `chatbot.py`
- `app/services/`: `telegram_update_service.py`, `telegram_update_runner.py`, `telegram_link_service.py`, `price_alert_service.py`, `price_alert_scan.py`, `price_alert_chart.py`, `daily_min_series.py` (hàm daily-min mới), `chatbot_service.py`, `chatbot_budget_service.py`
- `app/integrations/telegram.py`, `app/integrations/llm/*`
- `app/api/v1/`: `telegram.py` (webhook), `telegram_link.py`, `price_alerts.py` (cấu hình và điểm bất thường), `chatbot.py`
- `app/telegram_poller.py`, `scripts/telegram_webhook.py`

**File mới, frontend:**
- `src/types/telegram.ts`, `api/telegram.api.ts`, `api/telegram.mappers.ts`, `composables/useTelegramLink.ts`
- `src/types/price-alerts.ts`, `api/price-alerts.api.ts`, `api/price-alerts.mappers.ts`, `composables/usePriceAlertSettingsPage.ts`, `composables/usePriceAlertAnomaliesPage.ts`
- `src/pages/PriceAlertSettingsPage.vue`, `PriceAlertAnomaliesPage.vue`, `ChatbotUsagePage.vue`
- `src/styles/pages/_price-alert-settings-page.scss` (và các file `_price-alert-*.scss` khác nếu cần)
- Test tương ứng cho từng file trên

**File hiện có chỉ sửa tối thiểu, backend:**
- `app/api/v1/router.py` (đăng ký router), `app/models/__init__.py`, `app/db/base.py` (đăng ký model)
- `app/auth/seed_data.py` (permission mới)
- `app/services/audit_log.py` (allow-list)
- `app/core/config.py`, `core/logging.py`, `core/observability.py`, `.env.example`, `.env.production.example`
- `app/worker.py` (đăng ký cron, task, `timezone`)
- `pyproject.toml`, `uv.lock` (matplotlib, SDK nếu dùng)
- `docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.test.yml` (service bot nếu tách)
- Giai đoạn 2B (`created_via`): `models/quote.py`, `models/quote_version.py`, `schemas/quote.py`, `schemas/quote_list.py`, `services/quote_service.py`, `services/quote_query_service.py` (kể cả hàm export), `api/v1/quotes.py` (tham số lọc và `export_quotes`)
- `services/email.py` (`send_budget_alert`)

**File hiện có chỉ sửa tối thiểu, frontend:**
- `src/pages/ProfilePage.vue`, `styles/pages/_profile-page.scss`, `router/index.ts`, `layouts/AdminLayout.vue` (mục sidebar trang mới), `api/audit-logs.mappers.ts`, `pages/AuditLogsPage.vue`
- 2B: `pages/QuotesPage.vue` (bảng desktop và thẻ mobile), `composables/useQuotesPage.ts`, `stores/quotes-view.store.ts`, `types/quotes.ts`, `api/quotes.mappers.ts`. `api/quotes.api.ts` không cần sửa.

**Tài liệu và quy trình:** `CONTEXT.md`, `docs/quotify/Requirements.txt`, `docs/quotify/quotify-implementation-plan.md`, `docs/runbooks/deploy-vps-production.md`, `memory-bank/*`.

---

## Phụ lục B: Kết quả backtest trên dữ liệu thật

**Cách làm.** Script chỉ đọc, chạy trên DB dev (khôi phục từ dump 2026-10-02): 20.893 dòng giá `confirmed`, phiếu chưa hủy, toàn kỳ từ 10/2023 đến 02/10/2026, 361 chuỗi. **Phần 12 tháng gần nhất** (đối tượng của B.1 đến B.7): 9.798 dòng, 4.532 điểm daily-min, 303 chuỗi. Với mỗi chuỗi và mỗi ngày có báo giá, lấy daily-min của ngày đó, so với các điểm trước theo từng phương án, rồi phân mức theo D4. "Chống lặp" là quy tắc D5(a). Người nhận nhân viên là người nhập vật tư đó trong 90 ngày trước (D8). Các script **chưa nằm trong repo** (xem Mục 9.2 và việc đưa vào `backend/scripts/analysis/`).

**Các phương án so sánh** (điểm trước nằm trong cửa sổ 14 ngày lịch, trừ khi ghi khác):
- **A:** so với điểm giá **cũ nhất** trong 13 ngày lịch trước.
- **B:** so với điểm giá liền trước.
- **C:** so với trung bình các điểm trước.
- **MIN:** so với giá thấp nhất của các điểm trước (không gồm điểm mới), dấu theo hiệu.
- **MM:** hướng theo bước nhảy cuối, tăng thì so với min, giảm thì so với max của các điểm trước. Định nghĩa gốc thiếu chi tiết nên **các số MM (B.1, B.3, B.4) không tái hiện được độc lập**, chỉ mang tính tham khảo.
- **Bộ ba quy tắc** (D2): R1/R2/R3, qua hai vòng: cửa sổ 7 ngày lịch (vòng trung gian) và cửa sổ 7 ngày làm việc (vòng đã chốt, B.7).

**Giới hạn của phép thử.**
- Phát lại theo `received_date`, mỗi ngày chấm một lần vào cuối ngày. Hệ thống thật chấm mỗi khi có version mới `confirmed` (B.8: tin sau chống lặp nhiều hơn khoảng 5,6%).
- **Dữ liệu 12 tháng không đại diện cho tải thật:** 82,5% dòng là import, chỉ 565 dòng (5,8%) là nhập thật, nằm trong 6,3 tuần gần nhất. Xem B.8.
- Danh sách người nhận là ước lượng.
- Có 7 nhân viên nhập báo giá và 1 tài khoản import, nên số liệu theo người chỉ mang tính tham khảo.

### B.1 Phân bố mức, chưa chống lặp (12 tháng gần nhất)

N là số điểm giá có ít nhất 1 điểm trước trong cửa sổ. "% gửi" là tỷ lệ điểm vượt 2,5%.

| PA | N | Nhẹ↑ | Nhẹ↓ | TB↑ | TB↓ | Lớn↑ | Lớn↓ | % gửi |
|---|---|---|---|---|---|---|---|---|
| A | 4.105 | 598 | 397 | 254 | 156 | 92 | 33 | 37,3% |
| B | 4.105 | 273 | 210 | 65 | 63 | 45 | 39 | 16,9% |
| C | 4.105 | 431 | 258 | 129 | 63 | 46 | 31 | 23,3% |
| MIN | 4.105 | 868 | 80 | 348 | 36 | 146 | 26 | 36,6% |
| MM | 3.756 | 593 | 536 | 273 | 204 | 114 | 46 | 47,0% |

Độ lớn |%| theo phân vị (A): P50 = 1,7%, P70 = 3,0%, P90 = 5,7%, P99 = 16,1%. Nghĩa là **ngưỡng 2,5% nằm trong vùng dao động thường gặp** của daily-min giữa các nhà cung cấp (37% điểm vượt).

### B.2 Số tin sau chống lặp, theo chuỗi (12 tháng)

| PA | Tổng | Tin/tuần (trưởng phòng) | Tuần nhiều nhất | Nhẹ | TB | Lớn |
|---|---|---|---|---|---|---|
| A | 832 | 16,0 | 53 | 517 | 228 | 87 |
| B | 637 | 12,2 | 49 | 441 | 123 | 73 |
| C | 578 | 11,1 | 46 | 388 | 137 | 53 |
| MIN | 726 | 13,9 | 55 | 427 | 204 | 95 |
| MM | 1.118 | 21,4 | 62 | 721 | 283 | 114 |

Bảng này dùng chống lặp có "mồi" bằng lịch sử trước 12 tháng. Không mồi thì A/B/C/MIN là 840 / 637 / 579 / 733 (chênh nhỏ).

### B.3 Gộp theo vật tư (một tin mỗi vật tư mỗi ngày)

Mỗi vật tư có trung vị **5 kỳ giao hàng** (tối đa 44 trong toàn kỳ, 20 trong 12 tháng; một tin gộp tối đa 10 chuỗi), nên một cú biến động của thị trường sinh nhiều chuỗi cùng lúc. Ví dụ Khô đậu tương kỳ 12/2026, 01/2027, 02/2027 cùng giảm 3,4-4,3% trong cùng một ngày.

| PA | Tin theo chuỗi | Tin theo vật tư (/tuần) | Tuần nhiều nhất | Nhân viên: TB tin/tuần | p90 tuần | Nhân viên chỉ TB+Lớn: TB tin/tuần | p90 tuần |
|---|---|---|---|---|---|---|---|
| A | 832 | 365 (7,0) | 28 | 1,3 | 8 | 0,5 | 6 |
| MM | 1.118 | 453 (8,7) | 35 | 1,6 | 9 | 0,7 | 6 |

Các cột "Nhân viên" **không tái hiện được độc lập** (định nghĩa người nhận chưa đủ rõ): đo lại bằng tra cứu 90 ngày theo `received_date` ra 0,91 và 0,44. Ước lượng thời gian thực ở B.8 cao hơn nhiều (khoảng 2,7 đến 2,9 tin mỗi tuần).

Nếu chỉ gửi ngay mức Trung bình và Lớn (A, gộp theo vật tư): 150 tin/năm, tức khoảng 2,9 tin/tuần cho trưởng phòng. Nâng ngưỡng Nhẹ lên 3,5%: 5,3 tin/tuần. Lên 5%: 2,7 tin/tuần (tính cả mức Nhẹ).

**Tập trung:** Khô đậu tương chiếm 47% và Ngô hạt 21% số tin theo chuỗi, 5 vật tư đầu chiếm 78%. Hai vật tư này có nhiều kỳ giao hàng và báo giá dày nhất.

### B.4 So sánh A và MM (12 tháng, chưa chống lặp)

- Cả hai cùng báo: 1.194 (trong đó **66 điểm ngược chiều**).
- Chỉ A báo: 336. Chỉ MM báo: 572.
- Ví dụ "chỉ A báo": Khô đậu tương giảm dần 13,486 → 12,900 (−4,3% so với điểm đầu), nhưng hai ngày cuối bằng nhau nên MM không thấy bước nhảy.
- Ví dụ "chỉ MM báo" (lỗi nhập liệu): Khô cọ có điểm 5,179 → 9,505 → 5,172. MM so điểm cuối với max 9,505 và báo **−45,6%**, A chỉ báo −0,1%. Lưu ý 9,505 là giá **đã được sửa** từ 93,245, và điểm sai thật của chuỗi này là 187 (xem D12). Max và min nhạy với giá bất thường, nên cần cơ chế phát hiện giá bất thường trước khi tính biến động.

### B.5 Nhìn lại các dòng đã chốt mua (tham khảo, ngoài phạm vi quyết định)

Phần này chỉ mô tả, **không kết luận quyết định mua đúng hay sai** (Requirements 3.9). 101 dòng chốt mua, 71 dòng có điểm giá trước (14 ngày), 55 dòng có điểm giá sau (14 ngày) đã kiểm lại đúng.

| Chỉ số | Kết quả |
|---|---|
| Giá chốt so với khoảng 14 ngày trước (n = 40) | 29/40 dòng có giá chốt **thấp hơn hoặc bằng đáy** 14 ngày trước, 3/40 cao hơn hoặc bằng đỉnh |
| Đáy 14 ngày **sau** chốt so với giá chốt (n = 55) | Trung vị +1,6%. Thấp hơn giá chốt trên 2,5%: 6 dòng. Cao hơn trên 2,5%: 19 dòng |
| Giá mới nhất (trong 30 ngày) so với giá chốt (n = 66) | Trung vị +2,3% |

Các hàng n = 40 và n = 66 không tái hiện được độc lập vì tiêu chí chọn mẫu chưa được định nghĩa. Đo lại với tiêu chí "có ít nhất 2 điểm trước": n = 39 (27 dòng ≤ đáy, 4 dòng ≥ đỉnh); giá mới nhất trong 30 ngày: n = 62, trung vị +3,5%. Người mua thường chọn nhà cung cấp rẻ nhất trong ngày, nên giá chốt thấp hơn daily-min các ngày trước là điều dễ hiểu. Hệ thống không biết khối lượng và điều kiện hợp đồng.

### B.6 Kết luận từ backtest (vòng 1, phương án A và MM)

> Quyết định cuối cùng (bộ ba quy tắc, 7 ngày làm việc) dựa trên vòng 2 ở B.7 và B.8.

1. **Lựa chọn A, B, C ít quan trọng hơn cách gộp tin.** Gộp theo vật tư giảm khối lượng hơn một nửa. Mức Nhẹ nên vào bản tin tổng hợp.
2. **MM sinh nhiều tin nhất** (47% điểm bị báo) và nhạy với lỗi nhập liệu. Không dùng làm điều kiện gửi.
3. **MIN ("so với giá min") bắt giá tăng rất nhiều** (868 + 348 + 146 lần tăng) nhưng gần như không bắt giá giảm (80 + 36 + 26). Hợp để hiển thị "đắt hơn đáy bao nhiêu", chưa hợp để làm điều kiện gửi tin hai chiều.
4. **Cần cơ chế phát hiện giá bất thường** (lệch từ 30% so với trung vị) để không báo biến động giả và để trưởng phòng soát lỗi nhập liệu. Đã thành D12.
5. **Ngưỡng 2,5% nằm trong vùng dao động thường gặp** của daily-min giữa các nhà cung cấp. Đây là kết luận của vòng 1; mặc định 2,5% vẫn được giữ (D4) vì cấu hình được theo vật tư và mức Nhẹ chỉ vào bản tin tổng hợp.

### B.7 Vòng 2: bộ ba quy tắc, 7 ngày làm việc, giá bất thường

Cách làm: giống vòng 1 nhưng điểm tham chiếu là 7 ngày làm việc (bỏ thứ Bảy, Chủ Nhật khỏi phần đếm), trên cùng 12 tháng gần nhất. Điểm giá cuối tuần: 63 dòng thứ Bảy và 4 dòng Chủ Nhật (0,7% số dòng, 1,3% số điểm daily-min).

**Khối lượng tin** (số tin mỗi tuần chia cho 52 tuần, tất cả nhà cung cấp, sau chống lặp D5(a)):

| Cấu hình | Theo chuỗi | Gộp theo vật tư | Chỉ Trung bình + Lớn, gộp |
|---|---|---|---|
| 7 ngày lịch (vòng trung gian), theo chữ, **không** chặn bất thường | 17,7 | 7,4 | 2,6 |
| 7 ngày lịch, theo chữ, có chặn bất thường 30% | 17,5 | 7,3 | 2,4 |
| 7 ngày làm việc, theo chữ, có chặn bất thường 30% | 20,3 | 8,0 | 3,0 |
| **7 ngày làm việc, nhất quán hướng, có chặn 30% (đã chốt)** | **19,5** | **7,8** | **2,9** |
| *Phương án A, 14 ngày (vòng 1)* | 16,0 | 7,0 | 2,9 |

Cửa sổ 7 ngày làm việc dài hơn 7 ngày lịch (9 đến 11 ngày lịch) nên có nhiều tin hơn một chút. Với quy tắc đã chốt, tin theo chuỗi nhiều hơn A khoảng 22% (19,5 so với 16,0), chưa thể nói là "gần bằng", nhưng sau gộp theo vật tư thì gần nhau (7,8 so với 7,0).

**Quy tắc theo chữ và quy tắc nhất quán hướng** (12 tháng, trước chống lặp):

| | Điểm bị báo | Nhiều quy tắc cùng báo | Tin có hướng ngược bước nhảy cuối |
|---|---|---|---|
| Theo chữ (mỗi quy tắc độc lập) | 1.986 | 682 | **403 (khoảng 20%, loại 82 điểm có R1 = 0)** |
| Nhất quán hướng (đã chốt) | 1.540 | 641 | 0 |

Quy tắc chính trong bản đã chốt: R1 430 lần, R2 638 lần, R3 472 lần. Cả ba đều đóng góp.

**Giá bất thường** (lệch so với trung vị 7 ngày làm việc, ở mức daily-min, 12 tháng; D12 nay xét ở mức dòng với cửa sổ 30 ngày nên số này là cận dưới):

| Ngưỡng | Số điểm | Số chuỗi | Số vật tư |
|---|---|---|---|
| ≥ 20% | 17 | 14 | 8 |
| **≥ 30% (mặc định)** | **16** | **13** | **7** |
| ≥ 40% | 15 | 12 | 6 |
| ≥ 50% | 14 | 12 | 6 |

Mẫu: Khô cọ 187 → 5,179 (điểm sai thật là 187); Threonine 25,600 → 970 (−96%); Arginin 74,700 → 2,550 (−97%); Lysine 70% 15,628 → 600 (−96%); Methionine 70,000 → 119,700 (+71%); Cám mỳ 6,075 → 8,400 (+38%). Cụm ngày 15/09/2026 có 6 điểm cùng lệch khoảng −96% (Threonine, Arginin, Lysine, mỗi vật tư 2 kỳ). Hai điểm cuối (Methionine, Cám mỳ) có thể là biến động thật, đây là lý do cần nút "Giá đúng".

**Mức dao động theo vật tư** (điểm bị báo của bản đã chốt, tổng 1.540 điểm). P90 lấy theo chỉ số `xs[int(0.9n)]`, với n nhỏ gần P94 hơn (nội suy: Valine 6,2, Fermented Soybean Meal 4,4):

| Vật tư | Số điểm bị báo | Tỷ lệ | Trung vị \|%\| | P90 \|%\| |
|---|---|---|---|---|
| Khô đậu tương | 805 | 52% | 4,3 | 8,0 |
| Ngô hạt | 456 | 30% | 3,3 | 5,2 |
| Methionine | 41 | 3% | 4,9 | 13,7 |
| Tryptophan (CJ) | 27 | 2% | 4,0 | 6,9 |
| Valine | 17 | 1% | 3,8 | 7,9 |
| Fermented Soybean Meal | 17 | 1% | 3,5 | 4,7 |

Khô đậu tương và Ngô hạt chiếm 82% số điểm bị báo (85,6% số dòng 12 tháng, 73,5% số điểm daily-min). Đây là lý do cần ngưỡng theo vật tư (D4).

### B.8 Đo bổ sung từ rà soát độc lập (tải thật, giá bất thường, vòng đời)

Các phép đo dưới đây do agent rà soát tự viết script chạy trên DB dev (chỉ `SELECT`), kỳ 12 tháng tới 2026-10-02. Độ trễ đo theo **ngày lịch**; cần đo lại theo ngày làm việc ở dry-run replay. Script chưa nằm trong repo.

**Dữ liệu nhập thật so với import.**

| Chỉ tiêu | Số đo |
|---|---|
| Dòng nhập thật (`is_backfilled=false`), 12 tháng | 565 / 9.798 = 5,8% (toàn kỳ 565 / 20.893 = 2,7%) |
| Version không nhập lùi, 12 tháng | 163 / 1.770 = 9,2% |
| Dòng import (tài khoản seed admin, tạo ngày 19/08/2026) | 8.082 = 82,5% |
| Giai đoạn có nhập thật | 20/08 đến 02/10/2026 (44 ngày, 6,29 tuần), 7 người nhập |
| Dòng nhập thật theo tuần ISO 34 đến 40 | 89, 175, 20, 96, 49, 45, 91 |
| Nhập thật: chênh `confirmed_at` so với `received_date` | 562 dòng chênh 0 ngày, 3 dòng chênh 1 ngày |
| Nhân viên nhập lùi: chênh | 1.151 dòng, trung vị 13 ngày, P75 76, P90 179, tối đa 316 (trễ ≤ 1 ngày lịch: 220, ≤ 3 ngày lịch: 373, ≤ 7 ngày lịch: 522; đã thay bằng đo theo ngày làm việc ở kế hoạch 1B, Phụ lục C) |

**Tải tin theo nguồn kích hoạt** (cùng giai đoạn 20/08 đến 02/10, đơn vị tin mỗi tuần hoạt động; "TB+L" là Trung bình và Lớn, gộp theo vật tư):

| Kịch bản | Theo chuỗi | Gộp | TB+L gộp |
|---|---|---|---|
| S0: mọi dòng kích hoạt (cách backtest B.1 đến B.7) | 31,3 | 19,2 | 8,1 |
| S1: chỉ ngày có dòng nhập thật (D6 cũ) | 17,2 | 10,3 | 3,7 |
| S2: loại hoàn toàn dòng nhập lùi | 8,7 | 5,3 | 2,2 |

Chia cho 52 tuần thay vì tuần hoạt động thì S1 chỉ ra 2,08 / 1,25 / 0,44, thấp giả tạo vì mọi tin rơi vào 6,3 tuần cuối.

**Độ trễ cho phép của dòng do nhân viên nhập** (tin mỗi tuần hoạt động):

| Độ trễ cho phép | Theo chuỗi | Gộp | TB+L gộp |
|---|---|---|---|
| ≤ 0 ngày | 17,0 | 10,3 | 3,7 |
| ≤ 1 ngày | 24,0 | 14,8 | 5,9 |
| **≤ 3 ngày (D6 mới, xấp xỉ)** | **28,2** | **17,7** | **7,3** |
| ≤ 7 ngày | 31,5 | 19,6 | 8,3 |
| mọi dòng nhân viên | 45,8 | 27,4 | 11,5 |

Số tin gộp theo tháng tăng dần: 22 (10/2025), 23, 24, 23, 21, 32, 29, 27, 37, 35, 55 (08/2026), 77 (09/2026, khoảng 17,9 tin mỗi tuần). Trung bình 8 tuần cuối: 16,6 tin gộp và 7,0 tin TB+L mỗi tuần. Tuần cao nhất: 35 tin gộp, 15 tin TB+L; ngày cao nhất: 13 tin gộp. Với nhân viên (D8, theo S1): mỗi tin có khoảng 2 người nhận, mỗi nhân viên khoảng 2,7 đến 2,9 tin mỗi tuần, người nhiều nhất khoảng 7,6 tin mỗi tuần.

**Điểm đầu chuỗi và khoảng trống.** 509/4.532 điểm daily-min (11,2%) không có điểm trước trong cửa sổ: 277 là điểm đầu chuỗi, 232 sau khoảng trống hơn 7 ngày làm việc (trung vị 14 ngày, P90 41, tối đa 240). Trong 232 điểm sau khoảng trống, 127 (55%) lệch từ 2,5% so với điểm cũ gần nhất (44 Nhẹ, 51 Trung bình, 32 Lớn), bị bỏ qua im lặng. 69/303 chuỗi chỉ có 1 điểm trong 12 tháng, 50% chuỗi có từ 3 điểm trở xuống.

**Giá bất thường.**
- Chỉ 1 dòng trong 12 tháng bị daily-min "ẩn" (lệch từ +30% so với trung vị tham chiếu nhưng không phải min của ngày): Lysine 70% kỳ 09/2026, 23.500 (+49%), đã nhập lùi. Lỗi nhập **thấp** luôn thành min của ngày nên luôn lộ ra (16/16). Chênh lệch giữa các nhà cung cấp trong cùng một ngày (điểm có từ 2 dòng): trung vị (max−min)/min 1,68%, P90 4,5%, P99 10,8%.
- 12/16 điểm bất thường chỉ dựa trên đúng 1 điểm tham chiếu. Tham chiếu bị nhiễm độc: Tryptophan (CJ) 3.565 (15/09) và Khô cọ 9.505 (đã sửa từ 93.245) được nhận làm tham chiếu; Methionine +71% (17/03) là bước nhảy thật và bền (60.200 → 70.000 → 119.700 → 124.700 → 144.700).
- Trong giai đoạn nhập thật: 10 điểm bất thường trong 6,3 tuần (khoảng 1,6 điểm mỗi tuần), cộng 5 phiên bản sửa giá từ 30%. 9/16 điểm có tỷ lệ trung vị so với giá mới từ 25,8 đến 29,3, gần tỷ giá USD (khoảng 26.100 đến 26.290) chia 1.000.
- 41 version `superseded` trong 6 tuần (khoảng 5,9 mỗi tuần): 12 có đổi giá, 8 đổi từ 2,5%, 5 đổi từ 30% (ví dụ Vitamin A 673 → 473.780, Whey permeat 850 → 22.635, Khô cọ 93.245 → 9.505). Vì vậy 16 điểm bất thường là cận dưới.

**Nhiều lần chốt trong ngày và đổi nhà cung cấp.** 13,9% điểm nhập thật (67/483) có từ 2 version trong ngày, và 40/67 điểm daily-min đổi sau lần chốt đầu. Phát lại theo từng lần chốt: 114 tin sau chống lặp so với 108 (+5,6%); 10/66 ngày-vật tư (15%) có tin ở từ 2 thời điểm khác nhau; 1 ngày-chuỗi đổi hướng trong ngày. 70,6% điểm bị báo có nhà cung cấp rẻ nhất khác với điểm trước.

**Giờ chốt.** Xác nhận thật trải đều từ 08 giờ đến 21 giờ (cao điểm 10 giờ và 13 giờ đến 15 giờ). 6% version chốt vào thứ Bảy hoặc Chủ Nhật, nên cron không giới hạn trong giờ hành chính.

**Hàm ý cho thiết kế.** D6 mới (QĐ-16), đơn vị tin (QĐ-17), vòng đời giá bất thường (QĐ-18), watermark chồng lấp (4.1), và dry-run replay cho 1B (Mục 7).
