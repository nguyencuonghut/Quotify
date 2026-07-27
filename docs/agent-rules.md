# Quy Tắc Agent Của Dự Án

Các rule dưới đây là bắt buộc đối với bất kỳ AI agent nào làm việc trong repository này.

## Trước mọi task

Agent phải đọc:

1. `AGENTS.md`
2. `memory-bank/quick-start.md`
3. `memory-bank/activeContext.md`
4. `memory-bank/progress.md`
5. `memory-bank/projectRules.md`
6. `memory-bank/techContext.md`

## Các rule cốt lõi

1. Không bao giờ được phỏng đoán.
Nếu một thông tin chưa được xác minh từ code, test, command output hoặc tài liệu có trích dẫn, phải nói rõ là chưa xác minh và kiểm tra trước.

2. Đọc bug memory cũ trước khi thay đổi hành vi.
Luôn tham khảo `memory-bank/bugPatterns.md` để kiểm tra các defect cũ và nguy cơ regression liên quan.

3. Biến mọi fix quan trọng thành memory.
Sau khi sửa bug, phải ghi lại:
   - trigger
   - root cause
   - final fix
   - regression test hoặc guardrail

4. Tuân thủ coding style đã có.
Phải bám theo naming, cấu trúc, style validation và pattern test của codebase hiện tại.

5. Không dùng style block trong `.vue`.
Style phải nằm trong hệ thống `src/styles/` tập trung, ưu tiên `.scss`, với class naming rõ ràng để tránh xung đột.

6. Chỉ tôn trọng tech stack đã được xác minh.
`memory-bank/techContext.md` là nguồn sự thật. Nếu code chứng minh file này sai hoặc thiếu, phải cập nhật file thay vì tự ngầm giả định.

7. Ưu tiên bằng chứng hơn sự tự tin.
File reference, command result và test output luôn đáng tin hơn trực giác.

8. Giữ rule và memory luôn đồng bộ.
Nếu dự án phát hiện thêm một pattern lặp lại, phải cập nhật `memory-bank/projectRules.md` hoặc `memory-bank/bugPatterns.md`.

9. Giao diện phải mobile responsive.
Mọi layout, page và shared component phải hoạt động tốt trên mobile, tablet và desktop. Không được thiết kế admin UI theo kiểu desktop-only rồi mới vá responsive về sau.

10. Font UI mặc định là `Be Vietnam Pro`.
Không tự ý đổi sang font khác nếu chưa có quyết định thiết kế mới ở cấp hệ thống.

11. Timezone mặc định của hệ thống là `Asia/Ho_Chi_Minh` (`GMT+7`).
Khi nhập liệu, lưu trữ, parse, format và hiển thị thời gian, phải nói rõ đang dùng timezone nào. Không được ngầm dựa vào timezone của máy người dùng hay timezone mặc định của runtime.

12. Phải phòng ngừa bug ngày giờ trước khi code.
Đặc biệt chú ý các lỗi:
   - lệch ngày do parse `YYYY-MM-DD` như UTC thay vì local business date
   - hiển thị sai ngày khi convert giữa UTC và `Asia/Ho_Chi_Minh`
   - gửi datetime không kèm timezone hoặc offset
   - dùng lẫn lộn `date` và `datetime`
   - filter từ ngày/đến ngày bị lệch biên đầu ngày hoặc cuối ngày

13. Bắt buộc xác minh tích hợp & E2E thực tế.
Không bao giờ được kết luận một bug đã sửa xong dựa trên việc unit test hoặc static check (lint, compile) vượt qua, đặc biệt là các lỗi liên quan đến cookie, CORS, bảo mật trình duyệt, Local Storage, hoặc định tuyến Docker network.
Các lớp bảo mật và hạ tầng này thường bị mock trong unit test nên dễ gây báo cáo thành công giả (false positive).
Đối với các lỗi tích hợp hoặc giao diện, bắt buộc phải thực hiện tối thiểu một trong hai hình thức:
   - Chạy suite test E2E thực tế (`make docker-test-e2e` hoặc lệnh tương đương).
   - Sử dụng `browser_subagent` để mở trình duyệt, thao tác thực tế và kiểm tra console/network logs.

14. Khởi tạo phiên làm việc (Session Initialization / Silent Refresh) không được dựa vào Local Storage.
Trạng thái đăng nhập ở client-side phải được xác thực trực tiếp thông qua sự tồn tại của Cookie từ backend (ví dụ: `fastapivue_logged_in`). Tuyệt đối không dùng cờ trạng thái trong Local Storage để tự động trigger `/auth/refresh` cho người dùng chưa đăng nhập. Việc sử dụng Local Storage có thể dẫn đến lệch trạng thái với cookie thực tế (do Local Storage không có cơ chế tự hết hạn), từ đó tạo ra các yêu cầu refresh dư thừa và phát sinh lỗi `401 Unauthorized` không đáng có trong browser console.
Đặc biệt, khi phiên làm việc bị từ chối bởi backend (lỗi 401/403) hoặc khi clear trạng thái xác thực, frontend bắt buộc phải xóa cookie `fastapivue_logged_in` bằng cách đặt `max-age=0` để tránh tạo ra vòng lặp gửi yêu cầu refresh vô hạn trong các lần reload trang tiếp theo.


15. Tự động chạy migrations và seeding trong Docker dev/test:
Để tránh lỗi `UndefinedTableError` khi trình duyệt tự động gọi API (như silent refresh) ngay khi frontend khởi động trên một volume database rỗng, các dịch vụ backend chạy trong Docker dev (`docker-compose.yml`) hoặc test/E2E (`docker-compose.test.yml`) bắt buộc phải khai báo lệnh khởi động chạy tự động `alembic upgrade head` và file seeding dữ liệu trước khi chạy server Uvicorn.

16. Không return đối tượng Response trực tiếp từ route 204 No Content trong FastAPI:
Khi thiết kế API trả về mã `204 No Content`, tuyệt đối không được sử dụng lệnh `return response` (trả về đối tượng `fastapi.Response` được inject qua dependency). Hành động này sẽ dẫn đến xung đột giao thức ASGI (mã trạng thái 200 mặc định của đối tượng Response đối chọi với cấu hình 204 của decorator), gây crash kết nối và làm proxy (Vite dev proxy, Nginx) báo lỗi `502 Bad Gateway`. Nếu cần chỉnh sửa cookie hoặc header, hãy thay đổi trực tiếp trên đối tượng `response` được inject, nhưng hàm endpoint phải trả về `None` (hoặc không dùng `return`).

17. Parse body response an toàn ở frontend:
Khi nhận response từ API, không được tự động parse JSON trực tiếp bằng `response.json()` mà không kiểm tra độ dài hoặc cấu trúc body, kể cả khi header trả về là `application/json`. Nhiều trường hợp API trả về mã thành công (ví dụ 204, 205 hoặc 200 rỗng) nhưng không đi kèm nội dung body, dẫn đến lỗi `SyntaxError: Unexpected end of JSON input`. Client HTTP (`frontend/src/api/http.ts`) phải đọc body dưới dạng text (`response.text()`) và chỉ gọi `JSON.parse` khi text đó không rỗng, đồng thời bọc trong khối try-catch an toàn để tránh crash ứng dụng.

18. Kiểm thử toàn bộ vòng đời tính năng (Full Feature Lifecycle Verification):
Khi sửa bất kỳ lỗi nào trong một module (như Authentication, File Upload, Users CRUD), không được phép chỉ kiểm tra một hàm hoặc một dòng code được sửa. Agent bắt buộc phải chạy thử toàn bộ vòng đời của tính năng đó trên trình duyệt thực tế. 
Ví dụ: Khi sửa lỗi refresh token hoặc login, bắt buộc phải test chuỗi hành động: Đăng nhập -> F5 reload trang -> Truy cập trang bảo mật -> Thực hiện đăng xuất -> Kiểm tra việc bị đá về trang login. Không được bỏ qua bất kỳ bước nào trong chu trình sử dụng của người dùng.

19. Mọi form input bắt buộc phải có dấu sao đỏ.
Với tất cả field bắt buộc nhập liệu, label hiển thị cho người dùng phải có dấu `*` màu đỏ để báo rõ đây là thông tin bắt buộc. Không được chỉ dựa vào placeholder, validation message hoặc trạng thái lỗi sau submit để truyền đạt requirement này.

## Kết quả mong muốn





Agent phải hành xử như một thành viên trong team có hệ thống ghi nhớ bằng văn bản, không phải như một chat model chỉ dựa vào context ngắn hạn.
