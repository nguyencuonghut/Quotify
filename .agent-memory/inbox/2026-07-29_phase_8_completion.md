# Journal Entry: Hoàn Thành Phase 8 - Bảng Báo Giá Và Lịch Sử

**Thời gian:** 2026-07-29  
**Tác giả:** Gemini  
**Chủ đề:** Xây dựng màn hình tra cứu, so sánh biến động giá phẳng (flattened rows) từ tất cả các phiên bản và dòng báo giá vật tư.

---

## Kiến Thức Bền Vững Đã Học (Durable Knowledge)

### 1. CQRS Read Path Optimization (Phân tách luồng đọc)
- **Vấn đề:** Báo giá được cấu trúc dạng cây 3 lớp (`Quote` -> `QuoteVersion` -> `QuoteLine`). Khi tra cứu lịch sử giá và so sánh biến động giữa các nhà cung cấp, việc fetch thông tin theo cây sẽ cực kỳ chậm và gây khó khăn cho việc phân trang, sắp xếp trên DataTable.
- **Giải pháp:** Xây dựng `QuoteQueryService` làm nhiệm vụ đọc phẳng (flattened read path). Thực hiện một câu query join trực tiếp từ `QuoteLine` nối với tất cả các bảng catalog liên quan (`Supplier`, `Material`, `MaterialType`, `QuoteVersion`, `Quote`, `User`).
- **Ưu điểm:** Phân trang offset và sorting hoạt động tức thì ở tầng DB. Tránh hoàn toàn lỗi N+1 query bằng cách lấy chính xác các cột cần thiết cho bảng phẳng, tối ưu hóa băng thông truyền tải.

### 2. Tinh tế trong Active Route Highlight ở Sidebar
- **Vấn đề:** Khi người dùng click một dòng trên Bảng báo giá, hệ thống sẽ chuyển hướng sang trang chi tiết báo giá `/quotes/{quoteId}`. Do `/quotes/{quoteId}` là một route động, nếu sử dụng so sánh tuyệt đối hoặc so sánh tiền tố đơn thuần, sidebar có thể bị mất highlight, hoặc tệ hơn là highlight nhầm sang menu "Nhập báo giá" (vì cùng tiền tố `/quotes`).
- **Giải pháp:** Cải tiến hàm khớp route active `isItemActive(item)`:
  - Menu `Nhập báo giá` (`/quotes/new`): Chỉ active khi route đúng `/quotes/new` hoặc các route kết thúc bằng `/versions/new` hoặc `/edit`.
  - Menu `Bảng báo giá` (`/quotes`): Active khi route bắt đầu bằng `/quotes` ngoại trừ `/quotes/new` và các sub-routes tạo phiên bản/edit ở trên.
  - Kết quả: Sidebar luôn highlight đúng bối cảnh nghiệp vụ đang thao tác của người dùng.

### 3. Phân trang Lazy với Custom Date Filters trên PrimeVue v4
- Việc lưu trữ Kỳ giao hàng (`delivery_month`) dưới dạng `Date` (ngày đầu tháng) yêu cầu frontend gửi chính xác filter để backend so sánh. Sử dụng PrimeVue `DatePicker` ở chế độ `view="month"` và `dateFormat="yy-mm"` giúp người dùng chọn tháng giao hàng một cách mượt mà và trực quan, tự động reload lại dữ liệu DataTable lazy qua composable.
