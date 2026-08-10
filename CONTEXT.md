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

**Đã chốt mua**:
Dấu xác nhận công ty đã mua theo dòng báo giá tương ứng; Quotify ghi nhận thời điểm người dùng đánh dấu trong hệ thống.
_Tránh_: Quyết định mua

**Thời điểm đánh dấu chốt mua**:
Thời điểm người dùng tick "Đã chốt mua" trong Quotify. Đây là mốc phân tích hệ thống biết được, không nhất thiết là thời điểm ký hợp đồng hoặc phát sinh giao dịch thực tế.
_Tránh_: Ngày mua

**Người nhập phiếu**:
Người tạo phiếu báo giá ban đầu trong Quotify và là nguồn tính KPI số phiếu theo user.
_Tránh_: Người sửa phiên bản mới nhất
