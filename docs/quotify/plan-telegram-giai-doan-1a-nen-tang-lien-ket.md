# Kế Hoạch Triển Khai Giai Đoạn 1A: Nền Tảng Telegram Và Liên Kết Tài Khoản

## Trạng Thái

BẢN NHÁP ĐỂ XÁC NHẬN (bản 3). Chưa có dòng code nào được viết. Ngày soạn: 2026-10-03. Cập nhật 2026-10-04: đồng bộ với tài liệu cha sau vòng rà soát độc lập (tài liệu cha đã được sửa theo bảng "Độ Lệch Có Chủ Đích" và thêm điều kiện bảo mật K15).

Kế hoạch này là phần triển khai chi tiết của Giai đoạn 1A trong
[plan-telegram-bien-dong-gia-va-chatbot-ai.md](plan-telegram-bien-dong-gia-va-chatbot-ai.md)
(Mục 4.4 đến 4.9 và Mục 7). Các quyết định thiết kế ở tài liệu đó đã chốt. Chỗ kế hoạch này cố ý khác bản tài liệu cha trước ngày 2026-10-04 được liệt kê ở mục "Độ Lệch Có Chủ Đích So Với Tài Liệu Cha"; các chỗ đó **đã được đồng bộ vào tài liệu cha**.

Cách soạn:
- Local skill `to-issues`: chia lát cắt dọc (tracer bullet). Mỗi slice đi qua đủ các tầng cần thiết, tự xác minh được, có loại **HITL** (cần người quyết định hoặc thao tác ngoài code) hoặc **AFK** (agent làm và merge được), "chặn bởi" và tiêu chí chấp nhận. Không đăng issue lên tracker nào.
- Local skill `tdd`: trong mỗi slice, test đầu tiên là **tracer bullet** (hành vi chính đi hết đường), sau đó mới tới từng hành vi nhỏ, một test một đoạn code. Test đo hành vi qua giao diện công khai (HTTP ra vào, DB, request gửi đi Telegram), không đo chi tiết cài đặt.
- Local agent: 3 agent đọc song song ngày 2026-10-03 (công thức backend, công thức frontend, xác minh Telegram Bot API từ tài liệu chính thức), và 1 agent rà soát độc lập kế hoạch bản 1. Số liệu baseline do các agent đo trên cây git sạch.

## Mục Tiêu

Cuối Giai đoạn 1A, trên dev rồi production:
- Backend nói chuyện với Telegram an toàn, không lộ token bot.
- Bot nhận tin nhắn (webhook cho production, polling cho dev) và trả lời `/start`, `/stop`, `/help`.
- Người dùng liên kết, đổi, hủy tài khoản Telegram từ trang Hồ sơ.
- Mọi thao tác liên kết có hiệu lực đều được audit. Dữ liệu cũ và API cũ không đổi.

**Hoàn thành khi:** một người dùng liên kết, đổi sang tài khoản Telegram khác và hủy liên kết được trên dev, rồi lặp lại trên production với một tài khoản thử.

Chưa gửi thông báo giá nào ở giai đoạn này (đó là 1B).

## Ngoài Scope

- Gửi thông báo biến động giá, biểu đồ, người nhận theo vai trò, giá bất thường (1B, 1C).
- Bật/tắt thông báo và mức tối thiểu từng người (`/users/me/alert-preferences`, 1B/1C).
- Chatbot, LLM, ngân sách (Giai đoạn 2). Xử lý update qua hàng đợi arq (Giai đoạn 2A).
- Hạn mức bằng Redis, metric và cảnh báo cho webhook (1C).
- Bước xác nhận trong chat khi liên kết (xem K15, xét lại ở Giai đoạn 2).
- Mã QR là **tùy chọn** (Slice 5c).

## Thuật Ngữ (đưa vào `CONTEXT.md` ở Slice 0)

Từ "liên kết" có hai nghĩa nên tách như sau, và dùng nhất quán trong giao diện, bot và tài liệu. Các thuật ngữ về biến động giá (Điểm giá, Chuỗi, Cửa sổ tham chiếu, Ngày làm việc, Giá bất thường, Trưởng phòng, Bản tin tổng hợp, Sự kiện, Tin) nằm ở Mục 2 của tài liệu cha và cũng được đưa vào `CONTEXT.md`:

| Thuật ngữ | Nghĩa | Tránh |
|---|---|---|
| **Liên kết Telegram** | Quan hệ giữa một người dùng Quotify và một tài khoản Telegram | "kết nối Telegram" |
| **Đường dẫn liên kết** | URL `https://t.me/<bot>?start=<mã>` (deep link) | "liên kết" đứng một mình để chỉ URL |
| **Mã liên kết** | Chuỗi bí mật dùng một lần nằm trong đường dẫn (token) | "token" trong chuỗi hiển thị cho người dùng |
| **Hủy liên kết** | Hành động của người dùng. Trạng thái nội bộ tương ứng là `revoked` (thu hồi) | |
| **Đổi tài khoản Telegram** | Liên kết sang tài khoản Telegram khác, tài khoản cũ bị thu hồi | |

## Căn Cứ Đã Xác Minh

### Từ tài liệu chính thức của Telegram (đọc ngày 2026-10-03, bản Bot API 10.3 ghi trên trang)

| Điều | Kết luận |
|---|---|
| Webhook | HTTPS bắt buộc, cổng 443/80/88/8443, TLS 1.2+. `secret_token` 1 đến 256 ký tự `A-Z a-z 0-9 _ -`, gửi qua header `X-Telegram-Bot-Api-Secret-Token`. Không hỗ trợ IPv6, không hỗ trợ redirect, CN chứng chỉ phải trùng domain (Let's Encrypt dùng được). Non-2xx thì Telegram thử lại, số lần và khoảng cách không được nêu |
| `getUpdates` và webhook | **Loại trừ nhau.** Mã 409 không được tài liệu nhắc (xem Slice 0) |
| Đường dẫn liên kết | `https://t.me/<bot>?start=<param>`, param tối đa 64 ký tự `A-Za-z0-9_-`. Bot nhận tin nhắn `/start <param>`. Bấm lại khi đã Start có gửi lại không: **tài liệu không nói** (T3) |
| Chat riêng | `chat.type = "private"`. `from` có thể rỗng. `username` tùy chọn và có thể đổi, chỉ `id` ổn định, tới 52 bit nên dùng `BigInteger` |
| Bị chặn | `my_chat_member` cho chat riêng chỉ đến khi bot bị chặn hoặc bỏ chặn. **Bẫy:** `setWebhook` có `allowed_updates` thì phải liệt kê `my_chat_member`. Chuỗi lỗi 403 "bot was blocked by the user" **tài liệu không nêu**, xử lý theo `error_code` (T5) |
| Giới hạn gửi | Khoảng 1 tin mỗi giây mỗi chat, khoảng 30 tin mỗi giây toàn bot. Lỗi 429 kèm `parameters.retry_after` |
| Token | Nằm **trong URL path** `https://api.telegram.org/bot<token>/METHOD`, nên mọi log URL đều lộ token |
| `update_id` | Tăng dần nhưng sau ít nhất 1 tuần im lặng sẽ nhảy ngẫu nhiên. Update chưa nhận giữ tối đa 24 giờ. Dedupe bằng khóa duy nhất |
| Bot nhắn trước | Không được, người dùng phải nhắn trước |

Các điểm trên được agent kiểm bằng HTML thô của các trang chính thức. Rà soát độc lập không truy cập lại được tài liệu Telegram nên chưa kiểm chéo độc lập: "không hỗ trợ redirect" và số hiệu phiên bản vẫn nên xem là [ĐÃ ĐỌC, CHƯA KIỂM CHÉO].

### Từ code của repo

- Chưa có code Telegram. `users` không có cột Telegram và sẽ **không** thêm.
- Alembic head hiện tại `20260824_1000`, duy nhất một head.
- Token bot lộ qua hai đường nếu không xử lý: log `httpx` mức INFO (`backend/app/core/logging.py:31-42`) và span OTel của `HTTPXClientInstrumentor` (`backend/app/core/observability.py:183`; biến loại trừ URL được đọc bên trong `instrument()` nên phải đặt trước).
- `configure_logging` chỉ được gọi ở lifespan của FastAPI (`core/application.py:19`). Worker và script không gọi, nên log của tiến trình ngoài API không đi qua cấu hình này trừ khi tự gọi.
- `tests/test_audit_context_usage.py` quét `app/api/v1/*.py`, cấm `request.client.host` và `_extract_client_ip`. Lấy IP qua `AuditLogContext.from_request`.
- Rate limiter hiện có khóa theo IP, in-memory, không xóa key cũ.
- Audit allow-list (`services/audit_log.py`): key chứa `token|secret|session|...` luôn bị che, chạy trước allow-list.
- Test backend không dùng DB thật. Partial unique index, `ON CONFLICT`, `FOR UPDATE`, rollback savepoint chỉ kiểm chứng được bằng DB thật. Repo có service `postgres-test` trong `docker-compose.test.yml`.
- FastAPI 0.136.3: body JSON hỏng làm route trả **422 trước khi** chạy dependency kiểm secret, và body không phải `dict` cũng 422. Vì vậy webhook phải nhận `Request` và tự parse.
- Frontend: `ProfilePage.vue` có 2 panel, lưới 2 cột, chưa có spec. Không có thư viện QR. ESLint báo `no-undef` cho `URL`/`setTimeout` trong `.vue`. `loginAsAdmin` của e2e không dùng chung, mỗi spec tự định nghĩa một bản. `actionSeverity` nằm trong `AuditLogsPage.vue` (không export).

### Baseline (đo 2026-10-03, cây git sạch; rà soát độc lập đối chiếu lại đúng) — không được xấu hơn

| | Số liệu |
|---|---|
| Backend pytest | 385 passed |
| `ruff check .` | 62 lỗi (50 E501, 6 I001, 5 E741, 1 N817). `models/__init__.py` và `db/base.py` đã có sẵn 1 lỗi I001 |
| `ruff format --check` | 27 file không chuẩn |
| `mypy .` | 72 lỗi ở 18 file, đa số trong `tests/` |
| `bandit -r app` | 16 phát hiện (15 Low, 1 Medium B314 ở `vietcombank.py`) |
| Frontend ESLint | 69 vấn đề (12 lỗi, 57 cảnh báo), 9 file không liên quan |
| Frontend Prettier | 74 file lệch |
| `vue-tsc` | sạch |
| Frontend Vitest | 182 test, 4 fail ở 2 file (`useQuotifySettingsPage.spec.ts` 3 test, `audit-logs.page.spec.ts` 1 test) |

`make docker-test-backend` nối `pytest && ruff && mypy && bandit` bằng `&&`, ruff đang đỏ nên mypy và bandit không chạy tới. Chạy từng công cụ riêng cho file mới (xem Lệnh Chuẩn). `make docker-test-frontend` tự fail ở bước lint vì nợ cũ.

## Nguyên Tắc Bắt Buộc

1. **Additive.** Chỉ thêm bảng, thêm file. Không sửa migration cũ, không đổi API cũ. Production không có `downgrade`, lỗi migration thì forward-fix.
2. **Cờ tắt mặc định.** `TELEGRAM_ENABLED=false`. Mọi field Settings mới có default, production chưa cấu hình vẫn khởi động. Khi cờ tắt, **người dùng production không thấy thay đổi nào**, kể cả giao diện (K14).
3. **Token bot không bao giờ xuất hiện trong log, traceback, span, audit, response.** Có test chặn. Nội dung update của Telegram cũng không được log (tin `/start <mã>` chứa mã liên kết), chỉ log `update_id` và loại update.
4. **Webhook trả 2xx cho mọi update đã xác thực mà xử lý được hoặc "độc"** (hợp lệ, trùng, không hiểu, không phải chat riêng). Lỗi hạ tầng tạm thì trả 5xx để Telegram thử lại (K13). Chỉ trả 403 khi sai secret, 404 khi tính năng tắt.
5. **Phân tầng.** Service chỉ `flush()` và **trả về danh sách tin cần gửi**. Nơi `commit()` là route (API) hoặc *runner* dùng chung cho webhook và poller. Gửi tin Telegram **sau commit**, bọc `try/except` riêng, lỗi gửi không đổi kết quả nghiệp vụ. Hệ quả: tin trả lời là **at-most-once** (commit xong mà gửi lỗi thì mất tin trả lời, người dùng thử lại).
6. **Đọc ORM sau commit phải `refresh` hoặc gán timestamp bằng Python** (bẫy MissingGreenlet), verify bằng `curl` thật.
7. **Tiếng Việt có dấu** cho mọi chuỗi người dùng thấy và tài liệu. Tin Telegram dùng `parse_mode=HTML`, escape dữ liệu người dùng (`first_name`, `username`) bằng `html.escape(..., quote=False)`. Không escape cả chuỗi, không dùng Markdown (`**`).
8. **Không sửa lan nợ cũ.** Không `ruff format .`, `ruff check --fix .`, `prettier --write .`. Với 2 file đã lỗi I001 (`models/__init__.py`, `db/base.py`), chèn tay đúng thứ tự chữ cái.
9. **Mỗi slice kết thúc bằng một commit** có test xanh, lint sạch cho file mới, baseline không xấu hơn. Chạy `scripts/agent-task-close.sh` ở slice để lại kiến thức bền vững (S1, S3b, S6b).
10. **Xác minh thật, không chỉ unit test** (Rule 14 và 19): `curl`, `psql`, DB thật, bot Telegram thật, trình duyệt thật.

## Độ Lệch Có Chủ Đích So Với Tài Liệu Cha

**Trạng thái đồng bộ (2026-10-04):** tất cả các điểm dưới đây đã được cập nhật vào tài liệu cha (Mục 4.4 đến 4.8, RR-9, Mục 7, Mục 9). Slice 0 chỉ cần rà lại cho khớp, không còn phải sửa từ đầu. Ngoài các điểm này, tài liệu cha còn bổ sung các chi tiết 1A đã dùng: endpoint `DELETE /users/me/telegram/link-token` và định dạng `GET /users/me/telegram`, audit `telegram.link_requested`, `telegram.link_rejected`, `revoked_reason` mở rộng, dọn dữ liệu (K8), lệnh bot (K10), ẩn panel khi tắt (K14), K16.

| Điểm | Tài liệu cha | Kế hoạch 1A | Lý do |
|---|---|---|---|
| Partial unique index | `WHERE status='active'` (4.5) | `WHERE status IN ('active','blocked')` | Tài khoản bị chặn vẫn thuộc người dùng. Nếu không giữ chỗ thì người khác chiếm `telegram_user_id`, bỏ chặn sẽ vi phạm unique (K1) |
| Trạng thái `blocked`, `my_chat_member`, `allowed_updates` | "đánh dấu inactive" (4.4) | Thêm trạng thái `blocked` và xử lý `my_chat_member` | Phát hiện bị chặn đúng cách (K5) |
| PII trong audit | Câu hỏi mở (4.6) | Không ghi `telegram_user_id`, username (K2) | Truy vết đủ qua `telegram_account_id` |
| Biến cấu hình | 4.7 | Thêm `TELEGRAM_WEBHOOK_URL`, `TELEGRAM_API_BASE_URL`, `RATE_LIMIT_TELEGRAM_LINK_TOKEN`. Không dùng `${TELEGRAM_*:?}` trong compose production | `docker compose config` trong `make production-readiness-check` sẽ lỗi khi biến trống mà tính năng đang tắt (K9) |
| Hạn mức | R9: Redis, khóa theo người dùng Telegram | In-memory, khóa theo người dùng ứng dụng và Telegram | Production chạy một tiến trình uvicorn (R18). Redis để 1C. **Đây là lệch có chủ đích, không phải "R9 đã chấp nhận"** |
| Xử lý update | 4.6: trả 200 nhanh, xử lý nặng qua arq | Xử lý **inline** trong request webhook (một ghi DB và một cuộc gọi HTTP ngắn) | Chưa có tác vụ nặng. Chuyển sang arq ở Giai đoạn 2A |
| E2E | 4.10: Playwright với fake Telegram | E2E-A (mock mạng) bắt buộc, E2E-B tùy chọn (K11) | Giảm phụ thuộc, E2E-B làm sau |
| Triển khai production | Ở 1C | Slice 7 triển khai production ngay ở 1A (cờ tắt rồi bật) | Cần xác minh liên kết thật trên production sớm |
| Cập nhật `username`, kiểm `User.status` mỗi tin | 4.4 | Thực hiện ở Slice 4 | Mang sang đúng yêu cầu của tài liệu cha |
| Bật/tắt và mức tối thiểu trong panel | 4.9 | Hoãn sang 1B/1C | Chưa có thông báo để bật/tắt |

## Quyết Định Kỹ Thuật Cho 1A (xác nhận ở Slice 0)

Mỗi điểm có mặc định, chỉ cần sửa nếu không đồng ý.

| # | Quyết định | Mặc định |
|---|---|---|
| K1 | Partial unique "đang giữ liên kết" | `WHERE status IN ('active','blocked')` cho cả hai index (`telegram_user_id` và `user_id`) |
| K2 | Audit | Không ghi `telegram_user_id`/username. Sự kiện: `telegram.link_requested` (cấp mã, `entity_type="telegram_link_token"`), `telegram.linked`, `telegram.unlinked` (`entity_type="telegram_account"`, `entity_id` là UUID nội bộ), `telegram.link_rejected` (chỉ khi mã hợp lệ nên biết người dùng, `reason` ghi lý do). Mã sai hoặc lạ **không audit** (tránh bị flood). Allow-list thêm `channel` (`web` hoặc `telegram`), `telegram_account_id`, `replaced_account_id`, dùng lại `reason`. Không dùng `outcome`, `source` |
| K3 | Mã liên kết | `secrets.token_urlsafe(32)` (43 ký tự), băm sha256, hạn **10 phút**. Cấp mã mới thì mã cũ chưa dùng bị vô hiệu bằng cách đặt `expires_at = now()`, thực hiện **dưới khóa `FOR UPDATE` trên dòng người dùng** để hai tab cùng bấm không tạo hai mã hợp lệ. Mã mới thắng, đường dẫn cũ ở tab kia thành "không hợp lệ" (giao diện nói rõ) |
| K4 | Hạn mức `POST link-token` | Theo **người dùng**, 5 lần mỗi cửa sổ 60 giây, in-memory. Vượt thì 429 |
| K5 | `allowed_updates` | `["message","my_chat_member"]` (thêm `callback_query` ở 1B) |
| K6 | Webhook | **404** khi `TELEGRAM_ENABLED=false`, hoặc `TELEGRAM_MODE != webhook`, hoặc server chưa cấu hình `TELEGRAM_WEBHOOK_SECRET`. **403** khi header thiếu hoặc sai secret. **200** với mọi trường hợp còn lại sau khi xác thực, trừ lỗi hạ tầng tạm (K13) |
| K7 | Polling và bot | Polling chỉ dev (service `telegram-poller`, profile `telegram`). Poller **từ chối chạy** khi `APP_ENV=production`, khi `TELEGRAM_ENABLED=false`, hoặc `TELEGRAM_MODE != polling`. Dev và production dùng **hai bot khác nhau**. Script `set`/`delete` in `@username` (từ `getMe`) và URL webhook hiện tại rồi chỉ tiếp tục khi có `--yes`. `TELEGRAM_BOT_USERNAME` được chuẩn hóa (bỏ `@`) và đối chiếu với `getMe` khi script chạy. Lưu ý: service `frontend` dev có `env_file: .env` nên nhận cả token (rủi ro thấp, ghi nhận) |
| K8 | Dọn dữ liệu | `telegram_processed_updates` quá 3 ngày, `telegram_link_tokens` đã dùng hoặc hết hạn quá 7 ngày. Chạy tiện thể trong runner, tối đa mỗi giờ mỗi tiến trình |
| K9 | Biến cấu hình | Thêm so với tài liệu cha: `TELEGRAM_WEBHOOK_URL`, `TELEGRAM_API_BASE_URL` (mặc định `https://api.telegram.org`), `RATE_LIMIT_TELEGRAM_LINK_TOKEN` |
| K10 | Lệnh bot | `setMyCommands` phạm vi `all_private_chats`: `/start`, `/stop`, `/help` |
| K11 | E2E | E2E-A (chỉ giao diện, mock mạng) bắt buộc ở Slice 5b. E2E-B (toàn bộ, fake Telegram) tùy chọn ở Slice 6c |
| K12 | Mã QR | Không làm ở 1A. Nếu cần thì Slice 5c |
| K13 | Phân loại lỗi trong runner | **Lỗi "độc"** (dữ liệu hoặc lỗi lập trình): rollback, ghi `telegram_processed_updates` trong transaction mới, trả 200, gửi tin lỗi hệ thống. **Lỗi hạ tầng tạm** (mất kết nối DB, deadlock, timeout): rollback, **không** ghi dedupe, trả 503 để Telegram thử lại (poller: không tăng offset, backoff). Nếu transaction ghi dedupe cũng lỗi thì coi là hạ tầng tạm |
| K14 | Giao diện khi tính năng tắt | `GET /users/me/telegram` trả `enabled=false` thì **panel không hiển thị**. Production không đổi gì cho tới khi bật |
| K15 | Mô hình đe dọa đường dẫn liên kết | Ai có đường dẫn trong 10 phút có thể gắn Telegram của mình vào tài khoản của chủ đường dẫn, và ngược lại lừa người khác bấm đường dẫn của mình. Giảm thiểu ở 1A: mã sống ngắn, dùng một lần, tin xác nhận nêu **tên** (không nêu email), trang Hồ sơ hiển thị `@username` và thời điểm liên kết để người dùng nhận ra liên kết lạ, audit đầy đủ. **Không có bước xác nhận trong chat ở 1A**. Phải xét lại bằng một bước xác nhận trước khi chatbot Giai đoạn 2 được phép ghi dữ liệu. **Điều kiện này đã được đưa vào tài liệu cha** (Mục 5.3 và slice 2B) như một điều kiện chặn |
| K16 | DB dev khôi phục từ dump production | Sau khi khôi phục dump có bảng Telegram (từ lần triển khai Slice 7 trở đi), chạy `TRUNCATE telegram_accounts, telegram_link_tokens, telegram_processed_updates;` kẻo Telegram của người thật bị coi là "đang liên kết người khác" trên dev, và 1B có thể gửi nhầm. Ghi vào runbook (Slice 6b) |
| K17 | Log | Hạ `httpx` và `httpcore` xuống WARNING **và** scrub ở Formatter. Chấp nhận mất dòng INFO "HTTP Request" của httpx, kể cả cuộc gọi Vietcombank. Scrub chỉ phủ handler gốc (logger `uvicorn.*` có handler riêng nên không dựa vào scrub cho chúng) |
| K18 | Lớp test tích hợp DB thật | Thêm một lớp nhỏ (marker `integration`) chạy trên `postgres-test` cho 5 hành vi: dedupe đồng thời, hai partial unique, `FOR UPDATE` trên mã, rollback savepoint khi đổi tài khoản, phân biệt constraint vi phạm. Nếu không đồng ý thì các hành vi này chỉ kiểm bằng `psql` thủ công (yếu hơn, không chống hồi quy). Cách `backend-test` nối `postgres-test` **[CHƯA XÁC MINH]**, xem ở Slice 2 |
| K19 | Giữ nguyên hợp đồng khi tắt | Khi cờ tắt: `GET` vẫn 200 với `enabled=false`, `POST link-token` 503, webhook 404 |

## Hợp Đồng API (đóng băng ở Slice 3a, frontend dựa vào đây)

Tất cả dưới prefix `/api/v1`, cần đăng nhập (`get_current_user`), **không** cần permission riêng.

| Endpoint | Thành công | Lỗi |
|---|---|---|
| `GET /users/me/telegram` | 200 `{enabled, bot_username, account, pending_link}` | 401 |
| `POST /users/me/telegram/link-token` | 201 `{deep_link, expires_at, expires_in_seconds, bot_username}` | 429, 503 |
| `DELETE /users/me/telegram/link-token` | 204, idempotent (hủy yêu cầu đang chờ) | 401 |
| `DELETE /users/me/telegram` | 204, idempotent (hủy liên kết) | 401 |

Trong đó:
- `account` là `null` hoặc `{status: "active" | "blocked", username: string | null, first_name: string | null, linked_at: ISO8601}`. `username` lưu và trả **không có** `@` (giao diện thêm `@`). Liên kết đã thu hồi không hiển thị.
- `pending_link` là `null` hoặc `{expires_at: ISO8601, expires_in_seconds: number}`. `expires_in_seconds` do server tính tại thời điểm trả lời, để giao diện đếm ngược không phụ thuộc đồng hồ máy khách.
- `account` và `pending_link` **độc lập**: khi đổi tài khoản thì liên kết cũ vẫn `active` trong lúc chờ tài khoản mới.
- `enabled=false` thì `GET` vẫn 200 với `bot_username: null`, chỉ `POST` trả 503.
- `deep_link` luôn dạng `https://t.me/<bot_username>?start=<mã>` và **chỉ có trong response `POST`** (chỉ lưu băm). Giao diện giữ trong bộ nhớ, không ghi vào `localStorage` hay `sessionStorage`.
- Không có mã lỗi 409 và không có 404 cho hai `DELETE`. `detail` của backend có thể là tiếng Anh, giao diện map theo mã trạng thái sang tiếng Việt cố định.

Webhook (không JWT, không đưa vào OpenAPI): `POST /api/v1/telegram/webhook`, header `X-Telegram-Bot-Api-Secret-Token`, `Content-Type: application/json`.

## Mô Hình Dữ Liệu (migration additive, viết tay, không `--autogenerate`)

Chuỗi migration: migration S2 có `down_revision = "20260824_1000"`; migration S3a có `down_revision` là revision của migration S2. Chép header của `20260824_1000_add_quote_cancellation.py`, tên file `YYYYMMDD_HHMM_<mô_tả>.py`. Kiểm `alembic heads` còn đúng 1 head sau mỗi migration.

```
telegram_processed_updates          -- Slice 2
  update_id BIGINT PK (không autoincrement)
  received_at timestamptz server_default now()

telegram_accounts                   -- Slice 3a
  id UUID PK
  user_id FK users CASCADE (ix)
  telegram_user_id BIGINT NOT NULL
  chat_id BIGINT NOT NULL
  username varchar(64) NULL         -- lưu không có '@'
  first_name varchar(150) NULL
  status varchar(20) CHECK in ('active','revoked','blocked')
  linked_at timestamptz NOT NULL, revoked_at NULL
  revoked_reason varchar(30) NULL CHECK in ('replaced','user_unlink','stop_command','owner_inactive')
  last_seen_at NULL, created_at, updated_at
  UNIQUE PARTIAL uq_telegram_accounts_holding_telegram_user (telegram_user_id) WHERE status IN ('active','blocked')
  UNIQUE PARTIAL uq_telegram_accounts_holding_user          (user_id)          WHERE status IN ('active','blocked')

telegram_link_tokens                -- Slice 3a
  id UUID PK, user_id FK users CASCADE (ix)
  token_hash varchar(64) UNIQUE (ix)       -- sha256 hex
  expires_at timestamptz NOT NULL, used_at NULL, created_at
```

Ba model ở ba file riêng, đăng ký ở `app/models/__init__.py` và `app/db/base.py` **ngay trong slice thêm bảng** (S2 cho bảng dedupe, S3a cho hai bảng còn lại). `status` dùng `String(20)` kèm `CheckConstraint`, không dùng Enum. Không thêm relationship hay cột vào `User`.

## Bộ Tin Nhắn Của Bot (tiếng Việt có dấu, HTML, duyệt ở Slice 0)

`{tên}` là họ tên người dùng Quotify, luôn qua `html.escape(quote=False)`.

| Tình huống | Nội dung |
|---|---|
| `/start`, chưa liên kết | "Xin chào! Đây là bot thông báo biến động giá của Quotify. Để nhận thông báo, hãy mở trang Hồ sơ trên Quotify, bấm \"Liên kết Telegram\" rồi mở đường dẫn liên kết được tạo." |
| `/start`, đã liên kết (kể cả cùng người cùng Telegram bấm lại đường dẫn) | "Tài khoản Telegram này đã liên kết với <b>{tên}</b>. Gõ /help để xem hướng dẫn." |
| `/start <mã>` hợp lệ | "✅ Đã liên kết với tài khoản <b>{tên}</b>. Bạn sẽ nhận thông báo biến động giá tại đây. Gõ /stop để hủy liên kết." |
| Kích hoạt lại từ `blocked` | "✅ Đã kích hoạt lại liên kết với <b>{tên}</b>." |
| Mã sai, hết hạn hoặc đã dùng | "Đường dẫn liên kết không hợp lệ hoặc đã hết hạn. Hãy tạo đường dẫn mới trong trang Hồ sơ trên Quotify." |
| Telegram này đang gắn với người dùng khác | "Tài khoản Telegram này đang liên kết với một tài khoản Quotify khác. Hãy gõ /stop ở đây hoặc hủy liên kết ở tài khoản đó trước, rồi tạo đường dẫn mới." |
| Người dùng không còn hoạt động | "Tài khoản Quotify của bạn hiện không hoạt động nên không thể liên kết." |
| `/stop`, đang liên kết hoặc bị chặn | "Đã hủy liên kết. Bạn sẽ không nhận thông báo nữa. Để liên kết lại, hãy tạo đường dẫn mới trong trang Hồ sơ trên Quotify." |
| `/stop`, chưa liên kết | "Tài khoản Telegram này chưa được liên kết." |
| `/help` | "Các lệnh:\n/start — Bắt đầu hoặc xem trạng thái liên kết\n/stop — Hủy liên kết Telegram với Quotify\n/help — Xem hướng dẫn này\n\nBot này gửi thông báo biến động giá. Để liên kết, mở trang Hồ sơ trên Quotify." |
| Tin nhắn khác | "Tôi chưa hiểu yêu cầu này. Gõ /help để xem hướng dẫn." |
| Gửi tới chat cũ khi bị thay thế | "Liên kết Telegram này đã được thay thế bằng một tài khoản Telegram khác. Bạn sẽ không nhận thông báo ở đây nữa." |
| Lỗi hệ thống (K13) | "Hệ thống tạm thời chưa xử lý được yêu cầu. Vui lòng thử lại sau." |
| Nhóm, kênh | Bỏ qua, không trả lời |

Nhãn trong giao diện (Slice 5b): "Liên kết Telegram", "Đổi tài khoản Telegram", "Hủy liên kết", "Tạo đường dẫn mới", "Hủy yêu cầu".

## Lệnh Chuẩn

```bash
# Backend: từng công cụ riêng cho file mới (stack dev đang chạy, source mount vào /app)
docker compose exec backend uv run pytest tests/test_telegram_*.py -q --no-cov
docker compose exec backend uv run pytest -q --no-cov                       # toàn bộ, so với 385 passed
docker compose exec backend uv run ruff check <file mới>
docker compose exec backend uv run ruff format --diff <file mới>
docker compose exec backend uv run mypy <file mới>
docker compose exec backend uv run bandit -c pyproject.toml -r app          # so với 16 phát hiện
make migrate                                                                # alembic upgrade head
docker compose exec backend uv run alembic heads                            # đúng 1 head
docker compose exec postgres psql -U postgres -d app -c '\d telegram_accounts'

# Frontend, trong frontend/
npx eslint <file mới và file sửa> && npm run lint:styles
npx prettier --check <file mới>     # chỉ --write cho file MỚI
npx vue-tsc --noEmit -p tsconfig.app.json
npx vitest run <spec liên quan>
```

Sau khi đổi `.env` phải `docker compose up -d --force-recreate` (restart không nạp lại `env_file`). Chế độ `curl` kiểm webhook cần `TELEGRAM_MODE=webhook`, chạy poller cần `TELEGRAM_MODE=polling`: đổi `.env` và recreate khi chuyển qua lại. Container chạy bằng root nên file Alembic sinh ra cần `chown`. `docker compose down` không dừng service có profile, dùng `docker compose --profile telegram down`.

---

## Slice 0: Chuẩn Bị Và Kiểm Chứng Điều Kiện

**Loại:** HITL (thao tác với Telegram, VPS, tài liệu) | **Chặn bởi:** không | **Cỡ:** nhỏ

### Mục tiêu

Chốt điều kiện ngoài code và các điểm Telegram chưa nêu rõ **trước** khi viết dòng code đầu tiên. Phát hiện sớm nếu thiết kế webhook không khả thi trên hạ tầng thật.

### Việc cần làm

1. **Hướng dẫn dev (ghi vào runbook ở S6b):** tạo bot dev qua @BotFather (username kết thúc bằng `bot`, không đổi được sau này), tạo 1 đến 2 tài khoản Telegram thử, đặt `TELEGRAM_BOT_TOKEN` vào `.env` dev (gitignore). Bot production tạo ở Slice 7.
2. **Kiểm chứng thực nghiệm với bot dev** (dùng `read -rs TOKEN` và `curl -K -` để token không lộ trong `ps` hay lịch sử). Ghi vào Phụ lục A:
   - **T2**: `getUpdates` khi webhook đang bật trả mã nào.
   - **T3**: bấm lại đường dẫn khi đã Start có gửi lại `/start <param>` không (mobile, desktop, web). Thử param 64 và 65 ký tự.
   - **T5**: chặn bot rồi `sendMessage` trả mã và chuỗi lỗi gì. `my_chat_member.new_chat_member.status` khi chặn và bỏ chặn.
   - **T5b**: `sendMessage` tới ID chưa Start và ID bịa.
   - T6 đến T9 (429, 4096 ký tự, `callback_data`, ảnh) phục vụ 1B, chạy nếu tiện.
3. **Kiểm tra hạ tầng production, cả hai chiều** (người có SSH và mạng ngoài):
   - Ra ngoài: từ VPS, `curl -sS -o /dev/null -w '%{http_code}\n' https://api.telegram.org/`.
   - Chứng chỉ: `openssl s_client -connect quotify.honghafeed.com.vn:443 -servername quotify.honghafeed.com.vn | openssl x509 -noout -issuer -subject -dates`, đủ chuỗi trung gian.
   - **Vào từ ngoài:** gọi `https://quotify.honghafeed.com.vn/health` từ mạng ngoài công ty (ví dụ 4G), xác nhận không bị chặn bởi tường lửa hay allow-list.
   - DNS: có bản ghi A, và nếu có bản ghi AAAA thì xác nhận không làm Telegram gọi nhầm (Telegram không hỗ trợ IPv6 cho webhook).
   - Xác nhận production đang chạy `prod.conf`, **không** phải `prod-http-only.conf` (`docker compose` đọc `NGINX_CONF_FILE`).
4. **Xác nhận bảng quyết định K1 đến K19** và bộ tin nhắn. Quyết định K18 (lớp test tích hợp DB thật) cần người quyết định rõ vì thêm hạ tầng test.
5. **Cập nhật tài liệu:**
   - `CONTEXT.md`: bảng thuật ngữ ở trên (kèm cột "Tránh").
   - `docs/quotify/Requirements.txt` (mục 3.4 và 3.9) và `docs/quotify/quotify-implementation-plan.md` ("Nhật ký thay đổi"): thông báo giá và chatbot nay nằm trong phạm vi, giọng trung tính, không khuyến nghị mua bán.
   - Tài liệu cha `plan-telegram-bien-dong-gia-va-chatbot-ai.md`: **đã được cập nhật** theo bảng "Độ Lệch Có Chủ Đích" ngày 2026-10-04. Việc ở Slice 0 chỉ là rà lại cho khớp với kết quả kiểm chứng ở mục 2 và 3, và cập nhật nếu có khác biệt.
   - `CONTEXT.md` cũng thêm các thuật ngữ biến động giá ở Mục 2 của tài liệu cha, không chỉ các thuật ngữ liên kết.

### Tiêu chí chấp nhận

- [ ] Có bot dev, token trong `.env` dev, không có trong git.
- [ ] Phụ lục A điền xong T2, T3, T5, T5b. Nếu kết quả khác giả định thì sửa quyết định liên quan trước Slice 1.
- [ ] Hạ tầng production: ra ngoài được, chứng chỉ hợp lệ, vào được từ mạng ngoài, DNS ổn. Nếu không đạt thì dừng và xử lý trước khi sang Slice 2.
- [ ] K1 đến K19 và bộ tin nhắn được xác nhận (hoặc sửa), bao gồm quyết định K18.
- [ ] Các tài liệu ở mục 5 được cập nhật và commit.

---

## Slice 1: Cấu Hình Và Telegram Client An Toàn

**Loại:** AFK | **Chặn bởi:** Slice 0 | **Cỡ:** vừa

### Mục tiêu

Backend gọi được Telegram, và **không đường nào làm lộ token**. Chưa nhận update, chưa có bảng.

### Việc cần làm

1. `core/config.py`: các field Telegram (K9), mọi field có default, `*_FILE` cho token và secret qua `model_post_init`. `TELEGRAM_MODE` là `Literal["webhook","polling"]`. `TELEGRAM_BOT_USERNAME` chuẩn hóa bỏ `@`. Thiếu token lúc `TELEGRAM_ENABLED=true` thì báo lỗi lúc chạy, không ném khi tạo Settings. `.env.example` (dev: `TELEGRAM_MODE=polling`) và `.env.production.example` (`TELEGRAM_MODE=webhook`). Secret webhook sinh bằng `openssl rand -hex 32`, không `-base64`.
2. `core/logging.py` (K17): hạ `httpx` và `httpcore` xuống WARNING, và scrub regex `bot\d+:[A-Za-z0-9_-]{20,}` thành `bot<redacted>` ở **cấp Formatter** (JSON lẫn plain) để che cả `message` lẫn traceback.
3. `core/observability.py`: loại URL Telegram khỏi `HTTPXClientInstrumentor` bằng biến `OTEL_PYTHON_HTTPX_EXCLUDED_URLS`, đặt **trước** `instrument()`, **nối vào** giá trị có sẵn (không ghi đè) và **suy ra host từ `TELEGRAM_API_BASE_URL`** (không hard-code `api.telegram.org`). Tách thành hàm nhỏ để test.
4. `integrations/telegram.py`: client `httpx` theo mẫu `vietcombank.py` (inject `http_client`, base URL cấu hình). Phương thức: `get_me`, `send_message`, `set_webhook`, `delete_webhook`, `get_webhook_info`, `get_updates`, `set_my_commands`. **Không** gọi `raise_for_status()`: parse JSON `ok/error_code/description/parameters.retry_after`. Bắt `httpx.HTTPError` và ném lại lỗi đã làm sạch bằng `from None`. Exception `TelegramApiError`, `TelegramForbiddenError` (403), `TelegramRateLimitError` (429, `retry_after`), `TelegramNetworkError`. `__repr__` che token. Có `aclose()`. Hàm `escape_html` (Nguyên tắc 7). `send_message` báo lỗi rõ khi quá 4096 ký tự (không tự cắt, 1A không cần). Không dùng tham số mặc định là chuỗi rỗng cho biến tên chứa `token|secret` (bandit B105-B107).
5. `backend/scripts/telegram_webhook.py` (mẫu `seed_auth_rbac.py`), lệnh con `me`: **gọi `configure_logging` trước**, in `@username (id)` của bot, không in token.

### Thứ tự test (tracer trước)

1. **Tracer:** `get_me` trả thông tin bot qua `httpx.MockTransport` (mẫu `test_exchange_rate_service.py`).
2. Ánh xạ lỗi: 401, 403, 429 kèm `retry_after`, `ok:false`.
3. **Không lộ token:** với client thật và transport giả, (a) log INFO của `httpx` (JSON và plain), (b) log exception, (c) `str`/`repr` của exception và của client, (d) chuỗi traceback chained, đều không chứa token. Lỗi mạng và timeout cũng sạch.
4. Settings: mặc định tắt và không cần token, `*_FILE` nạp được, file rỗng thì lỗi (viết mới, `test_production_readiness.py:47-69` chỉ test đọc file thành công), `@` bị bỏ khỏi username.
5. Loại trừ OTel: nối vào giá trị có sẵn, host suy ra từ `TELEGRAM_API_BASE_URL`.
6. `send_message`: escape dữ liệu người dùng và báo lỗi khi quá 4096 ký tự.

### Cách xác minh thật

```bash
docker compose exec -T backend sh -c '
  uv run python scripts/telegram_webhook.py me 2>&1 | tee /tmp/me.out
  python3 -c "import os; t=os.environ[\"TELEGRAM_BOT_TOKEN\"]; out=open(\"/tmp/me.out\").read(); assert t and t not in out, \"LỘ TOKEN\"; print(\"OK: không lộ token\")"'
```

(Token đọc trong môi trường container, không in ra màn hình. Log của `docker compose exec` không nằm trong `docker compose logs`, nên kiểm trực tiếp stdout và stderr của chính lệnh.) Slice 1 chưa có tiến trình server nào gọi Telegram, nên kiểm log của backend và worker là việc của Slice 2.

### Tiêu chí chấp nhận

- [ ] `me` trả đúng username bot dev.
- [ ] Không có token trong log, traceback, repr (test và kiểm trực tiếp).
- [ ] `TELEGRAM_ENABLED=false` mặc định, backend và worker khởi động không cần biến Telegram.
- [ ] pytest 385 test cũ vẫn xanh. File mới sạch ruff, mypy, bandit.
- [ ] `.env.example`, `.env.production.example` có biến mới, giá trị mẫu không phải secret thật.

### Rollback

Không có migration. Xóa file mới và hoàn nguyên `config.py`, `logging.py`, `observability.py`, hai file `.env.*`, `tests/test_production_readiness.py`.

---

## Slice 2: Nhận Update, Chống Trùng, Webhook Và Polling

**Loại:** AFK | **Chặn bởi:** Slice 1 | **Cỡ:** vừa

### Mục tiêu

Bot dev trả lời `/help` bằng Telegram thật qua đường xử lý dùng chung cho webhook và polling ("walking skeleton"): một tin nhắn đi hết đường từ Telegram, qua chống trùng và hạn mức, tới trả lời. Webhook công khai xuất hiện từ slice này nên hạn mức và an toàn thuộc về slice này.

### Việc cần làm

1. Migration `telegram_processed_updates` + model, đăng ký ở `models/__init__.py` và `db/base.py`.
2. `services/telegram_update_service.py` (Nguyên tắc 5): `handle(session, update) -> list[OutboundMessage]`, chỉ `flush()`. Trong **một transaction**: chống trùng bằng `insert(...).on_conflict_do_nothing(index_elements=["update_id"]).returning(update_id)` rồi `scalar_one_or_none()` (an toàn kiểu dưới mypy strict, không phụ thuộc `rowcount` của driver). Chỉ xử lý `message` có `chat.type == "private"` và `from` không rỗng. `/help` và tin khác theo bộ tin nhắn. Chưa có liên kết ở slice này.
3. `services/telegram_update_runner.py`: `run_update(session_factory, client, payload, ...)` dùng chung webhook và poller. Kiểm hạn mức **trước** khi chạm DB (10 update mỗi phút mỗi người dùng Telegram, vượt thì bỏ qua và trả 200 không trả lời; limiter có TTL tự dọn key vì limiter hiện có không xóa key). Mở session, gọi service, `commit()`, **rồi** gửi các tin trong `try/except` chỉ log. Phân loại lỗi theo K13. Dọn dữ liệu theo K8. Không log nội dung update.
4. `api/v1/telegram.py` (`APIRouter(prefix="/telegram")`): `POST /webhook`, `include_in_schema=False`. Nhận **`request: Request`** (không khai báo `body` kiểu `dict`, vì FastAPI trả 422 trước dependency khi body hỏng). Thứ tự: kiểm bật/tắt và mode và secret cấu hình, nếu không thì 404 → kiểm header bằng `secrets.compare_digest` trên bytes, sai thì 403 → đọc `await request.body()` (có trần kích thước) và parse JSON trong `try/except` → `run_update`. Không gắn hạn mức theo IP. Đăng ký ở `api/v1/router.py` đúng thứ tự chữ cái.
5. `telegram_poller.py` (`python -m app.telegram_poller`): K7 (từ chối khi `APP_ENV=production`, `TELEGRAM_ENABLED=false` hoặc sai mode). Tự gọi `configure_logging`. Mở session mới mỗi update. `deleteWebhook` lúc khởi động. Long-poll 25 giây với timeout HTTP lớn hơn (khoảng 35 giây). Offset giữ trong bộ nhớ. Bắt SIGTERM, backoff khi lỗi mạng, `aclose()`. Gắn `request_id_context` dạng `tg-update-<id>` quanh mỗi update.
6. `docker-compose.yml`: service `telegram-poller` (copy khối `worker`), `profiles: ["telegram"]`, `depends_on` backend `service_healthy`. Lệnh dùng **`exec`** (`sh -lc "uv sync && exec uv run python -m app.telegram_poller"`) để SIGTERM tới được Python.
7. Mở rộng `scripts/telegram_webhook.py`: `set` (đặt webhook với `secret_token` và `allowed_updates` theo K5), `delete`, `info`, `commands` (K10). Theo K7: in `@username` (từ `getMe`) và URL webhook hiện tại rồi yêu cầu `--yes` cho `set` và `delete`.
8. **Lớp test tích hợp (nếu K18 đồng ý):** marker `integration` đăng ký trong `pyproject.toml` (có `--strict-markers`), fixture DB trỏ `postgres-test`. Xác minh cách `docker-compose.test.yml` nối `backend-test` với `postgres-test` rồi ghi vào kế hoạch **[CHƯA XÁC MINH]**.

### Thứ tự test (tracer trước)

1. **Tracer:** webhook với header secret đúng và update `/help` từ chat riêng → HTTP 200, và client thật (trên `MockTransport`) phát ra đúng một request `sendMessage` chứa nội dung `/help` tiếng Việt.
2. Cùng `update_id` lần hai: 200 và **không** có request `sendMessage` thứ hai.
3. Header thiếu hoặc sai: 403. Tính năng tắt, sai mode, hoặc thiếu secret cấu hình: 404, **kể cả khi body là rác** (không lộ route). Test với `Settings.model_validate` qua `app.dependency_overrides[get_settings]` (hàm thật có `lru_cache`).
4. Body JSON hỏng, body không phải `dict`, `Content-Type` sai: 200 và không có `sendMessage`, không lỗi 500.
5. Chat nhóm: 200, không gửi gì.
6. `sendMessage` lỗi (client giả ném `TelegramApiError`): vẫn 200, update vẫn được ghi dedupe.
7. Lỗi "độc" trong service: 200, ghi dedupe, tin lỗi hệ thống. **Lỗi hạ tầng tạm** (client DB giả ném `OperationalError`): 503 và **không** ghi dedupe.
8. Hạn mức theo người dùng Telegram: update thứ 11 trong một phút bị bỏ qua (không gửi gì, 200).
9. Poller (quan sát request ra qua `MockTransport`): offset trong `getUpdates` tăng đúng; từ chối chạy khi `APP_ENV=production`, khi tắt, hoặc sai mode; gọi `deleteWebhook` lúc đầu; khi lỗi hạ tầng tạm thì không tăng offset.
10. **Tích hợp DB thật (K18):** hai lần chèn đồng thời cùng `update_id` chỉ một lần được xử lý.
11. `test_audit_context_usage.py` và `test_permission_inventory.py` vẫn xanh.

### Cách xác minh thật

```bash
# TELEGRAM_MODE=webhook trong .env, TELEGRAM_ENABLED=true, recreate backend
H='Content-Type: application/json'
curl -i -X POST http://localhost:8000/api/v1/telegram/webhook -H "$H" -d '{}'                                              # 403
curl -i -X POST ... -H "$H" -H 'X-Telegram-Bot-Api-Secret-Token: SAI' -d '{}'                                             # 403
curl -i -X POST ... -H "$H" -H "X-Telegram-Bot-Api-Secret-Token: $S" -d '{"update_id":1,"message":{...,"text":"/help"}}'   # 200, gọi hai lần: lần hai không xử lý lại
curl -i -X POST ... -H "$H" -H "X-Telegram-Bot-Api-Secret-Token: $S" -d '{rác'                                            # 200
# đổi sang TELEGRAM_MODE=polling, recreate backend, rồi:
docker compose --profile telegram up -d telegram-poller      # nhắn /help cho bot dev trên Telegram: bot trả lời
docker compose --profile telegram stop telegram-poller       # phải dừng trong dưới 10 giây
docker compose exec postgres psql -U postgres -d app -c 'select count(*) from telegram_processed_updates'
docker compose logs backend telegram-poller 2>&1 | python3 -c "import os,sys; t=os.environ.get('TELEGRAM_BOT_TOKEN',''); assert t and t not in sys.stdin.read(); print('OK: log sạch')"
```

(Dòng cuối chạy với `TELEGRAM_BOT_TOKEN` nạp vào shell từ `.env`, không `echo`. Chỉ dùng khi biến đã được đặt, nếu rỗng thì lệnh `assert` sẽ báo lỗi chứ không "xanh giả".)

### Tiêu chí chấp nhận

- [ ] Nhắn `/help` cho bot dev bằng Telegram thật được trả lời tiếng Việt có dấu.
- [ ] Gửi trùng `update_id` không trả lời hai lần. Body hỏng vẫn 200 khi đã xác thực.
- [ ] Webhook 403, 404, 200, 503 đúng như K6 và K13. Route không lộ ra OpenAPI.
- [ ] Poller dừng sạch dưới 10 giây, từ chối khi sai điều kiện.
- [ ] Log backend và poller không chứa token.
- [ ] Baseline không xấu hơn. Migration lên xuống được trên dev, đúng 1 head.

### Rollback

Dừng poller, `TELEGRAM_ENABLED=false`, `deleteWebhook`. Bảng nhỏ, để lại.

---

## Slice 3a: Cấp Mã Liên Kết Và Đóng Băng Hợp Đồng API

**Loại:** AFK | **Chặn bởi:** Slice 2 | **Cỡ:** vừa

### Mục tiêu

Người dùng đăng nhập cấp được đường dẫn liên kết và xem được trạng thái. Hợp đồng API được đóng băng để frontend bắt đầu làm.

### Việc cần làm

1. Migration `telegram_accounts` + `telegram_link_tokens`, kể cả hai partial unique index theo K1, nối vào migration của Slice 2. Đăng ký hai model.
2. `services/telegram_link_service.py`: `issue_link_token(user_id)` (K3: khóa `FOR UPDATE` dòng người dùng, vô hiệu mã cũ bằng `expires_at = now()`, mã mới hạn 10 phút, `datetime.now(UTC)`), `cancel_pending(user_id)`, `get_status(user_id)`. Băm bằng hàm riêng (hàm trong `auth/service.py` là private).
3. `schemas/telegram.py` và `api/v1/telegram_link.py` (`APIRouter(prefix="/users/me/telegram")`): `GET ""`, `POST "/link-token"`, `DELETE "/link-token"` theo hợp đồng. `POST` giới hạn theo K4 bằng `request.app.state.rate_limiter.hit(key=f"telegram.link_token:{user.id}", ...)`, trả 503 khi tắt hoặc chưa cấu hình. `commit()` ở route, `refresh` hoặc gán timestamp bằng Python trước khi dựng response. Đăng ký router. Không sửa `users.py`.
4. Audit (K2): `telegram.link_requested` qua `AuditLogContext.from_request`. Thêm `channel`, `telegram_account_id`, `replaced_account_id` vào allow-list. Test mới trong `test_audit_log_service.py`: key mới được giữ, key chứa `token` vẫn bị che.
5. Lệnh `/start` trong service nhận update chưa xử lý mã (xử lý mã ở 3b).

### Thứ tự test (tracer trước)

1. **Tracer:** người dùng đăng nhập `POST link-token` → 201 với `deep_link` dạng `https://t.me/<bot>?start=<mã>`, và `GET` ngay sau đó trả `pending_link` với `expires_in_seconds` trong khoảng hợp lý.
2. Cấp mã lần hai: `GET` chỉ còn một `pending_link`, mã cũ không còn hợp lệ (kiểm qua DB, redeem ở 3b).
3. `DELETE link-token`: `pending_link` về `null`. Gọi lần hai vẫn 204.
4. `enabled=false`: `GET` 200 với `enabled=false`, `POST` 503. Vượt hạn mức: 429.
5. Audit `telegram.link_requested` được ghi, metadata không chứa mã.
6. Response không chứa mã băm, và mã gốc chỉ nằm trong `deep_link`.
7. **Tích hợp DB thật (K18):** hai partial unique hoạt động, hai yêu cầu cấp mã song song cho cùng người dùng chỉ để lại một mã hợp lệ.

### Cách xác minh thật

```bash
make migrate && docker compose exec backend uv run alembic downgrade -1 && make migrate && docker compose exec backend uv run alembic heads
docker compose exec postgres psql -U postgres -d app -c '\d telegram_accounts'          # thấy 2 partial unique
curl -s -X POST http://localhost:8000/api/v1/users/me/telegram/link-token -H "Authorization: Bearer $AT"   # có deep_link
curl -s http://localhost:8000/api/v1/users/me/telegram -H "Authorization: Bearer $AT"                       # pending_link có giá trị
# thử vi phạm unique trong BEGIN ... ROLLBACK bằng psql
```

### Tiêu chí chấp nhận

- [ ] Hợp đồng API đóng băng đúng như mục Hợp Đồng API, commit làm căn cứ cho Slice 5a.
- [ ] Hai partial unique index hoạt động (thử vi phạm trong `psql`).
- [ ] Không có token (gốc hoặc băm) lộ ngoài `deep_link` của `POST`.
- [ ] Baseline không xấu hơn.

### Rollback

`TELEGRAM_ENABLED=false`. Dev: `alembic downgrade -1`. Production: không downgrade, để bảng.

---

## Slice 3b: Liên Kết Qua Telegram Và Đổi Tài Khoản

**Loại:** AFK | **Chặn bởi:** Slice 3a | **Cỡ:** lớn (vẫn là một lát cắt vì chỉ có một luồng: bấm đường dẫn rồi liên kết)

### Mục tiêu

Mở đường dẫn trong Telegram thật liên kết được tài khoản, và **đổi sang tài khoản Telegram khác** (nguyên tử). Luồng đổi nằm ở slice này vì người đã liên kết A mà mở đường dẫn bằng B sẽ vi phạm `uq_telegram_accounts_holding_user` ngay khi có `redeem`.

### Việc cần làm

1. `redeem(mã, telegram_user_id, chat_id, username, first_name)` trong `telegram_link_service.py`: khóa dòng mã `FOR UPDATE`, kiểm hết hạn, đã dùng, người dùng phải `ACTIVE`, `telegram_user_id` chưa thuộc người khác. **Thu hồi liên kết cũ của người dùng (nếu có) và chèn liên kết mới nằm trong cùng một `begin_nested()`**; bắt `IntegrityError`, **phân biệt constraint vi phạm theo tên** (`..._holding_telegram_user` hay `..._holding_user`) để chọn đúng thông điệp. `flush()` rõ ràng giữa thu hồi và chèn. Cùng người cùng Telegram: idempotent, trả tin "đã liên kết".
2. Nhánh `/start <mã>` trong `telegram_update_service.py` theo bộ tin nhắn. Chỉ chat riêng.
3. Audit: `telegram.linked` (kèm `replaced_account_id` khi đổi, `channel="telegram"`) và `telegram.link_rejected` khi mã hợp lệ nhưng bị từ chối (`reason`). Dùng `AuditLogContext` có `actor_user_id` (không có `Request`) và `request_id=tg-update-<id>`. Mã sai hoặc lạ không audit.
4. Khi đổi tài khoản, sau commit gửi tin "đã được thay thế" tới chat cũ (best-effort, lỗi không làm hỏng việc đổi).

### Thứ tự test (tracer trước)

1. **Tracer:** người dùng cấp mã (3a), update `/start <mã>` từ chat riêng → client phát `sendMessage` "Đã liên kết với <b>{tên}</b>", và `GET /users/me/telegram` trả `account.status="active"`, `pending_link: null`.
2. Dùng lại mã đã dùng, mã hết hạn, mã lạ: không tạo liên kết, tin "không hợp lệ", mã lạ không có audit.
3. `telegram_user_id` đang giữ bởi người dùng khác: từ chối, tin tương ứng, audit `link_rejected` kèm `reason`.
4. Người dùng không `ACTIVE`: từ chối.
5. Cùng người cùng Telegram bấm lại: idempotent, không tạo bản ghi trùng.
6. **Đổi tài khoản:** người đã liên kết A mở đường dẫn bằng B → A `revoked` (`replaced`), B `active`, chat A nhận tin thay thế. Lỗi gửi tin cho A không làm hỏng việc đổi.
7. **Tích hợp DB thật (K18):** insert của B vi phạm unique → thu hồi A **bị rollback** (A vẫn `active`), và thông điệp trả về đúng theo constraint bị vi phạm; hai yêu cầu `redeem` song song cùng một mã chỉ một thành công.
8. `/start` không tham số khi chưa và đã liên kết.
9. `test_permission_inventory.py` vẫn xanh (không có `require_permission` với mã mới).

### Cách xác minh thật

```bash
# cấp mã (3a), mở deep_link trên Telegram thật bằng tài khoản thử A, bấm Start: bot trả lời "Đã liên kết"
curl -s http://localhost:8000/api/v1/users/me/telegram -H "Authorization: Bearer $AT"     # account.status = active
# dùng lại đường dẫn: bot báo không hợp lệ. Ghi kết quả T3 (bấm lại đường dẫn khi đã Start)
# cấp mã mới, mở bằng tài khoản thử B: A bị thu hồi và nhận tin thay thế
docker compose exec postgres psql -U postgres -d app -c "select status, revoked_reason from telegram_accounts order by created_at"
# audit: telegram.linked, kiểm metadata không có telegram_user_id hay username
```

### Tiêu chí chấp nhận

- [ ] Liên kết thật và đổi tài khoản thật hoạt động trên dev với Telegram thật.
- [ ] Mỗi người dùng không bao giờ có hai liên kết `active/blocked` (kiểm bằng psql).
- [ ] Audit `telegram.linked` đúng, metadata không có `telegram_user_id` hay username.
- [ ] Baseline không xấu hơn.

### Rollback

Như Slice 3a. Không có migration mới.

---

## Slice 4: Hủy Liên Kết, `/stop`, Bị Chặn, Duy Trì Liên Kết

**Loại:** AFK | **Chặn bởi:** Slice 3b | **Cỡ:** vừa

### Mục tiêu

Vòng đời liên kết đầy đủ ngoài việc tạo: hủy từ web, hủy từ Telegram, phát hiện bị chặn, giải phóng chỗ bị giữ lâu, và duy trì thông tin liên kết.

### Việc cần làm

1. `DELETE /users/me/telegram`: 204 idempotent. Thu hồi (`revoked`, `revoked_reason='user_unlink'`), audit `telegram.unlinked` (`channel="web"`).
2. Lệnh `/stop`: thu hồi (`stop_command`), audit `telegram.unlinked` (`channel="telegram"`). Cả liên kết `blocked` cũng hủy được.
3. Bị chặn: xử lý update `my_chat_member` (chặn thì `blocked`, bỏ chặn thì `active` chỉ khi tài khoản còn `blocked`). Hàm `mark_blocked(telegram_user_id)` dùng khi `send_message` ném `TelegramForbiddenError`. Liên kết lại cùng Telegram đang `blocked` thì kích hoạt lại (tin "đã kích hoạt lại").
4. **Giải phóng chỗ:** khi `redeem` gặp `telegram_user_id` đang bị giữ bởi người dùng **không còn `ACTIVE`**, tự thu hồi liên kết đó (`owner_inactive`) rồi tiếp tục liên kết. Tránh Telegram bị khóa vĩnh viễn bởi người đã nghỉ.
5. **Duy trì mỗi tin nhận** từ tài khoản đã liên kết: cập nhật `last_seen_at`, `username`, `first_name`; kiểm `User.status`, nếu không còn `ACTIVE` thì trả tin "không hoạt động" và không xử lý lệnh khác.
6. Dọn dữ liệu theo K8, mở rộng cho `telegram_link_tokens`.
7. Chạy `scripts/telegram_webhook.py commands` để đăng ký `/start`, `/stop`, `/help` (K10).

### Thứ tự test (tracer trước)

1. **Tracer:** người dùng đã liên kết gọi `DELETE /users/me/telegram` → 204, và `GET` trả `account: null`, audit `telegram.unlinked`.
2. `DELETE` khi chưa liên kết: 204. `/stop` đang liên kết, đang `blocked`, chưa liên kết.
3. `my_chat_member` chặn thì `blocked`, bỏ chặn thì `active`. Không bỏ chặn tài khoản đã `revoked`.
4. `send_message` ném 403 thì `mark_blocked`.
5. Telegram đang `blocked` mà người dùng khác thử liên kết: bị từ chối (K1). Liên kết lại cùng Telegram `blocked`: kích hoạt lại, không tạo bản ghi trùng.
6. Giải phóng chỗ: chủ cũ `locked` hoặc `inactive` thì liên kết mới thành công và liên kết cũ `owner_inactive`.
7. Mỗi tin nhận: `username` cập nhật khi đổi, người dùng không `ACTIVE` nhận tin "không hoạt động".
8. Dọn dữ liệu chỉ chạy tối đa mỗi giờ, xóa đúng loại dữ liệu cũ.
9. **Tích hợp DB thật (K18):** `DELETE` rồi liên kết lại không vi phạm unique.

### Cách xác minh thật

```bash
# hai tài khoản Telegram thử A và B, một người dùng Quotify
# 1. Liên kết A. DELETE từ web: A thu hồi.   2. Liên kết lại A, gõ /stop: thu hồi.
# 3. Liên kết A, chặn bot từ A trên Telegram: update my_chat_member đến, DB thành 'blocked' (đối chiếu T5). Bỏ chặn: 'active'.
# 4. Đặt người dùng thành locked qua API admin, liên kết Telegram đó cho người khác: được phép.
docker compose exec postgres psql -U postgres -d app -c "select status, revoked_reason from telegram_accounts order by created_at"
docker compose exec backend uv run python scripts/telegram_webhook.py commands --yes
```

### Tiêu chí chấp nhận

- [ ] Bốn đường: hủy web, `/stop`, bị chặn, giải phóng chỗ, đều xác minh với Telegram thật.
- [ ] Audit `telegram.unlinked` có `reason` và `channel` đúng.
- [ ] Baseline không xấu hơn.

### Rollback

Như Slice 3a. Không có migration mới.

---

## Slice 5a: Frontend, Phần Logic (types, api, mappers, composable)

**Loại:** AFK | **Chặn bởi:** Slice 3a (hợp đồng đã đóng băng, làm với mock), cần Slice 4 để chạy với backend thật | **Cỡ:** vừa

### Mục tiêu

Toàn bộ logic của panel Telegram, kiểm thử được độc lập với giao diện. Chưa chạm `ProfilePage.vue`.

### Việc cần làm

1. `types/telegram.ts`, `api/telegram.mappers.ts` (kiểm `deep_link` bắt đầu bằng `https://t.me/` trước khi dùng làm `href`, nếu không thì ném lỗi), `api/telegram.api.ts`. Token đọc từ `authStore.accessToken` tại **mỗi lần gọi**, không giữ trong closure.
2. `composables/useTelegramLink.ts` (không nhét vào `useProfilePage`). Trạng thái biểu diễn bằng **hai phần độc lập** `account` và `pending`, từ đó suy ra chế độ hiển thị (`loading | error | unlinked | pending | linked | blocked`), trong đó `linked` và `pending` có thể đồng thời đúng (đang đổi tài khoản).
3. Thời hạn do **server** quyết định: giữ `expires_in_seconds` lúc nhận và đếm ngược bằng đồng hồ đơn điệu (`performance.now()`) thay vì so với giờ máy khách. Poll mỗi 3 giây **cho tới khi server trả `pending_link: null`**, hoặc `account.linked_at` đổi so với lúc bắt đầu. Cờ chống request chồng. Tạm dừng khi tab ẩn (`document.hidden`), làm mới khi cửa sổ lấy lại focus hoặc tab hiện lại. Giữ `deep_link` chỉ trong `ref`.
4. Lỗi map theo mã trạng thái: 429 và 503 và 5xx ra thông báo tiếng Việt cố định. Không hiển thị `detail` của backend. Không có nhánh 409 hay 404 (hợp đồng không có).
5. Toàn bộ logic DOM và timer nằm trong file `.ts` (ESLint báo `no-undef` cho `URL`, `setTimeout` trong `.vue`).
6. Hành động: `startLinking`, `cancelPending` (gọi `DELETE link-token`), `copyLink`, `confirmUnlink`.

### Thứ tự test (tracer trước)

1. **Tracer:** `bootstrap` tải trạng thái rồi `startLinking` gọi API với token hiện tại, trạng thái chuyển sang chờ và có `deepLink` (mock `@/api/telegram.api` bằng `vi.hoisted` + `vi.mock`, `vi.resetAllMocks()` thay vì `clearAllMocks`, **không** sao chép dòng `permissionStore.permissions =` đang gây 3 test fail baseline).
2. Mapper: snake_case sang camelCase, `pending_link: null` thành không chờ, `deep_link` lạ (ví dụ `javascript:`) ném lỗi.
3. Poll mỗi 3 giây khi chờ và dừng khi server trả `pending_link: null` (fake timers `advanceTimersByTimeAsync`).
4. **Đổi tài khoản:** đang `linked` mà `startLinking` thì vẫn `linked` và `pending` cùng đúng; poll tới khi `linked_at` đổi thì dừng và báo thành công. Hủy yêu cầu chờ gọi `DELETE link-token`.
5. Đếm ngược theo `expires_in_seconds` đúng khi đồng hồ hệ thống (`Date`) bị lệch.
6. Chống request chồng. Tab ẩn thì không poll. Focus lại gọi đúng một lần. `dispose` gỡ timer và listener.
7. 429, 503, 5xx ra thông báo tiếng Việt tương ứng. Lỗi không phải `ApiError` ra thông báo dự phòng.

### Tiêu chí chấp nhận

- [ ] Test của các file mới xanh. File mới sạch eslint, prettier, `vue-tsc`.
- [ ] Không chạm `ProfilePage.vue`, `useProfilePage.ts`, `http.ts`, `auth.store.ts`.
- [ ] Baseline Vitest không đổi (4 fail cũ).

### Rollback

Xóa các file mới (không có tham chiếu từ nơi nào khác).

---

## Slice 5b: Frontend, Giao Diện Panel Trong Trang Hồ Sơ

**Loại:** AFK (có bước xác minh trình duyệt bắt buộc) | **Chặn bởi:** Slice 5a và Slice 4 | **Cỡ:** vừa

### Mục tiêu

Panel thứ ba "Thông báo Telegram" trong `ProfilePage.vue`: liên kết, đổi, hủy, chờ, hết hạn, bị chặn. **Khi `enabled=false` panel không hiển thị** (K14) nên production không đổi gì cho tới Slice 7.

### Việc cần làm

1. `ProfilePage.vue`: panel full-width mới (`v-if` theo trạng thái bật), `Dialog` xác nhận hủy dùng slot `#footer`, đặt trong `.profile-page` nhưng ngoài `<section>`. Nút `disabled` kèm `title` thay vì ẩn (trừ trường hợp tắt cả panel). Thông báo lỗi `role="alert"`, thành công `role="status"`. Mở đường dẫn bằng `<a target="_blank" rel="noopener noreferrer">` (PrimeVue `Button` có prop `as`), có nút sao chép. Hiển thị `@username` và thời điểm liên kết (K15). Khi F5 mất đường dẫn: ghi hướng dẫn "Tạo đường dẫn mới để lấy lại đường dẫn". Khi bị đổi mã ở tab khác: hướng dẫn tạo lại. Chỉ thêm, không sửa hai panel cũ.
2. `_profile-page.scss`: `.profile-page__panel--wide { grid-column: 1 / -1 }`, các lớp panel, lớp dialog là **selector cấp cao nhất** (Dialog teleport ra `<body>`), mở rộng media 768px. Token `--app-*`, không hardcode màu. Không có chuỗi `<style` trong `.vue`.
3. `data-testid` theo mẫu `profile-telegram-<phần tử>`.
4. Test và E2E-A (K11).

### Thứ tự test (tracer trước)

1. **Tracer:** (`ProfilePage.spec.ts` mới, mock hai composable, stub `Dialog` có slot footer, stub `AdminLayout`) trạng thái chưa liên kết hiển thị nút "Liên kết Telegram", bấm thì gọi `startLinking`.
2. `enabled=false` thì panel không có trong DOM.
3. Trạng thái chờ: `href` bắt đầu bằng `https://t.me/` (assert qua `attributes('href')`, stub `Button` chỉ có prop `label`), có nút "Hủy yêu cầu".
4. Đang `linked` và đang chờ cùng lúc: hiển thị cả `@username` và khối chờ.
5. `role="alert"` khi lỗi. Mở dialog rồi bấm xác nhận gọi `confirmUnlink`.
6. **E2E-A** (`tests/e2e/profile-telegram.spec.ts`): đăng nhập thật (copy hàm `loginAsAdmin`, cần `E2E_ADMIN_EMAIL` và `E2E_ADMIN_PASSWORD`), `page.route` mock ba endpoint bằng biến trong closure. Hai kịch bản: liên kết lần đầu, và **đổi tài khoản** (đang liên kết thì cấp mã mới, mock đổi `linked_at`). Hủy qua dialog.

### Cách xác minh thật (bắt buộc, Rule 9, 11, 14)

Trình duyệt thật với backend và bot dev thật: light, dark, 390px; liên kết đầy đủ, đổi, hủy; F5 giữa chừng; focus lại; mở hai tab cấp mã; dialog hủy. Kiểm console và network không lỗi.

### Tiêu chí chấp nhận

- [ ] Liên kết, đổi, hủy chạy end-to-end với bot thật ở light, dark và 390px.
- [ ] Production không thấy panel khi `enabled=false` (kiểm bằng cách tắt cờ).
- [ ] `ProfilePage.vue` và `useProfilePage.ts` không có lỗi ESLint mới. File mới sạch eslint, prettier, `vue-tsc`. Không `prettier --write` file cũ.
- [ ] Baseline Vitest không đổi.
- [ ] Không `v-html`, không lưu đường dẫn liên kết vào `localStorage`/`sessionStorage`.

### Rollback

Hoàn nguyên phần chèn thêm trong `ProfilePage.vue` và `_profile-page.scss`, xóa file mới.

---

## Slice 5c: Mã QR (tùy chọn)

**Loại:** HITL (thêm dependency cần đồng ý) | **Chặn bởi:** Slice 5b | **Cỡ:** nhỏ

Chỉ làm nếu muốn quét bằng điện thoại thay vì mở đường dẫn trên máy tính.
- Thêm `uqr` (MIT, không có dependency, tree-shake được), nạp lười `import('uqr')`, tự vẽ `<path>` SVG (`utils/qr-path.ts` thuần, có test), không dùng `v-html`, không dùng dịch vụ QR ngoài (URL chứa mã dùng một lần).
- Thêm token `--app-qr-bg` (#ffffff) và `--app-qr-fg` (#000000) vào **cả hai** khối theme.
- Quy trình dependency: `npm install uqr`, commit `package.json` và `package-lock.json`, kiểm chunk tách riêng khi `npx vite build`, `make frontend-dependency-audit` (chưa chạy, kết quả chưa biết), cập nhật `memory-bank/techContext.md`.

Tiêu chí: quét được mã bằng điện thoại thật ở light và dark; audit không có lỗi mức cao.

---

## Slice 6a: Nhãn Audit Phía Giao Diện

**Loại:** AFK | **Chặn bởi:** Slice 4 | **Cỡ:** nhỏ

### Việc cần làm

- `api/audit-logs.mappers.ts`: thêm nhãn `telegram.link_requested`, `telegram.linked`, `telegram.link_rejected`, `telegram.unlinked`, và loại thực thể `telegram_account`, `telegram_link_token`.
- `AuditLogsPage.vue`: thêm vào hai mảng tùy chọn lọc hành động và loại thực thể.
- **Không sửa `actionSeverity`** (hàm nằm trong `.vue`, không export). Các sự kiện Telegram rơi vào mức mặc định `info`, chấp nhận.
- Test thêm vào `audit-logs.mappers.spec.ts`. Lưu ý `audit-logs.page.spec.ts` đã có 1 test fail baseline.

### Tiêu chí chấp nhận

- [ ] Nhật ký audit lọc được theo `telegram.*` và hiển thị nhãn tiếng Việt.
- [ ] Vitest baseline không đổi.

---

## Slice 6b: Vận Hành, Tài Liệu Bền Vững, Hồi Quy

**Loại:** AFK | **Chặn bởi:** Slice 5b và Slice 6a | **Cỡ:** vừa

### Việc cần làm

1. Runbook `docs/runbooks/deploy-vps-production.md`: bảng biến môi trường, sinh secret (`openssl rand -hex 32`), lệnh đăng ký webhook, thứ tự tắt khẩn cấp (xem Slice 7), hướng dẫn dev (tạo bot, nạp `.env`), K16 (xóa bảng Telegram sau khi khôi phục dump production vào dev), cách đổi qua lại giữa `webhook` và `polling` trong `.env` dev.
2. `scripts/compliance/check-production-readiness.sh` phải vẫn qua khi chưa có biến Telegram.
3. Tài liệu bền vững: `CONTEXT.md`, `memory-bank/systemPatterns.md` (webhook không JWT, runner dùng chung, quy tắc không lộ token, phân loại lỗi), `memory-bank/techContext.md`, `memory-bank/bugPatterns.md` nếu gặp lỗi, rồi `bash scripts/agent-task-close.sh --agent claude --title "Telegram 1A" --summary "..."`.
4. Hồi quy toàn bộ: pytest đầy đủ (kể cả lớp tích hợp nếu K18), ruff, mypy, bandit so với baseline; Vitest đầy đủ; `make docker-test-e2e` nếu không bị chặn bởi nợ lint/typecheck cũ (nếu bị chặn thì ghi "blocked", không chạy runner khác thay thế).

### Tiêu chí chấp nhận

- [ ] Một người khác làm theo runbook mà không phải hỏi lại.
- [ ] Số liệu baseline không xấu hơn (so với bảng ở Căn Cứ).
- [ ] Đã chạy `agent-task-close.sh`, `memory-bank` và `CONTEXT.md` được cập nhật.

---

## Slice 6c: E2E Toàn Bộ Với Fake Telegram (tùy chọn)

**Loại:** AFK | **Chặn bởi:** Slice 6b | **Cỡ:** vừa

`docker-compose.test.yml` service `backend-e2e` thêm `TELEGRAM_ENABLED=true`, `TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_API_BASE_URL` trỏ fake server; service `e2e-test` thêm `E2E_TELEGRAM_WEBHOOK_SECRET`. Test lấy mã từ `deep_link`, mô phỏng Telegram bằng `POST /api/v1/telegram/webhook` (dùng `telegram_user_id` ngẫu nhiên mỗi lần chạy vì khóa unique), mở `/profile` kỳ vọng "Đã liên kết", gọi `DELETE` để dọn.

---

## Slice 7: Triển Khai Production Và Bật

**Loại:** HITL (thao tác trên VPS) | **Chặn bởi:** Slice 6b | **Cỡ:** nhỏ

### Việc cần làm (theo runbook mục 9)

1. Tạo **bot production** bằng @BotFather (khác bot dev). Sinh `TELEGRAM_WEBHOOK_SECRET` bằng `openssl rand -hex 32`. Đặt `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `TELEGRAM_WEBHOOK_URL=https://quotify.honghafeed.com.vn/api/v1/telegram/webhook`, `TELEGRAM_MODE=webhook`, **`TELEGRAM_ENABLED=false`** vào `.env` trên VPS.
2. Backup (`scripts/ops/backup-postgres.sh`, `backup-minio.sh`), `git pull`, so `.env.production.example` với `.env`.
3. `docker compose -f docker-compose.prod.yml build backend frontend worker`.
4. `docker compose -f docker-compose.prod.yml run --rm backend uv run alembic upgrade head` **trước** khi tráo container, rồi `up -d`, rồi **`restart reverse-proxy`**.
5. Kiểm `/health`, `/ready`, đăng nhập, trang Hồ sơ cũ (avatar, đổi mật khẩu) vẫn hoạt động và **không thấy panel Telegram** (K14).
6. Kiểm lại đường vào từ ngoài (Slice 0, mục 3) vẫn đạt.
7. **Bật:** đặt `TELEGRAM_ENABLED=true`, `docker compose -f docker-compose.prod.yml up -d --force-recreate backend`, rồi **`restart reverse-proxy`** (tạo lại `backend` đổi IP nội bộ, không restart thì nginx giữ IP cũ và toàn site trả 502). Rồi: `run --rm backend uv run python scripts/telegram_webhook.py set --yes` (kiểm `@username` và URL in ra đúng), `... commands --yes`, `... info`.
8. Thử với **một** tài khoản: liên kết, nhắn `/help`, đổi, hủy. Xem nhật ký audit. **Sau khi có tin thật đi qua**, chạy `info` lại: kỳ vọng `pending_update_count` bằng 0 và không có `last_error_message` (chỉ kiểm sau tin thật mới chứng minh Telegram vào được, kiểm ngay sau `set` luôn "sạch").
9. Kiểm token bot không có trong log backend (`docker compose -f docker-compose.prod.yml logs backend`, dùng kiểm tra bằng biến môi trường như Slice 2, không `echo` token) và, nếu stack observability đang chạy, không có trong span ở collector.
10. Khi bật cờ, panel Telegram hiện cho **mọi** người dùng. "Nhóm thử" chỉ là quy ước thông báo nội bộ, không phải cơ chế kỹ thuật.

### Tiêu chí chấp nhận

- [ ] Webhook đăng ký được, `getWebhookInfo` sạch lỗi sau tin thật.
- [ ] Liên kết, đổi, hủy chạy trên production với một tài khoản thử, có audit.
- [ ] Mọi chức năng cũ không đổi. Production không thấy panel trước khi bật.
- [ ] Token bot không có trong log và span.

### Rollback (theo thứ tự, không đảo)

1. **`deleteWebhook` trước** (`run --rm backend uv run python scripts/telegram_webhook.py delete --yes`, lệnh này chỉ cần token, không cần cờ bật). Nếu tắt cờ trước thì backend trả 404, Telegram tiếp tục thử lại và dồn update trong 24 giờ.
2. Đặt `TELEGRAM_ENABLED=false`.
3. `up -d --force-recreate backend`, rồi **`restart reverse-proxy`**.
4. Schema giữ nguyên (additive, tương thích code cũ). Không `downgrade`.

---

## Thứ Tự Và Phụ Thuộc

```
S0 ─► S1 ─► S2 ─► S3a ─► S3b ─► S4 ─┬─► S6a ─┐
                   │               │        ├─► S6b ─► S7
                   └─► S5a ────────┴─► S5b ─┘
                                        │
                                        └─► S5c (tùy chọn)
                                S6b ─► S6c (tùy chọn)
```

S5a có thể bắt đầu sau S3a bằng mock (hợp đồng đã đóng băng), S5b cần S5a và S4. S6a chỉ cần S4. Mỗi slice merge riêng được và không làm hỏng build, test của repo. Production không đổi hành vi nhìn thấy được cho tới Slice 7: backend có thêm route nhưng cờ tắt trả 404, và panel ẩn khi `enabled=false` (K14).

## Ma Trận Kiểm Thử

| Lớp | Slice | Cách |
|---|---|---|
| Unit backend: client, logging, Settings | 1 | `MockTransport`, bắt log, `test_production_readiness` |
| Hành vi backend qua HTTP và request gửi đi | 2, 3a, 3b, 4 | Client thật trên `MockTransport`, `app.dependency_overrides`, đo request `sendMessage` ra |
| DB thật (nếu K18) | 2, 3a, 3b, 4 | Marker `integration`, `postgres-test` |
| Xác minh DB thật bằng tay | 2, 3a, 3b, 4 | `alembic` lên xuống, `psql`, `curl` |
| Telegram thật | 1 đến 4 | Bot dev, tài khoản thử |
| Unit frontend | 5a, 5b, 6a | Vitest (mapper, composable fake timers, trang) |
| E2E giao diện | 5b | Playwright E2E-A, mock mạng |
| Trình duyệt thật | 5b | Light, dark, 390px, F5, focus, hai tab |
| E2E toàn bộ | 6c (tùy chọn) | Fake Telegram |
| Production | 7 | `getWebhookInfo` sau tin thật, tài khoản thử, audit, kiểm log |

Test hiện có bị ảnh hưởng: `test_audit_log_service.py` (thêm test key mới), `test_production_readiness.py` (thêm test secret file), `audit-logs.mappers.spec.ts` (thêm nhãn). `test_permission_inventory.py` không đổi vì 1A không thêm permission.

## Rủi Ro Và Cách Giảm

| # | Rủi ro | Cách giảm | Slice |
|---|---|---|---|
| 1 | Token bot lộ qua log httpx, traceback chained, span OTel | Hạ log, scrub ở Formatter, loại URL khỏi OTel (suy host từ cấu hình), không `raise_for_status`, test và kiểm trực tiếp | 1 |
| 2 | Webhook non-2xx gây Telegram retry bão; nhưng nuốt lỗi hạ tầng làm mất update | K13: lỗi độc 200, lỗi hạ tầng tạm 503 không ghi dedupe | 2 |
| 3 | Body hỏng làm route trả 422 và lộ route khi tính năng tắt | Nhận `Request`, kiểm secret trước, parse thủ công | 2 |
| 4 | Poller xóa webhook production hoặc chạy sai bot | Từ chối khi `APP_ENV=production`, script in `@username` và URL rồi cần `--yes`, đối chiếu username với `getMe`, hai bot riêng | 2 |
| 5 | Poller crash loop trước migration, hoặc không dừng sạch | `depends_on` backend healthy, `exec` trong lệnh, đo thời gian dừng | 2 |
| 6 | Người lạ spam bot làm phình `telegram_processed_updates` và tốn lần gọi `sendMessage` | Hạn mức theo người dùng Telegram trước khi chạm DB, dọn dữ liệu K8 | 2, 4 |
| 7 | Một Telegram gắn hai người, race khi liên kết | Partial unique (K1), `FOR UPDATE`, savepoint bao cả thu hồi và chèn, phân biệt constraint | 3a, 3b |
| 8 | Đổi tài khoản làm mất liên kết cũ khi insert mới lỗi | Một savepoint, test tích hợp DB thật | 3b |
| 9 | Hai tab cấp mã cùng lúc để lại hai mã hợp lệ | Khóa dòng người dùng, vô hiệu mã cũ, mã mới thắng, giao diện nói rõ | 3a |
| 10 | Đường dẫn liên kết bị lộ trong 10 phút | K15: mã ngắn hạn dùng một lần, hiển thị `@username` và thời điểm, audit, xét bước xác nhận ở Giai đoạn 2 | 3b, 5b |
| 11 | Telegram bị khóa vĩnh viễn bởi người dùng đã nghỉ | Giải phóng chỗ khi chủ cũ không `ACTIVE`, `/stop` hướng dẫn trong tin nhắn | 4 |
| 12 | MissingGreenlet khi đọc timestamp sau commit | Gán timestamp bằng Python, `refresh`, verify bằng `curl` | 3a, 3b |
| 13 | Panel hiện trên production trước khi bật | K14: ẩn khi `enabled=false` | 5b |
| 14 | Đồng hồ máy khách lệch làm poll dừng sớm hoặc thừa | Thời hạn do server quyết định, đếm ngược bằng đồng hồ đơn điệu | 5a |
| 15 | Đường dẫn liên kết rò qua `localStorage` hay log | Chỉ giữ trong `ref`, chỉ có ở response `POST`, mapper kiểm tiền tố, không log nội dung update | 3a, 5a |
| 16 | Dialog teleport làm SCSS lồng không áp dụng | Lớp dialog là selector cấp cao nhất | 5b |
| 17 | Sửa file cũ phát sinh diff không liên quan | Chỉ chèn thêm, không `--write` file cũ, so baseline | tất cả |
| 18 | Hai migration song song tạo hai head, làm sập startup dev | `alembic heads` trước mỗi commit migration | 2, 3a |
| 19 | Giả định Telegram sai (409, bấm lại đường dẫn, chuỗi lỗi chặn) | Slice 0 kiểm chứng thực nghiệm, xử lý theo `error_code` | 0 |
| 20 | VPS không ra được `api.telegram.org` hoặc Telegram không vào được 443 | Kiểm cả hai chiều ngay ở Slice 0, kiểm lại ở Slice 7 | 0, 7 |
| 21 | Tạo lại `backend` không `restart reverse-proxy` làm toàn site 502 | Mọi lệnh `up -d --force-recreate backend` đi kèm `restart reverse-proxy`, kể cả rollback | 7 |
| 22 | Rollback tắt cờ trước khi `deleteWebhook` làm Telegram retry dồn update | Thứ tự rollback cố định: `deleteWebhook` rồi tắt cờ | 7 |
| 23 | Dump production khôi phục vào dev mang theo liên kết Telegram thật | K16: truncate bảng Telegram sau khi khôi phục | 6b |
| 24 | Mất tin trả lời do commit trước gửi (at-most-once) | Chấp nhận, ghi trong Nguyên tắc 5, người dùng thử lại | 2 |
| 25 | Xóa cứng người dùng làm `CASCADE` xóa lịch sử liên kết | Khuyến nghị vô hiệu hóa thay vì xóa (R7 của plan cha). Ghi nhận, không xử lý ở 1A | ghi chú |
| 26 | `ruff` đỏ che `mypy` và `bandit` trong `make docker-test-backend` | Chạy từng công cụ riêng cho file mới | tất cả |
| 27 | Giả định cách `backend-test` nối `postgres-test` chưa kiểm chứng | Xác minh ở Slice 2 trước khi viết test tích hợp, quyết định ở K18 | 2 |

## Phụ Lục A: Kết Quả Kiểm Chứng Thực Nghiệm (điền ở Slice 0)

| # | Nội dung | Kết quả | Ngày |
|---|---|---|---|
| T2 | `getUpdates` khi webhook bật trả gì (409?) | | |
| T3 | Bấm lại đường dẫn khi đã Start: có gửi lại `/start <param>` không (mobile, desktop, web). Param 64 và 65 ký tự | | |
| T5 | Chặn bot: mã và chuỗi lỗi `sendMessage`, `my_chat_member.new_chat_member.status` khi chặn và bỏ chặn | | |
| T5b | `sendMessage` tới ID chưa Start và ID bịa | | |
| T6 | 40 tin liên tiếp: có 429 không, `retry_after` bao nhiêu (cho 1B) | | |
| T7 | Text 4097 ký tự, `parse_mode=HTML` với `<` thô: lỗi gì (cho 1B) | | |
| T8 | `callback_data` 65 byte, chuỗi 33 ký tự tiếng Việt (cho 1B) | | |
| T9 | Giới hạn ảnh 10MB, caption 1025 ký tự (cho 1B) | | |
| T10 | Retry, timeout, cổng webhook (kiểm ở Slice 7) | | |
| Hạ tầng | Ra ngoài từ VPS, chứng chỉ, vào từ mạng ngoài, DNS A và AAAA, `prod.conf` đang dùng | | |
| K18 | Cách `backend-test` nối `postgres-test` | | |

## Phụ Lục B: Danh Sách File

**Tạo mới (backend):**
`alembic/versions/<ngày>_telegram_processed_updates.py`, `alembic/versions/<ngày>_create_telegram_link_tables.py`,
`app/models/telegram_processed_update.py`, `telegram_account.py`, `telegram_link_token.py`,
`app/schemas/telegram.py`, `app/integrations/telegram.py`,
`app/services/telegram_update_service.py`, `app/services/telegram_update_runner.py`, `app/services/telegram_link_service.py`,
`app/api/v1/telegram.py` (webhook), `app/api/v1/telegram_link.py` (`/users/me/telegram*`),
`app/telegram_poller.py`, `scripts/telegram_webhook.py`.
Test: `test_telegram_client.py`, `test_telegram_webhook_api.py`, `test_telegram_update_service.py`, `test_telegram_poller.py`, `test_telegram_link_api.py`, `test_telegram_link_service.py`, `test_logging_redaction.py` (gồm cả test hàm loại trừ OTel). Nếu K18: các file trong lớp `integration` và fixture DB.

**Sửa tối thiểu (backend và hạ tầng):**
`app/api/v1/router.py`, `app/models/__init__.py`, `app/db/base.py`, `app/core/config.py`, `app/core/logging.py`, `app/core/observability.py`, `app/services/audit_log.py`, `tests/test_audit_log_service.py`, `tests/test_production_readiness.py`, `.env.example`, `.env.production.example`, `docker-compose.yml`, `docs/runbooks/deploy-vps-production.md`. Nếu K18: `pyproject.toml` (đăng ký marker), `docker-compose.test.yml`.

**Tạo mới (frontend):**
`src/types/telegram.ts`, `src/api/telegram.api.ts`, `src/api/telegram.mappers.ts`, `src/composables/useTelegramLink.ts`,
`tests/unit/telegram.mappers.spec.ts`, `tests/unit/useTelegramLink.spec.ts`, `tests/unit/ProfilePage.spec.ts`, `tests/e2e/profile-telegram.spec.ts`.
Chỉ nếu làm QR: `src/utils/qr-path.ts`, `tests/unit/qr-path.spec.ts`.

**Sửa tối thiểu (frontend):**
`src/pages/ProfilePage.vue`, `src/styles/pages/_profile-page.scss`, `src/api/audit-logs.mappers.ts`, `src/pages/AuditLogsPage.vue`, `tests/unit/audit-logs.mappers.spec.ts`. Chỉ nếu làm QR: `src/styles/tokens/theme.scss`, `package.json`, `package-lock.json`.

**Không đụng:** `app/models/user.py`, `app/api/v1/users.py`, `app/worker.py`, `app/auth/seed_data.py`, `docker-compose.prod.yml`, `docker/nginx/prod.conf`, `backend/pyproject.toml` (trừ marker nếu K18), `uv.lock`, `useProfilePage.ts`, `http.ts`, `auth.store.ts`, hàm `actionSeverity`.

**Tài liệu bền vững:** `CONTEXT.md`, `docs/quotify/Requirements.txt`, `docs/quotify/quotify-implementation-plan.md`, tài liệu cha, `memory-bank/*`, `.agent-memory` (qua `agent-task-close.sh`).
