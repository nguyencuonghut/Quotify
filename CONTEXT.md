# Quotify

Quotify lưu trữ lịch sử báo giá nguyên liệu và cung cấp dữ liệu tham khảo cho hoạt động mua hàng của phòng Thu Mua.

## Ngôn ngữ nghiệp vụ

**Phiếu báo giá**:
Báo giá nhận được từ một nhà cung cấp, giữ danh tính ổn định của báo giá qua nhiều lần điều chỉnh. Ngày báo giá, ngày nhận báo giá và tệp báo giá gốc thuộc về từng phiên bản báo giá.
_Tránh_: Bản ghi giá

**Dòng báo giá**:
Mức giá của một vật tư cho một kỳ giao hàng trong một phiên bản phiếu báo giá.
_Tránh_: Phiếu báo giá

**Phiên bản báo giá**:
Một snapshot đầy đủ của phiếu báo giá tại một lần nhà cung cấp phát hành hoặc điều chỉnh giá. Phiên bản mới thay thế cho việc ghi đè phiên bản cũ.
_Tránh_: Báo giá đã sửa

**Ngày báo giá**:
Ngày nhà cung cấp ghi trên phiếu báo giá.

**Ngày nhận báo giá**:
Ngày phòng Thu Mua thực tế nhận được báo giá.
_Tránh_: Ngày nhập

**Kỳ giao hàng**:
Tháng và năm dự kiến nhận lô hàng được chào giá.
_Tránh_: Ngày giao hàng

**Tỷ giá quy đổi**:
Tỷ giá USD bán ra của Vietcombank; tỷ giá có thể được nhập tay cho báo giá nhận trong quá khứ hoặc khi không lấy được tỷ giá tự động.
_Tránh_: Tỷ giá hiện tại

**Thuế nhập khẩu**:
Tỷ lệ phần trăm áp trên giá gốc USD/MT trước khi quy đổi sang VNĐ/KG; cấu hình hệ thống, mặc định `0%`.
_Tránh_: Chi phí quy đổi

**Chi phí làm hàng**:
Khoản chi phí cố định tính theo VNĐ/KG được cộng vào giá sau khi đổi từ USD/MT; cấu hình hệ thống, mặc định `200 VNĐ/KG`. Tên cũ là "Chi phí quy đổi" trước khi hệ thống tách riêng thuế nhập khẩu.
_Tránh_: Phí vận chuyển, Chi phí quy đổi

**Giá quy đổi**:
Giá VNĐ/KG được tính từ giá gốc USD/MT, tỷ giá quy đổi, thuế nhập khẩu và chi phí làm hàng theo công thức
`Giá quy đổi = (Giá USD/MT / 1000) * (1 + Thuế nhập khẩu) * Tỷ giá + Chi phí làm hàng`.
_Tránh_: Giá gốc

**Nhập lại báo giá**:
Việc nhập vào hệ thống một báo giá đã nhận trong quá khứ hoặc có kỳ giao hàng đã qua, tính theo múi giờ nghiệp vụ `Asia/Ho_Chi_Minh`.
_Tránh_: Sửa ngày báo giá

**Ghi chú thị trường**:
Nhận định có lịch sử riêng do người dùng bổ sung cho báo giá.
_Tránh_: Audit log

**Ghi chú dòng báo giá**:
Ghi chú ngắn gắn với một dòng báo giá cụ thể, hiện tại chỉ lưu tối đa một ghi
chú/dòng và không có lịch sử chỉnh sửa; khác với "Ghi chú thị trường" (gắn với
cả phiếu báo giá, có lịch sử chỉnh sửa riêng). Chủ yếu dùng khi import lại báo
giá cũ.
_Tránh_: Ghi chú thị trường

**Import báo giá cũ (Backfill Import)**:
Việc nhập lại nhiều báo giá lịch sử cùng lúc bằng file CSV, mỗi dòng file là
một dòng báo giá; các dòng cùng nhà cung cấp và cùng ngày nhận báo giá được
gộp vào một phiếu. Với dòng USD/MT, tỷ giá, thuế nhập khẩu và chi phí làm
hàng đều phải nhập tay theo giá trị tại đúng thời điểm đó, không dùng cấu
hình hiện hành. Phiếu tạo ra từ import có hiệu lực ngay (`confirmed`), không
qua bước xác nhận thủ công.
_Tránh_: Nhập lại báo giá (khái niệm chung, không nhất thiết qua file)

**Đã chốt mua**:
Dấu xác nhận công ty đã mua theo dòng báo giá tương ứng; Quotify ghi nhận thời điểm người dùng đánh dấu trong hệ thống.
_Tránh_: Quyết định mua

**Thời điểm đánh dấu chốt mua**:
Thời điểm người dùng tick "Đã chốt mua" trong Quotify. Đây là mốc phân tích hệ thống biết được, không nhất thiết là thời điểm ký hợp đồng hoặc phát sinh giao dịch thực tế.
_Tránh_: Ngày mua

**Người nhập phiếu**:
Người tạo phiếu báo giá ban đầu trong Quotify và là nguồn tính KPI số phiếu theo user.
_Tránh_: Người sửa phiên bản mới nhất

**Liên kết Telegram**:
Quan hệ giữa một người dùng Quotify và một tài khoản Telegram (nhận diện bằng mã người dùng Telegram, không phải username). Mỗi người dùng chỉ có tối đa một liên kết đang hiệu lực và mỗi tài khoản Telegram chỉ gắn với tối đa một người dùng.
_Tránh_: Kết nối Telegram

**Đường dẫn liên kết**:
URL `https://t.me/<bot>?start=<mã>` do trang Hồ sơ tạo, người dùng mở trong Telegram để hoàn tất liên kết. Chỉ hiển thị một lần ở phiên đã tạo và có hiệu lực 10 phút.
_Tránh_: Liên kết (đứng một mình để chỉ URL)

**Mã liên kết**:
Chuỗi bí mật dùng một lần nằm trong đường dẫn liên kết; hệ thống chỉ lưu bản băm.
_Tránh_: Token (trong chuỗi hiển thị cho người dùng)

**Hủy liên kết**:
Hành động của người dùng (ở trang Hồ sơ hoặc bằng lệnh `/stop`) để ngừng nhận thông báo; liên kết chuyển sang trạng thái đã thu hồi và vẫn được giữ làm lịch sử.

**Đổi tài khoản Telegram**:
Liên kết sang một tài khoản Telegram khác; liên kết cũ bị thu hồi cùng lúc với việc tạo liên kết mới (hoặc cả hai cùng không đổi nếu thất bại).

**Điểm giá**:
Giá thấp nhất (VNĐ/KG, giá đã lưu) của một chuỗi trong một ngày nhận báo giá. Là đơn vị để so sánh biến động.
_Tránh_: Giá hôm nay, Dòng giá

**Chuỗi giá**:
Cặp (vật tư, kỳ giao hàng). Biến động giá được tính trong từng chuỗi, không gộp các kỳ giao hàng khác nhau.
_Tránh_: Mã hàng

**Cửa sổ tham chiếu**:
7 ngày làm việc liền trước ngày của điểm giá mới. Giá tham chiếu (thấp nhất, cao nhất, gần nhất) lấy từ các điểm giá trong cửa sổ này.
_Tránh_: 7 ngày (nếu hiểu là ngày lịch)

**Ngày làm việc**:
Thứ Hai đến thứ Sáu. Chưa loại ngày lễ và Tết. Điểm nhận vào cuối tuần vẫn là điểm tham chiếu.
_Tránh_: Ngày thường

**Biến động giá**:
Thay đổi của điểm giá mới so với giá tham chiếu, được phát hiện bằng bộ ba quy tắc R1 (so với điểm gần nhất), R2 (so với giá thấp nhất), R3 (so với giá cao nhất) và phải cùng hướng.
_Tránh_: Cảnh báo giá, Tăng giảm giá

**Mức biến động**:
Nhẹ, Trung bình hoặc Lớn, phân theo ngưỡng phần trăm của từng vật tư (mặc định 2,5%, 5% và 10%).
_Tránh_: Mức độ nghiêm trọng

**Ngưỡng cảnh báo**:
Ba mức phần trăm phân biệt Nhẹ, Trung bình và Lớn. Có giá trị mặc định chung và có thể ghi đè theo từng vật tư.
_Tránh_: Giới hạn

**Nguồn kích hoạt**:
Phiên bản báo giá được chốt có thể sinh thông báo biến động: không do tài khoản import (admin hệ thống) tạo và có độ trễ không quá 3 ngày làm việc từ ngày nhận đến ngày chốt. Phiên bản không phải nguồn kích hoạt vẫn được dùng làm điểm tham chiếu.
_Tránh_: Báo giá mới

**Giá bất thường**:
Điểm giá lệch quá 30% so với trung vị 30 ngày của chuỗi, nghi nhập sai. Bị loại khỏi tính toán biến động và gửi thành thẻ để trưởng phòng xem xét.
_Tránh_: Giá sai (chưa kết luận)

**Sự kiện biến động**:
Bản ghi hệ thống ghi nhận một biến động giá của một chuỗi, trước khi quyết định gửi cho ai.
_Tránh_: Thông báo

**Tin thông báo**:
Một tin Telegram gửi cho một người nhận về một vật tư trong một lần quét; có thể gộp nhiều kỳ giao hàng.
_Tránh_: Sự kiện

**Bản tin tổng hợp**:
Tin gửi lúc 08:00 giờ Việt Nam gom các biến động mức Nhẹ (giai đoạn 1C, chưa có ở 1B).
_Tránh_: Báo cáo ngày

**Trưởng phòng**:
Người dùng có quyền nhận thông báo của mọi vật tư (`price_alerts.receive_all`), thường là vai trò `manager`. Không nhận biết bằng tên vai trò trong code.
_Tránh_: Quản lý (nếu chỉ dựa vào tên role)

**Admin hệ thống**:
Tài khoản seed (`AUTH_SEED_ADMIN_EMAIL`) chỉ dùng để quản trị và import, không nhập tay và không nhận thông báo biến động. Phiếu do tài khoản này tạo được xem là import.
_Tránh_: Admin (khi muốn nói người dùng có role admin bình thường)

