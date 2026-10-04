# Rà Soát Tài Liệu Thiết Kế Thông Báo Biến Động Giá Qua Telegram Và Chatbot AI

## Trạng Thái

**Đã thảo luận và áp dụng (2026-10-04).** Bốn quyết định Q1 đến Q4 đã được chốt (xem mục "Kết Quả Thảo Luận Và Áp Dụng" ngay dưới). Các mục S, N, T, Y đã được áp dụng vào tài liệu cha và kế hoạch 1A (ngoại trừ các mục ghi "chưa làm"). Việc tiếp theo: soạn kế hoạch 1B riêng.

Đối tượng rà soát: [plan-telegram-bien-dong-gia-va-chatbot-ai.md](plan-telegram-bien-dong-gia-va-chatbot-ai.md) (tài liệu cha, khoảng 950 dòng, đã qua nhiều vòng sửa) đối chiếu với [plan-telegram-giai-doan-1a-nen-tang-lien-ket.md](plan-telegram-giai-doan-1a-nen-tang-lien-ket.md) (kế hoạch 1A).

Cách rà soát: 3 local agent độc lập chạy song song ngày 2026-10-03, mỗi agent một góc nhìn:
- **Nhất quán và chất lượng tài liệu:** đọc toàn bộ, đối chiếu CONTEXT.md, Requirements.txt, kế hoạch 1A.
- **Chính xác kỹ thuật:** mở code thật, chạy truy vấn chỉ đọc trên DB dev, thử `EXPLAIN ANALYZE` và cú pháp `SET TRANSACTION READ ONLY`.
- **Kiểm lại số liệu backtest:** viết lại độc lập phép tính theo đặc tả trong tài liệu, so với từng con số, rồi đo thêm các giả định.

Các phát hiện dưới đây đã được gộp, loại trùng. Số dòng của tài liệu cha **không** được dùng làm vị trí (đã thay đổi theo thời gian), vị trí ghi theo tên mục.

## Kết Quả Thảo Luận Và Áp Dụng (2026-10-04)

### Quyết định

| Mã | Quyết định | Áp dụng vào tài liệu cha |
|---|---|---|
| **Q1** | Đổi D6 theo đề xuất: nguồn kích hoạt là version **không do tài khoản seed admin tạo** và có độ trễ **không quá 3 ngày làm việc**. Nhận biết import bằng tài khoản seed admin | D6, QĐ-16, Mục 3 (tham số mặc định), RR-2, B.8 |
| **Q2** | Đồng ý đề xuất: gộp trong một lần quét và chỉ gửi bổ sung khi leo thang; ảnh kèm caption ngắn, chi tiết gửi bằng tin văn bản; không sửa tin cũ | D5, QĐ-17, 4.2, 4.5 (`price_alert_messages`) |
| **Q3** | Đồng ý đề xuất: loại ở mức dòng rồi tính lại daily-min; tham chiếu gắn cờ 30 ngày; gộp cụm; người nhập nhận tin không có nút; chỉ người có `receive_all` và admin bấm được; có nhắc và hết hạn | D12, QĐ-18, 4.5, 4.6 |
| **Q4** | Đồng ý đề xuất. **Trưởng phòng có quyền bật/tắt tính năng** (`price_alerts.manage` gồm cả bật/tắt) | 4.6, 4.9, QĐ-19 |

### Các lựa chọn của tôi khi áp dụng (cần xác nhận lại nếu không đồng ý)

1. **Q4(a) migration cấp quyền:** chọn **phương án (a)** (migration tự chèn `permissions` rồi gán cho `manager`, chịu được thiếu role) thay vì (b) (gán qua giao diện Roles). Lý do: không phụ thuộc thao tác tay sau mỗi lần dựng môi trường, và test được.
2. **Q3, mục 6 (cảnh báo ngay lúc nhập):** ghi vào **backlog** ngoài phạm vi 1A đến 1C, không làm ngay.
3. **Thứ bậc các cờ (Q4(d)):** cờ môi trường là điều kiện cần, cờ DB là điều kiện đủ (theo đề xuất ban đầu).
4. **Giá trị cụ thể** cho các tham số mà đề xuất để mở (thời hạn nhắc 2 ngày làm việc, hết hạn 7 ngày làm việc, gộp cụm từ 3 cờ, trần 30 tin mỗi lần quét, chống lặp 14 ngày lịch, cửa sổ gắn cờ 30 ngày, mốc D8 theo `received_date`, lưu giữ 180 ngày, `daily_user_limit` 20) là **mặc định đề xuất, chưa được xác nhận từng giá trị**. Chúng nằm trong bảng "Tham số mặc định của 1B" (Mục 3 của tài liệu cha) và Mục 9.2.
5. **Áp dụng toàn bộ nhóm S, N, T, Y** theo cách đã mô tả, vì yêu cầu là "cập nhật lại các tài liệu bị ảnh hưởng bởi nội dung review". Nếu muốn giữ lại cách cũ ở mục nào thì cho biết mã mục.

### Trạng thái áp dụng

| Nhóm | Vị trí đã sửa trong tài liệu cha |
|---|---|
| S1, S2, S3, S4 | 4.1 (quét an toàn, khóa, dòng ứng viên), D2 mục 5, 4.5 (UNIQUE từng loại sự kiện), 4.8 |
| S5, S6 | 4.8 (`timezone`, quan sát worker) |
| S7, S8 | 4.5 (lược đồ mới: `price_alert_messages`, `price_alert_scan_state`, FK `ON DELETE`, CHECK, tên cột `*_from_percent` và `large_over_percent`, chỉ mục), D4, D9, D10 |
| S9 | 4.3 (hàm `get_daily_min_series`), 5.2 |
| S10, S11 | 4.5, 4.9, Mục 8, Phụ lục A (`created_via` đầy đủ điểm chạm; icon PrimeIcons có sẵn) |
| S12, S14 | 4.2 (ví dụ CNF, caption và biểu đồ khớp nhau, tie-break), D2 |
| S13 | D5, D8, bảng tham số mặc định |
| S15 | 4.5, 4.9 (icon và bộ lọc đọc `quote_versions.created_via`) |
| **S16** | **Chưa làm:** đưa script backtest vào repo (`backend/scripts/analysis/`). Đã ghi vào Phụ lục B và Mục 9.2. Phụ lục B đã bổ sung định nghĩa các phương án B, C, MIN, MM |
| S17, S18, S19 | 4.2, D5, 4.6 (giới hạn Telegram); 5.1 (thứ tự dedupe khi chuyển sang arq); 4.3 (`asyncio.to_thread`) |
| S20, S21, S22 | 4.8, RR-24; Mục 8 (runbook); 4.7 |
| S23 đến S29 | 5.2, 5.3, 5.4, 5.5, 5.6 |
| N1 đến N18 | Mục 1.2 (ghi nguồn từng số), D3, D12, B.1 đến B.8 |
| T1 | Ký hiệu `RR-n` cho rủi ro, sửa tham chiếu "Mục 6" |
| T2, T3, T4 | Mục 0.1 (QĐ-1 theo QĐ-12, thêm QĐ-16 đến 19), Mục 0 viết lại, Mục 9.1 (mã H, cột QĐ) |
| T5, T6 | Nhiều chỗ: Mục 7, 4.2, 4.5, 4.6, 4.9, Mục 8, 9.2 |
| T7 | Mục lục, Phụ lục A, định nghĩa phương án ở đầu Phụ lục B, chú thích vị trí D12 |
| T8, T9, T10 | Quy ước số, VNĐ thay "đ", dùng "vật tư", bỏ ngôi thứ nhất và nhận định "tin tốt/xấu", bỏ tên "Gemini Advanced" |
| T11 | D12, 4.1, 4.6 |
| Y1 đến Y6 | Mục 4.4 đến 4.8, RR-9, Mục 7, Mục 9, Phụ lục A; K15 vào 5.3 và slice 2B; thuật ngữ vào Mục 2; kế hoạch 1A đồng bộ ngược |

---

## Cách Đọc

| Mã | Loại | Nghĩa |
|---|---|---|
| **Q** | Cần quyết định | Chọn một hướng, ảnh hưởng thiết kế 1B. Nên chốt trước khi viết migration đầu tiên của 1B |
| **S** | Sửa thẳng | Có đáp án rõ, chỉ cần đưa vào tài liệu |
| **N** | Số liệu | Đính chính con số hoặc ghi rõ nguồn |
| **T** | Thống nhất | Lỗi thời, mâu thuẫn, ký hiệu, định dạng, ngôn ngữ |
| **Y** | Đồng bộ | Chỗ tài liệu cha phải cập nhật theo kế hoạch 1A |

Mức: **NGHIÊM TRỌNG** (sai thiết kế hoặc gây lỗi thật), **TRUNG BÌNH**, **NHẸ**.

## Kết Luận Tóm Tắt

- **Các số cốt lõi tái hiện đúng:** 1.540 điểm bị báo, 19,5 / 7,8 / 2,9 tin mỗi tuần, 16 điểm bất thường ở 13 chuỗi và 7 vật tư, độ nhạy ngưỡng 20/30/40/50%, bảng theo vật tư (805 / 456 / 41 / 27 / 17 / 17), các ví dụ số học của D2, 101 dòng chốt mua. Cửa sổ 7 ngày làm việc được đối chiếu với `numpy.busday_offset` trên 1.101 ngày, không sai lệch.
- **Kiến trúc khả thi.** Tái dùng được arq, Redis, EmailService, nginx, `QuoteService`. Không có xung đột tên bảng, index hay Alembic head (`20260824_1000`) với các bảng đề xuất.
- **Vấn đề nằm ở hai chỗ:**
  1. **Mẫu dữ liệu của backtest không đại diện cho tải thật.** 82,5% dòng trong 12 tháng là dữ liệu import một lần, dữ liệu nhập thật chỉ có 6,3 tuần. Tải thực tế cao hơn con số trong tài liệu khoảng 1,3 đến 3 lần.
  2. **Một số chi tiết cốt lõi của 1B chưa được xác định:** đơn vị "tin", vòng đời giá bất thường, cơ chế quét watermark, cấp quyền cho trưởng phòng, quyền truy cập giao diện cấu hình.
- **Kế hoạch 1A không bị ảnh hưởng**, trừ việc tài liệu cha chưa theo kịp (nhóm Y) và điều kiện bảo mật K15 chưa nằm trong phần chatbot của tài liệu cha.

---

## 1. Cần Quyết Định (Q)

Mỗi mục có ô trạng thái để điền khi thảo luận.

### Q1. D6 "bỏ qua phiếu nhập lùi" quá thô — NGHIÊM TRỌNG

**Vấn đề.** D6 hiện chỉ cho version `is_backfilled=false` sinh tin. Đo trên dữ liệu thật cho thấy điều kiện này loại phần lớn dữ liệu nhập thật của nhân viên.

**Bằng chứng** (đo bằng SQL trên DB dev, kỳ 12 tháng tới 2026-10-02):

| Chỉ tiêu | Số đo |
|---|---|
| Dòng `is_backfilled=false` | 565 / 9.798 = 5,8% |
| Dòng import (tài khoản seed admin, toàn bộ tạo ngày 19/08/2026) | 8.082 = 82,5% |
| Dòng nhân viên nhập lùi (`is_backfilled=true`) | 1.151, trong đó trễ ≤ 1 ngày: 220, ≤ 3 ngày: 373, ≤ 7 ngày: 522 |
| Giai đoạn có nhập thật | 20/08 đến 02/10/2026 (44 ngày, 6,29 tuần), 7 người nhập |
| Dòng nhập thật theo tuần ISO 34 đến 40 | 89, 175, 20, 96, 49, 45, 91 |
| Nhập thật: chênh `confirmed_at` so với `received_date` | 562 dòng chênh 0 ngày, 3 dòng chênh 1 ngày |
| Nhập lùi của nhân viên: chênh | trung vị 13 ngày, P75 76, P90 179, tối đa 316 |

Hành vi code: `_validate_backfill` chỉ chạy khi tạo hoặc sửa bản nháp, **không chạy lúc chốt** (`quote_service.py`). Bản nháp tạo hôm trước rồi chốt hôm nay vẫn có `is_backfilled=false` dù `received_date` đã cũ. Mô tả "ép true mỗi khi `received_date` < hôm nay" ở D6 và R2 thiếu chi tiết này.

**Tải tin theo từng cách xác định nguồn kích hoạt** (cùng giai đoạn 20/08 đến 02/10, đơn vị tin mỗi tuần hoạt động; "gộp" là gộp theo vật tư, "TB+L" là Trung bình và Lớn):

| Kịch bản | Theo chuỗi | Gộp | TB+L gộp |
|---|---|---|---|
| S0: mọi dòng đều kích hoạt (cách backtest hiện tại, chia cho tuần hoạt động) | 31,3 | 19,2 | 8,1 |
| **S1: chỉ ngày có dòng nhập thật (đúng D6 hiện tại)** | **17,2** | **10,3** | **3,7** |
| S2: loại hoàn toàn dòng nhập lùi | 8,7 | 5,3 | 2,2 |

Nếu chia cho 52 tuần thay vì 6,3 tuần hoạt động thì S1 chỉ ra 2,08 / 1,25 / 0,44, **thấp giả tạo**. Số công bằng là 10,3 tin gộp mỗi tuần (tài liệu ghi 7,8). Tin gộp theo tuần ISO 34 đến 40: 3, 18, 3, 11, 7, 9, 14, dao động rất mạnh. Số tin gộp theo tháng tăng dần: 22 (10/2025), 23, 24, 23, 21, 32, 29, 27, 37, 35, 55 (08/2026), 77 (09/2026, khoảng 17,9 tin mỗi tuần). Trung bình 8 tuần cuối: 16,6 tin gộp và 7,0 tin TB+L mỗi tuần.

**Phương án thay thế: cho phép nhập trễ ngắn.** Nguồn kích hoạt là dòng do nhân viên nhập (không phải tài khoản import) với độ trễ cho phép:

| Độ trễ cho phép | Theo chuỗi | Gộp | TB+L gộp |
|---|---|---|---|
| ≤ 0 ngày (tương đương D6 hiện tại) | 17,0 | 10,3 | 3,7 |
| ≤ 1 ngày | 24,0 | 14,8 | 5,9 |
| ≤ 3 ngày | 28,2 | 17,7 | 7,3 |
| ≤ 7 ngày | 31,5 | 19,6 | 8,3 |
| mọi dòng nhân viên | 45,8 | 27,4 | 11,5 |

Số tin theo người nhận (nhân viên, theo D8): mỗi tin có trung bình khoảng 2 người nhận, mỗi nhân viên nhận khoảng 2,7 đến 2,9 tin mỗi tuần, người nhiều nhất khoảng 7,6 tin mỗi tuần. Tài liệu hiện ghi 1,3.

**Đề xuất.** Thay `is_backfilled=false` bằng "không phải import (tài khoản seed hoặc tác vụ backfill) **và** `received_date` cách ngày chốt không quá 1 ngày làm việc (xét 3 ngày)", kết hợp watermark triển khai. Cách này tránh bão tin do import mà không bỏ phí tin trễ vài ngày. Đo lại bằng dry-run ở chế độ replay trước khi chốt con số.

**Câu hỏi cần chốt:** (a) đổi D6 theo hướng trên hay giữ nguyên? (b) ngưỡng trễ 1 hay 3 ngày làm việc? (c) cách nhận diện phiếu import: tài khoản seed admin hay cần đánh dấu riêng (nếu admin vừa nhập tay vừa là tài khoản seed thì bị loại nhầm)?

**Hệ quả kèm theo:** dry-run của 1B cần chế độ "replay" bỏ qua D6, vì DB dev gần như toàn dữ liệu nhập lùi, dry-run theo D6 sẽ ra gần như không có tin. Các số 19,5 / 7,8 / 2,9 phải ghi rõ là "đo trên mọi điểm, không phải dự báo cho production".

**Trạng thái:** [x] **Đã quyết định 2026-10-04:** đổi D6 theo đề xuất. Độ trễ **3 ngày làm việc**, nhận biết import bằng **tài khoản seed admin**. Đã áp dụng (D6, QĐ-16).

### Q2. "Một tin mỗi vật tư mỗi ngày" chưa khớp thiết kế (D5b) — NGHIÊM TRỌNG

**Vấn đề.**
- Sự kiện được tạo theo `(version, vật tư, kỳ giao hàng)`. `price_alert_deliveries` có `UNIQUE (event_id, user_id)`. Cron quét mỗi 1 đến 2 phút. Không có thực thể "tin" gộp nhiều sự kiện.
- Con số 7,8 tin mỗi tuần giả định đúng một tin mỗi vật tư mỗi ngày, trong khi backtest chấm mỗi ngày một lần ở **cuối ngày**.

**Bằng chứng (đo thêm).**
- Với dữ liệu nhập thật, 13,9% điểm (67/483) có từ 2 phiên bản trong ngày, và 40/67 điểm daily-min **đổi** sau lần chốt đầu.
- Phát lại theo từng lần chốt (thay vì cuối ngày): tin sau chống lặp 114 so với 108 (+5,6%). 10/66 ngày-vật tư (15%) có tin ở từ 2 thời điểm khác nhau. 1 ngày-chuỗi đổi hướng trong ngày.
- 70,6% điểm bị báo có nhà cung cấp rẻ nhất **khác** với điểm trước. Phần lớn "biến động" là đổi nhà cung cấp rẻ nhất, mà tin hiện không nêu điều đó.

**Chưa trả lời được trong tài liệu:**
- Quét lúc 09:01 gửi tin, 14:00 có báo giá khác cùng vật tư: gửi tin thứ hai hay sửa tin cũ?
- Leo thang trong ngày (Nhẹ rồi Trung bình): D5(a) cho gửi (mức khác), D5(b) nói một tin mỗi ngày.
- Báo giá thứ hai trong ngày không đổi daily-min có sinh sự kiện không?
- Khi các kỳ giao hàng khác hướng thì tiêu đề và biểu tượng ra sao? Tài liệu cũng chưa có ví dụ tin gộp nhiều kỳ.
- Caption ảnh Telegram giới hạn 1.024 ký tự, tin gộp trung vị 5 kỳ giao hàng (có vật tư tới 10 chuỗi) sẽ vượt.

**Phương án.**
- **(i) Chỉ gộp trong một lần quét.** Đơn giản, không sửa tin. Số liệu cần ước lại theo thời gian thực.
- **(ii) Gộp theo ngày bằng cách sửa tin cũ** (`editMessageText`/`editMessageCaption`). Gọn cho người đọc, phức tạp hơn khi cài.
- **(iii) Chỉ gửi bổ sung khi mức leo thang** trong cùng ngày, các thay đổi cùng mức không sinh tin mới.

**Đề xuất.** (i) kết hợp (iii), ảnh kèm caption ngắn, phần chi tiết các kỳ giao hàng gửi bằng `sendMessage` (giới hạn 4.096 ký tự). Thêm khóa nhóm `(material_id, ngày địa phương)` vào `price_alert_deliveries` hoặc một bảng `price_alert_messages` để idempotent. Mỗi tin ghi rõ "điểm giá có thể thuộc nhà cung cấp khác với lần trước".

**Trạng thái:** [x] **Đã quyết định 2026-10-04:** đồng ý đề xuất. Đã áp dụng (D5, QĐ-17).

### Q3. Giá bất thường (D12) có bốn lỗ hổng — NGHIÊM TRỌNG

**(a) Loại ở mức dòng, rồi tính lại daily-min.**
- Daily-min là min theo từng dòng của mọi nhà cung cấp, trong khi cờ gắn vào `quote_line_id`. Tài liệu chưa nói phải loại dòng bị cờ **trước** khi lấy min của ngày.
- Ví dụ thật: Threonine kỳ 11/2026 ngày 15/09/2026, dòng 970 VNĐ/KG (chốt 14:45) là **min của ngày**, nhưng cùng ngày một version khác có 26.000. Daily-min đúng sau khi loại dòng 970 là 26.000.
- Đo thêm: chỉ **1 dòng** trong 12 tháng bị daily-min "ẩn" (lệch từ +30% so với trung vị tham chiếu nhưng không phải min của ngày): Lysine 70% kỳ 09/2026, 23.500 (+49%), đã nhập lùi. Lỗi nhập **thấp** luôn thành min của ngày nên luôn lộ ra (16/16). Vì vậy việc kiểm tra ở mức dòng bổ sung rất ít, nhưng việc **loại** ở mức dòng là cần thiết.
- Đơn vị xét (daily-min hay từng dòng) chưa được nêu rõ: dòng phép thử nói ở mức daily-min, còn cột `quote_line_id` là mức dòng.

**(b) Điểm tham chiếu bị "nhiễm độc".**
- Điểm đầu tiên của chuỗi chưa có tham chiếu nên không bị gắn cờ. Khi điểm bị gắn cờ trôi ra khỏi cửa sổ, điểm kế tiếp thành "điểm đầu" và được nhận vô điều kiện.
- Thực tế: Tryptophan (CJ) 3.565 (15/09, −96,2%) được nhận làm tham chiếu. Khô cọ có chuỗi 187 → 5.165 → 5.179 → 9.505 → 5.172: điểm sai thật là **187** (190 USD gõ vào ô VNĐ/KG), còn **9.505 là giá đã được sửa** từ 93.245. Kết quả: 3 cờ giả lên các điểm đúng và 0 cờ lên điểm 187.
- 12/16 điểm bất thường chỉ dựa trên đúng 1 điểm tham chiếu (3 điểm dựa trên 3 điểm, 1 điểm dựa trên 2).
- Methionine +71% (17/03/2026) là bước nhảy **thật và bền** (60.200 → 70.000 → 119.700 → 124.700 → 144.700).
- Đo: 11,2% điểm daily-min (509/4.532) không có điểm trước trong cửa sổ, trong đó 277 là điểm đầu chuỗi và 232 sau khoảng trống hơn 7 ngày làm việc (trung vị 14 ngày, P90 41, tối đa 240). Trong 232 điểm sau khoảng trống, 127 (55%) lệch từ 2,5% so với điểm cũ gần nhất (44 Nhẹ, 51 Trung bình, 32 Lớn), **bị bỏ qua im lặng**. 69/303 chuỗi chỉ có 1 điểm trong 12 tháng.

**(c) Cờ chưa duyệt gây spam.**
- Không có quy tắc khi cờ ở trạng thái `pending` mà các điểm sau (đúng, cùng mặt bằng mới) tiếp tục lệch trên 30% so với cửa sổ chưa có điểm đầu. Mỗi điểm sinh thêm một tin bất thường cho tới khi qua 7 ngày làm việc hoặc có người bấm nút.
- Cụm ngày 15/09/2026 có 6 điểm cùng lệch khoảng −96% (Threonine ×2, Arginin ×2, Lysine ×2), cộng Khô cọ +2.662%. Ngoài ra còn Tryptophan (CJ) ×2 ngày 08/09 và Arginin ngày 29/09. Tin bất thường "gửi ngay vì hiếm" sẽ thành 6 tin cùng lúc.
- Khi "Giá đúng" được bấm: tính lại theo cửa sổ gốc của điểm đó hay cửa sổ hiện tại? Tin tính lại có gửi muộn không, hay chỉ làm điểm đó hợp lệ cho các lần sau? Điểm kế tiếp (Q) có tự được đánh giá lại không?
- Điểm bất thường trong version nhập lùi: D6 bỏ qua version nhập lùi nên không gắn cờ, nhưng điểm sai nhập lùi vẫn làm tham chiếu và làm lệch R1/R3 của điểm thật kế tiếp.

**(d) Ai bấm nút, vòng đời xem xét.**
- D12 gửi tin cho "trưởng phòng và người nhập phiếu" kèm hai nút. Mục 4.6 nói chỉ người có `price_alerts.receive_all` được bấm. Nhân viên nhận nút mà không bấm được.
- Chưa có đặc tả: hai trưởng phòng bấm khác nhau cùng lúc, nội dung tin sau khi bấm, không ai bấm (điểm bị loại vô thời hạn, không nhắc, "có thể thêm endpoint web sau"), người nhập phiếu bị xóa (`created_by_id` NULL), bị khóa hoặc chưa liên kết Telegram. "Người nhập phiếu" là `quotes.created_by_id` hay `quote_versions.created_by_id` cũng chưa được nêu (lỗi nhập sai thường do người tạo version).

**Quan sát bổ sung.**
- 9/16 điểm bất thường có tỷ lệ trung vị so với giá mới từ 25,8 đến 29,3. Tỷ giá USD hiện khoảng 26.100 đến 26.290 nên đây là dấu hiệu rất mạnh của **gõ giá USD/MT vào ô VNĐ/KG**. Có thể làm cảnh báo ngay lúc nhập (tính năng riêng, ngoài phạm vi 1A đến 1C).
- 41 version đã bị `superseded` trong 6 tuần (khoảng 5,9 mỗi tuần): 12 có đổi giá, 8 đổi từ 2,5%, 5 đổi từ 30%. Ví dụ Vitamin A 673 → 473.780, Whey permeat 850 → 22.635, Khô cọ 93.245 → 9.505. Con số "16 điểm bất thường" là **cận dưới**.
- Trong giai đoạn nhập thật: 10 điểm bất thường trong 6,3 tuần (khoảng 1,6 điểm mỗi tuần, khoảng 1 tin mỗi tuần sau gộp), cộng 5 phiên bản sửa giá từ 30%. Con số "0,3 điểm mỗi tuần" của tài liệu là cho 12 tháng toàn dữ liệu import, thấp hơn thực tế nhập thật 5 lần hoặc hơn.

**Đề xuất.**
1. Dòng bị loại = dòng có sự kiện `anomaly` ở trạng thái `pending` hoặc `rejected`. Daily-min tính sau khi loại các dòng đó. Đánh giá bất thường ở mức dòng của version vừa chốt, và áp dụng cả với version nhập lùi (chỉ để gắn cờ, không sinh tin biến động).
2. Việc **gắn cờ** dùng điểm hợp lệ gần nhất trong khoảng dài hơn (khoảng 30 ngày) thay vì cửa sổ 7 ngày làm việc, chỉ cho mục đích gắn cờ, và ghi "độ tin cậy thấp" khi chỉ có 1 điểm tham chiếu.
3. Gộp cụm: nhiều cờ cùng ngày (ví dụ từ 3) gộp thành một tin tóm tắt. Cờ `pending` quá N ngày thì hết hạn có thông báo. Điểm kế tiếp cùng mặt bằng với điểm đang `pending` không sinh tin mới mà gắn vào cùng thẻ.
4. Nhân viên (người nhập) nhận tin **không có nút**, chỉ có liên kết sửa phiếu. Chỉ người có `price_alerts.receive_all` (và admin) bấm được. Thêm `reviewed_by`, sửa nội dung tin sau khi bấm, bấm lần hai là no-op. Thêm đường xem xét trên web (hoặc ghi rõ là việc của 1C).
5. Định nghĩa trung vị cho 1 hoặc 2 điểm (số chẵn lấy trung bình hai điểm giữa).
6. Quyết định có làm cảnh báo lúc nhập (USD gõ vào ô VNĐ/KG) như một tính năng riêng hay không.

**Trạng thái:** [x] **Đã quyết định 2026-10-04:** đồng ý đề xuất. Đã áp dụng (D12, QĐ-18). Cảnh báo ngay lúc nhập chuyển vào backlog.

### Q4. Cấp quyền cho role `manager` và vị trí giao diện cấu hình — NGHIÊM TRỌNG

**(a) Migration cấp quyền sẽ chạy rỗng.**
- Mẫu `20260729_0810_restrict_quotify_settings_user_role.py` chỉ chạy `DELETE FROM role_permissions ...`, không có `INSERT`.
- Bảng `permissions` chỉ được điền bởi `AuthSeedService._ensure_permissions` (`auth_seed.py`), không bởi migration. Runbook chạy migrate (mục 9.5) **trước** seed (9.6). Compose test cũng `alembic upgrade head` rồi mới seed.
- Khi migration chạy lần đầu, hàng `permissions` cho `price_alerts.*` chưa tồn tại. Câu `INSERT ... SELECT ... FROM permissions WHERE code=...` ghi 0 dòng, không báo lỗi.
- `permissions.id` là UUID không có `server_default`, nên `INSERT` thô phải tự gọi `gen_random_uuid()`.
- DB test và dev mới không có role `manager`, migration phải chịu được trường hợp này.
- Hậu quả: trưởng phòng là người nhận chính (D7) nhưng không có `price_alerts.receive_all` và `price_alerts.manage`.

**Phương án.**
- **(a)** Migration tự `INSERT INTO permissions(id, code) VALUES (gen_random_uuid(), ...) ON CONFLICT (code) DO NOTHING`, rồi `INSERT INTO role_permissions SELECT ... WHERE roles.name='manager'` có `ON CONFLICT DO NOTHING`. Seed sau đó vẫn idempotent. Kèm test migration trên DB có và không có role `manager`.
- **(b)** Bỏ migration, ghi vào runbook bước "gán quyền cho role manager trong giao diện Roles sau bước seed".
- Lưu ý: cả hai phương án gắn với tên `manager` (migration) hoặc thao tác tay. Tài liệu cha nói không nên gắn logic vào tên role.

**(b) Giao diện cấu hình ngưỡng.**
- Mục 4.9 đặt panel ngưỡng trong `QuotifySettingsPage.vue`. Route `/quotify-settings` yêu cầu `quotify_settings.read` (`router/index.ts`). Role `manager` **không có** quyền này (đã truy vấn DB: khác biệt duy nhất giữa `manager` và `user` là `quotes.correct_user_quotes`; migration `0810` cố ý gỡ `quotify_settings.*` khỏi `user`). Trưởng phòng không vào được trang để sửa ngưỡng.
- **Đề xuất:** trang mới `/price-alert-settings` có guard `price_alerts.manage`, đặt trong sidebar. Không cấp `quotify_settings.read` cho `manager`.

**(c) Phạm vi quyền `price_alerts.manage`.** Quyền này gồm cả bật/tắt toàn bộ tính năng (`PUT /price-alert-settings` có `is_enabled`). Quyết định D4 chỉ chốt "admin và trưởng phòng sửa ngưỡng theo mặt hàng". Cần xác nhận trưởng phòng có được bật/tắt cả tính năng không, hay tách quyền.

**(d) Thứ bậc các cờ.** Có bốn cờ cùng chức năng: `TELEGRAM_ENABLED` (môi trường), `price_alert_settings.is_enabled` (DB), `CHATBOT_ENABLED` (môi trường), `chatbot_settings.is_enabled` (DB). Cần quy định thứ bậc (đề xuất: cờ môi trường là điều kiện cần, cờ DB là điều kiện đủ).

**Trạng thái:** [x] **Đã quyết định 2026-10-04:** đồng ý đề xuất, **trưởng phòng có quyền bật/tắt tính năng**. Đã áp dụng (4.6, 4.9, QĐ-19). Chọn phương án (a) cho migration.

---

## 2. Sửa Thẳng (S)

### Cơ chế quét và vận hành

| Mã | Mức | Nội dung | Cách sửa |
|---|---|---|---|
| S1 | NGHIÊM TRỌNG | **Watermark có thể bỏ sót version.** `confirmed_at` được gán bằng `datetime.now()` phía ứng dụng trước khi commit (`quote_service.py` ở hai chỗ chốt). Giao dịch T1 có `confirmed_at = t1` nhưng commit chậm hơn T2 (`t2 > t1`), cron thấy T2 rồi đẩy watermark qua t1, T1 không bao giờ được quét. Import commit mỗi 200 nhóm nên `confirmed_at` của nhóm đầu có thể sớm hơn thời điểm commit nhiều giây. Câu "không mất sự kiện vì watermark nằm trong DB" thiếu quy tắc tiến watermark | Quét `confirmed_at > watermark − 5 phút` kết hợp `INSERT ... ON CONFLICT DO NOTHING` (idempotent). Mỗi version xử lý trong savepoint riêng, lỗi một version được ghi và bỏ qua, không chặn watermark. Đặt watermark = thời điểm chuyển `is_enabled` từ false sang true, **mỗi lần bật** (D6 "thời điểm triển khai" sẽ gây bão tin nếu bật cờ sau vài tuần hoặc bật lại). Tách watermark khỏi bảng cấu hình singleton để cron không giữ khóa dòng làm nghẽn `PUT` cấu hình. Lọc `NOT is_backfilled` hoặc điều kiện của Q1 ngay trong SQL nhưng vẫn cho watermark tiến qua các version bị lọc |
| S2 | TRUNG BÌNH | **Khóa chống chạy chồng của cron.** `poll_and_run_scheduled_backups` dùng `with_for_update(skip_locked=True)` nhưng commit trong vòng lặp, trước khi cập nhật `next_run_at` nên khóa dòng đã nhả. Mẫu chỉ an toàn nhờ arq cron `unique=True` (dedupe theo tên và mốc thời gian), vốn **không** chặn chạy chồng khi job trước chưa xong (quét dài hơn 1 đến 2 phút thì tick sau chạy song song, `max_jobs` mặc định 10) | Dùng `pg_try_advisory_xact_lock` hoặc khóa Redis có TTL suốt lần quét. Giữ giao dịch DB ngắn. Tách giai đoạn tạo sự kiện và gửi tin khỏi giai đoạn gọi Telegram |
| S3 | TRUNG BÌNH | **UNIQUE gây IntegrityError.** `UNIQUE(quote_version_id, material_id, delivery_month, kind)` trong khi `quote_lines` cho phép nhiều dòng trùng khóa này (DB dev có 1.853 nhóm, chỉ trong dữ liệu backfill). Với `kind='anomaly'`, hai dòng bất thường cùng khóa gây lỗi. Nếu cả lần quét nằm trong một giao dịch thì watermark không bao giờ tiến | Đổi UNIQUE của `anomaly` thành `(quote_version_id, quote_line_id, kind)`. Dùng savepoint theo S1 |
| S4 | TRUNG BÌNH | **Version điều chỉnh và xóa dòng.** Version mới là snapshot đầy đủ, sao chép mọi dòng. Quét theo `confirmed_at` chỉ biết version, không biết dòng nào đổi giá. Câu "cần so với giá bản cũ để không báo kép" mâu thuẫn R4 "loại `superseded` khi tính baseline". `delete_confirmed_line` clone toàn bộ dòng rồi chốt, không có cờ phân biệt "xóa dòng" với "sửa giá" (chỉ có chuỗi `correction_reason` do người dùng nhập) | Định nghĩa "dòng ứng viên" = dòng có giá (hoặc ngày nhận) khác snapshot trước, hoặc dòng mới thêm. Lấy version nguồn qua `superseded_by_version_id`. Xóa câu "so với giá bản cũ". Nêu rõ `delete_confirmed_line` làm daily-min của ngày đổi nhưng không phát tin |
| S5 | TRUNG BÌNH | **arq hỗ trợ `timezone`** (arq 0.26.3). R8 và Mục 4.8 nói cron luôn theo UTC là lỗi thời một phần | Đặt `timezone = ZoneInfo("Asia/Ho_Chi_Minh")` trong `WorkerSettings` và test. Việt Nam không có DST. Vẫn cần `last_digest_local_date` (S7) vì worker tắt đúng 08:00 thì mất bản tin ngày đó |
| S6 | TRUNG BÌNH | **Worker không được Prometheus scrape.** `prometheus.yml` chỉ scrape `backend:8000/metrics`. Metric `quotify_*` do tiến trình FastAPI phát ra, nên counter đặt trong worker không bao giờ xuất hiện. Alert rules còn tên `fastapivue_*` | Ghi tổng kết mỗi lần quét vào DB (bảng `price_alert_scan_runs`) để backend phát gauge khi scrape, hoặc chạy `start_http_server` trong `on_startup` của worker và thêm job vào `prometheus.yml`. Thêm cảnh báo watermark trễ quá N phút |
| S7 | TRUNG BÌNH | **Lược đồ chưa đủ.** (1) `user_alert_preferences` không biểu diễn D9 (admin chỉ nhận khi bật, mặc định tắt) và D10 (mặc định theo vai trò): cột `is_enabled` mặc định true, `min_level` mặc định `'light'`. QĐ-14 nói "trưởng phòng nhận mọi tin" mâu thuẫn với mặc định mức Trung bình. (2) Admin có mọi quyền nên truy vấn người nhận theo `role_permissions` chọn cả admin, trong khi `has_permission` bypass theo tên role. (3) Không có `last_digest_local_date`. (4) `price_alert_deliveries.user_id` và `telegram_account_id` chưa ghi `ON DELETE`: xóa người dùng đã nhận tin bị chặn bởi `NO ACTION`. (5) `price_alert_events` không đủ trường để dựng lại tin (so sánh phụ, giá CNF mới và tham chiếu, danh sách giá gần đây của tin bất thường), tính lại lúc gửi có thể ra nội dung khác sau khi dữ liệu đổi. (6) Khối CNF so với điểm tham chiếu của quy tắc nào chưa quy định (ví dụ so với 345 USD ngày 30/09 là điểm của R1, trong khi lý do chính là R2). (7) Chưa nói `is_enabled=false` hoặc `min_level` có chặn tin giá bất thường (level NULL) hay không. (8) `price_alert_events`: `direction`, `received_date_ref`, `price_ref` chưa ghi ý nghĩa với `kind='anomaly'`. (9) Trạng thái `skipped`, `digest_queued` chưa mô tả chuyển trạng thái, chưa nói bỏ qua tài khoản `blocked`. (10) Chưa có trạng thái `sending`, chưa có chính sách dọn `telegram_processed_updates` và `price_alert_events` tăng vô hạn | `min_level` NULL nghĩa là mặc định theo vai trò. Thêm `admin_receive_all bool default false`. Thêm `last_digest_local_date`. Resolver loại admin tường minh bằng tên role và loại tài khoản seed. `deliveries.user_id` CASCADE, `deliveries.telegram_account_id` SET NULL. Thêm status `sending` kèm `lease_until`. Lưu đủ trường hiển thị (hoặc bản chụp nội dung) và ghi rõ tham chiếu CNF là điểm của quy tắc chính. Ghi rõ gửi Telegram là at-least-once (Telegram không có khóa idempotency). Thêm cron dọn bảng |
| S8 | TRUNG BÌNH | **Ngưỡng và tên cột.** D4 nói Lớn là `x > 10` (nghiêm ngặt), Trung bình `5 ≤ x ≤ 10`. Cột lại tên `large_min_percent` gợi ý `≥`, trong khi `light_min` và `medium_min` đúng là `≥`. CHECK `0 < light < medium < large` có nhưng không ràng buộc `anomaly_percent > large`: ghi đè `anomaly = 8%` với `large = 10%` làm mức Lớn không bao giờ xuất hiện. Bảng toàn cục không ghi CHECK. Mục 4.5 thiếu danh sách index | Đổi tên cột thành `*_threshold_percent` hoặc đổi định nghĩa Lớn thành `x ≥ 10`. Thêm CHECK `anomaly > large` (cả bảng toàn cục lẫn bảng ghi đè). Index tối thiểu: `price_alert_events(material_id, delivery_month, created_at)` và `price_alert_deliveries(status, created_at)`. Ghi chú: 4,996% hiển thị "5.00%" nhưng xếp Nhẹ, so ngưỡng không làm tròn |

### Truy vấn, giao diện, dữ liệu

| Mã | Mức | Nội dung | Cách sửa |
|---|---|---|---|
| S9 | TRUNG BÌNH | **Không tái dùng được hàm dashboard.** `_get_points` là private, giới hạn 1.000 dòng, join ghi chú, **không** tính daily-min (daily-min chỉ có ở frontend). `get_price_trends` gọi `_build_purchase_context` theo vòng lặp cho từng điểm chốt mua (N+1) và API không lộ `point_limit`. Truy vấn cần (`GROUP BY received_date, MIN(price)` theo chuỗi) chưa tồn tại. Hiệu năng không phải vấn đề: `EXPLAIN ANALYZE` chuỗi lớn nhất (578 dòng) khoảng 18 ms, dùng `ix_quote_lines_material_delivery_created` | Viết hàm mới `get_daily_min_series(material_id, delivery_month, date_from, date_to, exclude_line_ids)` trong service riêng. Sửa Mục 4.3 và 5.2: bỏ câu "không tự viết SQL song song". Công cụ `get_price_trend` của chatbot phải dùng hàm mới, không dùng `get_price_trends` (trả tới 500 điểm kèm ghi chú, tốn token) |
| S10 | TRUNG BÌNH | **`created_via` thiếu nhiều điểm chạm.** (1) Danh sách phẳng trả `QuoteFlattenedResponse` (`schemas/quote_list.py`), không phải `QuoteResponse`, và cả hai truy vấn phẳng dựng dict thủ công (`quote_query_service.py`). (2) Export Excel dùng `query_flattened_quotes_for_export` và endpoint `export_quotes`, bình luận trong `quotes.py` ghi xuất Excel phải tôn trọng bộ lọc. Quên export thì ô tick "Telegram" không ảnh hưởng file Excel. (3) `_apply_filters` dùng chung nên chỉ cần thêm tham số một chỗ. (4) Icon và bộ lọc dùng `quotes.created_via` hay `quote_versions.created_via` chưa chốt (cột "Created by" của danh sách lọc theo `QuoteVersion.created_by_id`; hai giá trị khác nhau khi trưởng phòng sửa phiếu do bot tạo). (5) `QuotesPage.vue` có cả bảng desktop và thẻ mobile, icon phải thêm cả hai. (6) `QuotesViewState` là kiểu bắt buộc, snapshot `sessionStorage` cũ trả `createdVia = undefined` và các điều kiện kiểu `!== null` coi là bộ lọc đang bật, cần `?? null`. Spec `quotes-view.store.spec.ts` có `sampleSnapshot` typed cần cập nhật. (7) `quotes.api.ts` **không cần sửa** (`buildQuotesQueryString` tự đổi camelCase sang snake_case), còn thiếu `quotes.mappers.ts` và `schemas/quote.py` | Bổ sung vào Mục 4.9, 8 và 10. Chốt cột nguồn (đề xuất `quote_versions.created_via`, vì danh sách đã ở cấp version). Viết test hồi quy cho `test_quotes_list_api.py`, `test_quotes_export_api.py`, `test_quote_query_service.py` và các spec frontend |
| S11 | NHẸ | **Icon bot.** PrimeIcons 7 không có `pi-robot` nhưng có `pi-telegram`, `pi-microchip-ai`, `pi-android` | Chọn một trong ba, bỏ lo SVG nội tuyến ở Mục 9.2 |
| S12 | NHẸ | **Điểm tham chiếu CNF mâu thuẫn trong ví dụ.** Ví dụ 4.2 dùng 345 USD/MT ứng với 7,800 VNĐ/KG, hàm ý tỷ giá khoảng 22.000 và biến động 2,4% trong 2 ngày, không thực tế | Đổi ví dụ cho khớp thực tế (tỷ giá khoảng 26.100 đến 26.290) |
| S13 | NHẸ | **`confirmed_at` không có index** (3.478 version thì chưa vấn đề). D5(a) "14 ngày" không rõ ngày lịch hay làm việc, "chiều, mức khác lần gửi gần nhất" cho gửi cả khi hạ mức, và chưa nói tin Nhẹ trong bản tin tổng hợp có tính là "đã gửi" không. D5(c) "trần số tin mỗi lần quét" không có con số, hành vi khi vượt, hay trường cấu hình. D8 "90 ngày gần nhất" chưa rõ mốc (`received_date`, `confirmed_at` hay `created_at`; có gồm phiếu đã hủy, phiếu chỉ có nháp; xét dòng của version nào; mốc kết thúc là lúc sinh sự kiện hay lúc gửi) | Thêm index additive cho `confirmed_at` khi cần. Ghi rõ các tham số D5(a), D5(c), D8 và đưa vào `price_alert_settings` |
| S14 | NHẸ | **Tie-break và hiển thị.** Khi tăng thì |R2| ≥ |R1| luôn đúng (đáy ≤ điểm gần nhất), khi giảm thì |R3| ≥ |R1|, nên R1 chỉ là lý do chính khi |%| bằng nhau, tức điểm gần nhất chính là đáy hoặc đỉnh (430/1.540 lần). Quy tắc hòa hiện tại ("lấy quy tắc có |%| lớn hơn") chưa phủ. Ví dụ 3 của D2: R3 trùng R1 (cùng điểm 10,000, cùng −4,00%) nên dòng "So sánh khác" sẽ lặp cùng một số. Caption ghi min/max "14 ngày qua" gồm điểm mới, còn biểu đồ vẽ min/max của vùng tham chiếu 7 ngày làm việc không gồm điểm mới (max là 7,900), hai số khác nhau. Tiêu đề 4.3 "Biểu đồ min-max 14 ngày" không khớp nội dung | Ghi "khi |%| bằng nhau, ưu tiên R1" và tính chất đơn điệu ở trên, thêm test thuộc tính. Khi quy tắc phụ trùng điểm tham chiếu với quy tắc chính thì không in dòng "So sánh khác". Thống nhất min/max trong caption và biểu đồ |
| S15 | NHẸ | **Nguồn nhập: bảng nào.** Xem S10 (4) | Chốt cùng S10 |
| S16 | NHẸ | **Script backtest không nằm trong repo**, không tái lập được | Đưa các script vào repo (ví dụ `backend/scripts/analysis/`) kèm hướng dẫn chạy, và ghi định nghĩa các phương án B, C, MIN, MM (hiện Phụ lục B không định nghĩa nên B.1 đến B.4 khó hiểu) |

### Giới hạn của Telegram

| Mã | Mức | Nội dung | Cách sửa |
|---|---|---|---|
| S17 | TRUNG BÌNH | `sendPhoto` có caption tối đa 1.024 ký tự, tin gộp nhiều kỳ giao hàng sẽ vượt. Với `parse_mode=HTML`, tên vật tư hay ghi chú chứa `<`, `&` phải `html.escape`, nếu không Telegram trả 400 "can't parse entities". `callback_data` tối đa 64 **byte**. [Kiến thức ngoài repo, đã xác nhận ở tài liệu Telegram trong lần đọc cho kế hoạch 1A] | Ảnh kèm caption ngắn, chi tiết gửi bằng `sendMessage` (4.096 ký tự). Ghi 400 là lỗi terminal, không thử lại. Dùng `callback_data` ngắn (mã sự kiện), không nhồi nội dung |
| S18 | NHẸ | Nếu ghi `update_id` vào `telegram_processed_updates` **trước** khi đưa vào arq mà Redis lỗi thì update mất | Dedupe trong worker, hoặc xóa dòng dedupe nếu đưa vào hàng đợi thất bại (áp dụng khi chuyển sang arq ở Giai đoạn 2A) |
| S19 | NHẸ | `matplotlib` là CPU đồng bộ, chạy thẳng trong coroutine arq sẽ chặn các job khác cùng vòng lặp. Lần import đầu xây font cache vài giây | Chạy bằng `asyncio.to_thread`, dùng API OO (`Figure`, `FigureCanvasAgg`), không dùng `pyplot` (không thread-safe). Image production tăng kích thước (đã nêu). Font tiếng Việt trong image vẫn [CHƯA XÁC MINH] |

### Môi trường và vận hành

| Mã | Mức | Nội dung | Cách sửa |
|---|---|---|---|
| S20 | TRUNG BÌNH | Dev dùng polling, production dùng webhook; một bot chỉ ở một chế độ (xung đột, lỗi 409). Dev DB khôi phục từ dump production sẽ mang theo `telegram_accounts` thật, `is_enabled=true` và watermark cũ. Worker dev với cùng token sẽ gửi tin thật | Hai token riêng. Script khôi phục tự đặt `price_alert_settings.is_enabled=false` và `telegram_accounts.status='revoked'` (đã có K16 ở kế hoạch 1A cho phần bảng Telegram) |
| S21 | TRUNG BÌNH | Mục 8 so với runbook mục 9: plan chỉ nhắc `backup-postgres.sh`, thiếu `backup-minio.sh` và `export COMPOSE_FILE=docker-compose.prod.yml` (9.2). Chưa nhắc bước so `.env.production.example` với `.env` thật khi có biến mới (9.3). Service worker bot mới phải có trong danh sách build (9.4). Seed (9.6) chạy **sau** migrate (9.5), liên quan Q4. Các bước còn lại (backup trước, `run --rm` migrate trước `up -d`, `restart reverse-proxy`, không downgrade) khớp. `check-production-readiness.sh` chỉ `docker compose config`, không đếm service nên không cần sửa | Bổ sung vào Mục 8 |
| S22 | NHẸ | `_apply_secret_file` chỉ ánh xạ thủ công 5 trường (`config.py`), mỗi secret mới phải thêm dòng. Compose production không dùng Docker secrets, secret đi qua `env_file: .env` | Ghi vào Mục 4.7 |

### Chatbot (xử lý trước Giai đoạn 2)

| Mã | Mức | Nội dung | Cách sửa |
|---|---|---|---|
| S23 | TRUNG BÌNH | **`SET TRANSACTION READ ONLY`.** Đã thử trên Postgres 16: chạy được. Hiệu lực chỉ đến hết giao dịch, mọi `commit` hoặc `rollback` trong luồng hỏi đáp làm mất chế độ. `SET LOCAL statement_timeout` không bind được tham số. `SELECT ... FOR UPDATE` không chạy trong giao dịch read-only | Dùng `execution_options(postgresql_readonly=True)` (SQLAlchemy 2.0.50 hỗ trợ cho asyncpg) hoặc sessionmaker riêng với `connect_args={"server_settings": {"default_transaction_read_only": "on", "statement_timeout": "5000"}}` để cố định, không quên |
| S24 | TRUNG BÌNH | **Quyền ghi và ownership.** Bảng quyền ở 5.2 chỉ liệt kê quyền đọc. `create_quote` cần `quotes.create`, `confirm_version` cần `quotes.update` cộng kiểm ownership. `_ensure_quote_mutation_allowed` (private, ném `HTTPException`) gọi `has_role(owner, "user")` cứng tên trong `_quote_owner_can_be_corrected_by`. `test_permission_inventory` chỉ kiểm lời gọi `require_permission`/`has_permission` có tham số là hằng chuỗi, bảng công cụ khai báo dạng dữ liệu sẽ lọt khỏi test | Tách helper ownership trả kết quả thuần (bool hoặc exception domain). Bổ sung quyền ghi vào bảng. Thêm test riêng cho bảng công cụ và quyền |
| S25 | TRUNG BÌNH | **Dựng dịch vụ ngoài HTTP.** `QuotePricingService` cần `ExchangeRateService(VietcombankExchangeRateClient(...))` và `QuotifySettingsService(session)` như `worker.py`. `VietcombankExchangeRateClient` tạo `httpx.AsyncClient` lười và không đóng. Gọi Vietcombank mỗi lần tính (R11, không cache) | Tạo một lần trong `on_startup` của worker bot. Cache tỷ giá theo ngày. Tính chi phí LLM dùng `fallback_usd_vnd_rate`, cache theo ngày |
| S26 | NHẸ | "Tỷ giá là số nguyên" ở luật nghiệp vụ chỉ được kiểm trong import (`quote_backfill_import.py`), còn `QuoteLineCreateRequest` cho `decimal_places=2` | Bỏ khỏi danh sách "luật phải giữ" hoặc ghi là quy ước riêng của bot |
| S27 | NHẸ | Khớp tên vật tư không dấu: app và migration không có `unaccent`, `global_search` dùng `ilike`. Chỉ 122 vật tư | Chuẩn hóa dấu bằng Python (`unicodedata`), không cần extension |
| S28 | NHẸ | Adapter LLM: OpenAI `tool_calls`, Anthropic `tool_use`, Gemini `functionCall` khác định dạng, lưu `chat_messages` theo định dạng nhà cung cấp sẽ hỏng lịch sử khi đổi. `chat_sessions.telegram_account_id/telegram_user_id` ghi nhập nhằng. `chat_messages` và `llm_usage_events` cùng lưu số token (hai nguồn). `get_price_alerts` ở 5.2 để "đăng nhập" trong khi các công cụ khác có quyền cụ thể. 5.6 một cặp đơn giá cho mọi mô hình | Lưu `chat_messages` theo định dạng trung lập, ánh xạ khi gọi. Chốt khóa phiên. Chọn một nguồn cho số token. Công cụ hỏi đáp dùng cùng định nghĩa biến động với D2. Khi đổi nhà cung cấp phải cập nhật đơn giá |
| S29 | NHẸ | **Ngân sách LLM.** `last_warn_month` ghi trước hay sau khi gửi email thành công: nếu ghi trước và email lỗi thì cả tháng không gửi lại. Chưa nói khi admin tăng trần giữa tháng. Cột `alert_email` là một địa chỉ. `daily_user_limit` không có giá trị mặc định | Gửi cảnh báo bằng `UPDATE ... WHERE last_warn_month IS DISTINCT FROM :m RETURNING` để tránh email trùng khi chạy song song, ghi tháng chỉ khi gửi thành công. Cho phép nhiều địa chỉ hoặc chốt một |

---

## 3. Số Liệu Cần Đính Chính (N)

### N1. Hai nguồn dữ liệu bị trộn trong cùng tài liệu

| Chỉ tiêu | Tài liệu cha, Mục 1.2 (khớp dump trong `backups/`, ghi "2026-10-03") | DB dev hiện tại (dump Downloads 2026-10-02) |
|---|---|---|
| Phiếu | 3.067 | 3.434 (3 phiếu đã hủy) |
| Version | 3.086 | 3.478 (confirmed 3.412, superseded 41, draft 25) |
| Dòng giá | 19.969 | 21.102 (confirmed chưa hủy: 20.893) |
| Vật tư | 119 (36 có báo giá) | 122 (51 có dòng giá, 49 có dòng confirmed) |
| Nhà cung cấp | 311 | 321 (95 có phiếu) |
| Người dùng | 12 (admin 1, user 8, manager 3) | 10 (admin 1, user 7, manager 2) |
| Chuỗi (vật tư, kỳ giao hàng) | 261 | 361 |
| Version nhập lùi | 3.026 / 3.086 | 3.279 / 3.478 (94,3%) |

Hai nguồn đều đúng với chính nó nhưng tài liệu không ghi rõ nguồn và ngày cho từng số. **Cần:** ghi nguồn và ngày cho mọi con số, và xác minh dump nào là production thật. Dump trong `backups/` có thể chưa phải dữ liệu production (đề cập trong báo cáo kỹ thuật là [CHƯA XÁC MINH]). Mọi khẳng định "trên production có role `manager` với 3 người dùng" đều dựa trên dump này.

### N2. Đính chính từng điểm

| Mã | Khẳng định của tài liệu | Số đo được | Sửa |
|---|---|---|---|
| N2 | Phụ lục B.7: "20.893 dòng ... 12 tháng gần nhất" | 20.893 là tổng 3 năm (từ 10/10/2023). 12 tháng chỉ có 9.798 dòng, 4.532 điểm daily-min, 303 chuỗi | Sửa số và nêu rõ kỳ. Thêm "trong 12 tháng chỉ 565 dòng (5,8%) là nhập thật, 82,5% là import" |
| N3 | D3 và B.7: "63 thứ Bảy và 4 Chủ Nhật, 0,6%" | 63 + 4 = 67 là số **dòng** = 0,7%. Ở mức điểm daily-min: 56 + 4 = 60 / 4.532 = 1,3%. Một cách đo khác: 129/10.414 = 1,2% toàn thời gian | Sửa thành "0,7% số dòng (1,3% số điểm)". Kết luận không đổi |
| N4 | "Trung vị 3 điểm giá mỗi chuỗi" (Mục 1.2) | Trung vị 4 điểm daily-min (cả toàn kỳ và 12 tháng), 5 dòng mỗi chuỗi | Sửa |
| N5 | "Tối đa 11 kỳ giao hàng mỗi vật tư" | Tối đa 44 (Khô đậu tương và Ngô hạt, toàn kỳ), 20 trong 12 tháng. Một tin gộp tối đa 10 chuỗi | Sửa |
| N6 | "8 người nhập" | 8 người tạo phiếu nhưng 1 là tài khoản seed admin (19.139 dòng, 91,6% dòng confirmed, tạo 19/08/2026). Thực tế 7 nhân viên (số dòng 12 tháng: 697, 271, 264, 206, 150, 67, 61) | Sửa thành "7 nhân viên cộng 1 tài khoản import" |
| N7 | D12 ví dụ "Khô cọ báo −45,6% vì một điểm 9,505 nhập sai" | 9.505 là giá **đã được sửa** từ 93.245 (phiên bản 2, ngày 19/09). Điểm nhập sai rõ ràng là 187. Theo luật chốt, −45,6% là cờ bất thường lên điểm **đúng** 5.172 | Sửa ví dụ ở D12 và B.4. Xem thêm Q3(b) |
| N8 | Cụm 15/09: "ít nhất 5 điểm" lệch −96% | 6 điểm (Threonine ×2, Arginin ×2, Lysine ×2) cùng ngày, thêm Khô cọ +2.662%. Ngoài ra Tryptophan (CJ) ×2 ngày 08/09 và Arginin ngày 29/09 cũng lệch −96% | Mở rộng, ghi "6 điểm". Lưu ý dòng 202 liệt kê 3 vật tư × 2 kỳ = 6 điểm nhưng ghi "ít nhất 5" |
| N9 | "0,3 điểm bất thường mỗi tuần" | Đúng cho 12 tháng toàn dữ liệu import. Trong giai đoạn nhập thật: 10 điểm / 6,3 tuần (khoảng 1,6 mỗi tuần) và 5 phiên bản sửa giá từ 30% | Ghi cả hai, nêu rõ "12 tháng toàn import" và "6,3 tuần nhập thật" |
| N10 | Dòng "7 ngày lịch, theo chữ: 17,7 / 7,4 / 2,6" (B.7) | Số này **không chặn** bất thường. Có chặn 30% thì 17,5 / 7,3 / 2,4. Các dòng còn lại có chặn | Ghi chú tiêu chí khác nhau của dòng này. Bảng "7 ngày lịch (vòng trước)" cũng không thuộc vòng 1 (A, 14 ngày) mà chưa được mô tả ở đâu: có một vòng trung gian chưa ghi |
| N11 | "403/1.986 tin hướng ngược (khoảng 20%)" | 403 khi loại 82 điểm có R1 = 0 (20,3%). Nếu đếm cả 51 điểm R1 = 0 mà R2 > 0 thì ra 454 | Ghi rõ cách đếm |
| N12 | P90 trong bảng theo vật tư (B.7) | Dùng chỉ số `xs[int(0.9n)]`. Với n = 17 đây là khoảng P94. Nội suy thì Valine 6,2 (tài liệu 7,9), Fermented Soybean Meal 4,4 (tài liệu 4,7) | Nội suy, hoặc ghi rõ cách lấy |
| N13 | Dòng MM (B.1, B.4), số tin MM ở B.3 | **Không tái hiện được**: phương án MM không được định nghĩa trong tài liệu | Định nghĩa MM rõ ràng ở Phụ lục B, hoặc bỏ các dòng này |
| N14 | B.3 nhân viên 1,3 tin mỗi tuần (p90 = 8) và 0,5 (p90 = 6) | Số đo độc lập 0,91 và 0,44 (7 nhân viên, tra cứu 90 ngày theo `received_date`), nhưng **ước lượng thời gian thực lại cao hơn nhiều** (2,7 đến 2,9 tin mỗi tuần, xem Q1). Định nghĩa người nhận (D8) chưa đủ rõ nên chưa kết luận số nào đúng | Làm rõ định nghĩa D8 (S13) rồi đo lại |
| N15 | B.5: n = 40 (29 dòng ≤ đáy, 3 dòng ≥ đỉnh); n = 66 trung vị +2,3% | Dùng tiêu chí "≥ 2 điểm trước" thì n = 39, 27 dòng ≤ đáy, 4 dòng ≥ đỉnh. n = 62, trung vị +3,5%. Các con số 101 / 71 / 55 / +1,6% / 6 / 19 khớp | Định nghĩa tiêu chí chọn mẫu, hoặc bỏ. Bảng dùng n = 40 trong khi có 71 dòng có điểm trước, chưa giải thích. B.5 gần như là kết luận về chất lượng quyết định, trái nguyên tắc trung lập (Requirements 3.9), nên bỏ hoặc ghi "tham khảo, ngoài phạm vi quyết định" |
| N16 | B.1: "ngưỡng 2,5% thấp hơn mức dao động thông thường" | P50 = 1,7% (thấp hơn 2,5%) và 37,3% điểm vượt ngưỡng | Sửa thành "2,5% nằm trong vùng dao động thường gặp (37% điểm vượt)". B.6 điểm 5 "nên cân nhắc 3,5 đến 5% cho mức Nhẹ" mâu thuẫn bề ngoài với mặc định 2,5% đã chốt, cần ghi rõ B.6 là kết luận của vòng 1 |
| N17 | D2 "gần bằng A": 19,5 so với 16,0 | Chênh +22%, chưa thể nói "gần bằng". Số liệu theo người nhận (B.3) chỉ có cho A và MM, chưa có cho quy tắc đã chốt | Sửa câu chữ, bổ sung số liệu theo người nhận cho quy tắc đã chốt |
| N18 | "Khô đậu tương và Ngô hạt chiếm khoảng 82 đến 85%" | 82% số điểm bị báo, 85,6% số dòng 12 tháng, 93,1% số dòng toàn kỳ, 73,5% số điểm daily-min | Ghi rõ mẫu số |

### Các con số đã kiểm là đúng (không cần sửa)

1.540 điểm bị báo; 1.986 (theo chữ); 682 / 641 (nhiều quy tắc cùng báo); R1/R2/R3 chính = 430/638/472; 19,5 / 7,8 / 2,9 tin mỗi tuần; 20,3 / 8,0 / 3,0 (theo chữ); 16 / 13 / 7 điểm bất thường; độ nhạy ngưỡng 20/30/40/50% (17/16/15/14 điểm); bảng theo vật tư (805 / 456 / 41 / 27 / 17 / 17, 52% / 30%, hai vật tư đầu 82%); B.1 từng ô các cột A, B, C, MIN (N = 4.105); B.2 tổng 832 / 637 / 578 / 726 (khi chống lặp được "mồi" bằng lịch sử trước 12 tháng; không mồi thì 840 / 637 / 579 / 733, chênh ở bản đã chốt chỉ 19,48 so với 19,38); B.3 A gộp theo vật tư 365 và TB+L 150, nâng ngưỡng Nhẹ lên 3,5% thì 5,3 và lên 5% thì 2,7; ba ví dụ D2 và ví dụ giá bất thường Threonine −96,21%; cửa sổ 23/09 đến 01/10 và "9 đến 11 ngày lịch"; 101 dòng chốt mua, 71 có điểm trước, 55 có điểm sau, trung vị +1,6%, 6 và 19 dòng; `delivery_month` luôn là ngày 01 (0 ngoại lệ trong 21.102 dòng); phiếu import thuộc tài khoản seed admin (100%); 20.328/20.893 dòng `is_backfilled`.

---

## 4. Nhất Quán Và Lỗi Thời (T)

| Mã | Mức | Nội dung | Cách sửa |
|---|---|---|---|
| T1 | TRUNG BÌNH | **Hai hệ ký hiệu va chạm.** R1 đến R3 (quy tắc ở D2) trùng R1 đến R19 (rủi ro ở Mục 6). Câu "bẫy R1 ở **Mục 9**" sai mục (rủi ro nằm ở Mục 6). "(R1)" ở 5.3, "(R3)", "(R4)" là rủi ro, còn "làm lệch cả R1 lẫn R3" ở D12 là quy tắc. Cột `rule ('R1'\|'R2'\|'R3')` ở 4.5 càng dễ nhầm | Đổi mã rủi ro thành `RR-1…RR-19` (hoặc đổi quy tắc thành Q1/Q2/Q3 nhưng giữ giá trị cột DB), sửa "Mục 9" thành "Mục 6" |
| T2 | TRUNG BÌNH | **Hai hệ đánh số quyết định cùng dải 1 đến 15 nhưng khác nghĩa.** QĐ-1…15 ở Mục 0.1 và câu hỏi 1…15 ở Mục 9.1 (ví dụ số 14 là "D5 đến D10" ở 0.1 nhưng là "biến động % USD/MT" ở 9.1). QĐ-12, QĐ-13, QĐ-14 mỗi dòng gộp 2 đến 6 quyết định không liên quan (QĐ-13 gộp "không tính % CNF" và "cảnh báo ngân sách qua email"). 9.1 xáo trộn thứ tự (D11a, 1 đến 12, D11c, 13 đến 15) và chưa có cột QĐ tương ứng | Thêm cột "QĐ" vào 9.1, đánh mã H1…H15 cho câu hỏi, tách các QĐ gộp |
| T3 | TRUNG BÌNH | **Mục 0.1 chưa theo kịp QĐ-12.** QĐ-1 vẫn mô tả "bộ ba quy tắc" theo cách hiểu từng quy tắc độc lập (theo chữ). Câu lẻ ngoài bảng ("Điều chỉnh hướng tin...") là phần sót của vòng sửa trước, nên gộp vào QĐ-12 | Cập nhật QĐ-1 hoặc ghi "xem QĐ-12" |
| T4 | TRUNG BÌNH | **Mục 0 (tóm tắt điều hành) gần như không nêu nội dung đã chốt** (bộ ba quy tắc, 7 ngày làm việc, giá bất thường, người nhận). Điểm 5 vẫn nói "cần chốt điều này trước khi bắt đầu Bước 2" dù D11 đã chốt dùng API key. Điểm 7 chỉ nói "D5 đến D10", không nêu D12. Điểm 1 "chưa có gì về Telegram trong tài liệu" không còn đúng khi tính cả hai tài liệu kế hoạch | Viết lại Mục 0 theo trạng thái hiện tại |
| T5 | TRUNG BÌNH | **Các câu lỗi thời cụ thể.** (a) Giai đoạn 0 ghi "chốt D1-D11", phải là D1 đến D12 cùng các QĐ, và tiêu đề vẫn là "Chốt phạm vi (không code)" dù đã xong. (b) 4.3 "Công nghệ (cần chốt)", "matplotlib (đề xuất)", trong khi 1B đã dùng matplotlib. (c) 4.2 "Khi chọn hiển thị theo CNF thì dùng USD/MT": không còn tính năng "chọn hiển thị theo CNF" (QĐ-13 loại bỏ biến động % trên CNF), dòng này là phần sót. (d) D2 "A vẫn có thể giữ làm dòng thông tin phụ 'xu hướng 14 ngày' (đề xuất, chưa chốt)": không có trong mẫu tin 4.2 và không có trong 9.2, cần chốt hoặc bỏ. (e) 4.9 "Chỉ cần ở Bước 1" liệt kê cả nguồn nhập Telegram (2B) và trang "Chi phí chatbot" (2A); 4.5 chứa `created_via` (2B); 4.6 chứa `chatbot.manage` (2A). (f) Mục 8 "Thay đổi nhỏ bắt buộc ở code cũ chỉ gồm…" thiếu refactor `QuotifyDashboardService`, `QuoteService`, `models/quote*.py`, `schemas/quote.py`, `email.py`. (g) Dòng "Nguồn: 4 agent đọc…" không phản ánh phần backtest bằng script. (h) Dòng "BẢN NHÁP ĐỂ THẢO LUẬN" trong khi gần như mọi quyết định đã "ĐÃ CHỐT"; kế hoạch 1A gọi tài liệu cha là "đã chốt". Tiêu đề Mục 3 "đã chốt và đề xuất" cần cập nhật. D5 mục (e) "cân nhắc nâng ngưỡng Nhẹ" nằm trong khối "ĐÃ CHỐT" nhưng không phải quyết định | Sửa từng chỗ |
| T6 | TRUNG BÌNH | **Mục 9.2 không liệt kê hết điểm mở rải rác trong thân:** số trần "flood guard", cửa sổ chống lặp 14 ngày, chọn matplotlib và font tiếng Việt trong image, "chấp nhận gõ không dấu", TTL hội thoại "đề xuất 30 ngày", xóa người dùng cứng, cột `alert_email` một hay nhiều địa chỉ | Bổ sung vào 9.2 hoặc đưa vào các Q/S ở trên |
| T7 | NHẸ | **Cấu trúc.** D12 nằm giữa D6 và D7 (thứ tự D1…D6, D12, D7…D11). Tài liệu ~950 dòng chưa có mục lục. "Mục 10: Phụ lục: tập tin sẽ chạm vào" và "Phụ lục B" (không có Phụ lục A). Phụ lục B không định nghĩa phương án B, C, MIN, MM, và dòng "so với các điểm trong 13 ngày trước theo từng phương án (D2)" tham chiếu D2 nay chỉ còn bộ ba quy tắc | Thêm mục lục, đổi "Mục 10" thành "Phụ lục A", đưa D12 về vị trí hợp lý hoặc chú thích |
| T8 | NHẸ | **Định dạng số.** Văn xuôi dùng dấu phẩy thập phân kiểu Việt ("+4,49%", "2,5") nhưng mẫu tin dùng "+5.57%", "8,150.00" (đúng quy ước 1.5). Trong cùng một câu có "13,486" (hàng nghìn) và "−4,3%" (thập phân) ở B.4 và D12. Giá trong ví dụ D2 ghi "7,900" không có ".00". Tiền "2.000.000 đ" (Quy tắc 1.5 cấm `₫`, `đ/KG`) | Thêm một dòng quy ước định dạng số cho văn xuôi, hoặc dùng "7,900.00 / +4.49%" nhất quán. Viết "2.000.000 VNĐ" |
| T9 | NHẸ | **Thuật ngữ.** "Mặt hàng" (19 lần) và "vật tư" (32 lần) dùng lẫn lộn; CONTEXT.md chỉ có "Vật tư". "Nhập lùi / nhập muộn / nhập lại / backfill / import" dùng lẫn lộn; CONTEXT.md có "Nhập lại báo giá" và "Import báo giá cũ". "Báo giá gần nhất" (4.2, QĐ-1) thực chất là **điểm giá** (giá thấp nhất của ngày), có thể không phải báo giá mới nhất của ngày. Nhãn kiểm chứng không thống nhất: `[CHƯA XÁC MINH]` (8 chỗ) và `[CẦN XÁC MINH]` (2 chỗ). Nhiều từ tiếng Anh nội bộ (daily-min, watermark, flood guard, dry-run, tracer) chưa được định nghĩa | Dùng "vật tư", "điểm giá gần nhất". Chọn một nhãn kiểm chứng. Định nghĩa thuật ngữ một lần |
| T10 | NHẸ | **Ngôn ngữ và giọng văn.** Có "cần bạn xác nhận" và "Theo hiểu biết của tôi" (ngôi thứ nhất và thứ hai, trái giọng khách quan của các kế hoạch khác như phase-7-audit-log). Giọng không trang trọng: "nhồi", "Rẻ, không cần role mới", "đừng gắn logic". Câu "giá giảm là tin tốt, giá tăng là tin xấu" ở 4.2 là nhận định đánh giá, trái nguyên tắc trung lập (1.5, Requirements 3.9). Tên "Gemini Advanced" có thể đã đổi, cần xác minh hoặc bỏ tên cụ thể | Sửa theo giọng khách quan |
| T11 | NHẸ | **Chi tiết nghiệp vụ nhỏ.** Phiếu bị hủy hoặc `delete_confirmed_line` sau khi đã gửi tin: không có tin thu hồi hay đính chính. Điểm đã được "Giá đúng" thì hợp lệ trở lại: nên nêu rõ ở D2 mục 4. Cách xác định phiếu import cho D6/D8/D9 chỉ qua "tài khoản seed admin", không có đánh dấu riêng (admin vừa nhập tay vừa là tài khoản seed thì bị loại nhầm). Cách chống trùng cho `callback_query` (kích thước `callback_data`, kiểm quyền) chưa nêu ở 4.6 | Bổ sung |

---

## 5. Đồng Bộ Với Kế Hoạch 1A (Y)

| Mã | Mức | Nội dung |
|---|---|---|
| Y1 | TRUNG BÌNH | **Tài liệu cha cần cập nhật theo bảng "Độ Lệch Có Chủ Đích" của 1A** (đã nằm trong việc của Slice 0): partial unique `IN ('active','blocked')` (4.4, 4.5), trạng thái `blocked` và `my_chat_member` (4.4), PII trong audit (4.6), biến cấu hình (4.7, kể cả "compose production dùng `${VAR:?msg}`" mâu thuẫn K9), R9 (in-memory là lệch có chủ đích, **không** phải "R9 đã chấp nhận"), webhook xử lý nội tuyến thay vì arq (4.6, chuyển sang arq ở 2A), E2E-A thay cho fake Telegram (4.10), triển khai production ở 1A (Mục 7), bật/tắt hoãn sang 1B/1C (4.9). |
| Y2 | TRUNG BÌNH | **Chưa nằm trong bảng độ lệch của 1A, tài liệu cha vẫn lệch:** endpoint `DELETE /users/me/telegram/link-token` và định dạng `GET /users/me/telegram` (cha 4.6 không có); sự kiện audit `telegram.link_requested`, `telegram.link_rejected` (cha chỉ có `linked`, `unlinked`); `revoked_reason` thêm `stop_command`, `user_unlink`, `owner_inactive` (kế hoạch 1A); dọn dữ liệu K8, lệnh bot K10, ẩn panel khi tắt K14, TRUNCATE sau khôi phục dump K16; tên file SCSS (`_telegram-*.scss` trong cha, `_profile-page.scss` trong 1A); danh sách file Mục 10 (1A có ba model, `telegram_update_service/runner`, `telegram_link.py`, `telegram_poller.py`, `scripts/telegram_webhook.py`, `logging.py`, `observability.py`, `AuditLogsPage.vue`, runbook); 1A không có `send_photo` (cha Mục 7 liệt kê `sendPhoto` ở 1A); Mục 7 1C của cha gồm runbook và `.env.production.example` mà 1A đã làm ở S1 và S6b; hạn mức Redis (1A "hoãn sang 1C") không có trong 1C của cha; cha mục 4.4 yêu cầu cập nhật `username` mỗi tin và kiểm `User.status` mỗi tin, 1A mang sang Slice 4. Tài liệu cha không có liên kết tới file kế hoạch 1A. |
| Y3 | **NGHIÊM TRỌNG (bảo mật)** | **K15 của 1A chưa có trong tài liệu cha.** K15 ghi "phải xét lại bằng một bước xác nhận trong chat trước khi chatbot Giai đoạn 2 được phép ghi dữ liệu". Điều kiện này **hoàn toàn không xuất hiện** ở 5.3 và Mục 7 (2A, 2B) của cha. Nếu Giai đoạn 2 bắt đầu mà không nhớ điều kiện này thì người có đường dẫn liên kết trong 10 phút có thể gắn Telegram của mình vào tài khoản của chủ đường dẫn rồi dùng chatbot để ghi dữ liệu. Cần nằm ở 2B như một điều kiện chặn |
| Y4 | TRUNG BÌNH | **Thuật ngữ cần đưa vào CONTEXT.md khác nhau giữa hai tài liệu.** Cha, Mục 2: *Liên kết Telegram*, *Biến động giá*, *Ngưỡng cảnh báo*, *Mức biến động*. 1A: *Liên kết Telegram*, *Đường dẫn liên kết*, *Mã liên kết*, *Hủy liên kết*, *Đổi tài khoản Telegram*. Cần gộp, và bổ sung thuật ngữ cha dùng nhiều mà CONTEXT.md chưa có: *Điểm giá* (daily-min), *Chuỗi* (vật tư, kỳ giao hàng), *Cửa sổ tham chiếu*, *Ngày làm việc*, *Giá bất thường*, *Trưởng phòng*, *Bản tin tổng hợp*. Cha còn dùng "token" khi 1A quy ước "mã liên kết" |
| Y5 | TRUNG BÌNH | **Mục 7 (1B, 1C) thiếu hạng mục và chưa phân phase:** API cấu hình và tùy chọn (tới đâu ở 1B hay 1C); bộ xử lý `callback_query` (nút "Giá đúng", "Nhập sai"); định dạng bản tin tổng hợp 08:00 (không có ví dụ, không nói bản tin rỗng, cuối tuần, cửa sổ tính); chế độ dry-run và replay (xem Q1); cấu hình `PRICE_ALERTS_*`; cách bật cờ lần đầu ở 1B khi chưa có giao diện (giao diện ở 1C). Tiêu chí "Hoàn thành khi: phân bố mức hợp lý" của 1B quá mơ hồ, nên có số mục tiêu (so với 7,8 và 2,9, nay đã biết thực tế khác, xem Q1). |
| Y6 | TRUNG BÌNH | **Mục 10 và 4.6 thiếu hạng mục.** Mục 10 thiếu file frontend cho cấu hình ngưỡng và tùy chọn (types, api, composable cho `price-alert-settings`, `alert-preferences`) và file backend `models/quote.py`, `schemas/quote.py`, `services/quote_service.py` (Mục 8 và 4.5 đều yêu cầu sửa), `quotify_dashboard_service.py` (4.3). Danh sách file mới trộn đường dẫn (`frontend/src/types/...` rồi `api/...`, `pages/...`). 4.6 không có endpoint cho trang "Chi phí chatbot" (xem chi phí, sửa trần) dù có quyền `chatbot.manage`. Audit: 4.6 nói "chỉ 1 sự kiện tổng kết mỗi lần quét" nhưng không đặt tên sự kiện, và cron chạy mỗi 1 đến 2 phút nên cần "chỉ ghi khi có sự kiện"; thay đổi trần ngân sách (5.6) cũng chưa có tên sự kiện |

---

## 6. Điều Chưa Kiểm Chứng Được

- **Telegram:** VPS ra được `api.telegram.org` và Telegram vào được cổng 443 (ngoài phạm vi repo, kiểm ở Slice 0 của 1A). "Không hỗ trợ redirect" và số hiệu phiên bản Bot API chỉ do một agent đọc, chưa kiểm chéo.
- **SMTP production** có thật hay chưa: chỉ thấy giá trị mẫu (`smtp.example.com`, `admin@quotify.local`) trong `.env.production.example`.
- **Điều khoản dữ liệu và hạn mức** của gói miễn phí Google AI Studio.
- **Font tiếng Việt** trong image production.
- **`DELETE /users/{id}` còn trả 500 hay không:** chỉ phân tích tĩnh (`User.refresh_tokens` không có cascade hay `passive_deletes`, `refresh_tokens.user_id` NOT NULL, file không đổi từ commit đầu), chưa chạy thử.
- **Số liệu production thật:** các agent chỉ kiểm dump trong `backups/` và DB dev. Dump trong `backups/` có thể chưa phải production (xem N1).
- **Hành vi Gemini** (function calling, file input) và các giới hạn Telegram (caption, `callback_data`) là kiến thức ngoài repo.
- **Số liệu không tái hiện được** do tài liệu không định nghĩa: xem N13, N14, N15.

---

## 7. Đề Xuất Chương Trình Thảo Luận (2026-10-04)

Thứ tự: quyết định có ảnh hưởng lớn trước, rồi duyệt hàng loạt phần còn lại.

1. **Q1: D6 và nguồn kích hoạt.** Quyết định trước vì nó đổi mọi ước lượng tải (D5, trần flood guard, kích thước worker, tiêu chí dry-run).
2. **Q2: đơn vị "tin" và cách gộp.** Phụ thuộc Q1 một phần (tải tin).
3. **Q3: vòng đời giá bất thường.** Quyết định xử lý cờ chưa duyệt, tham chiếu, ai bấm nút, có làm cảnh báo lúc nhập hay không.
4. **Q4: quyền cho `manager` và vị trí giao diện cấu hình.**
5. **Duyệt hàng loạt:** nhóm S, N, T, Y. Chỉ cần xác nhận "đồng ý áp dụng toàn bộ", ngoại trừ các mục muốn bàn riêng.
6. **Bước tiếp theo sau thảo luận:**
   - Áp dụng các thay đổi đã đồng ý vào tài liệu cha, một lượt.
   - Đưa script backtest vào repo (S16).
   - Soạn **kế hoạch 1B riêng** theo mẫu kế hoạch 1A (bảng quyết định K, slice, tiêu chí chấp nhận), dùng tài liệu cha làm nguồn lý do. Tách phần "đặc tả chuẩn" (D2, D3, D4, D5, D12 viết lại thành một mục duy nhất, không lẫn lý do) khỏi phần lập luận và Phụ lục B.
   - Đưa K15 vào điều kiện chặn của slice 2B (Y3).

## Phụ Lục: Dữ Liệu Đo Bổ Sung (từ agent kiểm backtest)

Các phép đo dưới đây do agent tự viết script chạy trên DB dev (chỉ `SELECT`). Script nằm ở thư mục tạm của phiên làm việc, **không có trong repo** (xem S16).

- **Cuối ngày so với từng lần chốt** (dữ liệu nhập thật): tin sau chống lặp 108 (cuối ngày) và 114 (+5,6%, đánh giá lại mỗi khi daily-min đổi).
- **Mật độ nhập thật:** 163/1.770 version (9,2%) không nhập lùi trong 12 tháng; 565 dòng; 483 điểm daily-min nhập thật; 7 người nhập; theo tuần ISO 34 đến 40 lần lượt 89, 175, 20, 96, 49, 45, 91 dòng. Toàn kỳ: 565/20.893 = 2,7% dòng nhập thật.
- **Phân bố chênh lệch giữa các nhà cung cấp trong cùng một ngày** (điểm có từ 2 dòng): trung vị (max−min)/min = 1,68%, P90 = 4,5%, P99 = 10,8%. Chỉ 4/9.798 dòng cao hơn min cùng ngày từ 1,3 lần.
- **Giờ chốt:** xác nhận thật trải đều từ 08 giờ đến 21 giờ (cao điểm 10 giờ và 13 giờ đến 15 giờ). 6% phiên bản chốt vào thứ Bảy hoặc Chủ Nhật. Nếu cron chỉ chạy trong giờ hành chính thì phải tính đến tin dồn.
- **Chuỗi thưa:** 50% chuỗi có từ 3 điểm trở xuống trong 12 tháng. 509/4.532 điểm (11,2%) không có điểm trước trong cửa sổ.
- **Cửa sổ 7 ngày làm việc** đã đối chiếu với `numpy.busday_offset` trên 1.101 ngày: 0 sai lệch.
