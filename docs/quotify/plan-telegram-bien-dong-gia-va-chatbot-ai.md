# Kế hoạch: Thông báo biến động giá qua Telegram và Chatbot AI

> **Trạng thái:** BẢN NHÁP ĐỂ THẢO LUẬN. Chưa có dòng code nào được viết.
> **Cập nhật 2026-10-03:** đã chốt các quyết định về điều kiện gửi tin, giá bất thường, ngưỡng theo mặt hàng, phạm vi bot, nhà cung cấp LLM và ngân sách (xem Mục 0.1 và Mục 9).
> **Ngày soạn:** 2026-10-03.
> **Phạm vi:** Bước 1 (thông báo biến động giá qua Telegram) và Bước 2 (nâng cấp thành chatbot AI).
> **Nguyên tắc nền:** Production đã chạy. Mọi thay đổi chỉ được **additive** (thêm bảng, thêm cột nullable, thêm file). Không sửa migration cũ, không đổi hành vi API cũ.

Nguồn: 4 agent đọc toàn bộ tài liệu `.md`, backend (model, service, API, worker) và frontend. Mục nào chưa kiểm chứng được sẽ ghi **[CHƯA XÁC MINH]**.

---

## 0. Tóm tắt điều hành

1. Hiện **chưa có gì** về Telegram, LLM, OCR hay PDF trong repo (code, tài liệu, cấu hình). Đây là tính năng hoàn toàn mới.
2. Hạ tầng tái dùng được: worker **arq + Redis** (đã có cron), pattern adapter `httpx` (Vietcombank), `EmailService` (mẫu "thông báo không làm hỏng nghiệp vụ"), `QuotifyDashboardService` (min/max/avg), cơ chế audit, nginx đã proxy `/api/`.
3. Điểm mới cần thêm: bảng liên kết Telegram, bảng sự kiện/gửi thông báo, bảng cấu hình ngưỡng, engine tính biến động, bộ vẽ biểu đồ ảnh phía server, webhook nhận tin từ Telegram.
4. **Bước 1 đã cần nhận tin từ Telegram.** Để liên kết tài khoản an toàn bằng mã `/start <token>`, bot phải nhận được update. Vì vậy webhook (hoặc long-polling) phải có ngay ở Bước 1, không chờ Bước 2.
5. **Tài khoản ChatGPT Plus / Gemini Advanced / Claude Pro trả phí theo tháng KHÔNG cấp quyền gọi API.** Chatbot cần API key riêng (tính phí theo token). Cần chốt điều này trước khi bắt đầu Bước 2.
6. Chatbot hỏi đáp nên dùng **tool-calling với các hàm cố định** (gọi lại service có sẵn), không cho AI tự sinh SQL. Cách này đáp ứng "chỉ READ" và "cấm SQL nguy hiểm" bằng thiết kế, không bằng bộ lọc.
7. Đã chốt các quyết định ở Mục 0.1, gồm cả D5 đến D10 (chống spam, nguồn dữ liệu kích hoạt, người nhận tin). Chỉ còn một số điểm mở nhỏ ở Mục 9.2.

---

## 0.1 Quyết định đã chốt

| # | Ngày | Quyết định | Chi tiết |
|---|---|---|---|
| QĐ-1 | 2026-10-03 | Điều kiện gửi tin = **bộ ba quy tắc**: so với báo giá cập nhật gần nhất, so với giá thấp nhất và so với giá cao nhất của 7 ngày làm việc liền trước. Chỉ quan tâm giá, **không phân biệt nhà cung cấp** | D2 |
| QĐ-2 | 2026-10-03 | Cửa sổ tham chiếu là **7 ngày làm việc**, loại trừ thứ Bảy và Chủ Nhật | D3 |
| QĐ-3 | 2026-10-03 | Có loại thông báo riêng cho **giá bất thường** (nghi nhập sai) | D12 |
| QĐ-4 | 2026-10-03 | Ba khoảng % (Nhẹ, Trung bình, Lớn) **cấu hình được theo từng mặt hàng**. Mặc định 2,5 / 5 / 10%. **Admin và trưởng phòng** được sửa | D4 |
| QĐ-5 | 2026-10-03 | LLM: **dev dùng API key Google AI Studio (Gemini), gói miễn phí**. Nhà cung cấp production chưa chọn, thiết kế adapter đa nhà cung cấp | D11, 5.5 |
| QĐ-6 | 2026-10-03 | Chính sách dữ liệu: **cho phép** gửi nội dung báo giá, ảnh và PDF sang hệ thống bên thứ ba | D11 |
| QĐ-7 | 2026-10-03 | Phạm vi bot: **chỉ chat riêng**, **chỉ tiếng Việt có dấu**, **không có khung giờ yên lặng** | 4.4, 4.8, 5.1 |
| QĐ-8 | 2026-10-03 | Tin nhắn **hiển thị thêm giá CNF (USD/MT)** cho dòng nhập USD | 4.2 |
| QĐ-9 | 2026-10-03 | Chatbot nhập liệu **luôn tạo nháp rồi mới chốt**. **Ghi nhận nguồn nhập qua Telegram**: chỉ thêm **icon bot ở cột "Trạng thái"** của danh sách báo giá, kèm **ô tick lọc** theo nguồn Telegram | 4.5, 4.9, 5.3 |
| QĐ-10 | 2026-10-03 | **Admin hệ thống quản lý chi phí LLM**, trần ngân sách khoảng **2.000.000 đ mỗi tháng** | 5.6 |
| QĐ-11 | 2026-10-03 | Chưa loại ngày lễ và Tết khỏi ngày làm việc | D3 |
| QĐ-12 | 2026-10-03 | Giá bất thường: chỉ chấp nhận bằng nút **Giá đúng** (không tự động). Người nhận: **trưởng phòng và người nhập phiếu**. Xác nhận hướng tin theo bước nhảy cuối (D2) | D2, D12 |
| QĐ-13 | 2026-10-03 | **Không tính biến động % trên CNF**: chuỗi USD/MT cũng chỉ tính % trên VNĐ/KG. Cảnh báo ngân sách LLM gửi **qua email admin** | D1, 5.6 |
| QĐ-14 | 2026-10-03 | Đồng ý toàn bộ đề xuất **D5 đến D10**: chống spam (chỉ gửi khi chiều hoặc mức đổi, gộp tin theo vật tư, mức Nhẹ vào bản tin 08:00, trần số tin mỗi lần quét), bỏ qua phiếu nhập lùi và import, trưởng phòng nhận mọi tin, nhân viên nhận tin của vật tư mình đã nhập trong 90 ngày, admin chỉ nhận khi bật tùy chọn, cờ bật/tắt và mức tối thiểu cho từng người | D5 đến D10 |
| QĐ-15 | 2026-10-03 | Chuỗi so sánh là **(vật tư, kỳ giao hàng)**, **không gộp nhiều kỳ giao hàng** vào một chuỗi. Giá so sánh là `price_converted_vnd_per_kg` của version `confirmed`, phiếu chưa hủy | D1 |

Điều chỉnh hướng tin theo hướng của bước nhảy cuối (xem D2) đã được xác nhận trong QĐ-12.

---

## 1. Hiểu biết nền tảng về dự án (đã xác minh từ code)

### 1.1 Stack và hạ tầng

| Thành phần | Chi tiết |
|---|---|
| Backend | Python 3.12, FastAPI 0.136, SQLAlchemy 2 async + asyncpg, Alembic, Pydantic v2, `uv` |
| Worker | arq 0.26 + Redis 7. Chỉ có 1 cron (`poll_and_run_scheduled_backups`, mỗi phút). Chạy `arq app.worker.WorkerSettings` |
| DB | Postgres 16. Một role duy nhất (`postgres`). Alembic head hiện tại: `20260824_1000` |
| Frontend | Vue 3.5 + TS, Pinia, PrimeVue 4, Chart.js, vee-validate + zod, SCSS tập trung (cấm `<style>` trong `.vue`) |
| Deploy | VPS, build qua SSH, **không CI/CD**. Migrate bằng `docker compose -f docker-compose.prod.yml run --rm backend uv run alembic upgrade head` **trước** `up -d`. Sau `up -d` phải `restart reverse-proxy` |
| Domain | `quotify.honghafeed.com.vn`, HTTPS 443 (certbot). Nginx route `/api/` → backend nên webhook đi qua được mà không sửa nginx |
| Thư viện thiếu | Không có SDK Telegram, SDK LLM, matplotlib/Pillow, thư viện đọc PDF |

Phân tầng backend: `api/v1/*` (route, kiểm quyền, ownership, audit, **commit**) → `services/*` (logic, chỉ `flush`, **không kiểm quyền**) → `models/*`. Thư mục `repositories/` rỗng.

### 1.2 Mô hình dữ liệu giá

- Giá chỉ nằm ở `quote_lines`: `price_original` + `currency` (VND/USD) + `unit` (KG/MT), và **`price_converted_vnd_per_kg`** (giá chuẩn hóa VNĐ/KG, đóng băng lúc confirm).
- Chỉ hỗ trợ 2 cặp: `VND/KG` và `USD/MT`. Công thức USD/MT: `(giá/1000) × (1 + thuế%) × tỷ giá + chi phí làm hàng`.
- Chuỗi tự nhiên của một mặt hàng: **(`material_id`, `delivery_month`)**. `delivery_month` luôn là ngày 01 của tháng trong dữ liệu thật, nhưng backend **không ép** (bẫy R1 ở Mục 9).
- Phiên bản: `draft → confirmed → superseded`. Mỗi phiếu tối đa 1 draft. Phân tích hiện có chỉ dùng `status='confirmed'` AND `confirmed_at IS NOT NULL` AND `quotes.cancelled_at IS NULL`.
- Ba mốc thời gian khác nhau: `received_date` (ngày nhận, Date, ngày nghiệp vụ), `confirmed_at` (lúc dữ liệu có hiệu lực), `delivery_month` (kỳ giao hàng).
- "Người nhập phiếu" = `quotes.created_by_id` (bất biến, nguồn KPI). `quote_versions.created_by_id` là người tạo từng version (trưởng phòng tạo bản điều chỉnh thì là trưởng phòng). Hai nơi trong code dùng hai định nghĩa khác nhau.
- **Không có bảng gán nhân viên ↔ vật tư phụ trách.** "Mặt hàng mình nhập" phải suy ra từ `quotes.created_by_id × quote_lines.material_id`.
- Dashboard loại tài khoản seed admin (`AUTH_SEED_ADMIN_EMAIL`, dùng cho import) khỏi thống kê theo người.

Quy mô (từ bản dump 2026-10-03, ước lượng): 3.067 phiếu, 3.086 version, 19.969 dòng giá, 119 vật tư (36 có báo giá), 311 NCC, 12 user, 261 chuỗi (vật tư, kỳ giao hàng), trung vị 3 điểm giá mỗi chuỗi.

### 1.3 Role và quyền

- Seed chỉ có `admin` (bypass mọi quyền theo tên role) và `user` (21 quyền).
- **"Trưởng phòng" trên dữ liệu thật là role `manager`** (không phải role hệ thống, tạo tay ngày 2026-08-25): quyền của `user` + `quotes.correct_user_quotes`. Dump có admin 1, user 8, manager 3.
- Code **không** hard-code tên `manager`, chỉ dùng permission `quotes.correct_user_quotes`. Role không phải hệ thống có thể bị đổi tên hoặc xóa, nên đừng gắn logic thông báo vào tên role.
- `seed_auth_rbac.py` chỉ cập nhật role `admin` và `user`. Role `manager` **không** được seed: quyền mới phải gán bằng migration dữ liệu (tiền lệ: `20260729_0810_restrict_quotify_settings_user_role.py`).
- `test_permission_inventory.py` bắt buộc mọi permission dùng trong code phải có trong `BASE_PERMISSION_CODES`.
- Auth: access JWT 30 phút (bộ nhớ) + refresh cookie httpOnly. Bot Telegram không có JWT, nên phải gọi service trực tiếp trong tiến trình và **tự kiểm quyền** (xem R3).

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

**Việc cần làm trước khi code:** ghi vào "Nhật ký thay đổi" của kế hoạch, cập nhật `CONTEXT.md` (thuật ngữ mới: *Liên kết Telegram*, *Biến động giá*, *Ngưỡng cảnh báo*, *Mức biến động*), và nêu rõ chatbot **không đưa khuyến nghị mua/bán**.

---

## 3. Quyết định (đã chốt và đề xuất)

### Nhóm A: Định nghĩa biến động giá

**D1. Giá nào để so sánh? (ĐÃ CHỐT, QĐ-15)**
- Quyết định: `price_converted_vnd_per_kg`, chuỗi **(vật tư, kỳ giao hàng)**, chỉ version `confirmed`, phiếu chưa hủy.
- **Đã chốt (QĐ-1):** không phân biệt nhà cung cấp. Điểm giá của một ngày là giá thấp nhất trong ngày giữa mọi NCC.
- **Đã chốt (QĐ-13):** chuỗi USD/MT cũng chỉ tính % trên VNĐ/KG, không thêm quy tắc tính % trên CNF.
- Lưu ý: dòng USD/MT bị ảnh hưởng bởi tỷ giá. Cùng giá USD nhưng tỷ giá đổi vẫn thành "biến động". Có thể chấp nhận (vì giá VNĐ/KG mới là thứ phòng Thu Mua mua thật), nhưng tin nhắn nên ghi rõ "giá quy đổi".
- **Không gộp nhiều kỳ giao hàng vào một chuỗi** vì giá kỳ xa khác kỳ gần (đã chốt, QĐ-15).

**D2. Điều kiện biến động (ĐÃ CHỐT, QĐ-1): bộ ba quy tắc so với 7 ngày làm việc liền trước.**

Định nghĩa:
- **Điểm giá** của một ngày là giá thấp nhất trong ngày (daily-min) của chuỗi (vật tư, kỳ giao hàng), giữa mọi NCC.
- **Điểm mới** là điểm của ngày đang xét. **Các điểm trước** là các điểm nằm trong cửa sổ 7 ngày làm việc (D3), không gồm điểm mới.

| Quy tắc | So giá mới với | Áp dụng khi |
|---|---|---|
| **R1** | Điểm trước **gần nhất** (báo giá cập nhật gần nhất) | luôn luôn |
| **R2** | Giá **thấp nhất** của các điểm trước | giá mới **tăng** so với R1 |
| **R3** | Giá **cao nhất** của các điểm trước | giá mới **giảm** so với R1 |

Cách kết hợp:
1. **Hướng** của tin theo hướng của R1 (bước nhảy cuối). Giá mới bằng đúng điểm trước thì không có tin.
2. **Mức** của tin là mức cao nhất trong các quy tắc áp dụng, tính theo ngưỡng của mặt hàng (D4). **Lý do chính** là quy tắc cho mức cao nhất (hòa thì lấy quy tắc có |%| lớn hơn). Các quy tắc còn lại hiển thị như thông tin phụ.
3. Cần **ít nhất 1 điểm trước** trong cửa sổ, nếu không thì không gửi.
4. Điểm bị gắn "giá bất thường" (D12) không được dùng làm điểm tham chiếu và không sinh tin biến động.

**Vì sao điều chỉnh so với cách hiểu theo chữ.** Nếu mỗi quy tắc chạy độc lập rồi lấy mức cao nhất, backtest cho thấy **khoảng 20% tin (403/1.986) có nhãn tăng/giảm ngược với bước nhảy cuối**. Ví dụ giá vừa giảm so với lần trước nhưng vẫn cao hơn đáy tuần thì tin sẽ ghi "TĂNG". Quy tắc nhất quán hướng loại bỏ mâu thuẫn này, khối lượng tin gần như không đổi (19,5 so với 20,3 tin/tuần theo chuỗi). **Đã được xác nhận (QĐ-12).**

Ví dụ (giá thấp nhất mỗi ngày, VNĐ/KG, điểm mới là thứ Sáu 02/10/2026, cửa sổ là 23/09 đến 01/10):

| | Các điểm trước | Điểm mới | R1 | R2 / R3 | Kết quả |
|---|---|---|---|---|---|
| **1. Tăng** | 23/09: 7,900 · 25/09: **7,720** · 30/09: 7,800 | 8,150 | +4,49% (so với 7,800) | R2: **+5,57%** (so với đáy 7,720) | 🔺🟠 **Tăng Trung bình**, lý do chính R2 |
| **2. Giảm** | 24/09: **10,400** · 28/09: 10,000 · 30/09: 9,800 | 9,300 | −5,10% (so với 9,800) | R3: **−10,58%** (so với đỉnh 10,400) | 🔻🔴 **Giảm Lớn**, lý do chính R3 |
| **3. Hướng ngược** | 25/09: 9,000 · 30/09: 10,000 | 9,600 | −4,00% (so với 10,000) | R2 **bỏ qua** vì R1 là giảm (R2 sẽ là +6,67%) | 🔻🟡 **Giảm Nhẹ**, lý do chính R1 |

Ví dụ 3 cho thấy lý do cần quy tắc nhất quán hướng. Giá đã giảm so với lần trước nên tin phải là "giảm", dù giá vẫn cao hơn đáy tuần.

**Các phương án đã so sánh** (Phụ lục B): A (so với điểm cũ nhất 14 ngày), B (điểm liền trước), C (trung bình), MIN, MM. Bộ ba quy tắc cho khối lượng tin gần bằng A, bắt được cú đảo chiều mà A bỏ sót. A vẫn có thể giữ làm dòng thông tin phụ "xu hướng 14 ngày" (đề xuất, chưa chốt).

**D3. Cửa sổ tham chiếu (ĐÃ CHỐT, QĐ-2): 7 ngày làm việc.**
- Cửa sổ là 7 ngày làm việc (thứ Hai đến thứ Sáu) liền trước ngày của điểm mới, theo `received_date`, múi giờ `Asia/Ho_Chi_Minh`. **Thứ Bảy và Chủ Nhật không được đếm.**
- Cách tính: lùi từng ngày từ ngày liền trước, bỏ qua thứ Bảy và Chủ Nhật, cho đến khi đủ 7 ngày làm việc. Cửa sổ là khoảng từ ngày thứ 7 đó đến ngày liền trước, tức **9 đến 11 ngày lịch**. Ví dụ điểm mới thứ Sáu 02/10/2026 thì cửa sổ là 23/09 đến 01/10.
- Điểm giá nhận vào cuối tuần (0,6% dữ liệu 12 tháng gần nhất) vẫn được dùng làm điểm tham chiếu nếu nằm trong khoảng.
- **Ngày lễ và Tết chưa được loại trừ ở v1** (đã chốt, QĐ-11). Kỳ nghỉ dài làm cửa sổ thưa điểm, nhưng không sinh tin sai vì quy tắc cần có ít nhất 1 điểm trước.
- Mốc **kích hoạt** vẫn là `confirmed_at` (lúc version có hiệu lực).
- Biểu đồ gửi kèm vẫn hiển thị 14 ngày lịch để người mua thấy bức tranh rộng, và tô sáng vùng tham chiếu 7 ngày làm việc.

**D4. Biên ngưỡng (ĐÃ CHỐT, QĐ-4): mặc định 2,5 / 5 / 10%, cấu hình được theo từng mặt hàng.**
- Mặc định toàn hệ thống, tính theo `|%|` bằng `Decimal`, không làm tròn trước khi so:
  - Nhẹ: `2,5 ≤ x < 5`
  - Trung bình: `5 ≤ x ≤ 10`
  - Lớn: `x > 10`
  - Dưới 2,5%: không gửi.
- **Ghi đè theo mặt hàng:**
  - Theo **vật tư** (không theo kỳ giao hàng).
  - Ghi đè đủ **cả ba số** hoặc không ghi đè (không ghi đè từng phần). Điều kiện `0 < Nhẹ < Trung bình < Lớn`.
  - Mặt hàng không có ghi đè dùng mặc định.
  - Thay đổi có hiệu lực từ lần quét kế tiếp, **không báo lại** dữ liệu cũ.
  - Mọi thay đổi ghi audit (`changes[]`, old/new).
  - Ai được sửa: **admin và trưởng phòng** (permission `price_alerts.manage`, đã chốt).
- **Vì sao cần ghi đè** (Phụ lục B.7): mức dao động khác nhau theo mặt hàng. Trung vị |%| của các điểm bị báo: Khô đậu tương 4,3% (P90 8,0%), Ngô hạt 3,3% (P90 5,2%), Methionine 4,9% (P90 13,7%). Riêng Khô đậu tương chiếm khoảng 52% số điểm bị báo, nên là ứng viên đầu tiên cho ngưỡng cao hơn.

**D5. Chống spam (ĐÃ CHỐT, QĐ-14).** Backtest với quy tắc đã chốt (Phụ lục B.7, 12 tháng gần nhất) cho thấy khối lượng tin là vấn đề thật: daily-min giữa các NCC dao động nhiều. Nếu gửi theo từng chuỗi (vật tư, kỳ giao) thì trưởng phòng nhận khoảng **19,5 tin/tuần**.
- Quyết định: (a) chỉ gửi khi **(chiều, mức) khác lần đã gửi gần nhất của chuỗi đó trong 14 ngày**; (b) **gộp theo vật tư**: một tin cho mỗi vật tư mỗi ngày, liệt kê các kỳ giao hàng vượt ngưỡng (còn khoảng **7,8 tin/tuần**); (c) mức Nhẹ gom vào **bản tin tổng hợp 08:00 giờ VN**, mức Trung bình và Lớn gửi ngay (khoảng **2,9 tin/tuần** cho trưởng phòng); (d) trần số tin mỗi lần quét (flood guard); (e) cân nhắc nâng ngưỡng Nhẹ của các mặt hàng dao động mạnh bằng cấu hình theo mặt hàng (D4).

**D6. Nguồn dữ liệu nào kích hoạt thông báo? (ĐÃ CHỐT, QĐ-14)**
- Quyết định v1: **bỏ qua version `is_backfilled=true`** và bỏ qua phiếu import. Lưu ý `is_backfilled` bị ép `true` mỗi khi `received_date` < hôm nay, nên phiếu nhập muộn hợp lệ cũng bị bỏ qua. Đây là đánh đổi chấp nhận được để tránh bão tin khi import hàng nghìn dòng.
- Khi triển khai lần đầu, đặt `watermark = thời điểm triển khai` để dữ liệu cũ không sinh thông báo.

**D12. Giá bất thường (ĐÃ CHỐT, QĐ-3): loại thông báo riêng, nghi nhập sai.**
- **Điều kiện:** giá mới lệch từ **30%** trở lên so với **trung vị** các điểm trước trong cửa sổ 7 ngày làm việc. Ngưỡng 30% là mặc định toàn hệ thống và cũng ghi đè được theo mặt hàng.
- **Hành động:**
  - Gửi thông báo "⚠️ GIÁ BẤT THƯỜNG" cho **trưởng phòng và người nhập phiếu** (đã chốt, QĐ-12). Admin không nhận mặc định.
  - Giá đó **bị loại khỏi tham chiếu** và không sinh tin biến động, cho đến khi được xem xét.
  - Tin có hai nút trong Telegram: **✅ Giá đúng** (chấp nhận, tính lại biến động) và **❌ Nhập sai** (giữ loại, người nhập sửa phiếu trên web).
- **Vì sao cần** (Phụ lục B.7): trong 12 tháng có khoảng 16 điểm bất thường (0,3 điểm mỗi tuần), ở 13 chuỗi thuộc 7 vật tư. Phần lớn lệch rất lớn (khoảng −96%), giống lỗi nhập sai đơn vị hoặc tỷ giá. Có cả một cụm ngày 15/09/2026 gồm Threonine, Arginin và Lysine cùng lệch −96% trong một ngày, gợi ý một lỗi hệ thống. Nếu không chặn, các điểm này làm lệch cả R1 lẫn R3 (ví dụ Khô cọ báo −45,6% vì một điểm 9,505 nhập sai).
- **Ngưỡng ít nhạy:** thử 20%, 30%, 40%, 50% cho số điểm lần lượt 17, 16, 15, 14. Vì vậy 30% là mặc định an toàn.
- **Giới hạn đã biết:**
  - Điểm **đầu tiên** của chuỗi chưa có tham chiếu nên không thể bị gắn cờ. Nếu chính điểm đầu sai thì điểm kế tiếp (đúng) sẽ bị gắn cờ. Ví dụ Khô cọ có giá trước là 187 rồi mới 5,179. Tin ghi cả hai giá để người đọc tự nhận ra điểm nào sai.
  - Biến động **thật** nhưng lớn cũng bị gắn cờ (ví dụ Cám mỳ 6,075 → 8,400, +38%). Nút "Giá đúng" xử lý trường hợp này. **Không tự động chấp nhận** khi điểm kế tiếp xác nhận mặt bằng mới (đã chốt, QĐ-12).
  - Phép thử đo ở mức daily-min. Kiểm tra ở mức từng dòng báo giá có thể tìm ra thêm lỗi, cần đo lại ở giai đoạn dry-run (1B).
- Gửi ngay (không gom bản tin), vì hiếm.

### Nhóm B: Người nhận

**D7. "Trưởng phòng" (ĐÃ CHỐT, QĐ-14).** thêm permission mới `price_alerts.receive_all`, cấp cho role `manager` bằng migration dữ liệu. Không so tên role.

**D8. "Nhân viên nhận mặt hàng mình đã nhập báo giá" (ĐÃ CHỐT, QĐ-14).** user nhận cảnh báo của vật tư `M` nếu user là `quotes.created_by_id` của ít nhất một phiếu có dòng vật tư `M` trong **90 ngày gần nhất** (cấu hình được). Phiếu import thuộc tài khoản seed admin nên không tính.

**D9. Admin có nhận tất cả không? (ĐÃ CHỐT, QĐ-14)** Admin bypass mọi quyền, nên cần quy ước: admin chỉ nhận nếu có liên kết Telegram **và** bật tùy chọn (mặc định tắt). Tài khoản seed admin bị loại.

**D10. Người dùng có tự tắt/bật theo mức không? (ĐÃ CHỐT, QĐ-14)** có 1 cờ bật/tắt chung và 1 cờ "mức tối thiểu" (Nhẹ/Trung bình/Lớn) cho mỗi người. Mặc định: trưởng phòng từ mức Trung bình, nhân viên từ mức Nhẹ (gom bản tin).

### Nhóm C: Chatbot AI

**D11. Nhà cung cấp LLM và chính sách dữ liệu (QĐ-5, QĐ-6).**
- **Dev:** dùng API key của **Google AI Studio** (Gemini).
- **Production:** chưa chọn nhà cung cấp. Thiết kế `LLMClient` đa nhà cung cấp (OpenAI, Gemini, Anthropic) để đổi bằng cấu hình, chọn sau khi đo chi phí và chất lượng đọc ảnh/PDF tiếng Việt trên dev. Gói thuê bao tiêu dùng (ChatGPT Plus, Gemini Advanced, Claude Pro) không có API, chạy thật cần API key tính phí theo token (ngân sách ở 5.6).
- **Chính sách dữ liệu (đã chốt):** cho phép gửi nội dung báo giá, ảnh và PDF sang hệ thống bên thứ ba.
- **Dev dùng gói miễn phí (đã chốt, QĐ-5).** Theo hiểu biết của tôi, gói miễn phí có thể cho phép Google dùng nội dung gửi lên để cải thiện sản phẩm, và có hạn mức tốc độ và số lượt thấp **[CẦN XÁC MINH điều khoản và hạn mức hiện hành]**. DB dev chứa dữ liệu thật. Việc gửi dữ liệu sang bên thứ ba đã được phép (QĐ-6), nhưng khi test nên ưu tiên dữ liệu thử hoặc ảnh/PDF mẫu để không phơi bày dữ liệu thật không cần thiết. Không dùng gói miễn phí cho production. Hạn mức thấp cũng làm bài đo chi phí mỗi lượt và thử tải chưa phản ánh production.
- Dù đã được phép, vẫn chỉ gửi nội dung tối thiểu cần để trả lời. Không gửi email, mật khẩu, mã người dùng hay dữ liệu cá nhân không liên quan sang LLM.

---

## 4. Bước 1: Thông báo biến động giá qua Telegram

### 4.1 Luồng tổng thể

```
Nhân viên confirm báo giá ──► quote_versions (confirmed_at = now)
                                         │
              cron arq mỗi 1-2 phút ◄────┘   (quét confirmed_at > watermark)
                        │
                        ▼
       PriceAlertService (thuần, Decimal, TDD)
         · dựng daily-min của chuỗi (vật tư, kỳ giao hàng), cửa sổ 7 ngày làm việc (D3)
         · loại điểm bất thường (D12), rồi áp bộ ba quy tắc R1/R2/R3 (D2)
         · phân mức theo ngưỡng của mặt hàng (D4), xác định chiều
         · kiểm tra chống trùng/leo thang
                        │
                        ▼
       price_alert_events (1 sự kiện/chuỗi/lần) ──► giải quyết người nhận
                        │                              (manager: tất cả; user: theo D8)
                        ▼
       price_alert_deliveries (1 dòng/người nhận, UNIQUE chống gửi trùng)
                        │
        vẽ PNG (matplotlib) + soạn caption HTML ──► Telegram sendPhoto
```

Lý do chọn **cron quét + watermark** thay vì móc vào route confirm:
- Không phải sửa `quotes.py` (an toàn cho code cũ đang chạy).
- Bắt được mọi đường confirm: API `confirm_version`, `delete_confirmed_line` (tự tạo và confirm bản điều chỉnh), `create_quote(confirm_immediately=True)` của import.
- Mất kết nối Redis hay worker tạm dừng không làm mất sự kiện, vì watermark nằm trong DB.
- Đổi lại: trễ tối đa 1-2 phút. Chấp nhận được với thông báo giá.

Hai trường hợp phải loại: version `superseded` (khi tính baseline) và `delete_confirmed_line` (tạo version confirmed mới nhưng **không** phải biến động giá, chỉ bỏ một dòng). Bản điều chỉnh sửa sai giá thì **có** thể là biến động thật, cần so với giá bản cũ để không báo kép (R4).

### 4.2 Giao diện tin nhắn

Telegram không có chữ màu. Dùng emoji kép (chiều + mức) và ảnh biểu đồ có dải màu theo mức.

| Mức | Tăng | Giảm | Màu dải trên biểu đồ |
|---|---|---|---|
| Nhẹ (mặc định 2,5-5%) | 🔺🟡 **TĂNG NHẸ** | 🔻🟡 **GIẢM NHẸ** | Vàng |
| Trung bình (mặc định 5-10%) | 🔺🟠 **TĂNG TRUNG BÌNH** | 🔻🟠 **GIẢM TRUNG BÌNH** | Cam |
| Lớn (mặc định >10%) | 🔺🔴 **TĂNG LỚN** | 🔻🔴 **GIẢM LỚN** | Đỏ |

Quy ước màu theo **mức độ** (không theo tốt/xấu), vì với bộ phận Thu Mua giá giảm là tin tốt còn giá tăng là tin xấu. Phân biệt chiều bằng mũi tên và chữ. Giọng thông báo trung tính.

Ví dụ tin biến động (HTML parse mode, ảnh biểu đồ là ảnh chính, đây là caption). Dùng ví dụ 1 ở D2:

```
🔺🟠 TĂNG TRUNG BÌNH · Ngô hạt
Kỳ giao hàng: 12/2026

Giá thấp nhất hôm nay: 8,150.00 VNĐ/KG (02/10/2026)

Lý do chính: so với giá thấp nhất 7 ngày làm việc
  +5.57%   (7,720.00 · 25/09/2026)
So sánh khác
  +4.49%   so với báo giá gần nhất (7,800.00 · 30/09/2026)

14 ngày qua (giá thấp nhất mỗi ngày)
  Thấp nhất: 7,720.00 (25/09)
  Cao nhất:  8,150.00 (02/10)

🔗 Xem chi tiết: https://quotify.honghafeed.com.vn/quotes/<id>
```

**Hiển thị CNF (QĐ-8).** Khi điểm giá mới là dòng nhập **USD/MT**, tin thêm một khối giá CNF (lấy từ `price_original`, đơn vị USD/MT):

```
CNF (USD/MT)
  352.00  (02/10/2026)  so với 345.00 (30/09/2026): +2.03%
```

- Dòng "so với" chỉ hiển thị khi **cả điểm mới và điểm tham chiếu đều là dòng USD/MT**. Nếu không thì chỉ hiển thị giá CNF của điểm mới.
- Điều kiện gửi tin và mức độ vẫn tính trên **VNĐ/KG** (D1, QĐ-13). Vì giá quy đổi phụ thuộc tỷ giá, đôi khi VNĐ/KG đổi mà CNF không đổi. Dòng CNF giúp người đọc nhận ra đó là biến động do tỷ giá. Khi hai bên khác chiều, tin ghi chú ngắn "chênh lệch do tỷ giá".
- Dòng nhập VND/KG không có khối CNF.

Tin không nêu nhà cung cấp vì người dùng chỉ quan tâm giá. Thông tin NCC xem ở liên kết chi tiết. Khi gộp theo vật tư (D5), tin có một khối cho mỗi kỳ giao hàng vượt ngưỡng, ảnh biểu đồ vẽ kỳ giao có mức cao nhất.

Ví dụ tin giá bất thường (D12), dùng dữ liệu thật ngày 15/09/2026:

```
⚠️ GIÁ BẤT THƯỜNG · Threonine
Kỳ giao hàng: 11/2026

Giá nhận 15/09/2026: 970.00 VNĐ/KG
Các giá gần đây (7 ngày làm việc): 25,600.00 · 25,435.00 · 25,900.00
Lệch −96.21% so với trung vị 25,600.00

Giá này chưa được dùng để tính biến động.
[✅ Giá đúng]  [❌ Nhập sai]
🔗 Xem phiếu: https://quotify.honghafeed.com.vn/quotes/<id>
```

Quy ước hiển thị bắt buộc: `10,200.00 VNĐ/KG`, ngày `DD/MM/YYYY`, giờ VN, tiếng Việt có dấu. Tin ghi rõ "giá quy đổi" nếu nguồn là USD/MT. Khi chọn hiển thị theo CNF thì dùng `USD/MT` đúng đơn vị (đã từng lỗi callout hardcode VNĐ/KG).

### 4.3 Biểu đồ min-max 14 ngày

- Dữ liệu: dùng lại logic daily-min và truy vấn kiểu `_get_summary`/`_get_points` của `QuotifyDashboardService` (đã ưu tiên điểm **mới nhất** sau bug 13/08). Không tự viết SQL song song nếu tránh được. Cần refactor nhỏ để có hàm công khai, có test.
- Hiển thị: 14 ngày lịch, đường daily-min, hai đường ngang min và max **của vùng tham chiếu 7 ngày làm việc** (gắn nhãn giá), vùng tham chiếu được tô sáng, điểm cuối tô theo màu mức, tiêu đề, nhãn ngày `dd/MM`.
- Công nghệ (cần chốt): 

| Phương án | Ưu | Nhược |
|---|---|---|
| **matplotlib (đề xuất)** | Linh hoạt, chất lượng tốt, chạy offline | Kéo theo numpy, tăng ~60-100MB image. Cần font có tiếng Việt (DejaVu Sans hỗ trợ), nhúng vào image **[CHƯA XÁC MINH trong image prod]** |
| Pillow tự vẽ | Nhẹ | Tự vẽ trục, nhãn, thủ công |
| Dịch vụ ngoài (QuickChart) | Không thêm dependency | Dữ liệu giá rời công ty |

- Vẽ trong **worker**, không vẽ trong request. Chỉ có worker bị ảnh hưởng nếu tách image. Phải build lại `backend` và `worker`.

### 4.4 Liên kết tài khoản Telegram

Nguyên tắc: **định danh người nhận là `users.id`**, không phải `chat_id`. `telegram_user_id` là khóa liên kết ổn định, `username` chỉ để hiển thị vì người dùng có thể đổi.

Luồng liên kết:
1. Người dùng vào **Hồ sơ** trên web → bấm "Liên kết Telegram".
2. Backend sinh token ngẫu nhiên dùng một lần, lưu **băm sha256**, hạn 10 phút, trả deep-link `https://t.me/<tên_bot>?start=<token>`.
3. Người dùng mở link, bấm Start. Telegram gửi update `/start <token>` tới webhook.
4. Backend xác thực token, kiểm tra `telegram_user_id` chưa gắn với user khác, tạo liên kết `active`, hủy token, gửi tin xác nhận. Ghi audit.
5. Frontend thấy trạng thái đổi sang "Đã liên kết" (poll vài giây hoặc làm mới khi focus).

Các trường hợp biên:

| Trường hợp | Xử lý |
|---|---|
| Đổi sang tài khoản Telegram mới | Nút "Đổi tài khoản": sinh token mới. Khi tài khoản mới xác nhận, **trong một transaction** thu hồi liên kết cũ (`revoked_at`, lý do `replaced`), tạo liên kết mới. Chat cũ nhận tin "đã hủy liên kết" (nếu còn gửi được). Giữ lịch sử |
| Hủy liên kết từ web | `DELETE /users/me/telegram` thu hồi liên kết |
| Hủy liên kết từ Telegram | Lệnh `/stop` thu hồi liên kết. Người dùng chặn bot (Telegram trả 403) thì đánh dấu inactive, không retry vô hạn |
| Telegram đã gắn với user khác | Từ chối, báo "tài khoản Telegram này đã được liên kết với tài khoản khác. Hãy hủy ở tài khoản kia trước" |
| Đổi `username` Telegram | Không ảnh hưởng. Cập nhật `username` hiển thị lần tin nhắn sau |
| Người dùng bị khóa/vô hiệu | Mỗi lần gửi và mỗi tin nhận đều kiểm tra `User.status = active` |
| Nhắn từ nhóm (group) | Chỉ chấp nhận chat riêng (`chat.type = private`) |
| Xóa user cứng | `DELETE /users/{id}` từng trả 500 khi user có `refresh_tokens` (chưa fix **[CHƯA XÁC MINH đã sửa]**). Khuyến nghị vô hiệu hóa thay vì xóa |

Ràng buộc DB: hai chỉ mục **partial unique** (mẫu `uq_quote_versions_single_draft`): mỗi `telegram_user_id` chỉ có 1 liên kết `active`, mỗi `user_id` chỉ có 1 liên kết `active`.

Không bắt người dùng gõ mật khẩu Quotify hay `chat_id` vào chat. Không nhồi cột Telegram vào `users` vì `PUT /users/{id}` ghi đè toàn bộ.

### 4.5 Mô hình dữ liệu (migration mới, additive)

Head hiện tại là `20260824_1000`. Migration mới đặt tên `YYYYMMDD_HHMM_<mô_tả>.py`, `--rev-id` đúng quy ước, viết tay (autogenerate sẽ sinh DROP index giả vì ORM thiếu nhiều index composite).

```
telegram_accounts
  id UUID PK
  user_id FK users CASCADE (ix)
  telegram_user_id BIGINT NOT NULL
  chat_id BIGINT NOT NULL
  username varchar(64) NULL, first_name varchar(150) NULL
  status varchar(20)  CHECK in ('active','revoked','blocked')
  linked_at timestamptz, revoked_at NULL, revoked_reason varchar(30) NULL
  last_seen_at NULL, created_at, updated_at
  UNIQUE PARTIAL (telegram_user_id) WHERE status='active'
  UNIQUE PARTIAL (user_id)          WHERE status='active'

telegram_link_tokens
  id UUID PK, user_id FK users CASCADE, token_hash varchar(64) UNIQUE
  expires_at, used_at NULL, created_at

telegram_processed_updates          -- chống xử lý trùng (Telegram có thể gửi lại)
  update_id BIGINT PK, received_at timestamptz

price_alert_settings (singleton)    -- KHÔNG nhét vào quotify_settings
  id, singleton_key 'default'
  reference_working_days int default 7       -- D3
  light_min_percent numeric(5,2) default 2.50
  medium_min_percent numeric(5,2) default 5.00
  large_min_percent numeric(5,2) default 10.00
  anomaly_percent numeric(5,2) default 30.00 -- D12
  staff_lookback_days int default 90
  digest_hour_local smallint default 8
  last_scanned_confirmed_at timestamptz   -- watermark
  is_enabled bool default false           -- cờ bật, phát hành "tắt" trước
  updated_by_id, created_at, updated_at

price_alert_material_thresholds             -- D4: ghi đè theo vật tư
  material_id UUID PK FK materials CASCADE
  light_min_percent numeric(5,2) NULL
  medium_min_percent numeric(5,2) NULL
  large_min_percent numeric(5,2) NULL
  anomaly_percent numeric(5,2) NULL         -- NULL = dùng mặc định
  CHECK: ba cột ngưỡng cùng NULL hoặc cùng NOT NULL
  CHECK: 0 < light < medium < large khi NOT NULL
  updated_by_id FK users SET NULL, created_at, updated_at

price_alert_events
  id UUID PK, quote_version_id FK, material_id FK, delivery_month date
  kind varchar(10) ('change'|'anomaly')
  quote_line_id FK NULL                     -- dòng bị gắn cờ (kind='anomaly')
  direction varchar(4) NULL ('up'|'down')
  level varchar(10) NULL ('light'|'medium'|'large')   -- NULL khi kind='anomaly'
  rule varchar(2) NULL ('R1'|'R2'|'R3')               -- lý do chính
  percent_change numeric(8,2)               -- anomaly: độ lệch so với trung vị
  price_new numeric(12,2), price_ref numeric(12,2)
  received_date_new date, received_date_ref date
  window_min numeric(12,2), window_max numeric(12,2)
  review_status varchar(10) NULL ('pending'|'accepted'|'rejected')   -- kind='anomaly'
  reviewed_by_id FK users SET NULL NULL, reviewed_at NULL
  created_at
  UNIQUE (quote_version_id, material_id, delivery_month, kind)

price_alert_deliveries
  id UUID PK, event_id FK CASCADE, user_id FK, telegram_account_id FK
  status varchar(20) ('pending','sent','failed','skipped','digest_queued')
  attempts int, last_error varchar(255) NULL, sent_at NULL, created_at
  UNIQUE (event_id, user_id)               -- idempotent khi retry

user_alert_preferences                      -- tùy chọn cá nhân (D10)
  user_id PK FK users CASCADE
  is_enabled bool default true
  min_level varchar(10) default 'light'
  created_at, updated_at
```

**Thay đổi bảng hiện có (additive, nullable, QĐ-9).** Ghi nhận nguồn nhập báo giá:
```
quotes.created_via         varchar(20) NULL   -- 'telegram' | NULL (NULL = web hoặc dữ liệu cũ)
quote_versions.created_via varchar(20) NULL
CHECK created_via IS NULL OR created_via IN ('telegram')
```
Không backfill dữ liệu cũ (giữ NULL). `QuoteService.create_quote` và `create_version` nhận thêm tham số tùy chọn `created_via` (mặc định `None`, hành vi cũ không đổi). Thêm trường tùy chọn `created_via` vào schema `QuoteResponse` và phiên bản. Giao diện: icon bot trong cột "Trạng thái" của danh sách báo giá và ô tick lọc theo nguồn Telegram (xem 4.9). Khóa audit `channel` thêm vào allow-list.

Mọi bảng mới phải thêm vào `app/models/__init__.py` (và nên thêm vào `app/db/base.py`).

### 4.6 API và quyền

| Endpoint | Quyền | Ghi chú |
|---|---|---|
| `POST /api/v1/users/me/telegram/link-token` | đăng nhập | Sinh deep-link. Rate limit |
| `GET /api/v1/users/me/telegram` | đăng nhập | Trạng thái liên kết |
| `DELETE /api/v1/users/me/telegram` | đăng nhập | Hủy liên kết |
| `GET/PUT /api/v1/users/me/alert-preferences` | đăng nhập | Bật/tắt, mức tối thiểu |
| `GET/PUT /api/v1/price-alert-settings` | `price_alerts.manage` (mới) | Ngưỡng mặc định, bật/tắt |
| `GET /api/v1/price-alert-settings/materials` | `price_alerts.manage` | Danh sách vật tư kèm ngưỡng hiệu lực, có phân trang (`limit ≤ 100`) và tìm kiếm |
| `PUT /api/v1/price-alert-settings/materials/{material_id}` | `price_alerts.manage` | Ghi đè ba ngưỡng và/hoặc ngưỡng bất thường của một vật tư |
| `DELETE /api/v1/price-alert-settings/materials/{material_id}` | `price_alerts.manage` | Bỏ ghi đè, về mặc định |
| `POST /api/v1/telegram/webhook` | **không JWT**, xác thực `X-Telegram-Bot-Api-Secret-Token` | Trả 200 nhanh, xử lý nặng qua arq |

Permission mới: `price_alerts.receive_all` (trưởng phòng), `price_alerts.manage` (admin **và trưởng phòng**, QĐ-4), `chatbot.manage` (chỉ admin, quản lý ngân sách LLM, **không** cấp cho trưởng phòng). Phải thêm vào `BASE_PERMISSION_CODES`, `test_permission_inventory.py`, migration dữ liệu cho role `manager`, và chạy lại `seed_auth_rbac.py` trên prod bằng `run --rm`.

Xem xét giá bất thường: xử lý qua nút trong Telegram (callback `callback_query` đến cùng webhook). Chỉ người có `price_alerts.receive_all` được bấm. Có thể thêm endpoint web sau.

Audit event mới (`telegram.linked`, `telegram.unlinked`, `price_alerts.settings_updated`, `price_alerts.threshold_updated`, `price_alerts.anomaly_reviewed`): thêm key vào `ALLOWED_AUDIT_METADATA_KEYS`. Tránh key chứa `token`, `secret`, `session`. Không ghi audit từng tin gửi hàng loạt, chỉ 1 sự kiện tổng kết mỗi lần quét. `telegram_user_id` có phải PII để ghi audit hay không cần chốt.

### 4.7 Cấu hình

Thêm vào `Settings` (`core/config.py`), theo mẫu có `*_FILE` cho secret, và vào `.env.example` + `.env.production.example`:

```
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN / TELEGRAM_BOT_TOKEN_FILE
TELEGRAM_BOT_USERNAME
TELEGRAM_WEBHOOK_SECRET / TELEGRAM_WEBHOOK_SECRET_FILE
TELEGRAM_MODE=webhook|polling        # dev dùng polling
TELEGRAM_HTTP_TIMEOUT_SECONDS=10
```

Trong compose prod, secret dùng `${VAR:?msg}`, không viết literal.

### 4.8 Worker

- Thêm cron vào `WorkerSettings.cron_jobs` (cạnh `poll_and_run_scheduled_backups`): `poll_price_alerts` mỗi 1-2 phút, `send_price_alert_digest` mỗi giờ (kiểm tra giờ địa phương).
- arq cron chạy theo **timezone hệ thống (UTC trong container)**. `hour=8` nghĩa là 15:00 giờ VN. Phải tự tính theo `ZoneInfo("Asia/Ho_Chi_Minh")`, hoặc quét mỗi giờ rồi so với giờ VN.
- Quét dùng `SELECT ... FOR UPDATE SKIP LOCKED` hoặc advisory lock để hai tiến trình không quét trùng (mẫu `poll_and_run_scheduled_backups`).
- Job gửi tin: bọc `try/except` riêng, retry có backoff, xử lý 429 (`retry_after`) và 403 (bot bị chặn). Chỉ bỏ qua khi trạng thái terminal (`sent`/`failed`), không bỏ qua trạng thái đang chạy (bug 27/07).
- Worker không tự reload code: sau khi sửa phải restart (dev) hoặc build lại `worker` (prod).
- **Không có khung giờ yên lặng** (QĐ-7): tin Trung bình, Lớn và giá bất thường gửi ngay mọi giờ. Người dùng tự tắt tiếng chat bot trong Telegram nếu cần. Bản tin tổng hợp mức Nhẹ vẫn gửi lúc 08:00 giờ VN.

### 4.9 Giao diện web

Chỉ cần ở Bước 1:
- Panel thứ ba trong `ProfilePage.vue` ("Thông báo Telegram"): trạng thái liên kết, nút Liên kết / Đổi tài khoản / Hủy, bật-tắt, mức tối thiểu. Composable mới `useTelegramLink.ts`, API `telegram.api.ts` + `telegram.mappers.ts`, kiểu `types/telegram.ts`.
- Panel "Ngưỡng cảnh báo giá" (mặc định toàn hệ thống: Nhẹ, Trung bình, Lớn, ngưỡng bất thường) trong `QuotifySettingsPage.vue` cho admin, hoặc trang mới.
- Bảng **"Ngưỡng theo mặt hàng"**: DataTable lazy (`limit ≤ 100`), tìm theo tên hoặc mã vật tư, cột Nhẹ / Trung bình / Lớn / Bất thường. Mặt hàng chưa ghi đè hiển thị giá trị mặc định với nhãn "mặc định". Sửa qua Dialog, kiểm tra `0 < Nhẹ < Trung bình < Lớn`, nút "Dùng mặc định". Người thiếu quyền thấy nút ở trạng thái `disabled` kèm `title` giải thích (quy ước dự án).
- Tuân thủ: không `<style>` trong `.vue`, SCSS mới ở `styles/pages/_telegram-*.scss`, token `--app-*`, responsive, dấu `*` đỏ cho trường bắt buộc, thông báo inline (không Toast), `data-testid` cho test.
- Thêm nhãn `telegram.*` vào `audit-logs.mappers.ts`.
- **Nguồn nhập Telegram (QĐ-9):** chỉ làm hai thứ trên danh sách báo giá (`QuotesPage.vue`), không làm ở trang chi tiết phiếu.
  - **Icon bot** trong cột "Trạng thái" (cột `version_status`, cạnh các badge Đã xác nhận, Đã hủy), có tooltip "Nhập qua Telegram", chỉ hiển thị khi `createdVia = 'telegram'`. PrimeIcons chưa chắc có biểu tượng robot **[CHƯA XÁC MINH]**, nếu không thì dùng SVG nội tuyến.
  - **Ô tick lọc** "Chỉ phiếu nhập qua Telegram" cạnh các bộ lọc "Trạng thái chốt" và "Trạng thái phiếu". Tick = chỉ phiếu nhập qua Telegram, không tick = tất cả (giả định, cần bạn xác nhận). Backend thêm tham số tùy chọn `created_via` vào `GET /quotes` và `QuoteQueryService.query_flattened_quotes` (không đổi hành vi khi không truyền). Frontend cập nhật `quotes.api.ts`, `useQuotesPage.ts`, `quotes-view.store.ts` (lưu bộ lọc trong `sessionStorage`) và kiểu, mapper của báo giá.
- Trang **"Chi phí chatbot"** (chỉ admin, `chatbot.manage`): chi phí tháng đến hiện tại so với trần, theo ngày, theo người dùng, sửa trần (Bước 2, xem 5.6).

### 4.10 Kiểm thử

- TDD cho phần lõi thuần: hàm tính %, phân mức theo biên D4 (kiểm các giá trị đúng 2,5 / 5 / 10), chọn điểm tham chiếu, chống trùng/leo thang, giải quyết người nhận.
- Cửa sổ 7 ngày làm việc: điểm mới vào thứ Hai, thứ Sáu, thứ Bảy; cửa sổ vắt qua cuối tuần; điểm nhận cuối tuần.
- Bộ ba quy tắc: ba ví dụ ở D2 làm test mẫu (tăng, giảm, hướng ngược), hòa mức giữa hai quy tắc, chỉ có 1 điểm trước, giá mới bằng điểm trước.
- Ngưỡng theo mặt hàng: ghi đè đủ ba số, dùng mặc định khi không ghi đè, từ chối giá trị không tăng dần, đổi ngưỡng không báo lại dữ liệu cũ.
- Giá bất thường: loại khỏi tham chiếu, nút Giá đúng (chấp nhận, tính lại biến động), nút Nhập sai, điểm đầu chuỗi không thể bị gắn cờ.
- **Fake Telegram transport** (không gọi Telegram thật trong unit test, theo tiền lệ fixture Vietcombank). Cố định "hôm nay" bằng monkeypatch.
- Test múi giờ: biên 00:00/24:00 GMT+7, ranh giới cửa sổ 7 ngày làm việc inclusive/exclusive rõ ràng.
- Verify thật: `curl` webhook với secret đúng/sai, chạy cron trên Docker dev, kiểm `MissingGreenlet` (sau `commit` phải `await session.refresh`). Playwright cho luồng liên kết (cần fake Telegram server).
- `test_permission_inventory.py` và `test_audit_log_service.py` phải qua.
- Tính toán dữ liệu thử trên DB dev (vừa khôi phục từ dump 2026-10-02) để kiểm tra phân bố mức biến động thật.

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
- **Chỉ tiếng Việt có dấu** (QĐ-7): mọi câu trả lời và nút bấm bằng tiếng Việt có dấu, system prompt yêu cầu như vậy. Đề xuất chấp nhận cả câu hỏi gõ không dấu (khớp tên vật tư bằng chuỗi đã bỏ dấu) nhưng luôn trả lời có dấu.

### 5.2 Hỏi đáp và báo cáo (chỉ đọc)

**Tool-calling với hàm cố định**, mỗi hàm tham số hóa, gọi lại service có sẵn:

| Tool | Gọi tới | Quyền cần |
|---|---|---|
| `find_material(name)` | `MaterialAdminService` lookup | `materials.read` |
| `get_price_trend(material, delivery_month, days)` | `QuotifyDashboardService.get_price_trends` | `dashboard.read` |
| `compare_suppliers(material, delivery_month)` | `QuoteQueryService` | `quotes.read` |
| `list_recent_quotes(filters)` | `QuoteQueryService` | `quotes.read` |
| `weekly_entry_activity()` | `QuotifyDashboardService` | `dashboard.read` |
| `get_price_alerts(days)` | `price_alert_events` | đăng nhập |

Phòng thủ nhiều lớp để đáp ứng "chỉ READ" và "cấm SQL nguy hiểm":
1. **Không có tool nào ghi hoặc nhận SQL.** AI không có đường tới câu lệnh tự do.
2. Mọi truy vấn của luồng hỏi đáp chạy trong transaction **`SET TRANSACTION READ ONLY`** và `statement_timeout`. Rẻ, không cần role mới.
3. Giai đoạn tăng cường (tùy chọn): role Postgres chỉ `SELECT` trên view whitelist (loại `users.password_hash`, `refresh_tokens`, `audit_logs`, `files`) và engine thứ hai cho luồng hỏi đáp. Cần quyền `CREATE ROLE`.
4. Không cung cấp tool đọc `users`, `audit_logs`, `refresh_tokens`, `files`.
5. Giới hạn kích thước kết quả (cap `limit`), không quét `quote_lines` (~20.000 dòng) không filter. Kiểm `EXPLAIN` cho truy vấn mới.
6. Câu trả lời chỉ dựa trên kết quả tool. System prompt yêu cầu từ chối câu hỏi ngoài dữ liệu Quotify. Giọng trung tính, **không khuyến nghị mua/bán**.
7. Chỉ dùng version `confirmed` (danh sách phẳng mặc định còn cả `draft`, phải lọc).

Nếu sau này cần "hỏi tự do" kiểu text-to-SQL thì chỉ làm sau khi có role read-only và view whitelist, kèm trình phân tích câu lệnh chỉ cho phép một câu `SELECT`. Không đề xuất làm ở v1.

Quyền đọc báo giá hiện là toàn cục theo `quotes.read` (không phân quyền theo chủ phiếu), nên nhân viên hỏi bot xem được giá của người khác, giống như xem trên web.

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
- Luật nghiệp vụ phải giữ: chỉ cặp `VND/KG` và `USD/MT`; NCC phải có trong `supplier_materials` của vật tư; `received_date` không ở tương lai; `received_date` < hôm nay hoặc `delivery_month` < tháng hiện tại thì bắt buộc `is_backfilled`; USD/MT quá khứ bắt buộc tỷ giá nhập tay; ép `delivery_month` về **ngày 01** (R1); tỷ giá là số nguyên.
- **Luôn tạo draft, bước chốt là hành động riêng của người dùng** (QĐ-9). Không có cấu hình "chốt ngay". Phiếu và phiên bản tạo qua bot được đánh dấu `created_via = 'telegram'`.
- `_ensure_quote_mutation_allowed` đang là hàm private ném `HTTPException` trong `quotes.py`. Cần tách một hàm dùng chung (thay đổi nhỏ, giữ nguyên hành vi API) hoặc viết lại kiểm tra tương đương cho bot. Service **không** tự kiểm quyền (R3).
- Audit `quotes.quote_created` do route phát chứ không phải service, nên bot phải tự ghi, kèm `channel=telegram` (thêm key vào allow-list).
- Chống tạo trùng: dedupe theo `update_id`, khóa theo chat, và phát hiện trùng hoàn toàn (mẫu `quote_backfill_import.py`).
- Ảnh/PDF: kiểm MIME, magic bytes, kích thước, số trang trước khi gọi LLM (giới hạn chi phí). Hiện upload file nguồn không kiểm các thứ này. Lưu qua `FileAdminService`. MinIO client là đồng bộ trong hàm async nên phải chạy trong worker hoặc `to_thread`.
- **Prompt injection:** nội dung PDF/ảnh là dữ liệu không tin cậy. Tool ghi duy nhất là "tạo nháp", luôn qua thẻ xác nhận. Không có tool xóa, hủy, sửa danh mục.
- Dòng ghi chú nếu có phải sanitize (`nh3`).

### 5.4 Nhớ ngữ cảnh hội thoại

```
chat_sessions   id, telegram_account_id/telegram_user_id, user_id, summary text,
                last_message_at, expires_at
chat_messages   id, session_id, role('user'|'assistant'|'tool'), content,
                tool_calls JSON, input_tokens, output_tokens, created_at
(chi phí LLM theo dõi ở bảng llm_usage_events, xem 5.6)
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
- Key API là secret (`*_FILE`, có owner và chính sách xoay vòng). Có timeout, giới hạn token, lỗi LLM không được làm hỏng bot (trả lời "tạm thời không xử lý được").
- Test bằng transport giả, không gọi LLM thật. Cần bộ test "đánh giá" nhỏ (golden set) cho trích xuất báo giá tiếng Việt.

### 5.6 Ngân sách và chi phí LLM (QĐ-10)

- **Admin hệ thống quản lý chi phí.** Trần ngân sách khoảng **2.000.000 đ mỗi tháng** (khoảng 75 USD ở tỷ giá ~26.500), cấu hình được.

```
chatbot_settings (singleton)
  is_enabled bool default false
  monthly_budget_vnd numeric(14,0) default 2000000
  warn_percent smallint default 80
  daily_user_limit int                        -- số lượt hỏi mỗi người mỗi ngày
  input_price_usd_per_mtok  numeric(10,4)     -- đơn giá model đang dùng (cấu hình)
  output_price_usd_per_mtok numeric(10,4)
  fallback_usd_vnd_rate numeric(12,2)         -- khi không lấy được tỷ giá Vietcombank
  alert_email varchar(255) NULL               -- NULL = dùng ADMIN_EMAIL_FOR_BACKUPS
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
- **Kênh cảnh báo là email admin (QĐ-13).** Thêm `EmailService.send_budget_alert` theo mẫu `send_backup_notification` (SMTP đồng bộ trong `asyncio.to_thread`). Gọi **sau commit**, bọc `try/except` riêng, lỗi gửi mail không được làm đổi kết quả nghiệp vụ. Người nhận là `chatbot_settings.alert_email`, nếu trống thì `ADMIN_EMAIL_FOR_BACKUPS`. **Điều kiện:** SMTP production hiện chỉ có giá trị mẫu trong `.env.production.example` **[CHƯA XÁC MINH có SMTP thật trên VPS]**, cần cấu hình và gửi thử trước khi dựa vào kênh này. Trang quản trị vẫn hiển thị chi phí tháng nhưng không phải kênh cảnh báo chính.
- **Giới hạn lượt mỗi người mỗi ngày** (Redis) để một người không dùng hết ngân sách.
- **Trang "Chi phí chatbot"** chỉ admin (`chatbot.manage`): chi phí tháng đến hiện tại so với trần, theo ngày, theo người dùng, sửa trần. Mọi thay đổi trần ghi audit.
- **Chưa có số liệu chi phí mỗi lượt.** Cần đo thực tế trên dev với Google AI Studio (số token và chi phí cho hỏi đáp, đọc ảnh, đọc PDF) trước khi chốt model và hạn mức lượt mỗi người.

---

## 6. Rủi ro và điểm dễ làm vỡ code cũ

| # | Rủi ro | Cách xử lý |
|---|---|---|
| R1 | `delivery_month` backend **không ép ngày 01**. Dashboard so `==` chính xác | Chuẩn hóa `date_trunc('month')` khi nhóm chuỗi. Bot phải gửi ngày 01 |
| R2 | `is_backfilled` bị ép `true` mỗi khi `received_date` < hôm nay (3.026/3.086 version là backfilled). Không có nghĩa "import hàng loạt" | Xem D6. Không dùng làm điều kiện duy nhất mà không ghi rõ đánh đổi |
| R3 | **Authz nằm ở tầng API**, service không kiểm quyền và không kiểm ownership. Bot gọi service sẽ **bỏ qua toàn bộ RBAC** nếu không tự thêm | Mọi tool/hành động phải kiểm `has_permission` và ownership. Tách helper dùng chung |
| R4 | Bản điều chỉnh (`superseded`) và `delete_confirmed_line` đều tạo version confirmed mới, dễ sinh cảnh báo kép hoặc giả | Loại `superseded` khi tính baseline. Không coi xóa dòng là biến động. Khóa dedupe |
| R5 | `create_job_queue` mở pool Redis mới mỗi lần, không đóng | Dùng một pool chung cho webhook |
| R6 | Token bot nằm trong URL `api.telegram.org/bot<TOKEN>/...`. httpx log URL ở INFO và `HTTPXClientInstrumentor` ghi URL vào span OTel | Hạ log httpx, scrub URL, không log token. Verify trên prod **[CHƯA XÁC MINH]** |
| R7 | Xóa user cứng: `created_by_id` thành NULL (mất người nhận); `DELETE /users/{id}` từng 500 | Vô hiệu hóa thay vì xóa. Bỏ qua user không `active` |
| R8 | arq cron theo UTC | Tự tính theo giờ VN |
| R9 | Rate limiter in-memory theo IP | Redis, khóa theo user Telegram |
| R10 | Import backfill đi thẳng `create_quote(confirm_immediately=True)`, không qua route confirm. Cron quét `confirmed_at` bắt cả import | Watermark ban đầu, bỏ `is_backfilled`, flood guard |
| R11 | Tỷ giá gọi Vietcombank **từng dòng**, không cache. Buổi sáng sớm feed có thể chưa cập nhật nên lỗi | Bot hỏi tỷ giá tay khi lỗi. Cân nhắc cache theo ngày |
| R12 | Số liệu tiền dùng `float` ở frontend. Backend dùng `Decimal` | Chỉ tính ở backend bằng `Decimal` |
| R13 | `seed_auth_rbac.py` ghi đè quyền role `user` về đúng `USER_ROLE_PERMISSION_CODES`. Không đụng role `manager` | Cấp quyền mới cho `manager` bằng migration dữ liệu |
| R14 | Hai định nghĩa "người nhập" (`Quote.created_by_id` vs `QuoteVersion.created_by_id`) | Chốt D8: dùng `Quote.created_by_id` |
| R15 | Phiếu `draft` có trong danh sách phẳng mặc định | Mọi truy vấn của bot lọc `confirmed` |
| R16 | `update_draft` luôn tính lại giá, `create_version` không giữ `note` | Cẩn thận khi bot tạo bản điều chỉnh |
| R17 | Dữ liệu hội thoại, PII nằm trong backup. Dữ liệu gửi LLM bên thứ ba (đã được phép, QĐ-6) | Chính sách lưu giữ. Chỉ gửi nội dung tối thiểu. Dev dùng gói miễn phí nên ưu tiên dữ liệu thử, xác minh điều khoản dữ liệu của gói (D11) |
| R18 | Prod chạy 1 tiến trình uvicorn, Redis không mật khẩu và worker bỏ qua `REDIS_URL` | Không đổi Redis sang có mật khẩu mà không sửa worker |
| R19 | Nợ kỹ thuật nền (lint/prettier/test baseline, `smoke.spec.ts` lỗi thời, alert rules còn tên `fastapivue_*`) | So với baseline trước khi báo "không lỗi mới". Không sửa lan |

### Lệch tài liệu và code đã phát hiện (cần biết trước khi tin tài liệu)

- `memory-bank/progress.md`, `activeContext.md` dừng ở 22/08. Nhiều thay đổi 17-25/08 chưa vào memory-bank: import `.xlsx`, dashboard làm lại, hủy phiếu/xóa dòng, `sequence_number`, tỷ giá lịch sử, `created_by_role`, role correction.
- `Requirements.txt` còn công thức cũ ("Chi phí quy đổi") và "bắt buộc lý do nhập lại" đã bỏ từ 04/08.
- `projectbrief.md`, `README.md` còn mô tả "chỉ có boilerplate".
- `systemPatterns.md` ghi grace refresh token 30s, code là 120s.
- `docs/adr/` không tồn tại.

---

## 7. Kế hoạch triển khai theo lát cắt dọc

Mỗi lát cắt có migration (nếu cần), backend, UI (nếu cần), test, tài liệu. Làm theo TDD. Mỗi lát cắt phát hành **tắt** bằng cờ cấu hình, bật dần.

### Giai đoạn 0: Chốt phạm vi (không code)
- Thảo luận và chốt D1-D11.
- Cập nhật `CONTEXT.md`, `Requirements.txt`, `quotify-implementation-plan.md` (Nhật ký thay đổi), tài liệu này.
- Chuẩn bị bot Telegram (`@BotFather`), kiểm tra VPS ra được `api.telegram.org` và Telegram vào được `443`.
- Kiểm tra DB prod: role `manager` có tồn tại không, số user theo role, tên role thật.

### Giai đoạn 1A: Nền tảng Telegram và liên kết tài khoản
- Migration: `telegram_accounts`, `telegram_link_tokens`, `telegram_processed_updates`.
- `integrations/telegram.py` (httpx, `sendMessage`, `sendPhoto`, `setWebhook`), cấu hình, secret, scrub log.
- Webhook (`/api/v1/telegram/webhook`) + chế độ polling cho dev. Xử lý `/start <token>`, `/stop`, `/help`.
- API liên kết + panel Hồ sơ trên web. Audit. Test (fake transport, e2e luồng liên kết).
- **Hoàn thành khi:** một user liên kết, đổi, hủy được tài khoản Telegram trên dev.

### Giai đoạn 1B: Engine biến động và thông báo
- Migration: `price_alert_settings`, `price_alert_material_thresholds`, `price_alert_events`, `price_alert_deliveries`, `user_alert_preferences`, permission mới + cấp cho `manager`.
- `PriceAlertService` (hàm thuần, TDD): cửa sổ ngày làm việc, bộ ba quy tắc, phát hiện giá bất thường. Cron quét + giải quyết người nhận + chống trùng.
- Bộ vẽ biểu đồ (matplotlib, font tiếng Việt) + định dạng tin + gửi + retry.
- Thử trên DB dev (đã có dữ liệu thật): dry-run chỉ ghi log, không gửi.
- **Hoàn thành khi:** dry-run cho phân bố mức hợp lý, tin mẫu đúng định dạng trên Telegram thật.

### Giai đoạn 1C: Cấu hình, bản tin tổng hợp, vận hành
- UI ngưỡng mặc định và ngưỡng theo mặt hàng, tùy chọn cá nhân, bản tin 08:00.
- Metrics (`quotify_*`), runbook triển khai, cập nhật `.env.production.example`, compliance script.
- Triển khai prod: backup, build (`backend`, `frontend`, `worker`), migrate bằng `run --rm`, seed quyền, `up -d`, `restart reverse-proxy`, bật cờ cho một nhóm nhỏ trước.

### Giai đoạn 2A: Hạ tầng chatbot và hỏi đáp
- Migration: `chat_sessions`, `chat_messages`, `chatbot_settings`, `llm_usage_events`, permission `chatbot.manage`.
- Ngân sách LLM (5.6): kiểm tra trần trước mỗi lần gọi, cảnh báo admin, trang "Chi phí chatbot".
- `LLMClient` + adapter, queue và service worker bot, lock/rate limit bằng Redis, trần chi phí.
- Tool chỉ đọc + `SET TRANSACTION READ ONLY` + bộ test tool + golden set hỏi đáp.
- Bộ nhớ hội thoại, `/reset`.

### Giai đoạn 2B: Nhập liệu bằng văn bản
- Migration: `quotes.created_via`, `quote_versions.created_via` (nullable). Icon bot ở cột Trạng thái và ô tick lọc nguồn Telegram trên danh sách báo giá.
- Trích xuất có cấu trúc, phân giải NCC/vật tư, thẻ xác nhận, `create_quote` (luôn draft, `created_via = 'telegram'`), chốt, audit, idempotency.

### Giai đoạn 2C: Nhập liệu bằng ảnh và PDF
- Kiểm tra file, lưu MinIO, trích xuất đa mô thức, hỏi lại khi mơ hồ, xử lý nhiều báo giá trong một file.

### Giai đoạn 2D: Tăng cường
- Role Postgres read-only + view whitelist cho luồng hỏi đáp. Rà soát prompt injection, chi phí, quyền riêng tư. Restore drill có dữ liệu hội thoại.

---

## 8. Khuyến nghị triển khai production (additive)

- Prod hiện chạy migrate bằng image **mới** trước khi thay container, nên code cũ chạy một lúc trên schema mới. Chỉ thêm bảng và cột nullable. Không đổi tên, không xóa, không downgrade.
- Phát hành mọi tính năng với cờ **tắt**. Thêm bảng và quyền trước, bật sau.
- Backup bắt buộc trước migrate (`scripts/ops/backup-postgres.sh`).
- Không sửa các file lõi nếu tránh được: `http.ts`, `auth.store.ts`, `router/guards.ts`, `useDashboardPage.ts`, `quotes.py`, `quote_service.py`. Ưu tiên file mới.
- Thêm `telegram_accounts` ở bảng riêng, **không** thêm cột vào `users`.
- **Ngoại lệ có chủ đích** (QĐ-9): thêm cột `created_via` nullable vào `quotes` và `quote_versions`, tham số tùy chọn `created_via` vào `QuoteService.create_quote`/`create_version`, và trường tùy chọn vào schema phản hồi. Thêm tham số lọc tùy chọn `created_via` vào `GET /quotes` và `QuoteQueryService`. Hành vi mặc định không đổi. Cần viết test hồi quy cho các API báo giá hiện có.
- Thay đổi nhỏ bắt buộc ở code cũ chỉ gồm: đăng ký router, thêm vào `models/__init__.py`, `BASE_PERMISSION_CODES`, allow-list audit, `Settings`, `WorkerSettings`, compose, và (nếu chọn) tách helper ownership.

---

## 9. Câu hỏi đã trả lời và điểm còn mở

### 9.1 Đã trả lời (2026-10-03)

| # | Câu hỏi | Trả lời |
|---|---|---|
| D1 | Gộp nhiều kỳ giao hàng vào một chuỗi không | Không gộp. Chuỗi là (vật tư, kỳ giao hàng) |
| D5 đến D10 | Chống spam, nguồn dữ liệu kích hoạt, người nhận tin, tùy chọn từng người | Đồng ý toàn bộ đề xuất |
| D11a | Nhà cung cấp LLM | Chưa chốt cho production. Dev dùng API key Google AI Studio |
| D11b | Chính sách dữ liệu | Cho phép gửi nội dung báo giá, ảnh, PDF sang bên thứ ba |
| 1 | Tin nhắn gửi vào nhóm hay chat riêng | Chỉ chat riêng |
| 2 | Ngôn ngữ bot | Chỉ tiếng Việt có dấu |
| 3 | Khung giờ yên lặng | Không có |
| 4 | Hiển thị CNF cho dòng USD | Có |
| 5 | Chatbot nhập liệu có chốt ngay không | Luôn tạo nháp rồi mới chốt |
| 6 | Ai quản lý chi phí LLM, có trần không | Admin hệ thống. Trần khoảng 2.000.000 đ mỗi tháng |
| 7 | Ghi nhận nguồn nhập qua Telegram | Có |
| 8 | Loại ngày lễ và Tết khỏi ngày làm việc | Tạm thời chưa |
| 9 | Ai sửa ngưỡng theo mặt hàng | Admin và trưởng phòng |
| 10 | Giá bất thường có tự chấp nhận không | Không, chỉ bằng nút Giá đúng |
| 11 | Người nhận tin giá bất thường | Trưởng phòng và người nhập phiếu |
| 12 | Điều chỉnh hướng tin ở D2 | Đồng ý |
| D11c | Gói Google AI Studio khi test dev | Dùng gói miễn phí |
| 13 | Vị trí nhãn Telegram, có lọc theo nguồn không | Chỉ icon bot ở cột "Trạng thái". Có ô tick lọc theo nguồn Telegram |
| 14 | Biến động % cho chuỗi USD/MT | Không làm, chỉ tính trên VNĐ/KG |
| 15 | Kênh gửi cảnh báo ngân sách LLM | Email admin |

### 9.2 Còn mở

**Điểm mở nhỏ (không chặn việc bắt đầu, chốt trong lúc làm):**

1. **Nhà cung cấp LLM cho production.** Chọn sau khi đo chi phí và chất lượng đọc ảnh/PDF tiếng Việt trên dev.
2. **Điều khoản dữ liệu và hạn mức của gói miễn phí Google AI Studio** **[CẦN XÁC MINH]**. Dev chứa dữ liệu thật và hạn mức thấp có thể khiến bài đo chi phí chưa phản ánh production.
3. **Giới hạn lượt hỏi mỗi người mỗi ngày** (giá trị cụ thể), sau khi đo chi phí mỗi lượt.
4. **SMTP production** có thật chưa **[CHƯA XÁC MINH]**, và email nhận cảnh báo ngân sách (một hay nhiều địa chỉ admin).
5. **Ô tick lọc nguồn Telegram:** tick = chỉ phiếu Telegram, không tick = tất cả (giả định, chờ xác nhận). Biểu tượng bot: chọn icon.

---

## 10. Phụ lục: tập tin sẽ chạm vào

**File mới (dự kiến):**
- `backend/alembic/versions/2026MMDD_HHMM_*.py` (một migration cho mỗi lát cắt)
- `backend/app/models/telegram_account.py`, `price_alert.py`, `chat.py`
- `backend/app/schemas/telegram.py`, `price_alert.py`
- `backend/app/services/price_alert_service.py`, `price_alert_chart.py`, `telegram_link_service.py`, `chatbot_service.py`, `chatbot_budget_service.py`
- `backend/app/integrations/telegram.py`, `integrations/llm/*`
- `backend/app/api/v1/telegram.py`, `price_alerts.py`
- `frontend/src/types/telegram.ts`, `api/telegram.api.ts`, `api/telegram.mappers.ts`, `composables/useTelegramLink.ts`, `pages/ChatbotUsagePage.vue`
- `frontend/src/styles/pages/_telegram-*.scss`
- Test tương ứng cho từng file trên

**File hiện có chỉ sửa tối thiểu:**
- `backend/app/api/v1/router.py` (đăng ký router)
- `backend/app/models/__init__.py`, `db/base.py` (đăng ký model)
- `backend/app/auth/seed_data.py` (permission mới)
- `backend/app/services/audit_log.py` (allow-list)
- `backend/app/core/config.py`, `.env.example`, `.env.production.example`
- `backend/app/worker.py` (đăng ký cron và task)
- `backend/pyproject.toml`, `uv.lock` (matplotlib, SDK nếu dùng)
- `docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.test.yml` (service bot nếu tách)
- `frontend/src/pages/ProfilePage.vue`, `QuotifySettingsPage.vue`, `api/audit-logs.mappers.ts`
- `CONTEXT.md`, `docs/quotify/Requirements.txt`, `docs/quotify/quotify-implementation-plan.md`, `memory-bank/*`
- `backend/app/services/quote_query_service.py`, `backend/app/api/v1/quotes.py` (tham số lọc `created_via`), `backend/app/services/email.py` (`send_budget_alert`)
- `frontend/src/pages/QuotesPage.vue`, `composables/useQuotesPage.ts`, `stores/quotes-view.store.ts`, `api/quotes.api.ts`, `types/quotes.ts` (icon bot và ô tick lọc)

---

## Phụ lục B: Kết quả backtest trên dữ liệu thật

**Cách làm.** Script chỉ đọc, chạy trên DB dev (khôi phục từ bản dump 2026-10-02): 20.893 dòng giá `confirmed`, phiếu chưa hủy, từ 10/2023 đến 02/10/2026, 361 chuỗi (vật tư, kỳ giao hàng). Với mỗi chuỗi và mỗi ngày có báo giá, lấy daily-min của ngày đó, so với các điểm trong 13 ngày trước theo từng phương án (D2), rồi phân mức theo D4. "Chống lặp" là quy tắc D5(a). Người nhận nhân viên = người nhập vật tư đó trong 90 ngày trước (D8).

**Giới hạn của phép thử.**
- Phát lại theo `received_date`, mỗi ngày chấm một lần vào cuối ngày. Hệ thống thật chấm mỗi khi có version mới `confirmed`.
- Phần lớn dữ liệu cũ là nhập lùi (20.328/20.893 dòng `is_backfilled`). Mật độ nhập thời gian thực có thể khác.
- Danh sách người nhận là ước lượng.
- Chỉ có 8 người nhập, nên số liệu theo người chỉ mang tính tham khảo.

### B.1 Phân bố mức, chưa chống lặp (12 tháng gần nhất)

N = số điểm giá có ít nhất 1 điểm trước trong cửa sổ. "% gửi" = tỷ lệ điểm vượt 2,5%.

| PA | N | Nhẹ↑ | Nhẹ↓ | TB↑ | TB↓ | Lớn↑ | Lớn↓ | % gửi |
|---|---|---|---|---|---|---|---|---|
| A | 4.105 | 598 | 397 | 254 | 156 | 92 | 33 | 37,3% |
| B | 4.105 | 273 | 210 | 65 | 63 | 45 | 39 | 16,9% |
| C | 4.105 | 431 | 258 | 129 | 63 | 46 | 31 | 23,3% |
| MIN | 4.105 | 868 | 80 | 348 | 36 | 146 | 26 | 36,6% |
| MM | 3.756 | 593 | 536 | 273 | 204 | 114 | 46 | 47,0% |

Độ lớn |%| theo phân vị (A): P50 = 1,7%, P70 = 3,0%, P90 = 5,7%, P99 = 16,1%. Nghĩa là **ngưỡng 2,5% thấp hơn mức dao động thông thường** của daily-min giữa các NCC.

### B.2 Số tin sau chống lặp, theo chuỗi (12 tháng)

| PA | Tổng | Tin/tuần (trưởng phòng) | Tuần nhiều nhất | Nhẹ | TB | Lớn |
|---|---|---|---|---|---|---|
| A | 832 | 16,0 | 53 | 517 | 228 | 87 |
| B | 637 | 12,2 | 49 | 441 | 123 | 73 |
| C | 578 | 11,1 | 46 | 388 | 137 | 53 |
| MIN | 726 | 13,9 | 55 | 427 | 204 | 95 |
| MM | 1.118 | 21,4 | 62 | 721 | 283 | 114 |

### B.3 Gộp theo vật tư (một tin mỗi vật tư mỗi ngày)

Mỗi vật tư có trung vị **5 kỳ giao hàng** (tối đa 11), nên một cú biến động của thị trường sinh nhiều chuỗi cùng lúc. Ví dụ Khô đậu tương kỳ 12/2026, 01/2027, 02/2027 cùng giảm 3,4-4,3% trong cùng một ngày.

| PA | Tin theo chuỗi | Tin theo vật tư (/tuần) | Tuần nhiều nhất | Nhân viên: TB tin/tuần | p90 tuần | Nhân viên chỉ TB+Lớn: TB tin/tuần | p90 tuần |
|---|---|---|---|---|---|---|---|
| A | 832 | 365 (7,0) | 28 | 1,3 | 8 | 0,5 | 6 |
| MM | 1.118 | 453 (8,7) | 35 | 1,6 | 9 | 0,7 | 6 |

Nếu chỉ gửi ngay mức Trung bình và Lớn (A, gộp theo vật tư): 150 tin/năm, tức ~2,9 tin/tuần cho trưởng phòng. Nâng ngưỡng Nhẹ lên 3,5%: 5,3 tin/tuần. Lên 5%: 2,7 tin/tuần (tính cả mức Nhẹ).

**Tập trung:** Khô đậu tương chiếm 47% và Ngô hạt 21% số tin theo chuỗi, 5 vật tư đầu chiếm 78%. Hai vật tư này có nhiều kỳ giao hàng và báo giá dày nhất.

### B.4 So sánh A và MM (12 tháng, chưa chống lặp)

- Cả hai cùng báo: 1.194 (trong đó **66 điểm ngược chiều**).
- Chỉ A báo: 336. Chỉ MM báo: 572.
- Ví dụ "chỉ A báo": Khô đậu tương giảm dần 13,486 → 12,900 (−4,3% so với điểm đầu), nhưng hai ngày cuối bằng nhau nên MM không thấy bước nhảy.
- Ví dụ "chỉ MM báo" (lỗi nhập liệu): Khô cọ có điểm 5,179 → **9,505** → 5,172. MM so điểm cuối với max 9,505 và báo **−45,6%**, A chỉ báo −0,1%. Max/min nhạy với số nhập sai. Cần cơ chế phát hiện giá bất thường trước khi tính biến động.

### B.5 Nhìn lại các dòng đã chốt mua (mô tả, không kết luận đúng/sai)

101 dòng chốt mua, 71 dòng có điểm giá trước (14 ngày), 55 dòng có điểm giá sau (14 ngày).

| Chỉ số | Kết quả |
|---|---|
| Giá chốt so với khoảng 14 ngày trước (n = 40) | 29/40 dòng có giá chốt **thấp hơn hoặc bằng đáy** 14 ngày trước, 3/40 cao hơn hoặc bằng đỉnh |
| Đáy 14 ngày **sau** chốt so với giá chốt (n = 55) | Trung vị +1,6%. Thấp hơn giá chốt trên 2,5%: 6 dòng. Cao hơn trên 2,5%: 19 dòng |
| Giá mới nhất (trong 30 ngày) so với giá chốt (n = 66) | Trung vị +2,3% |

Lưu ý: người mua thường chọn NCC rẻ nhất trong ngày, nên giá chốt thấp hơn daily-min các ngày trước là điều dễ hiểu, không nên coi là đánh giá chất lượng quyết định. Hệ thống không biết khối lượng và điều kiện hợp đồng.

### B.6 Kết luận từ backtest (vòng 1, phương án A và MM)

> Quyết định cuối cùng (bộ ba quy tắc, 7 ngày làm việc) dựa trên vòng 2 ở B.7.

1. **Lựa chọn A, B, C ít quan trọng hơn cách gộp tin.** Gộp theo vật tư giảm khối lượng hơn một nửa. Mức Nhẹ nên vào bản tin tổng hợp.
2. **MM sinh nhiều tin nhất** (47% điểm bị báo) và nhạy với lỗi nhập liệu. Không nên dùng làm điều kiện gửi.
3. **MIN ("so với giá min") bắt giá tăng rất nhiều** (868 + 348 + 146 lần tăng) nhưng gần như không bắt giá giảm (80 + 36 + 26). Hợp để hiển thị "đắt hơn đáy bao nhiêu", chưa hợp để làm điều kiện gửi tin xu hướng hai chiều.
4. **Cần cơ chế phát hiện giá bất thường** (ví dụ lệch trên 30% so với trung vị của chuỗi) để không báo biến động giả và để trưởng phòng soát lỗi nhập liệu. Có thể làm thành một loại thông báo riêng.
5. **Ngưỡng 2,5% thấp hơn nhiễu thông thường** của daily-min giữa các NCC. Nên cân nhắc 3,5-5% cho mức Nhẹ, hoặc để mức Nhẹ chỉ có trong bản tin tổng hợp.

### B.7 Vòng 2: bộ ba quy tắc, 7 ngày làm việc, giá bất thường

Cách làm: giống vòng 1 nhưng điểm tham chiếu là 7 ngày làm việc (bỏ thứ Bảy, Chủ Nhật khỏi phần đếm), chạy lại trên DB dev (20.893 dòng giá `confirmed`, phiếu chưa hủy, 12 tháng gần nhất). Điểm giá cuối tuần chỉ chiếm 0,6% (63 điểm thứ Bảy, 4 điểm Chủ Nhật).

**Khối lượng tin** (số tin mỗi tuần, tất cả NCC, sau chống lặp D5(a), có chặn bất thường 30%):

| Cấu hình | Theo chuỗi | Gộp theo vật tư | Chỉ Trung bình + Lớn, gộp |
|---|---|---|---|
| 7 ngày lịch (vòng trước), theo chữ | 17,7 | 7,4 | 2,6 |
| 7 ngày làm việc, theo chữ | 20,3 | 8,0 | 3,0 |
| **7 ngày làm việc, nhất quán hướng (đã chốt)** | **19,5** | **7,8** | **2,9** |
| *Phương án A, 14 ngày (vòng 1)* | 16,0 | 7,0 | 2,9 |

Cửa sổ 7 ngày làm việc dài hơn 7 ngày lịch (9 đến 11 ngày lịch) nên có nhiều tin hơn một chút.

**Quy tắc theo chữ và quy tắc nhất quán hướng** (12 tháng, trước chống lặp):

| | Điểm bị báo | Nhiều quy tắc cùng báo | Tin có hướng ngược bước nhảy cuối |
|---|---|---|---|
| Theo chữ (mỗi quy tắc độc lập) | 1.986 | 682 | **403 (khoảng 20%)** |
| Nhất quán hướng (đã chốt) | 1.540 | 641 | 0 |

Quy tắc chính trong bản đã chốt: R1 430 lần, R2 638 lần, R3 472 lần. Cả ba đều đóng góp.

**Giá bất thường** (lệch so với trung vị 7 ngày làm việc, 12 tháng):

| Ngưỡng | Số điểm | Số chuỗi | Số vật tư |
|---|---|---|---|
| ≥ 20% | 17 | 14 | 8 |
| **≥ 30% (mặc định)** | **16** | **13** | **7** |
| ≥ 40% | 15 | 12 | 6 |
| ≥ 50% | 14 | 12 | 6 |

Mẫu: Khô cọ 187 → 5,179; Threonine 25,600 → 970 (−96%); Arginin 74,700 → 2,550 (−97%); Lysine 70% 15,628 → 600 (−96%); Methionine 70,000 → 119,700 (+71%); Cám mỳ 6,075 → 8,400 (+38%). Cụm ngày 15/09/2026 có ít nhất 5 điểm cùng lệch khoảng −96% (Threonine ×2 kỳ, Arginin ×2 kỳ, Lysine ×2 kỳ). Hai điểm cuối (Methionine, Cám mỳ) có thể là biến động thật, đây là lý do cần nút "Giá đúng".

**Mức dao động theo mặt hàng** (điểm bị báo của bản đã chốt, tổng 1.540 điểm):

| Vật tư | Số điểm bị báo | Tỷ lệ | Trung vị \|%\| | P90 \|%\| |
|---|---|---|---|---|
| Khô đậu tương | 805 | 52% | 4,3 | 8,0 |
| Ngô hạt | 456 | 30% | 3,3 | 5,2 |
| Methionine | 41 | 3% | 4,9 | 13,7 |
| Tryptophan (CJ) | 27 | 2% | 4,0 | 6,9 |
| Valine | 17 | 1% | 3,8 | 7,9 |
| Fermented Soybean Meal | 17 | 1% | 3,5 | 4,7 |

Khô đậu tương và Ngô hạt chiếm 82% số điểm bị báo. Đây là lý do cần ngưỡng theo từng mặt hàng (D4).
