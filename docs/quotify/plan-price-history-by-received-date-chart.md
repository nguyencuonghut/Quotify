# Kế Hoạch: Chart So Sánh Giá Lịch Sử Theo Ngày Báo Giá (Cho 1 Kỳ Giao Hàng Cố Định)

## 1. Bài Toán

Người dùng muốn xem **diễn biến giá theo thời gian chào giá** (không phải
theo kỳ giao hàng) cho 2-3 mặt hàng, khi đã **cố định 1 kỳ giao hàng** cụ
thể. Ví dụ: xem giá lịch sử "Ngô hạt" và "Khô đậu nành" cho hàng về
tháng 12/2026 — biết rằng báo giá cho kỳ 12/2026 đã bắt đầu xuất hiện từ rất
sớm (ví dụ báo giá ngày 01/01/2026 đã chào cho hàng về 12/2026).

## 2. Khác Biệt Với Chart "So Sánh Giá Theo Kỳ Hàng Về" Đã Có

| | Chart đã có | Chart mới này |
|---|---|---|
| Trục X | Kỳ giao hàng (biến thiên, mỗi điểm 1 kỳ) | Ngày nhận báo giá, theo tháng (biến thiên) |
| Kỳ giao hàng | Không cố định | **Cố định đúng 1 giá trị** người dùng chọn |
| Câu hỏi trả lời | "Mặt hàng nào rẻ hơn ở kỳ giao hàng X?" | "Chốt mua sớm hay muộn cho kỳ giao hàng X thì giá tốt hơn?" |

Đây là 2 chart bổ sung cho nhau, không thay thế — nên làm **panel thứ 3
riêng** trên Dashboard, không sửa chart đã có.

## 3. Rà Soát Dữ Liệu (Không Đoán)

Đã đọc `backend/app/api/v1/quotify_dashboard.py` và
`backend/app/services/quotify_dashboard_service.py`:

- Endpoint hiện có `GET /dashboard/quotify/price-trends` **đã hỗ trợ sẵn**
  `delivery_month` (khớp chính xác `QuoteLine.delivery_month == delivery_month`)
  cùng với `material_id` và `received_date_start`/`received_date_end` —
  **không cần sửa backend**, áp dụng đúng pattern đã dùng ở chart trước: gọi
  lại endpoint N lần song song (1 lần/mặt hàng), lần này truyền thêm cố định
  `delivery_month`, merge ở frontend.
- Mỗi điểm trả về vẫn có sẵn `receivedDate`, `materialId/Name`,
  `convertedPriceVndPerKg` — đủ để dựng trục X mới (theo tháng của
  `receivedDate`) mà không cần đổi gì ở backend/schema.

## 4. Thiết Kế

### Bộ lọc riêng cho panel (độc lập với bộ lọc chung của Dashboard)

- **Kỳ giao hàng** (bắt buộc chọn — chart không có ý nghĩa nếu chưa chọn):
  DatePicker `view="month"`, giống DatePicker "Kỳ giao hàng" đã có ở bộ lọc
  chính.
- **Mặt hàng**: MultiSelect tối đa 3, tái dùng y hệt component/UX đã xây ở
  chart so sánh trước (`selectionLimit`, hiển thị "Tên (mã)").

### Trục & series

- Trục X: **tháng nhận báo giá** (bucket theo tháng của `receivedDate`) — dùng
  tháng thay vì ngày để nhất quán với phần còn lại của dashboard và tránh
  quá nhiều điểm rời rạc nếu 1 mặt hàng được báo giá nhiều lần/tháng.
- Trục Y: Giá quy đổi VNĐ/KG (giống mọi chart khác).
- Mỗi mặt hàng: 1 đường trung bình + dải MIN-MAX có thể toggle — **tái dùng
  y nguyên** cơ chế vừa xây (màu riêng theo mặt hàng, checkbox ẩn/hiện dải
  mặc định bật, ẩn dataset dải khỏi legend).
- Tooltip: `TB {avg} (Thấp {min} – Cao {max}) VNĐ/KG (n báo giá)` mỗi mặt
  hàng + dòng chênh lệch giữa các mặt hàng — tái dùng nguyên `formatNumber`,
  `buildPriceDifferenceLines`, hạ tầng external-tooltip đã có.
- Click vào điểm → điều hướng `/quotes` lọc theo `materialId` +
  `deliveryMonth` (cố định) + khoảng `receivedDate` của tháng được click.
  **Cần kiểm tra lại `QuotesPage.vue`/`useQuotesPage.ts`** có đang hỗ trợ đọc
  `receivedDateStart`/`receivedDateEnd` qua query string chưa — nếu chưa,
  đây là gap tương tự `materialId` đã phát hiện và vá ở chart trước.

### Góc nhìn Data Analyst — insight chính

- Chart này phục vụ quyết định **THỜI ĐIỂM chốt mua** cho 1 kỳ giao hàng đã
  biết trước, khác hẳn mục đích "chọn nguyên liệu nào" của chart kia.
- Đề xuất v2 (không bắt buộc v1): vẽ 1 đường thẳng đứng đánh dấu "Hôm nay"
  nếu kỳ giao hàng được chọn vẫn còn trong tương lai — giúp người dùng biết
  đã đi được bao nhiêu phần trăm "vòng đời chào giá" của kỳ đó, và liệu xu
  hướng giá gần đây có đang tăng/giảm để cân nhắc chốt ngay hay chờ.

## 5. Trường Hợp Biên

1. Kỳ giao hàng đã qua (không còn báo giá mới phát sinh) → chart tĩnh, bỏ
   qua đường đánh dấu "Hôm nay".
2. Mặt hàng mới bắt đầu được chào giá muộn hơn mặt hàng kia (ví dụ NCC mới
   tham gia) → tháng đầu không có dữ liệu hiện đúng là khoảng trống
   (`spanGaps:false`), không nội suy — giống nguyên tắc chart trước.
3. Chọn 3 mặt hàng → dải MIN-MAX dễ rối, đã có sẵn cơ chế toggle từng mặt
   hàng để xử lý, không cần thêm gì mới.
4. Nếu người dùng đổi "Kỳ giao hàng" sau khi đã chọn mặt hàng → phải gọi lại
   API (tương tự cách `loadMaterialComparison` phản ứng khi đổi mặt hàng).

## 6. Vị Trí UI & Triển Khai

- Thêm 1 panel **thứ 3** trên Dashboard, tên đề xuất: **"Diễn biến giá theo
  thời gian chào giá"**, đặt sau panel "So sánh giá nguyên liệu theo kỳ hàng
  về".
- Không sửa backend. Tái dùng tối đa: MultiSelect mặt hàng, màu theo mặt
  hàng, dải MIN-MAX + toggle, tooltip, `buildPriceDifferenceLines`,
  `getOrCreateChartTooltipElement`. Phần code mới chủ yếu là: 1 hàm merge
  theo tháng-nhận-báo-giá (biến thể của `buildMaterialComparisonBuckets`,
  nhóm theo `receivedDate` thay vì `deliveryMonth`), state cho DatePicker kỳ
  giao hàng cố định, và tái tạo `comparisonChartData`/`comparisonChartOptions`
  cho trục X mới.
- Đề xuất triển khai bằng TDD (như chart trước), theo đúng thứ tự: chọn kỳ
  giao hàng + mặt hàng → fetch song song với `delivery_month` cố định →
  merge theo tháng nhận báo giá → callout chênh lệch → dataset chart → UI.
