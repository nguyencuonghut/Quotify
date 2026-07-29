# Journal Entry: Sửa và Xóa Ghi Chú Thị Trường Inline kiểu Facebook (Phase 7 - Cải tiến)

**Thời gian:** 2026-07-29  
**Tác giả:** Gemini  
**Chủ đề:** Hỗ trợ Thêm, Sửa, và Xóa inline từng phiên bản ghi chú thị trường theo phong cách thảo luận bình luận.

---

## Kiến Thức Bền Vững Đã Học (Durable Knowledge)

### 1. Quản lý trạng thái Inline Edit trong Vue 3
- **Thách thức:** Khi hiển thị danh sách ghi chú dạng timeline hoặc comments, làm thế nào để người dùng sửa một ghi chú cụ thể ngay tại chỗ (inline) mà không làm ảnh hưởng đến các ghi chú khác?
- **Giải pháp:** Sử dụng một biến phản xạ `isEditingRevisionId = ref<string | null>(null)` lưu trữ ID của revision đang sửa. 
  - Trong vòng lặp `v-for`, ta kiểm tra điều kiện `v-if="isEditingRevisionId === rev.id"`.
  - Nếu đúng, ta thay thế view tĩnh bằng thẻ `<Editor>` liên kết với một biến tạm `editingRevisionContent`.
  - Khi lưu hoặc hủy, ta reset ID về `null`, giúp UI trở lại trạng thái đọc mượt mà và trực quan.

### 2. Tự động dọn dẹp dữ liệu cha ở Database (Cascade Cleanup)
- **Thách thức:** Khi xóa revision cuối cùng của một ghi chú, bản ghi `QuoteNote` cha (chỉ mang tính chất container liên kết với Quote) sẽ trở nên vô nghĩa và mồ côi trong DB.
- **Giải pháp:** Trong service layer `delete_revision`:
  - Thực thi xóa `QuoteNoteRevision` tương ứng.
  - Gọi `flush()` để đồng bộ trạng thái xóa trong transaction.
  - Thực hiện query đếm số lượng revisions còn lại liên kết với `note_id`.
  - Nếu số lượng đếm được bằng `0`, tự động gọi `delete(note)` để xóa luôn bản ghi container cha.
  - Điều này giúp dọn dẹp DB sạch sẽ và tránh các lỗi orphan records mà không cần cấu hình cascade phức tạp ở mức Schema.

### 3. Tối ưu hóa cập nhật Local State trong Composables
- **Thách thức:** Khi cập nhật hoặc xóa một phần tử con qua API thành công, nếu gọi lại API fetch toàn bộ detail sẽ gây tốn tài nguyên mạng và nhấp nháy UI.
- **Giải pháp:** Cập nhật cục bộ (Optimistic/Local State Mutation) trong composable:
  - Khi sửa: Tìm index của revision trong mảng `note.value.revisions` và ghi đè bằng đối tượng revision mới trả về từ API.
  - Khi xóa: Lọc bỏ phần tử bị xóa ra khỏi mảng bằng `filter()`. Nếu mảng sau lọc bị rỗng, reset `note.value` về cấu trúc mặc định trống.
  - Điều này mang lại trải nghiệm phản hồi tức thời cực kỳ mượt mà.
