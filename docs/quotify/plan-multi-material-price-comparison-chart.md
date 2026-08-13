# Kế Hoạch: Chart So Sánh Giá Nhiều Mặt Hàng Theo Kỳ Hàng Về

> **V1 đã triển khai xong ngày 12/08/2026** bằng TDD (skill `tdd`), theo đúng
> thiết kế dưới đây — không sửa backend. Xem `frontend/src/composables/useDashboardPage.ts`
> (`buildMaterialComparisonBuckets`, `buildPriceDifferenceLines`, `loadMaterialComparison`,
> `comparisonChartData`/`comparisonChartOptions`), `frontend/src/pages/DashboardPage.vue`
> (panel mới "So sánh giá nguyên liệu theo kỳ hàng về"), và fix kèm theo ở
> `frontend/src/pages/QuotesPage.vue` (đọc thêm `route.query.materialId` lúc
> mount — trước đó chỉ đọc `deliveryMonth`, khiến click từ chart mới chỉ lọc
> đúng kỳ mà không lọc đúng mặt hàng).

## 1. Bài Toán

Bộ phận Thu Mua cần so sánh nhanh xu hướng giá theo kỳ giao hàng giữa 2-3
nguyên liệu **có thể thay thế nhau** trong công thức thức ăn chăn nuôi (ví
dụ Ngô hạt và Khô đậu nành), để quyết định nên mua nguyên liệu nào rẻ hơn
cho từng kỳ.

Chart hiện có "Giá theo kỳ hàng về" chỉ xem được **1 mặt hàng/lần** (lọc
theo `selectedMaterialId`) — không hỗ trợ so sánh trực tiếp nhiều mặt hàng
trên cùng 1 chart.

## 2. Rà Soát Thực Tế (Không Đoán)

- Endpoint `GET /dashboard/quotify/price-trends` hiện chỉ nhận đúng 1
  `material_id` (`backend/app/api/v1/quotify_dashboard.py`), áp dụng bằng
  so khớp bằng nhau (`QuoteLine.material_id == material_id`,
  `quotify_dashboard_service.py`) — không hỗ trợ danh sách.
- Mỗi điểm trả về (`QuotifyPriceTrendPoint`) **đã có sẵn**
  `material_id`/`material_name`/`material_code` — không cần đổi schema để
  gộp dữ liệu nhiều mặt hàng ở frontend.
- `point_limit` (mặc định 500, tối đa 1000) là **cap toàn cục cho cả câu
  query**, không chia theo từng mặt hàng. Nếu đổi filter sang `.in_()` mà
  không sửa logic limit, 1 mặt hàng có nhiều báo giá sẽ "ăn hết" quota,
  khiến mặt hàng khác gần như không còn điểm nào — rủi ro thật, phải tránh.
- `converted_price_vnd_per_kg` là giá đã quy đổi chung về VNĐ/KG bất kể
  đơn vị/tiền tệ gốc (VND/KG giữ nguyên, USD/MT quy đổi qua tỷ giá + thuế +
  chi phí làm hàng) — **là mẫu số chung an toàn để so sánh trực tiếp giữa
  các mặt hàng khác nhau**.
- Frontend đã có `listMaterialsLookup` (danh sách mặt hàng active) và
  PrimeVue `MultiSelect` đã dùng ở `SuppliersPage.vue` — có thể tái dùng
  UI pattern, PrimeVue `MultiSelect` hỗ trợ sẵn `selectionLimit` để giới
  hạn tối đa 3 lựa chọn.

## 3. Thiết Kế Chart

### Loại chart & trục

- Line chart nhiều series, giống hạ tầng chart hiện có (Chart.js).
- Trục X: kỳ giao hàng (delivery month), giống chart hiện tại.
- Trục Y: Giá quy đổi VNĐ/KG — **1 trục chung** cho tất cả mặt hàng được
  chọn (an toàn vì đây là mẫu số chung đã quy đổi).

### Series

- **1 đường/mặt hàng được chọn** (tối đa 3), vẽ **giá trung bình mỗi kỳ**.
- Không vẽ thêm dải min-max cho mỗi mặt hàng ở v1 — nếu chọn 3 mặt hàng,
  vẽ đủ cả min/avg/max sẽ ra 9 đường, quá rối, đi ngược mục đích "so sánh
  nhanh". Dải min-max theo từng mặt hàng để v2 (toggle riêng).
- Mỗi mặt hàng 1 màu riêng, **không dùng lại quy ước màu xanh/cam/tím của
  chart cũ** (ở đó màu mang nghĩa "thấp nhất/cao nhất/trung bình" — ở đây
  màu đại diện cho MẶT HÀNG, ý nghĩa khác, không tái dùng để tránh nhầm).
- `spanGaps: false` — nếu 1 mặt hàng không có báo giá ở 1 kỳ nào đó, để hở
  khoảng trống rõ ràng, không nối liền gây hiểu sai là có dữ liệu liên tục.

### Tooltip (tái dùng hạ tầng external tooltip đã xây cho chart cũ)

Mỗi kỳ giao hàng hover vào hiển thị:

```
12/2026
🟦 Ngô hạt: 7,200.00 VNĐ/KG (12 báo giá)
🟨 Khô đậu nành: 9,450.00 VNĐ/KG (8 báo giá)

Khô đậu nành cao hơn Ngô hạt: +2,250.00 VNĐ/KG (+31%)

Nhấp vào 1 đường để xem báo giá tương ứng trong Bảng báo giá
```

- Ghi rõ **số báo giá đóng góp vào giá trung bình** mỗi mặt hàng/kỳ — để
  người dùng tự đánh giá độ tin cậy (trung bình từ 1 báo giá khác hẳn
  trung bình từ 50 báo giá, không nên trình bày như nhau).
- Dòng chênh lệch: nếu đúng 2 mặt hàng, so trực tiếp; nếu 3 mặt hàng, so
  từng mặt hàng còn lại với mặt hàng **rẻ nhất** tại kỳ đó (mốc rõ ràng,
  hữu ích cho quyết định thay thế).

### Tương tác

- Click vào 1 điểm trên đường của mặt hàng nào → điều hướng `/quotes`
  với filter `materialId` + `deliveryMonth` của đúng mặt hàng đó (tái
  dùng pattern deep-link đã làm ở chart cũ, cần xác định đúng dataset
  được click để lấy material tương ứng).

### Chọn mặt hàng

- `MultiSelect` (PrimeVue), `selectionLimit={3}`, tối thiểu 2 để vẽ (disable
  chart + hiện gợi ý "Chọn thêm 1 mặt hàng để so sánh" nếu mới chọn 1).
- Không giới hạn ở tầng hệ thống việc mặt hàng nào "thay thế được nhau" —
  hệ thống hiện không có khái niệm "nhóm thay thế" trong domain model. Đây
  là công cụ so sánh giá tự do, người dùng tự chọn đúng theo nghiệp vụ của
  mình; không thêm khái niệm nghiệp vụ mới vào model nếu không được yêu
  cầu riêng.
- Hiển thị "Tên (mã)" trong danh sách chọn để tránh nhầm mặt hàng cùng tên.

## 4. Nguồn Dữ Liệu — Đề Xuất KHÔNG Sửa Backend Ở V1

Vì `point_limit` là cap toàn cục (rủi ro chia sẻ quota không đều nếu đổi
sang `material_id IN (...)`), đề xuất v1:

- **Gọi lại đúng endpoint hiện có `N` lần song song** (`Promise.all`), mỗi
  lần 1 `material_id` trong tối đa 3 mặt hàng được chọn — giữ nguyên cap
  500/1000 riêng cho từng mặt hàng, không đụng logic backend, không rủi ro
  1 mặt hàng "ăn" quota của mặt hàng khác.
- Áp dụng đồng thời các filter chung hiện có (loại NCC, khoảng ngày nhận)
  cho cả N lần gọi.
- Gộp kết quả ở frontend theo `deliveryMonth`, tính trung bình + số báo
  giá mỗi (mặt hàng, kỳ) — tương tự cách `buildDeliveryMonthBuckets` hiện
  có nhưng nhóm thêm theo `materialId`.
- Đánh đổi: nhiều request hơn (tối đa 3, chạy song song, không tuần tự) —
  hợp lý ở quy mô hiện tại; nếu sau này cần so sánh nhiều hơn 3 mặt hàng,
  cân nhắc đổi backend sang `material_ids: list[UUID]` + chia đều limit
  theo từng mặt hàng (v2, xem mục 6).

## 5. Trường Hợp Biên (Góc Nhìn Data Analyst)

1. **Thiếu dữ liệu 1 kỳ cho 1 mặt hàng**: để hở đường (`spanGaps:false`),
   không nối liền — nối liền sẽ ngộ nhận có dữ liệu liên tục.
2. **Trung bình từ quá ít báo giá**: hiển thị rõ số n trong tooltip, không
   ẩn — n=1 không đại diện "giá thị trường" như n=50.
3. **2 mặt hàng lệch thang giá quá xa** (ví dụ so nguyên liệu thô với phụ
   gia vi lượng giá cao): dùng 1 trục Y chung sẽ làm đường giá thấp bị dẹt
   sát đáy. Với ví dụ Ngô hạt/Khô đậu nành mức giá đủ gần nên ổn; nếu
   người dùng tự chọn 2 mặt hàng lệch giá nhiều, đây là hạn chế đã biết —
   để v2 thêm toggle "Xem theo % thay đổi so với đầu kỳ" khi cần so sánh
   XU HƯỚNG thay vì giá tuyệt đối.
4. Không có dữ liệu "nhóm nguyên liệu thay thế" trong hệ thống — ghi rõ
   đây là công cụ so sánh tự do, không tự động gợi ý mặt hàng nào thay thế
   được mặt hàng nào.

## 6. Vị Trí Trong UI & Phân Kỳ

- Thêm **panel chart mới riêng** trên Dashboard, không sửa chart "Giá theo
  kỳ hàng về" hiện có (chart đó phục vụ mục đích khác: soi độ phân tán giá
  của 1 mặt hàng — vẫn cần giữ).
- Tên đề xuất: "So sánh giá nguyên liệu theo kỳ hàng về".

**V1 (đề xuất triển khai ngay khi được duyệt):**

- MultiSelect tối đa 3 mặt hàng, gọi API hiện có N lần song song, vẽ N
  đường trung bình, tooltip có số báo giá + chênh lệch, click điều hướng
  `/quotes` lọc đúng mặt hàng + kỳ.

**V2 (khi có nhu cầu thật, không làm trước):**

- Toggle dải min-max riêng theo từng mặt hàng.
- Toggle xem theo %-thay-đổi khi mặt hàng lệch thang giá.
- Đổi backend sang `material_ids: list[UUID]` + chia đều `point_limit`
  theo từng mặt hàng, giảm số request khi mở rộng so sánh > 3 mặt hàng.
- Export dữ liệu so sánh ra CSV.
