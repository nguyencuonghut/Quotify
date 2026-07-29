# Journal Entry: Hoàn Thành Phase 7 (Backend & Frontend) - Ghi Chú Thị Trường & Lịch Sử Chỉnh Sửa

**Thời gian:** 2026-07-28  
**Tác giả:** Gemini  
**Chủ đề:** Triển khai tính năng Ghi chú thị trường dạng rich text an toàn và Lịch sử phiên bản (Revision History).

---

## Kiến Thức Bền Vững Đã Học (Durable Knowledge)

### 1. HTML Sanitization an toàn trong Python bằng `nh3`
- **Thách thức:** Lưu trữ ghi chú rich text HTML từ PrimeVue Editor tiềm ẩn nguy cơ bảo mật XSS lớn nếu không dọn dẹp kỹ.
- **Giải pháp:** Sử dụng thư viện Rust-based `nh3` (bọc ngoài thư viện `ammonia` của Rust).
- **Cấu hình allowlist V1 an toàn:**
  - Chỉ cho phép các thẻ cơ bản: `p`, `br`, `b`, `strong`, `i`, `em`, `ul`, `ol`, `li`, `a`.
  - Chỉ cho phép thuộc tính liên kết an toàn: `a` -> `href`, `target`, `rel`.
  - Chỉ cho phép các url scheme an toàn: `http`, `https`, `mailto`. Các protocol nguy hại như `javascript:` bị vô hiệu hóa tự động.
  - Khống chế payload tối đa 20 KB (20,480 ký tự) để chống các cuộc tấn công DoS/overflow.

### 2. Thiết kế DB Append-Only phục vụ lịch sử thay đổi (Revision History)
- **Mô hình:**
  - `QuoteNote`: 1-to-1 với `Quote`.
  - `QuoteNoteRevision`: Nhiều-to-1 với `QuoteNote`.
- **Cơ chế ghi:** Khi cập nhật ghi chú, hệ thống không bao giờ UPDATE nội dung cũ của `QuoteNoteRevision`. Thay vào đó, nó tính toán số hiệu phiên bản mới (`current_max_revision + 1`), ghi đè metadata `updated_at` ở `QuoteNote`, và chèn một dòng `QuoteNoteRevision` mới chứa thông tin tác giả (`author_id`), nội dung mới, và mốc thời gian.
- **Tối ưu hóa SQL Alchemy:** Sử dụng `selectinload(QuoteNote.revisions).selectinload(QuoteNoteRevision.author)` để nạp kèm toàn bộ revisions cùng thông tin tác giả chỉ trong một câu query duy nhất, tránh hoàn toàn lỗi N+1 query.

### 3. Tích hợp rich text editor trên giao diện PrimeVue v4
- **Thành phần:** Sử dụng component `<Editor>` của PrimeVue v4 kết hợp dependency `quill` phiên bản `2.0.2`.
- **Logic cập nhật phía Frontend:**
  - Khi load chi tiết báo giá (`loadQuote`), load song song thông tin note (`loadNote`).
  - Giao diện cung cấp chế độ Chỉnh sửa (Editor rich text) gated bằng quyền `quotes.update` và chế độ Đọc (render an toàn qua `v-html`).
  - Liệt kê toàn bộ lịch sử phiên bản của note. Khi click vào một phiên bản, một Dialog sẽ hiển thị nội dung HTML lịch sử của phiên bản đó giúp người dùng đối chiếu mà không gây xáo trộn nội dung hiện hành.
