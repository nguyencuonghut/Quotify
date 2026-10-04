# Kiểm Thử Tay Telegram Giai Đoạn 1A Trên Môi Trường Dev

Bảng kịch bản để kiểm tay toàn bộ tính năng Telegram đã có (Giai đoạn 1A: liên kết tài khoản) trước khi đưa lên production (Slice 7 của [plan-telegram-giai-doan-1a-nen-tang-lien-ket.md](plan-telegram-giai-doan-1a-nen-tang-lien-ket.md)).

**Phạm vi.** Chỉ 1A: liên kết, đổi, hủy, `/start`, `/stop`, `/help`, bị chặn, nhật ký audit, cờ bật/tắt. **Chưa có** (1B trở đi): tính biến động giá, gửi thông báo giá, biểu đồ, chatbot. **Không kiểm được trên dev:** webhook qua HTTPS công khai (dev dùng polling); phần đó kiểm ở Slice 7.

## 0. Chuẩn bị

| Việc | Lệnh hoặc cách làm |
|---|---|
| Dev stack chạy | `docker compose up -d` (backend, frontend, worker, postgres...) |
| **Bật poller** (không tự bật) | `docker compose --profile telegram up -d telegram-poller` |
| Kiểm poller | `docker compose --profile telegram logs --tail=5 telegram-poller` phải có `telegram.poller_started username=HHQuotifyBot` |
| `.env` dev | `TELEGRAM_ENABLED=true`, `TELEGRAM_MODE=polling`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME=HHQuotifyBot` |
| Mở giao diện | `http://localhost:5173`, trang **Hồ sơ** (menu người dùng ở góc phải) |
| Xem trạng thái nhanh | `bash scripts/ops/telegram-dev-state.sh` (chỉ đọc; giờ UTC, Việt Nam = UTC+7) |
| Hai tài khoản Quotify thử | `tg.test.a@example.com` và `tg.test.b@example.com` (vai trò `user`; mật khẩu do người chuẩn bị cung cấp riêng, không ghi vào tài liệu) |
| Bot | `https://t.me/HHQuotifyBot` |
| Telegram thứ hai (tùy chọn) | Chỉ cần cho mục 3.3; có thể dùng Telegram Web/Desktop đăng nhập bằng số khác, hoặc nhờ đồng nghiệp |

Lưu ý: mỗi lần bấm "Liên kết Telegram" tạo một đường dẫn sống **10 phút**, dùng **một lần**. Đăng nhập sai nhiều sẽ bị giới hạn 5 lần mỗi phút.

## 1. Liên kết cơ bản (tài khoản A, một Telegram)

Đăng nhập bằng tài khoản A. Cột "Kết quả" để bạn ghi Đạt hoặc Lỗi.

| # | Làm gì | Kỳ vọng | Kết quả |
|---|---|---|---|
| 1.1 | Mở trang Hồ sơ | Có panel thứ ba "Thông báo Telegram", ghi "Chưa có tài khoản Telegram nào được liên kết." và nút "Liên kết Telegram" | |
| 1.2 | Bấm "Liên kết Telegram" | Hiện khối chờ: đếm ngược 10:00, ô đường dẫn `https://t.me/HHQuotifyBot?start=...`, nút "Mở Telegram", "Sao chép đường dẫn", mã QR, nút "Tạo đường dẫn mới", "Hủy yêu cầu" | |
| 1.3 | Bấm "Sao chép đường dẫn" | Nhãn đổi thành "Đã sao chép" trong 2 giây; dán ra được đúng đường dẫn | |
| 1.4 | Bấm "Mở Telegram" rồi bấm **Start** | Bot trả lời "✅ Đã liên kết với tài khoản **Test Telegram A**. Bạn sẽ nhận thông báo biến động giá tại đây. Gõ /stop để hủy liên kết." Trong ≤3 giây panel tự đổi: "Đã liên kết tài khoản Telegram.", hiện tên/@username, thời điểm liên kết, trạng thái "Đang hoạt động", nút "Đổi tài khoản Telegram", "Hủy liên kết" | |
| 1.5 | Chạy `bash scripts/ops/telegram-dev-state.sh` | 1 dòng liên kết `active`, không còn đường dẫn hiệu lực, audit có `telegram.linked` kênh `telegram` | |
| 1.6 | **QR:** hủy liên kết (1.11 bên dưới) rồi bấm "Liên kết Telegram" lại, quét QR trên màn hình bằng camera điện thoại | iPhone hiện nhãn xanh ở đầu màn hình camera: chạm vào nhãn để mở Telegram, rồi Start. Liên kết hoàn tất như 1.4 | |
| 1.7 | Trong chat bot gõ `/help` | Danh sách lệnh `/start`, `/stop`, `/help` (tiếng Việt có dấu) | |
| 1.8 | Gõ `/start` (đã liên kết) | "Tài khoản Telegram này đã liên kết với **Test Telegram A**. Gõ /help để xem hướng dẫn." | |
| 1.9 | Gõ `xin chào` | "Tôi chưa hiểu yêu cầu này. Gõ /help để xem hướng dẫn." | |
| 1.10 | Bấm "Hủy liên kết" trên web, chọn "Giữ liên kết" | Hộp thoại đóng, liên kết vẫn còn | |
| 1.11 | Bấm "Hủy liên kết", chọn "Hủy liên kết" | Panel về "Chưa có tài khoản...", báo "Đã hủy liên kết Telegram."; DB: `revoked`/`user_unlink`; audit `telegram.unlinked` kênh `web` | |
| 1.12 | Liên kết lại (1.2 đến 1.4), rồi gõ `/stop` trong Telegram | Bot: "Đã hủy liên kết. Bạn sẽ không nhận thông báo nữa..." DB: `revoked`/`stop_command`; audit `telegram.unlinked` kênh `telegram`. Panel đổi sau khi bạn quay lại tab hoặc F5 | |
| 1.13 | Gõ `/stop` lần nữa | "Tài khoản Telegram này chưa được liên kết." | |
| 1.14 | Gõ `/start` khi chưa liên kết | "Xin chào! Đây là bot thông báo biến động giá của Quotify..." | |

## 2. Đường dẫn liên kết: hết hạn, thay thế, dùng lại

| # | Làm gì | Kỳ vọng | Kết quả |
|---|---|---|---|
| 2.1 | Tạo link, **Hủy yêu cầu** rồi mở link đó trong Telegram | Bot: "Đường dẫn liên kết không hợp lệ hoặc đã hết hạn..." Không có liên kết mới | |
| 2.2 | Tạo link, liên kết xong (như 1.4), rồi **bấm lại đúng link cũ** trong Telegram | Bot báo "không hợp lệ" (mã dùng một lần); trạng thái liên kết không đổi | |
| 2.3 | Tạo link, rút ngắn hạn: `docker compose exec -T postgres psql -U postgres -d app -c "update telegram_link_tokens set expires_at = now() - interval '1 second' where used_at is null"`, rồi mở link | Bot báo "không hợp lệ hoặc đã hết hạn". Trên web, trong ≤3 giây hiện thông báo "Đường dẫn liên kết đã hết hạn hoặc bị thay thế..." và khối chờ biến mất | |
| 2.4 | Mở **hai tab** cùng tài khoản. Tab 1 tạo link, rồi tab 2 bấm "Tạo đường dẫn mới" | Trong ≤3 giây tab 1 báo "Đường dẫn trong tab này đã bị thay thế bởi đường dẫn mới hơn" và ẩn link cũ. Mở link cũ trong Telegram: "không hợp lệ"; link của tab 2 dùng được | |
| 2.5 | Tạo link rồi bấm F5 | Khối chờ vẫn còn đếm ngược nhưng ghi "Đường dẫn chỉ hiển thị một lần ở phiên này. Tạo đường dẫn mới để lấy lại đường dẫn." | |
| 2.6 | Bấm "Tạo đường dẫn mới" liên tiếp 6 lần trong 1 phút | Lần thứ 6 báo lỗi "Bạn thao tác quá nhanh. Vui lòng thử lại sau ít phút." (giới hạn 5 lần/60 giây); đợi 1 phút thì tạo lại được | |
| 2.7 | Tạo link, copy mã, gửi `/start mã-bậy-bạ-12345` cho bot | Bot báo "không hợp lệ"; không có audit nào mới (kiểm bằng script) | |

## 3. Nhiều tài khoản

### 3.1 Telegram đang gắn với người dùng khác

| # | Làm gì | Kỳ vọng | Kết quả |
|---|---|---|---|
| 3.1.1 | Tài khoản A liên kết Telegram X (như 1.4) | `active` | |
| 3.1.2 | Đăng nhập tài khoản **B** (cửa sổ ẩn danh), tạo link, mở bằng **cùng Telegram X** | Bot: "Tài khoản Telegram này đang liên kết với một tài khoản Quotify khác. Hãy gõ /stop ở đây hoặc hủy liên kết ở tài khoản đó trước, rồi tạo đường dẫn mới." B vẫn "Chưa liên kết"; audit `telegram.link_rejected` lý do `telegram_in_use`; link của B **vẫn còn hiệu lực** | |
| 3.1.3 | Trong Telegram gõ `/stop` (hủy liên kết A), rồi mở lại **đúng link của B** (còn trong 10 phút) | Liên kết thành công cho B: "✅ Đã liên kết với tài khoản **Test Telegram B**" | |

### 3.2 Cùng người, cùng Telegram, đường dẫn mới

| # | Làm gì | Kỳ vọng | Kết quả |
|---|---|---|---|
| 3.2.1 | Khi A đang liên kết, bấm "Đổi tài khoản Telegram" rồi mở link mới bằng **chính Telegram đó** | Bot: "Tài khoản Telegram này đã liên kết với **Test Telegram A**...". Không có bản ghi mới (script vẫn 1 dòng `active`) | |

### 3.3 Đổi sang Telegram khác (cần Telegram thứ hai, gọi là Y)

| # | Làm gì | Kỳ vọng | Kết quả |
|---|---|---|---|
| 3.3.1 | A đang liên kết Telegram X. Bấm "Đổi tài khoản Telegram" | Panel vẫn hiện tài khoản X **và** khối chờ cùng lúc; nút chính đổi thành "Tạo đường dẫn mới" | |
| 3.3.2 | Mở link bằng Telegram Y, bấm Start | Y nhận "✅ Đã liên kết..."; **X nhận** "Liên kết Telegram này đã được thay thế bằng một tài khoản Telegram khác..."; panel đổi sang tài khoản Y; DB: X `revoked`/`replaced`, Y `active`; audit `telegram.linked` có `replaced_account_id` | |
| 3.3.3 | Sau đó nhắn `/help` từ X | Bot xử lý như người chưa liên kết (X không còn nhận thông báo) | |

## 4. Bị chặn và bỏ chặn

| # | Làm gì | Kỳ vọng | Kết quả |
|---|---|---|---|
| 4.1 | Khi A đang liên kết: trong Telegram bấm tên bot → ⋮ → **Block user** (điện thoại: **Stop bot**) | DB trong vài giây: `blocked`. Trên web (quay lại tab hoặc F5): "Bot đang bị chặn" màu cam kèm gợi ý bỏ chặn rồi gõ /start | |
| 4.2 | **Unblock / Restart bot**, gõ `/start` | DB về `active`; web hiện "Đang hoạt động" sau khi quay lại tab hoặc F5 | |
| 4.3 | Chặn rồi bỏ chặn, rồi tạo link mới của **chính A** và mở | Bot: "đã liên kết"; trạng thái `active` | |

## 5. Vòng đời người dùng (cần quyền admin)

Dùng tài khoản admin thật của bạn ở một cửa sổ khác. Vào **Người dùng**, sửa trạng thái tài khoản thử A.

| # | Làm gì | Kỳ vọng | Kết quả |
|---|---|---|---|
| 5.1 | A đang liên kết Telegram X. Admin đặt A thành `locked` (hoặc `inactive`). Gõ `/help` từ X | Bot: "Tài khoản Quotify của bạn hiện không hoạt động nên không thể liên kết." (không xử lý lệnh khác) | |
| 5.2 | A vẫn `locked`. B tạo link và mở bằng **Telegram X** | Liên kết cho B **thành công** (Telegram được nhường vì chủ cũ không còn hoạt động). DB: A `revoked`/`owner_inactive`; audit `telegram.unlinked` lý do `owner_inactive` (không có người thao tác) | |
| 5.3 | Admin trả A về `active` | A lại dùng được; A chưa liên kết (đã bị thu hồi ở 5.2) | |

## 6. Nhật ký audit

| # | Làm gì | Kỳ vọng | Kết quả |
|---|---|---|---|
| 6.1 | Admin vào **Nhật ký audit**, lọc hành động "Liên kết Telegram", "Hủy liên kết Telegram"... | Có 4 loại sự kiện với nhãn tiếng Việt: Yêu cầu liên kết Telegram, Liên kết Telegram, Từ chối liên kết Telegram, Hủy liên kết Telegram. Lọc theo loại thực thể "Liên kết Telegram" và "Mã liên kết Telegram" cũng được | |
| 6.2 | Mở chi tiết một sự kiện | Metadata chỉ có `channel`, `telegram_account_id`, `replaced_account_id`, `reason`. **Không** có telegram_user_id, username, mã liên kết | |

## 7. Cờ bật/tắt (K19)

| # | Làm gì | Kỳ vọng | Kết quả |
|---|---|---|---|
| 7.1 | Đặt `TELEGRAM_ENABLED=false` trong `.env`, chạy `docker compose up -d --force-recreate backend` | Sau khi backend khỏe, trang Hồ sơ **không còn** panel Telegram (các panel khác bình thường). `GET /api/v1/users/me/telegram` trả 200 `enabled:false`; `POST .../link-token` trả 503 | |
| 7.2 | Poller khi cờ tắt: `docker compose --profile telegram up -d --force-recreate telegram-poller` (phải tạo lại container thì mới nạp lại `.env`; `restart` không đủ) | Poller thoát ngay với thông báo "TELEGRAM_ENABLED=false, poller không chạy." (xem `docker compose --profile telegram logs --tail=3 telegram-poller`) | |
| 7.3 | Đặt lại `TELEGRAM_ENABLED=true`, rồi `docker compose up -d --force-recreate backend` và `docker compose --profile telegram up -d --force-recreate telegram-poller` | Panel trở lại; liên kết đã có vẫn còn; bot lại trả lời | |

## 8. Bảo mật và log

| # | Làm gì | Kỳ vọng | Kết quả |
|---|---|---|---|
| 8.1 | `docker compose logs backend telegram-poller \| grep -c -F "$(grep '^TELEGRAM_BOT_TOKEN=' .env \| cut -d= -f2-)"` | `0` (token không xuất hiện trong log) | |
| 8.2 | Chrome DevTools → Application → Local/Session Storage khi đang có link chờ | Không có đường dẫn hay mã liên kết | |
| 8.3 | Nhóm: thêm bot vào một nhóm và nhắn `/start` trong nhóm | Bot **không trả lời** trong nhóm | |
| 8.4 | Gõ liên tục hơn 10 tin trong 1 phút từ một Telegram | Các tin vượt hạn mức bị bỏ qua (không trả lời), không lỗi | |

## 9. Giao diện

| # | Làm gì | Kỳ vọng | Kết quả |
|---|---|---|---|
| 9.1 | Chuyển giao diện sáng và tối (nút trăng ở topbar) ở từng trạng thái: chưa liên kết, chờ, đã liên kết, bị chặn | Chữ rõ, trạng thái xanh/cam đúng, QR luôn đen trên nền trắng | |
| 9.2 | Thu hẹp cửa sổ còn khoảng 390px (hoặc dùng điện thoại) | Panel xếp một cột, các nút rộng hết bề ngang, QR ở giữa, không có thanh cuộn ngang | |
| 9.3 | Dùng bàn phím (Tab) | Các nút và ô đường dẫn lấy được focus; thông báo lỗi có `role="alert"` | |

## 10. Dọn dẹp sau khi test

```bash
# Xóa dữ liệu liên kết (dev, an toàn)
docker compose exec -T postgres psql -U postgres -d app -c \
  "TRUNCATE telegram_accounts, telegram_link_tokens, telegram_processed_updates;"

# Xóa hai tài khoản Quotify thử (xóa refresh token trước vì DELETE /users/{id} đang lỗi 500 với người dùng đã đăng nhập)
docker compose exec -T postgres psql -U postgres -d app -c \
  "delete from refresh_tokens where user_id in (select id from users where email like 'tg.test.%@example.com');
   delete from user_roles where user_id in (select id from users where email like 'tg.test.%@example.com');
   delete from users where email like 'tg.test.%@example.com';"
```

Dòng audit `telegram.*` và nhật ký của hai người dùng thử vẫn được giữ lại (nhật ký audit là lịch sử). Nếu muốn xóa dòng audit thử trên **dev**, chỉ xóa theo đúng điều kiện `action like 'telegram.%'`.

## 11. Khi nào coi là đạt

Mọi dòng ở mục 1 đến 9 là "Đạt" (mục 3.3 có thể bỏ qua nếu không có Telegram thứ hai, vì đã được kiểm tự động bằng Telegram giả). Dòng nào "Lỗi" thì ghi lại bước, kết quả thực tế, và đầu ra của `bash scripts/ops/telegram-dev-state.sh` để sửa.
