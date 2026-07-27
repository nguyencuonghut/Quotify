# Quotify

Quotify lưu trữ lịch sử báo giá nguyên liệu và cung cấp dữ liệu tham khảo cho hoạt động mua hàng của phòng Thu Mua.

## Ngôn ngữ nghiệp vụ

**Phiếu báo giá**:
Báo giá nhận được từ một nhà cung cấp, chứa thông tin chung và một hoặc nhiều dòng báo giá.
_Tránh_: Bản ghi giá

**Dòng báo giá**:
Mức giá của một vật tư cho một kỳ giao hàng trong một phiên bản phiếu báo giá.
_Tránh_: Phiếu báo giá

**Phiên bản báo giá**:
Một lần phát hành của phiếu báo giá; phiên bản mới thay thế cho việc ghi đè phiên bản cũ khi nhà cung cấp điều chỉnh giá.
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

**Chi phí quy đổi**:
Khoản chi phí cố định tính theo VNĐ/KG được cộng vào giá sau khi đổi từ USD/MT.
_Tránh_: Phí vận chuyển

**Giá quy đổi**:
Giá VNĐ/KG được tính từ giá gốc USD/MT, tỷ giá quy đổi và chi phí quy đổi.
_Tránh_: Giá gốc

**Nhập lại báo giá**:
Việc nhập vào hệ thống một báo giá đã nhận trong quá khứ hoặc có kỳ giao hàng đã qua.
_Tránh_: Sửa ngày báo giá

**Ghi chú thị trường**:
Nhận định có lịch sử riêng do người dùng bổ sung cho báo giá.
_Tránh_: Audit log

**Đã chốt mua**:
Dấu xác nhận công ty đã mua theo dòng báo giá tương ứng.
_Tránh_: Quyết định mua
