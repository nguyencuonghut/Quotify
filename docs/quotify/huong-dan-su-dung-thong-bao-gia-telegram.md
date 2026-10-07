# Hướng Dẫn Sử Dụng: Thông Báo Biến Động Giá Qua Telegram

Tài liệu dành cho người dùng Quotify (nhân viên nhập báo giá, trưởng phòng, admin). Không cần biết kỹ thuật. Cập nhật 2026-10-07.

## 1. Tính năng này làm gì?

Quotify tự theo dõi giá trong các phiếu báo giá đã chốt và **báo cho bạn qua Telegram** khi có chuyện đáng chú ý, để bạn không phải mở bảng giá soi từng vật tư:

| Bạn nhận được | Khi nào | Ví dụ ngắn |
|---|---|---|
| **Tin biến động giá** | Giá một vật tư tăng hoặc giảm đáng kể so với những ngày gần đây | "🟠 TĂNG TRUNG BÌNH · Ngô hạt, 7,720 → 8,150" |
| **Bản tin 08:00** | Mỗi sáng, gom các biến động nhẹ của hôm trước | "📋 Bản tin giá · 07/10" |
| **Cảnh báo giá bất thường** | Một mức giá lệch quá xa giá gần đây, nghi nhập sai | "⚠️ GIÁ BẤT THƯỜNG · Threonine" |
| **Nhắc cập nhật giá** | Một vật tư lâu không có giá mới | "⏰ 13 vật tư chưa có giá mới" |

Ngoài Telegram, trên web còn có: trang **Giá bất thường** (xem và duyệt các giá nghi sai), trang **Thông báo giá** (cài đặt, dành cho trưởng phòng và admin), và bảng **Độ mới của giá theo vật tư** ở Dashboard.

Hệ thống chỉ **thông báo**, không tự sửa giá, không tự mua bán và không khuyến nghị mua hay bán.

## 2. Ai nhận gì?

| Vai trò | Tin biến động giá | Bản tin 08:00 | Giá bất thường | Nhắc cập nhật giá |
|---|---|---|---|---|
| **Trưởng phòng (Manager)** | Mọi vật tư, mặc định từ mức **Trung bình** | Nếu bạn chọn mức tối thiểu là Nhẹ | Có, **kèm nút duyệt** | Mọi vật tư đến hạn nhắc |
| **Nhân viên nhập báo giá (User)** | Vật tư **bạn đã nhập trong 90 ngày gần đây**, mặc định từ mức **Nhẹ** | Có (các tin mức Nhẹ nằm ở đây) | Chỉ khi **chính bạn nhập** giá đó, **không có nút duyệt** | Chỉ vật tư bạn đã nhập gần đây |
| **Admin** | Chỉ khi bạn tự bật "nhận mọi thông báo" ở Hồ sơ | như trên | có nút duyệt nếu nhận | Chỉ khi bật như trên |

Muốn nhận được tin, bạn cần: (1) đã **liên kết Telegram** (mục 3); (2) không tắt thông báo ở Hồ sơ (mục 8). Tài khoản quản trị hệ thống dùng để import dữ liệu **không bao giờ nhận tin**.

> Tính năng được đưa vào dùng dần. Nếu bạn đã liên kết mà chưa nhận tin, có thể bạn chưa nằm trong nhóm đang chạy thử; hỏi quản trị viên.

## 3. Bắt đầu: liên kết tài khoản Telegram

Chỉ cần làm một lần.

1. Đăng nhập Quotify, vào **Hồ sơ** (bấm ảnh đại diện góc trên bên phải), tìm mục **Thông báo Telegram**.
2. Bấm **Liên kết Telegram**. Hệ thống tạo một đường dẫn và mã QR **dùng một lần, hết hạn sau 10 phút**.
3. Trên điện thoại, quét mã QR, hoặc bấm **Mở Telegram**, hoặc **Sao chép đường dẫn** rồi dán vào Telegram.
4. Trong cuộc trò chuyện với **Quotify Bot**, bấm **Start** (Bắt đầu).
5. Bot trả lời xác nhận, và trang Hồ sơ đổi sang **Đã liên kết** sau vài giây.

Lưu ý:
- Đừng gửi đường dẫn hay mã QR cho người khác. Mỗi tài khoản Telegram chỉ liên kết được với **một** tài khoản Quotify, và ngược lại.
- Bot **không bao giờ** hỏi mật khẩu Quotify của bạn.
- Chỉ dùng được trong **chat riêng** với bot, không dùng trong nhóm.
- Quá 10 phút chưa bấm Start: bấm **Tạo đường dẫn mới**. Muốn bỏ yêu cầu: **Hủy yêu cầu**.
- **Đổi sang Telegram khác:** bấm **Đổi tài khoản Telegram** rồi làm lại từ bước 3 bằng Telegram mới; liên kết cũ tự bị thu hồi.
- **Ngừng nhận tin:** ở Hồ sơ bấm **Hủy liên kết**, hoặc gõ `/stop` trong chat với bot. Muốn nhận lại thì liên kết lại.

Các lệnh của bot: `/start` (kiểm tra trạng thái), `/help` (trợ giúp), `/stop` (hủy liên kết).

Nếu bạn **chặn bot** trong Telegram thì hệ thống không gửi được tin; mở Telegram, bỏ chặn bot rồi làm mới trang Hồ sơ.

## 4. Tin biến động giá

### 4.1 Khi nào có tin?

Mỗi khi một phiếu báo giá được **chốt** (không phải bản nháp), hệ thống so sánh giá mới của từng vật tư và từng **kỳ giao hàng** với các ngày gần đây. Giá được so là **giá quy đổi VNĐ/KG**, và mỗi ngày lấy **giá thấp nhất** trong ngày, **không phân biệt nhà cung cấp**.

Giá mới được so với:
- **Giá gần nhất** trước đó (luôn so);
- **Giá thấp nhất** trong 7 ngày làm việc trước đó, nếu giá mới **tăng**;
- **Giá cao nhất** trong 7 ngày làm việc trước đó, nếu giá mới **giảm**.

Chiều của tin (tăng hay giảm) theo so sánh với giá gần nhất. Mức của tin theo phần trăm lệch **lớn nhất** trong các so sánh trên.

### 4.2 Các mức

| Mức | Mặc định | Biểu tượng | Ý nghĩa |
|---|---|---|---|
| **Nhẹ** | từ 2,5% đến dưới 5% | 🟡 | Đáng biết; gom vào bản tin 08:00 |
| **Trung bình** | từ 5% đến 10% | 🟠 | Gửi ngay |
| **Lớn** | trên 10% | 🔴 | Gửi ngay |

Màu chỉ mức độ biến động, **không** nói giá tăng là tốt hay xấu (điều đó tùy bạn đang mua hay bán). Dưới 2,5% thì không có tin. Trưởng phòng có thể đổi các ngưỡng này cho từng vật tư (mục 9).

### 4.3 Cách đọc một tin

Mỗi biến động có **hai phần** gửi liền nhau: một **ảnh biểu đồ kèm vài dòng tóm tắt**, và một **tin chi tiết**.

Ảnh kèm tóm tắt (ví dụ):

```
🟠 TĂNG TRUNG BÌNH · Ngô hạt
7,720 → 8,150 VNĐ/KG (+430)
▲5.57% so với thấp nhất 7 ngày
```

- **7,720 → 8,150**: giá cũ (điểm tham chiếu) và giá mới, đơn vị VNĐ/KG, làm tròn nguyên.
- **▲ 5.57%**: giá tăng 5,57% (▼ là giảm), và so với mốc nào.
- Nếu có thêm dòng **"Kỳ 11/2026 và 2 kỳ khác"**: vật tư này còn kỳ giao hàng khác cũng biến động; ảnh vẽ kỳ mạnh nhất.
- Nếu có **"⚠️ Tăng rất mạnh, nên kiểm tra phiếu"**: biến động từ 30% trở lên, có thể do nhập sai.

Biểu đồ vẽ 14 ngày gần nhất: đường giá thấp nhất mỗi ngày, hai đường ngang là giá thấp nhất và cao nhất của vùng tham chiếu 7 ngày làm việc, điểm cuối tô màu theo mức.

Tin chi tiết (gửi im lặng) gồm:
- **Chi tiết kỳ giao hàng**, giá thấp nhất 7 ngày và ngày của nó, **giá mới và ngày nhận**;
- dòng **"Cũng: ▲4.49% so với điểm gần nhất"** (so sánh phụ, chỉ in khi khác mốc chính);
- **7 ngày qua: 7,720 – 7,900**: khoảng giá của tuần tham chiếu;
- với phiếu nhập **USD/MT**: dòng **CNF** (giá USD/MT gốc); nếu chênh lệch chủ yếu do tỷ giá sẽ ghi "(chênh lệch do tỷ giá)";
- **🔗 Xem phiếu →** để mở phiếu trên web;
- **ℹ️** nhắc rằng điểm giá có thể thuộc **nhà cung cấp khác** với lần trước (vì so giá thấp nhất mọi nhà cung cấp).

Nếu nhiều kỳ giao hàng cùng biến động, tin chi tiết mở đầu bằng bảng **"Các kỳ giao hàng vượt ngưỡng"**, mỗi dòng một kỳ.

### 4.4 Khi nào KHÔNG có tin (dù bạn vừa nhập phiếu)?

- Phiếu còn là **bản nháp** (chưa chốt).
- Phiếu được **nhập muộn** quá 3 ngày làm việc kể từ ngày nhận báo giá (nhập bù dữ liệu cũ không gây tin).
- Dữ liệu **import** hàng loạt từ phiếu cũ.
- Biến động **dưới 2,5%**, hoặc **chưa có giá nào** của vật tư và kỳ đó trong 7 ngày làm việc trước để so sánh.
- Hệ thống đã báo **cùng chiều và cùng mức** cho vật tư đó trong 14 ngày qua (tránh báo lặp). Nếu giá tiếp tục đi thêm theo cùng chiều từ khoảng 5% so với lần báo gần nhất, hoặc leo lên mức cao hơn, hoặc đổi chiều thì vẫn báo.
- Giá đó đang bị nghi **nhập sai** và chờ duyệt (mục 6).
- Tính năng đang **tắt**, hoặc bạn chưa liên kết Telegram, đã tắt thông báo, hoặc mức biến động thấp hơn **mức tối thiểu** bạn chọn (mục 8).

Thứ Bảy và Chủ nhật **không được đếm** là ngày làm việc. Ngày lễ và Tết **chưa** được loại trừ.

## 5. Bản tin 08:00 (các biến động nhẹ)

Các biến động mức **Nhẹ** không gửi từng tin. Mỗi sáng từ 08:00 bạn nhận **một bản tin gom**:

```
📋 Bản tin giá · 07/10
▲4.00% Lúa mỳ 3 · 8,580
...
Xem trên web →
```

- Mỗi vật tư một dòng: chiều ▲/▼, phần trăm, giá mới. Tối đa 30 dòng, còn lại ghi "và N vật tư nữa, xem trên web".
- **Không có biến động nhẹ thì không có bản tin.** Cuối tuần vẫn có nếu có tin.
- Bản tin chỉ gom tin của hôm trước; tin nhẹ quá 3 ngày chưa gửi sẽ không còn được gửi.

Trưởng phòng mặc định không nhận mức Nhẹ; muốn nhận, đặt mức tối thiểu là **Nhẹ** ở Hồ sơ.

## 6. Giá bất thường (nghi nhập sai)

### 6.1 Là gì?

Khi một mức giá **lệch từ 30% trở lên** so với **giá giữa (trung vị)** của các giá hợp lệ trong 30 ngày qua, hệ thống nghi người nhập gõ sai (thường gặp: gõ giá USD vào ô VNĐ/KG, thừa hoặc thiếu số 0). Giá đó được **tạm loại** khỏi mọi phép so sánh cho đến khi có người xem xét, để một con số sai không làm sai các tin biến động sau đó.

### 6.2 Ai nhận và làm gì?

```
⚠️ GIÁ BẤT THƯỜNG · Threonine

Kỳ giao hàng: 11/2026
Giá nhận 15/09: 970
Giá hợp lệ gần đây:
25,600 · 25,435 · 25,900
Trung vị: 25,600
Lệch ▼96.21%
🔗 Xem phiếu →

Giá này tạm chưa được dùng
để tính biến động.
[✅ Giá đúng]  [❌ Nhập sai]
```

- **Trưởng phòng** nhận tin có hai nút:
  - **✅ Giá đúng**: giá thật (biến động thật nhưng lớn). Giá được dùng lại bình thường làm mốc so sánh.
  - **❌ Nhập sai**: giá bị loại. Người nhập cần sửa phiếu.
- **Người nhập phiếu** nhận cùng nội dung nhưng **không có nút**, kèm lời nhắc "Vui lòng kiểm tra và sửa phiếu nếu nhập sai" và liên kết mở phiếu.
- Người bấm đầu tiên quyết định; người bấm sau thấy "đã được xử lý bởi ...". Sau khi bấm, tin được sửa lại để ghi người xử lý, thời điểm, kết quả, và nút biến mất.
- Có từ **3 giá bất thường trở lên trong cùng ngày**: gộp thành **một tin tóm tắt** (tối đa 10 giá, mỗi giá một hàng nút).
- Nếu **chưa ai xử lý**: nhắc lại một lần sau 2 ngày làm việc; sau **7 ngày làm việc** thẻ hết hạn (giá vẫn bị loại, ngừng nhắc).

### 6.3 Xử lý trên web

Menu **Báo giá → Giá bất thường** (dành cho trưởng phòng và admin). Có danh sách các giá **đang chờ duyệt** và **lịch sử 30 ngày** đã duyệt (ai duyệt, lúc nào). Bấm **Giá đúng** hoặc **Nhập sai** rồi xác nhận trong hộp thoại. Duyệt trên web hay trên Telegram cho cùng kết quả; tin Telegram đã gửi cũng được sửa theo để bỏ nút (nếu hệ thống sửa được, nút bấm sau đó vẫn báo "đã được xử lý").

### 6.4 Nhãn trên chi tiết phiếu

Trong trang chi tiết phiếu, dòng giá từng bị gắn cờ có nhãn trạng thái (chỉ để xem):

| Nhãn | Nghĩa |
|---|---|
| **Nghi nhập sai, chờ duyệt** | Giá lệch lớn, đang chờ trưởng phòng xác nhận |
| **Đã đánh dấu nhập sai** | Trưởng phòng đã bác giá này |
| **Giá đã được xác nhận** | Trưởng phòng đã xác nhận giá đúng |
| **Nghi nhập sai, hết hạn duyệt** | Không ai xác nhận trong thời hạn |

## 7. Độ mới của giá theo vật tư và tin nhắc cập nhật giá

Mục đích: nhắc nhập **đủ giá** cho các vật tư quan trọng, tránh để một vật tư quá lâu không có báo giá mới.

### 7.1 Bảng "Độ mới của giá theo vật tư" (mọi người dùng Dashboard đều xem được)

Ở **Dashboard → tab Tổng quan**, dưới bảng "Tình hình nhập báo giá theo tuần". Bảng đi theo **tuần** bạn chọn ở ô chọn tuần phía trên (chọn tuần rồi bấm **Lọc**).

Bốn thẻ tóm tắt: **Đang theo dõi**, **Đã cập nhật**, **Đúng hạn**, **Quá hạn**.

Mỗi dòng là một vật tư:

| Cột | Ý nghĩa |
|---|---|
| **Số lần** | Số **phiếu** đã chốt có vật tư đó và **ngày nhận báo giá** trong tuần. Một phiếu có nhiều dòng của cùng vật tư vẫn tính **một** lần |
| **Số NCC** | Số nhà cung cấp trong các phiếu đó |
| **Nhận gần nhất** | Ngày nhận báo giá gần nhất của vật tư |
| **Số ngày chưa có giá** | Từ ngày nhận gần nhất đến hôm nay (hoặc đến Chủ nhật nếu xem tuần cũ) |
| **Chu kỳ** | Số ngày tối đa nên có giá mới (do trưởng phòng đặt) |
| **Trạng thái** | **Đã cập nhật** (có giá mới trong tuần), **Đúng hạn** (chưa có giá mới trong tuần nhưng còn trong chu kỳ), **Quá hạn** (đã quá chu kỳ), **Chưa có giá** (vật tư được theo dõi nhưng chưa từng có giá) |
| **Người nhập gần nhất** | Người nhập phiếu có giá gần nhất, để biết hỏi ai |

Dòng **Quá hạn** và **Chưa có giá** được tô nền đỏ nhạt. Bảng có **ô tìm kiếm** (tìm theo tên, mã, loại hoặc người nhập, gõ không dấu cũng được), các bộ lọc **Trạng thái**, **Loại vật tư**, **Người nhập gần nhất**, và bấm **tiêu đề cột** để sắp xếp (bấm lần ba để bỏ sắp xếp). Trên điện thoại bảng đổi thành các thẻ, có ô "Sắp xếp theo".

Lưu ý: bảng này tính theo **ngày nhận báo giá**, còn bảng nhập báo giá theo tuần phía trên tính theo **giờ nhập**, nên hai bảng có thể lệch số khi phiếu nhập trễ.

### 7.2 Danh sách theo dõi và chu kỳ (trưởng phòng và admin cài)

Không phải vật tư nào cũng cần có giá đều đặn, nên chỉ vật tư **được theo dõi** mới bị tính là "quá hạn". Trang **Hệ thống → Thông báo giá**, bảng **Ngưỡng theo vật tư**, có cột **Theo dõi** và **Chu kỳ (ngày)**:
- Bấm biểu tượng **mắt** ở cột Thao tác để bật hoặc tắt theo dõi và đặt chu kỳ (từ 1 đến 365 ngày), hoặc **Bỏ cấu hình**.
- Danh sách ban đầu được tạo tự động từ dữ liệu thật: vật tư có giá ở **ít nhất 3 ngày** trong 90 ngày gần đây, chu kỳ **7, 14 hoặc 30 ngày** tùy tần suất. Trưởng phòng nên rà lại: tắt vật tư không cần theo dõi, siết chu kỳ vật tư quan trọng.
- Bảng này sắp xếp được theo cột **Vật tư** và **Chu kỳ (ngày)**.

### 7.3 Tin nhắc qua Telegram

Khi trưởng phòng **bật** nhắc ở trang Thông báo giá (mặc định tắt), mỗi **ngày làm việc từ giờ đã chọn (mặc định 09:00)** bạn nhận một tin nếu có vật tư đến hạn nhắc:

```
⏰ 13 vật tư chưa có giá mới · 07/10
🔴 1 trễ nhiều · 🟡 12 vừa trễ

👤 Vũ Hoàng Giang · 1
🔴 Cám mỳ · 21 ngày

👤 Hoàng Thúy Dung · 7
🟡 Arginin 98% · 8 ngày
🟡 Lysine 70% · 8 ngày
...

Số ngày tính từ lần nhận giá gần nhất. 🔴 = trễ từ gấp đôi chu kỳ.
Xem chi tiết trên web →
```

- Tin **gom theo người nhập gần nhất** (người cần được nhắc). Người có vật tư trễ nhiều đứng đầu; "Chưa rõ người nhập" luôn ở cuối.
- **🔴** là trễ từ gấp đôi chu kỳ trở lên; **🟡** là mới quá hạn. Con số là **số ngày chưa có giá**.
- Trưởng phòng thấy mọi vật tư; nhân viên chỉ thấy vật tư mình đã nhập gần đây.
- **Nhịp nhắc:** lần đầu vào ngày làm việc đầu tiên sau khi quá hạn, rồi **mỗi 3 ngày làm việc**, tối đa **5 lần** cho một đợt quá hạn. Có giá mới là hết nhắc. Vì vậy vật tư quá hạn có thể không xuất hiện ở tin hôm nay dù vẫn "Quá hạn" trên bảng: bảng cho thấy tình trạng, tin chỉ nhắc đúng nhịp.
- Không có vật tư nào đến hạn nhắc thì không có tin. Cuối tuần không nhắc.
- Vật tư **chưa từng có giá** không được nhắc qua Telegram, chỉ hiện ở bảng Dashboard.

## 8. Tùy chọn cá nhân

**Hồ sơ → Tùy chọn thông báo giá** (hiện khi tính năng Telegram đang bật):
- **Nhận thông báo biến động giá qua Telegram**: bật hoặc tắt toàn bộ. Tắt thì bạn không nhận **cả tin biến động, bản tin, giá bất thường lẫn nhắc cập nhật giá**.
- **Mức tối thiểu**: Nhẹ, Trung bình hoặc Lớn, hoặc để **mặc định theo vai trò** (trưởng phòng: Trung bình; nhân viên: Nhẹ). Mức tối thiểu **không áp dụng** cho giá bất thường (nhận theo vai trò) và nhắc cập nhật giá.
- **Admin** có thêm tùy chọn nhận mọi thông báo như trưởng phòng.

## 9. Trang cấu hình (trưởng phòng và admin)

Menu **Hệ thống → Thông báo giá**. Chỉ người có quyền quản lý thông báo giá (trưởng phòng, admin) mới thấy.

1. **Bật hoặc tắt:**
   - **Gửi thông báo biến động giá qua Telegram**: công tắc tổng cho cả nhóm tính năng. Mỗi lần **bật lại**, hệ thống chỉ theo dõi các phiếu chốt **từ lúc bật trở đi**; phiếu cũ không sinh tin.
   - **Gửi thẻ giá bất thường** (có nút Giá đúng, Nhập sai).
2. **Ngưỡng mặc định:** Nhẹ từ, Trung bình từ, Lớn trên, Giá bất thường từ (mặc định 2,5 / 5 / 10 / 30%). Phải tăng dần.
3. **Tham số:** cửa sổ tham chiếu (7 ngày làm việc), độ trễ tối đa của phiếu nhập (3 ngày làm việc), cửa sổ nhân viên (90 ngày), cửa sổ chống lặp (14 ngày), trần tin mỗi lần quét (30), giờ bản tin (8), cửa sổ giá bất thường (30 ngày), gốc dự phòng (30 ngày).
4. **Nhắc cập nhật giá:** công tắc, **giờ nhắc** (0 đến 23, mặc định 9). Nhắc chỉ chạy khi công tắc tổng ở mục 1 đang bật (trang sẽ ghi chú nếu công tắc tổng tắt).
5. **Ngưỡng theo vật tư:** mỗi vật tư có thể có ngưỡng riêng (bấm biểu tượng **bút**), vì có vật tư dao động mạnh hơn hẳn (ví dụ cho vật tư biến động nhiều đặt ngưỡng cao hơn để bớt tin). Bấm **Dùng mặc định** để quay về ngưỡng chung. Cột **Nguồn** cho biết vật tư đang dùng ngưỡng riêng hay mặc định. Có ô tìm kiếm vật tư.
6. Mọi thay đổi đều được ghi vào **Nhật ký audit** (ai, lúc nào, đổi gì).

Thay đổi có hiệu lực ở lần quét kế tiếp (khoảng 30 giây), và **không** báo lại dữ liệu cũ.

## 10. Câu hỏi thường gặp

**Tôi nhập phiếu xong nhưng không thấy tin?**
Tin chỉ gửi khi biến động đủ lớn và đủ điều kiện ở mục 4.4. Có thể do: phiếu chưa chốt; biến động dưới 2,5%; mới có đúng một giá của vật tư và kỳ đó; đã báo cùng chiều và mức trong 14 ngày; phiếu nhập trễ quá 3 ngày làm việc; hoặc biến động nhẹ nằm trong bản tin 08:00 hôm sau.

**Tôi đã liên kết mà không nhận tin nào?**
Kiểm lần lượt: Hồ sơ hiện **Đã liên kết**; công tắc **Nhận thông báo** ở Hồ sơ đang bật; mức tối thiểu không quá cao so với biến động; bạn không **chặn bot**; công tắc tổng ở trang Thông báo giá đang bật; bạn có nằm trong nhóm chạy thử không (hỏi quản trị viên).

**Sao tin báo "tăng" mà giá nhà cung cấp tôi vừa nhập lại thấp hơn?**
Hệ thống so **giá thấp nhất trong ngày giữa mọi nhà cung cấp**, nên giá mới có thể thuộc nhà cung cấp khác với điểm trước. Tin có ghi chú này.

**Tôi thấy giá USD/MT nhưng tin tính phần trăm trên VNĐ/KG?**
Đúng. Phần trăm luôn tính trên **VNĐ/KG quy đổi**; dòng CNF (USD/MT) chỉ để tham khảo. Khi tỷ giá thay đổi, giá quy đổi đổi theo nên có thể xuất hiện biến động dù giá USD giữ nguyên (tin có ghi "chênh lệch do tỷ giá").

**Bấm nhầm "Nhập sai" hoặc "Giá đúng" thì sao?**
Quyết định đầu tiên là cuối cùng trên thẻ đó. Nếu bấm "Nhập sai" nhầm, báo người nhập sửa lại phiếu; nếu bấm "Giá đúng" nhầm, liên hệ quản trị viên.

**Vì sao vật tư "Quá hạn" trên Dashboard mà hôm nay tôi không nhận tin nhắc?**
Tin nhắc chỉ gửi đúng nhịp (ngày đầu quá hạn, rồi cách 3 ngày làm việc, tối đa 5 lần), và chỉ gửi nếu bạn là người đủ điều kiện nhận. Bảng Dashboard cho thấy tình trạng tại thời điểm xem.

**Ai thấy bảng "Độ mới của giá" và ai sửa được danh sách theo dõi?**
Mọi người xem được Dashboard đều **xem** bảng. Chỉ trưởng phòng và admin **sửa** danh sách theo dõi, chu kỳ và cài đặt thông báo.

## 11. Giới hạn cần biết

- Chỉ **chat riêng** với bot; chưa có nhóm. Chỉ tiếng Việt. Không có khung giờ yên lặng, tin gửi bất kỳ lúc nào có biến động (nhắc cập nhật giá và bản tin theo giờ cố định).
- **Ngày lễ và Tết chưa được loại** khỏi ngày làm việc, nên kỳ nghỉ dài có thể làm vài vật tư bị nhắc "quá hạn" dù thực tế chưa cần.
- Điểm giá **đầu tiên** của một vật tư và kỳ giao hàng chưa có gì để so nên không sinh tin.
- Một giá bất thường thật nhưng lớn (giá nhảy bậc có thật) cũng bị gắn cờ cho tới khi trưởng phòng bấm **Giá đúng**; hệ thống **không tự chấp nhận**.
- Chưa cảnh báo **ngay lúc đang gõ** phiếu; chỉ cảnh báo sau khi phiếu được chốt.
- Bot chỉ gửi thông báo; chưa hỏi đáp hay nhập phiếu qua Telegram.

## 12. Thuật ngữ

| Từ | Nghĩa |
|---|---|
| **Kỳ giao hàng** | Tháng hàng về của một dòng giá; mỗi kỳ được theo dõi riêng |
| **Giá thấp nhất trong ngày** | Giá thấp nhất của vật tư và kỳ đó trong một ngày nhận báo giá, giữa mọi nhà cung cấp |
| **Vùng tham chiếu** | 7 ngày làm việc liền trước ngày của giá mới |
| **Chốt phiếu** | Chuyển phiếu từ nháp sang có hiệu lực; chỉ phiếu đã chốt mới được tính |
| **Giá bất thường** | Giá lệch từ 30% so với trung vị 30 ngày gần đây, nghi nhập sai |
| **Trung vị** | Giá "ở giữa" khi xếp các giá từ thấp đến cao |
| **Theo dõi** | Vật tư nằm trong danh sách cần có giá mới theo chu kỳ |
| **Chu kỳ** | Số ngày tối đa nên có giá mới của một vật tư |
| **Quá hạn** | Đã quá chu kỳ mà chưa có giá mới |
| **Pilot, nhóm chạy thử** | Nhóm người dùng đang nhận tin trước khi mở rộng cho mọi người |
