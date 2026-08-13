# Kế Hoạch: Chart So Sánh Giá Theo Mùa Vụ Qua Các Năm (1 Mặt Hàng, 1 Tháng Hàng Về, Nhiều Năm)

> **V1 đã triển khai xong** (13/08/2026). Panel thứ 4 "So sánh giá theo mùa
> vụ qua các năm" đã lên Dashboard, triển khai theo TDD. Trục X tương đối
> ("T-11".."T0 (giao hàng)") đúng như thiết kế mục 2. Tổng quát hóa thêm
> `buildGroupedComparisonBuckets` (compareKeys/formatLabel tùy chỉnh) và
> `buildComparisonChartOptions` (formatSeriesRowLabel tùy chỉnh) — cả 2 chart
> cũ không đổi hành vi. Đã kiểm chứng bằng Playwright thật: Ngô hạt, tháng
> hàng về 10, năm 2024/2025/2026 — tooltip hiện đúng "2024 (04/2024): TB...",
> callout chênh lệch đúng, click-through điều hướng đúng
> `deliveryMonth`/`receivedDateStart`/`receivedDateEnd` riêng theo từng năm.

## 1. Bài Toán

Người dùng muốn so sánh **giá chào cho cùng 1 tháng hàng về (ví dụ tháng 10),
qua nhiều năm khác nhau** (2023, 2024, 2025, 2026), cho **1 loại nguyên liệu**.
Ví dụ: xem giá Ngô hạt cho hàng về tháng 10 của 4 năm liên tiếp, để trả lời
câu hỏi "giá năm nay đang cao/thấp hơn cùng kỳ mọi năm bao nhiêu?" và "diễn
biến giá tiến tới kỳ giao hàng có theo đúng quy luật mùa vụ mọi năm hay đang
bất thường?".

Điểm mấu chốt người dùng đã tự chỉ ra: **khoảng thời gian chào giá (ngày nhận
báo giá) của mỗi năm nằm ở vị trí lịch hoàn toàn khác nhau**:

| Tháng hàng về | Khoảng ngày nhận báo giá thực tế |
|---|---|
| 10/2026 | 01/2026 → 10/2026 |
| 10/2025 | 12/2024 → 09/2025 |
| 10/2024 | 11/2023 → 10/2024 |
| 10/2023 | 01/2023 → 10/2023 |

## 2. Quyết Định Thiết Kế Quan Trọng Nhất — Trục X Phải Là Thời Gian TƯƠNG ĐỐI, Không Phải Ngày Lịch Tuyệt Đối

Đây là điểm khác biệt bản chất so với 2 chart đã có (chart so sánh mặt hàng
theo kỳ hàng về, và chart diễn biến theo ngày báo giá cho 1 kỳ hàng về cố
định) — cả 2 chart đó đều dùng trục X là **ngày lịch tuyệt đối** (kỳ giao
hàng, hoặc tháng nhận báo giá), là đúng vì tất cả series so sánh **cùng nằm
trong 1 khung thời gian lịch**.

Ở đây thì KHÔNG: nếu vẽ trục X là ngày lịch tuyệt đối, 4 đường của 4 năm sẽ
nằm ở 4 vùng hoàn toàn tách biệt trên trục X (như bảng trên), **không chồng
lên nhau được nên không thể so sánh trực quan** — mất hết ý nghĩa của chart.

**Giải pháp**: đổi trục X thành **"số tháng trước kỳ giao hàng"** (tương đối,
không phải lịch tuyệt đối):

- `0` = đúng tháng hàng về (ví dụ tháng 10/2026 với đường của năm 2026).
- `-1` = 1 tháng trước hàng về (tháng 9/2026 cho đường 2026, tương ứng tháng
  9/2025 cho đường 2025, tháng 9/2024 cho đường 2024, ...).
- `-9` = 9 tháng trước hàng về, v.v.

Công thức: với mỗi báo giá, `offset = (năm_nhận×12 + tháng_nhận) −
(năm_hàng_về×12 + tháng_hàng_về)` (luôn ≤ 0). Nhờ vậy, dù 4 năm có khoảng
ngày lịch khác nhau hoàn toàn, khi quy về offset thì **cùng nằm chung 1 trục
X**, chồng lên nhau đúng theo "cùng giai đoạn trong vòng đời chào giá" — đây
mới là cách so sánh đúng ý nghĩa mùa vụ.

## 3. Rà Soát Dữ Liệu (Không Đoán)

Đã xác nhận lại (không cần đọc thêm — đúng pattern đã dùng ở 2 chart trước):

- Endpoint `GET /dashboard/quotify/price-trends` đã hỗ trợ sẵn `material_id` +
  `delivery_month` (khớp chính xác) — **không cần sửa backend**. Với chart
  này: gọi lại endpoint N lần song song, 1 lần/năm được chọn, cùng
  `material_id`, `delivery_month = <năm>-<tháng>-01`.
- Mỗi điểm trả về có `receivedDate` — đủ để tự tính `offset` ở frontend, không
  cần trường mới nào từ backend.

## 4. Thiết Kế

### Bộ lọc riêng cho panel (độc lập với bộ lọc chung Dashboard và 3 panel kia)

- **Nguyên liệu**: chọn **1** mặt hàng (Select, không phải MultiSelect — khác
  với 2 chart trước vì ở đây so sánh là GIỮA CÁC NĂM, mặt hàng luôn cố định).
- **Tháng hàng về**: chọn **1 tháng trong năm** (1–12), không gắn năm — ví dụ
  Select "Tháng 1" .. "Tháng 12". Đây là điểm khác với `DatePicker
  view="month"` đã dùng ở chart trước (chart trước cần cả tháng VÀ năm cụ thể;
  chart này chỉ cần THÁNG, năm sẽ do ô chọn năm dưới đây quyết định).
- **Các năm để so sánh**: MultiSelect chọn năm, tối đa **5 năm** (giữ pattern
  giới hạn giống `MAX_COMPARISON_MATERIALS` ở 2 chart trước, để chart không bị
  rối và không gọi API quá nhiều lần song song). Danh sách năm khả dụng: đề
  xuất tính động là "5 năm gần nhất tính đến năm hiện tại" (đơn giản, không
  cần query riêng để biết năm nào có dữ liệu).

### Trục & series

- Trục X: **offset tháng tương đối so với kỳ giao hàng** (xem mục 2), hiển thị
  dạng `T-9`, `T-8`, ..., `T-1`, `T0 (giao hàng)`.
- Trục Y: Giá quy đổi VNĐ/KG (giống mọi chart khác).
- Mỗi năm được chọn = 1 đường trung bình + dải MIN-MAX có thể toggle — **tái
  dùng y nguyên** cơ chế đã xây (bảng màu, checkbox ẩn/hiện dải mặc định bật,
  ẩn dataset dải khỏi legend). Legend hiển thị tên năm (`2023`, `2024`, ...)
  thay vì tên mặt hàng.
- Tooltip mỗi năm nên hiện thêm **tháng lịch thực tế** bên cạnh offset, vì
  offset là số trừu tượng — ví dụ dòng tooltip: `2026 (07/2026): TB 7.200
  (Thấp 7.000 – Cao 7.400) VNĐ/KG (12 báo giá)`, để người dùng biết chính xác
  tháng nào trên lịch đang được so sánh cho từng năm — tái dùng
  `formatNumber`, `buildPriceDifferenceLines` (so năm nào rẻ hơn/đắt hơn năm
  nào, cùng cơ chế 2-năm/3+-năm-so-với-rẻ-nhất đã có), hạ tầng external
  tooltip đã có.
- Click vào điểm (năm Y, offset K) → điều hướng `/quotes` lọc theo
  `materialId` + `deliveryMonth` (cố định theo năm Y) + khoảng `receivedDate`
  = đúng tháng lịch thực tế tương ứng offset K của năm Y (đã có sẵn trong dữ
  liệu tính offset, không cần tính lại) — cùng pattern click-through 2 chart
  trước.

### Góc nhìn Data Analyst — insight chính

- Câu hỏi chart này trả lời: **"Giá mùa vụ năm nay đang cao/thấp hơn cùng kỳ
  các năm trước bao nhiêu?"** và **"Diễn biến giá tiến tới kỳ giao hàng có
  đang theo đúng quy luật mùa vụ (ví dụ luôn tăng dần khi gần tới kỳ giao
  hàng) hay đang lệch bất thường so với các năm trước?"** — khác hẳn 2 chart
  đã có (chart 1: "mặt hàng nào rẻ hơn ở kỳ X"; chart 2: "chốt sớm hay muộn
  thì lợi hơn cho kỳ X cụ thể").
- Đây là kiểu phân tích **seasonality / year-over-year** kinh điển trong phân
  tích giá nông sản — rất có giá trị cho quyết định "năm nay nên chốt mua ở
  giai đoạn nào" dựa trên hình dạng đường giá lịch sử các năm trước cùng kỳ.

## 5. Trường Hợp Biên

1. Một năm được chọn hoàn toàn không có báo giá cho tháng hàng về đó → đường
   năm đó trống toàn bộ, hiện ghi chú "Năm 2023: chưa có báo giá cho tháng
   hàng về này" (không coi là lỗi).
2. Số tháng có dữ liệu (độ dài "vòng đời chào giá") khác nhau giữa các năm
   (ví dụ 9 tháng vs 12 tháng, đúng như bảng ở mục 1) → xử lý tự nhiên vì mỗi
   offset chỉ xuất hiện trên chart nếu có ít nhất 1 năm có dữ liệu ở offset
   đó — không cần ép các năm có cùng độ dài.
3. Năm hiện tại nếu kỳ giao hàng vẫn còn trong tương lai (ví dụ đang ở
   T-9/T-8, chưa tới T0) → dữ liệu năm đó chỉ có phần đầu, ngắn hơn các năm đã
   qua. **Không được diễn giải nhầm "giá thấp hơn"** chỉ vì thiếu offset gần
   T0 — nên thêm chú thích nhỏ nếu năm gần nhất chưa đủ dữ liệu tới T0.
4. Chọn 4-5 năm cùng lúc → dải MIN-MAX dễ rối, tái dùng cơ chế toggle từng năm
   đã có, không cần thêm gì mới.
5. Đổi mặt hàng hoặc đổi tháng hàng về sau khi đã chọn năm → gọi lại API
   (giống cách 2 chart trước phản ứng khi đổi bộ lọc).

## 6. Ghi Chú Kỹ Thuật Khi Triển Khai (Không Phải Thiết Kế, Để Tham Khảo Sau)

Khác với 2 chart trước (nhóm theo khóa là CHUỖI ngày lịch, ví dụ `"2026-07-01"`
— sắp theo `localeCompare` vẫn đúng vì chuỗi ISO sắp đúng thứ tự thời gian),
chart này nhóm theo **offset là SỐ NGUYÊN có thể âm** (`-9`, `-8`, ..., `0`).
`localeCompare` trên chuỗi số âm SẼ SAI thứ tự (ví dụ chuỗi `"-9"` >
`"-8"` theo so sánh ký tự, ngược với thứ tự số học đúng là `-9 < -8`). Khi
triển khai cần tổng quát hóa thêm `buildGroupedComparisonBuckets` để nhận
comparator sắp xếp tùy chỉnh (hoặc nhóm theo số rồi format hiển thị riêng),
không thể tái dùng nguyên bản hàm hiện tại. Các phần còn lại (band toggle,
tooltip, callout chênh lệch, palette, click-through) tái dùng được như đã nêu
ở mục 4.

## 7. Vị Trí UI & Triển Khai

- Thêm 1 panel **thứ 4** trên Dashboard, tên đề xuất: **"So sánh giá theo mùa
  vụ qua các năm"**, đặt sau panel "Diễn biến giá theo thời gian chào giá".
- Không sửa backend. Tái dùng tối đa: màu theo series, dải MIN-MAX + toggle,
  tooltip, `buildPriceDifferenceLines`, `getOrCreateChartTooltipElement`,
  pattern gọi API N lần song song + merge ở frontend, pattern click-through.
  Phần code mới chủ yếu là: hàm tính `offset` tháng tương đối từ
  `receivedDate` + `deliveryMonth` của từng lần gọi, và bản tổng quát hóa
  thêm của hàm bucket để sắp đúng theo số học (mục 6).
- Đề xuất triển khai bằng TDD (như 2 chart trước) khi được duyệt, theo đúng
  thứ tự: chọn mặt hàng + tháng hàng về + các năm → fetch song song với
  `delivery_month` khác nhau mỗi năm → tính offset & merge theo offset →
  callout chênh lệch → dataset chart → UI.
