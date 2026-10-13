# Kế Hoạch Triển Khai Chatbot, Mục 5.1: Kiến Trúc Đường Ống Bot

## Trạng Thái

**ĐÃ CHỐT CÁC ĐIỂM CẦN QUYẾT (2026-10-13, bản 8, sau rà soát độc lập). S0, S1 VÀ S2 ĐÃ XONG trên nhánh `feat/telegram-chatbot` (chưa merge vào `main`); S0 và S1 bạn đã xác nhận trên Telegram thật.** Chưa có dòng code nào. Các điểm "đã quyết theo bằng chứng" ở mục 9 chưa gặp phản đối nhưng chưa được xác nhận riêng. Cơ sở: commit `7eb64e9` trên `main`, cây git sạch, Alembic head `20261007_0900`.

Kế hoạch này là phần triển khai chi tiết của **mục 5.1** (và phần hạ tầng của Giai đoạn 2A) trong [plan-telegram-bien-dong-gia-va-chatbot-ai.md](plan-telegram-bien-dong-gia-va-chatbot-ai.md). Nó chỉ xây **đường ống**: nhận tin, xếp hàng, xử lý ở worker riêng, trả lời. Phần "bộ não" (LLM, công cụ, bộ nhớ, ngân sách) cắm vào đường ống qua một cổng duy nhất (`ChatEngine`, mục 4.6) và thuộc các kế hoạch riêng của 5.2 đến 5.6.

Cách soạn:
- Local skill `to-issues`: chia lát cắt dọc (tracer bullet), mỗi lát có loại **HITL/AFK**, "chặn bởi" và tiêu chí chấp nhận. Không đăng issue lên tracker nào.
- Local skill `tdd`: trong mỗi lát, test đầu tiên là tracer bullet đi hết đường, rồi mới tới từng hành vi, một test một đoạn code. Test đo hành vi qua giao diện công khai (webhook vào, request Telegram ra, trạng thái DB), chỉ giả lập ranh giới hệ thống (Telegram, Redis, LLM).
- Local agent: 4 agent Explore chỉ đọc chạy song song ngày 2026-10-13 (luồng webhook và update; worker, Redis, compose; service, DB, quyền; lịch sử bug và memory-bank), cộng ba điểm tôi tự kiểm trực tiếp (ngữ nghĩa `_job_id` của arq, `parse_mode=None` của client Telegram, khối `worker` trong compose production). Sau đó **một agent rà soát độc lập** kiểm lại trích dẫn, tấn công thiết kế và chạy thực nghiệm; kết quả và các sửa đổi đã áp dụng ở mục 12 và Phụ lục A.

Quy ước: `KT1` đến `KT21` là quyết định kiến trúc (mục 5). `RC-1` đến `RC-29` là rủi ro (mục 8). `S0` đến `S10` là lát cắt (mục 6). Mục nào chưa kiểm chứng ghi **[CHƯA XÁC MINH]**.

---

## 1. Phạm Vi

**Làm trong kế hoạch này:**
- Chuyển tin nhắn văn bản thường của người đã liên kết từ xử lý trong request webhook sang hàng đợi bền vững và worker riêng.
- Hộp thư `bot_updates` trong Postgres làm nguồn sự thật: không mất tin khi Redis hoặc worker lỗi, mỗi chat xử lý tuần tự, mỗi lần thử gọi engine tối đa một lần, trả lời không trùng lặp quá mức.
- Cổng `ChatEngine`, ngữ cảnh người dùng `BotPrincipal` (kiểm quyền), engine DB chỉ đọc có `statement_timeout`.
- Đường gửi trả lời: chia tin dài, chỉ báo "đang gõ", xử lý 429 và 403.
- Cổng bật dần (cờ env và danh sách người dùng thử), công tắc tắt khẩn cấp.
- **Hạn mức sử dụng mỗi người mỗi ngày** (lượt hỏi và lượt dùng file, mục 4.11): cổng thực thi trong đường ống, giá trị cấu hình được. Phần đếm token và trang quản trị hạn mức theo từng người thuộc 5.5 và 5.6.
- Quan sát, cấu hình, compose dev/prod/test, runbook, triển khai production với cờ tắt.
- Một `StubChatEngine` (trả câu cố định) để chứng minh đường ống chạy đủ từ đầu đến cuối.

**Không làm (có kế hoạch riêng):**
- `LLMClient` và adapter nhà cung cấp (5.5), ngân sách và chi phí (5.6), đếm token theo người dùng và trang cấu hình hạn mức theo từng người (5.6), công cụ chỉ đọc (5.2), bộ nhớ hội thoại và `/reset` (5.4), nhập liệu và ghi dữ liệu (5.3), ảnh và PDF (2C).
- Bước xác nhận trong chat khi liên kết (K15): chỉ chặn việc **ghi** dữ liệu ở 2B, không chặn đường ống chỉ đọc này (xem RC-14).
- Sửa `create_job_queue` rò pool Redis ở luồng import/backup. Ghi là nợ, không sửa lan.
- Bộ giới hạn tốc độ Redis (KT15). Chấp nhận câu hỏi gõ không dấu (thuộc 5.2, khớp tên vật tư).

---

## 2. Hiện Trạng Đã Xác Minh Từ Code

Đường dẫn tính từ `backend/` trừ khi ghi khác. "Agent" nghĩa là do agent đọc code và báo cáo; "tự kiểm" là tôi đọc trực tiếp; "reviewer" là agent rà soát độc lập đã đối chiếu lại.

| Chủ đề | Thực tế | Bằng chứng |
|---|---|---|
| Webhook xử lý **trong request** | `await runner.process(payload)`, không có hàng đợi hay `BackgroundTasks`. Tin thường **không có deadline**; chỉ nút bấm có `asyncio.wait_for` 4,0 giây. nginx không đặt `proxy_read_timeout` (mặc định 60 giây, suy luận) | `app/api/v1/telegram.py:82`, `app/services/telegram_update_runner.py:35,122-157,171-173`, `docker/nginx/prod.conf:43-51` (agent, reviewer đã đối chiếu) |
| Dedupe cùng giao dịch với xử lý | `_record_update` là dòng đầu của `handle()`; runner commit sau `handle()`, lỗi hạ tầng thì rollback (kéo theo dòng dedupe) và webhook trả 503 để Telegram gửi lại; update "độc" ghi dedupe riêng rồi báo lỗi; tin trả lời gửi **sau** commit (at-most-once) | `app/services/telegram_update_service.py:219,447-456`, `telegram_update_runner.py:194-239` (agent, reviewer) |
| Phân loại update | `parse_update` chỉ đọc `message` (chỉ `text`), `my_chat_member`, `callback_query`; `edited_message` nằm ngoài `ALLOWED_UPDATES`. Chỉ chat `private`. `/start <mã>` đi trước kiểm tra user `ACTIVE`. **Mọi thứ còn lại, kể cả văn bản thường của người đã liên kết lẫn chưa liên kết, trả `UNKNOWN_TEXT`** (chỉ `/start` trần mới có hướng dẫn). Ảnh, tài liệu, giọng nói chưa có xử lý | `telegram_update_service.py:127,230,235-263`, `app/integrations/telegram.py:16` (agent, reviewer) |
| Client Telegram | Có `send_message`, `send_photo`, `answer_callback_query`, `edit_*`, `set_webhook` (không đặt `max_connections`, mặc định Telegram là 40), `get_updates`. **Không có** `sendChatAction`, `getFile`, tách tin dài (quá 4096 ký tự thì ném `TelegramMessageTooLongError`). `parse_mode` nhận `None` (tự kiểm). Không tự retry; lỗi 429 mang `retry_after`, lỗi 403 có lớp riêng. Mỗi lời gọi HTTP có timeout 10 giây | `app/integrations/telegram.py:13,125-150,281-297,384-403`, `app/core/config.py:171` (tự kiểm, agent, reviewer) |
| Poller dev | Xử lý **tuần tự** từng update bằng cùng `runner.process`; từ chối chạy khi `APP_ENV=production` | `app/telegram_poller.py:38,122,150` (agent, reviewer) |
| Worker hiện có | Một `WorkerSettings`, 12 mục `functions` (5 tác vụ nghiệp vụ và 7 coroutine cron). **Bỏ qua `REDIS_URL`** (chỉ dùng host và port). Không đặt `max_jobs`, `job_timeout`, `queue_name`, `max_tries`, nên chạy theo mặc định arq 0.26.3: 10 slot, timeout 300 giây, 5 lần thử, hàng đợi `arq:queue`. `timezone` đã đặt theo `APP_TIMEZONE`. Worker **không phơi metric** | `app/worker.py:169-192,1181-1212`, `.venv/.../arq/worker.py:190-212` (agent, reviewer) |
| Pool Redis | `create_job_queue` mở pool mới mỗi lần gọi và không đóng; `BackupAdminService` gọi `_create_pool` trực tiếp, cùng lỗi. Không có pool chung trên `app.state`. `arq.create_pool` thử kết nối 5 lần cách 1 giây rồi ném lỗi | `app/services/job_admin.py:36-60`, `app/services/backup_admin.py:102-109`, `arq/connections.py` (agent, reviewer) |
| Khóa và giới hạn tốc độ | **Không có khóa Redis nào.** Mọi loại trừ hiện dùng Postgres: advisory lock theo giao dịch (nhả khi commit), `FOR UPDATE` (kể cả `SKIP LOCKED` ở `price_alert_sender.py:167`, `worker.py:980`), `lease_until` ở bộ gửi tin. Giới hạn tốc độ: `InMemoryRateLimiter` (theo IP) và `TelegramUserRateLimiter` trong runner (10 tin/60 giây, 30 nút/60 giây, theo từng tiến trình) | `app/services/price_alert_scan.py:50-51,111-113`, `app/core/rate_limit.py:25-61`, `telegram_update_runner.py:46-118` (agent, reviewer) |
| Arq: `_job_id` và kill | `enqueue_job` trả `None` khi đã tồn tại **khóa job hoặc khóa kết quả** cùng `_job_id`. **Đã đo ở S0(b)** (Docker, Python 3.12, arq 0.26.3, Redis 7): `keep_result=0` cho dùng lại id ngay sau khi job xong (kể cả job lỗi), còn mặc định 3600 giây thì id bị chặn 1 giờ; sau `SIGKILL` khóa "đang chạy" hết hạn ở `job_timeout + 10` giây **tính từ lúc job bắt đầu** và chỉ khi có worker sống dọn thì job mồ côi mới bị báo "max retries exceeded" (hàm không chạy lại), còn không có worker nào chạy thì cùng id bị chặn đến 24 giờ; `SIGTERM` cho hàm nhận `CancelledError` và chạy xong khối dọn, nhưng khóa "đang chạy" của arq bị xóa còn khóa job thành mồ côi (hàm cũng không chạy lại khi worker khởi động); `retry_jobs=False` loại bỏ mồ côi đó | `.venv/.../arq/connections.py:119-180`, `arq/worker.py:74-77,201,269-270`; thực nghiệm S0(b), Phụ lục A.2 (agent chạy, chưa được tôi tái lập) |
| DB | Một engine lười, chỉ `pool_pre_ping=True`, mặc định `pool_size=5, max_overflow=10`. **Chưa có** sessionmaker chỉ đọc hay `statement_timeout`. SQLAlchemy 2.0.50, asyncpg 0.31.0. Dialect hỗ trợ `postgresql_readonly` và **chạy được dưới READ COMMITTED** (đo ở S0(a); cảnh báo trong tài liệu SQLAlchemy rằng asyncpg chỉ hỗ trợ `readonly` với SERIALIZABLE là lỗi thời), nhưng tùy chọn này **chỉ đặt được trước khi kết nối bắt đầu giao dịch** | `app/db/session.py:17-36`, `sqlalchemy/dialects/postgresql/base.py:227-228,3195-3289`, `asyncpg.py:841-847,1118-1122` (agent, reviewer) |
| Quyền | Service **không** import `HTTPException`; chỉ `api/v1/*` và `auth/dependencies.py` làm vậy. `has_permission(user, code)` là hàm đồng bộ thuần (admin bypass theo tên role) nhưng cần `roles -> permissions` đã nạp. `AuthService.get_active_user(user_id=...)` nạp đủ và trả `None` nếu không `ACTIVE`; đã có tiền lệ dùng ngoài HTTP | `app/auth/permissions.py:21-33`, `app/auth/service.py:139-149`, `app/services/price_alert_review_service.py:66-67` (agent, reviewer) |
| Liên kết | `touch_linked_identity` nối `users`, gồm cả liên kết `blocked`, và **chuyển `blocked` về `active` khi có tin mới**; kết quả không có email người dùng | `app/services/telegram_link_service.py:181,212` (agent, reviewer) |
| Audit ngoài HTTP | `AuditLogContext` dựng được bằng constructor, không cần `Request`; worker và Telegram đã làm vậy (`request_id=f"tg-update-{update_id}"`, `channel=telegram`) | `app/services/audit_log.py:132-167`, `app/worker.py:148-166`, `telegram_update_service.py:387-408,436-446` (agent, reviewer) |
| Hạ tầng triển khai | Compose không có `restart:`, giới hạn bộ nhớ hay CPU. Production chạy **một** tiến trình uvicorn. Redis là `redis:7-alpine` không mật khẩu, có volume `/data` (snapshot mặc định, có thể cũ), không công bố cổng. Service `worker` có khối `build:` riêng (cùng Dockerfile, target `prod`), không có `image:`. Poller chỉ có ở dev (profile `telegram`). `docker compose build <svc>` **có build** service nằm trong profile không kích hoạt khi gọi đích danh, còn `up` thì bỏ qua (reviewer đã thử) | `docker-compose.prod.yml:148-181`, `docker-compose.yml:143-197` (tự kiểm, agent, reviewer) |
| Script kiểm sẵn sàng | `check-production-readiness.sh` không kiểm tên service. `check-price-alert-readiness.sh` bắt buộc các tiêu đề runbook `## 13.` đến `## 15.` đúng nguyên văn, nên **không đánh số lại**, phần bot thêm thành mục 16 | `scripts/compliance/check-price-alert-readiness.sh:26-28` (agent, reviewer) |
| Phụ thuộc | Chưa có SDK LLM, `pypdf`. Pillow chỉ là phụ thuộc gián tiếp của matplotlib (image đã tăng khoảng 130 MB vì matplotlib). `.venv` cục bộ chạy Python 3.14, và CLI `arq` cục bộ lỗi `get_event_loop` ở đó; image Docker là Python 3.12 | `pyproject.toml`, `uv.lock`, `docs/runbooks/deploy-vps-production.md:843` (agent, reviewer) |
| Đã có sẵn dùng lại | `get_daily_min_series` (Slice 2 của 1B), `QuoteQueryService`, `MaterialAdminService`, `QuotifyDashboardService`, `SupplierAdminService`, `PriceAlertEvent`. Chưa có bảng hay model chatbot, chưa có `created_via`, chưa có khóa cấu hình `CHATBOT_*` hay `LLM_*` | `app/services/daily_min_series.py:23`, `app/models/price_alert.py:404` (agent, reviewer) |
| Production đã nói chuyện với Telegram | Gửi và nhận webhook chạy từ 2026-10-04. Điểm "[CHƯA XÁC MINH] VPS ra được `api.telegram.org`" của tài liệu cha **đã lỗi thời**. VPS **không** ra được Docker Hub (cần `mirror.gcr.io`), nên khả năng ra endpoint của nhà cung cấp LLM vẫn chưa biết | `memory-bank/progress.md:239,266,290` (agent) |

**Mốc so sánh hồi quy** (đã chạy lại ở S0(f), 2026-10-13, HEAD `7eb64e9`; số liệu do agent đo, chưa được tôi tái lập; lệnh tái hiện ở Phụ lục A.2): pytest 1.281 pass, 6 fail, 1 skip, trong đó **6 test fail là âm tính giả** vì đọc file ngoài `backend/` mà image test không có (trên máy host cả 6 đều qua); tầng integration 428 test chạy và qua; ruff 62; `mypy app` 15 (`mypy .` bị dừng vì trùng tên module `conftest`); bandit 17; vitest 464 pass và đúng 4 lỗi cũ; ESLint 69; vue-tsc 0; Prettier 86 file; e2e Docker 9 pass và 31 fail (4 lỗi cũ cộng 27 lỗi do 6 spec 1C và 1D gắn cứng `http://127.0.0.1:4173`). Nhiều con số khác với ghi chép trong `memory-bank/`, nên **mốc để so sánh là bảng ở Phụ lục A.2**, không phải các con số cũ (RC-26).

---

## 3. Lệch Với Tài Liệu Cha

| # | Tài liệu cha nói | Thực tế | Xử lý trong kế hoạch này |
|---|---|---|---|
| 1 | 5.1: webhook "enqueue arq (queue riêng `bot`)" | Webhook hiện xử lý trong request, chưa có đường tới arq | Xây hand-off mới, chỉ cho tin văn bản thường (KT1) |
| 2 | 5.1 dòng 763: rủi ro "ghi `update_id` trước khi đưa vào hàng đợi mà Redis lỗi thì update bị mất" | Hiện **chưa tồn tại** vì chưa có hàng đợi. Rủi ro này xuất hiện đúng lúc ta thêm hand-off | Hộp thư cùng giao dịch với dedupe, chuông ngoài giao dịch (KT2, KT3) |
| 3 | `command: arq app.worker.BotWorkerSettings` | `app/worker.py` đã hơn 1.200 dòng, test ghim `WorkerSettings`, và từng có sự cố import vòng sau deploy 1D (`progress.md:290`) | Module riêng `app/bot_worker.py` (KT6) |
| 4 | "Redis lock theo chat" | Repo chưa có khóa Redis nào. Khóa Redis không đảm bảo thứ tự (job của update 2 có thể chạy trước update 1 đang chờ) và cần gia hạn khi LLM chậm | Đảm bảo thứ tự bằng claim trong Postgres (KT4) |
| 5 | "Dùng một pool Redis chung" | Đúng là chưa có. `create_job_queue` rò pool ở luồng cũ | Pool chung chỉ cho bên gửi mới, tạo lười (KT7); luồng cũ để nguyên, ghi nợ |
| 6 | 5.4: "giới hạn theo người dùng bằng Redis" | Chưa có bộ giới hạn Redis; runner đã có giới hạn bộ nhớ theo Telegram user | Giữ giới hạn hiện có, thêm trần số tin chờ mỗi chat (KT15). **Hạn mức lượt và file mỗi ngày thực thi ngay ở đường ống bằng DB** (mục 4.11); hạn mức token do 5.6 bổ sung |
| 7 | 5.2, bảng công cụ: `get_price_alerts` cần `dashboard.read` | Route duy nhất đọc cảnh báo (anomalies) cần **`price_alerts.receive_all`**, và chỉ trả `kind='anomaly'`; **chưa có** service đọc `kind='change'` | Đầu vào cho kế hoạch 5.2 |
| 8 | 5.2: `compare_suppliers` gọi `QuoteQueryService` | Không có hàm so sánh hay gộp theo NCC; truy vấn phẳng trả mọi dòng, cùng NCC có thể lặp. Tool tra NCC cần `suppliers.read`, không có trong bảng | Đầu vào cho 5.2 |
| 9 | 5.2: `weekly_entry_activity` và "không có tool nào đọc `users`" | `get_weekly_entry_activity` trả email và họ tên của mọi người dùng đang hoạt động (PII) | Đầu vào cho 5.2: bọc lại hoặc bỏ trường PII |
| 10 | 5.2: `get_daily_min_series` là "hàm mới" | Đã có từ Slice 2 của 1B | Chỉ cần tái dùng |
| 11 | 5.4: "không ghi nội dung hội thoại vào audit" | `content` nằm trong `ALLOWED_AUDIT_METADATA_KEYS`; khóa chứa `session`/`token` luôn bị che (`chat_session_id`, `tokens_in` sẽ thành `[REDACTED]`) | Không audit từng câu hỏi (KT14); đặt tên khóa tránh `session|token` |
| 12 | 5.1: poller và webhook cùng một hàm xử lý | Đúng, nhưng poller tuần tự, nên một lần gọi LLM chậm sẽ chặn mọi update sau | Hand-off sửa luôn việc này: poller chỉ ghi hộp thư và đánh chuông (cần nối `BotDispatcher` vào poller, `telegram_poller.py:150`) |
| 13 | 5.6: một cột `chatbot_settings.daily_user_limit` (mặc định 20), kiểm bằng Redis | Chưa có bảng nào. Một số duy nhất không phân biệt câu hỏi chữ với đọc file và với chi phí token thật; không có ngoại lệ theo từng người | Tách ba hạn mức (lượt, file, token) kèm ghi đè theo từng người; đếm bằng DB (mục 4.11, KT19 đến KT21). Cần sửa bảng `chatbot_settings` ở 5.6 theo mục 4.11 |

---

## 4. Kiến Trúc Đề Xuất

### 4.1 Nguyên tắc

1. **Postgres là sự thật, arq chỉ là cái chuông.** Mọi trạng thái bền (tin nào đang chờ, đang xử lý, đã trả lời) nằm ở bảng `bot_updates`. Hàng đợi arq chỉ để đánh thức worker. Mất Redis, mất hàng đợi, worker chết giữa chừng: đều **không làm mất tin**, vì một cron quét lại từ DB.
2. **Không đổi hành vi hiện có khi cờ tắt.** Hand-off chỉ áp dụng cho văn bản thường của người đã liên kết (và nằm trong danh sách người dùng thử, nếu có), khi `CHATBOT_ENABLED=true`. Lệnh, nút bấm, `my_chat_member`, liên kết, `/stop` giữ nguyên đường inline và deadline cũ.
3. **Mỗi chat xử lý tuần tự.** Hai tin "giá ngô" rồi "còn tháng 12 thì sao?" gửi liền nhau được trả lời lần lượt, mỗi tin thấy kết quả của tin trước. Thứ tự là theo `update_id` **trong khả năng**: Telegram có thể giao tin lệch thứ tự (xem RC-17), nên bất biến cứng là "mỗi chat một dòng đang chạy tại một thời điểm", còn thứ tự là nỗ lực tốt nhất.
4. **Mỗi lần thử gọi engine tối đa một lần; tối đa `BOT_MAX_ATTEMPTS` lần thử.** Câu trả lời được lưu **trước khi** gửi, nên gửi lỗi thì gửi lại câu đã lưu, không gọi engine lần hai. Engine chỉ được gọi lại khi lần thử trước **chưa lưu được câu trả lời** (lỗi tạm thời của engine, worker chết, lease hết hạn). Chi phí LLM của 5.6 phải đếm theo **từng lần thử**, không theo từng update.
5. **Không giữ kết nối DB suốt lúc gọi LLM.** Chỉ dùng các giao dịch ngắn để claim, lưu, hoàn tất.
6. **Cổng hẹp cho phần bộ não.** 5.2 đến 5.6 chỉ cần cài `ChatEngine`, không đụng hàng đợi, khóa, gửi tin.
7. **Chỉ thêm, không sửa.** Một bảng mới, một module worker mới, một service compose mới. Phần sửa ở code cũ giới hạn ở mục 10.
8. **Mọi ghi kết quả đều có "rào chắn".** Worker chỉ được lưu, hoàn tất hay thất bại một dòng khi dòng đó vẫn thuộc về nó (`status='processing'` và đúng số lần thử); không thì bỏ qua lặng lẽ (KT16).

### 4.2 Sơ đồ

```
Telegram ─► POST /api/v1/telegram/webhook ─► kiểm secret ─► TelegramUpdateRunner.process
                                        │   (MỘT giao dịch)
                                        │   1. dedupe update_id                         (như cũ)
                                        │   2. lệnh, nút bấm, my_chat_member ─► INLINE  (như cũ)
                                        │   3. văn bản thường của người đã liên kết
                                        │        và CHATBOT_ENABLED (và trong danh sách thử)
                                        │        ─► INSERT bot_updates (status=queued)
                                        ▼ COMMIT (lỗi vẫn là 503, Telegram gửi lại như cũ)
                              BotDispatcher.notify(chat_id, update_id)  (sau commit, giới hạn 2 giây,
                                        │                                  lỗi chỉ ghi log)
                                        │  arq: queue "quotify:bot", _job_id="bot:<update_id>"
                                        ▼
          ┌──────────────────  bot-worker  (BotWorkerSettings)  ──────────────────┐
          │ drain_chat(chat_id)  lặp đến hết hàng hoặc hết ngân sách thời gian:     │
          │   1. claim đầu hàng đợi của chat          [giao dịch ngắn, lease]       │
          │   2. nạp BotPrincipal (user ACTIVE + quyền), liên kết còn hiệu lực      │
          │   3. cổng hạn mức UsageGate (lượt, file, token mỗi ngày)                │
          │   4. ChatEngine.reply(turn)               ◄─ cổng cắm của 5.2 đến 5.6   │
          │   5. lưu reply_text, reply_saved_at       [giao dịch ngắn, có rào chắn] │
          │   6. kiểm lần cuối rồi gửi Telegram (chia tin, "đang gõ", 429, 403)     │
          │   7. complete: status=replied, xóa payload và reply                     │
          │                                                                          │
          │ sweep_bot_updates (cron 30 giây): chỉ đánh chuông cho chat có việc chờ   │
          │ cleanup_bot_updates (cron ngày): xóa dòng cũ                             │
          └──────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Phân loại update

| Update | Đường xử lý | Lý do |
|---|---|---|
| `callback_query` (nút duyệt giá) | **Inline**, deadline 4 giây | `answerCallbackQuery` hết hạn khoảng 15 giây; hành vi 1B không được đổi |
| `my_chat_member` | Inline | Chỉ đổi trạng thái liên kết, nhanh |
| `/start`, `/stop`, `/help`, `/limit`, lệnh lạ | Inline | Chỉ DB, nhanh; `/start <mã>` phải đi trước kiểm tra `ACTIVE` (đã có). Chấp nhận việc phản hồi của lệnh có thể **vượt trước** câu trả lời đang chờ trong hàng |
| Văn bản thường, người đã liên kết, cờ bật, trong danh sách thử (hoặc danh sách trống) | **Hand-off** (ghi hộp thư) | Có thể gọi LLM hàng chục giây |
| Văn bản thường, cờ tắt hoặc ngoài danh sách thử | `UNKNOWN_TEXT` như hiện nay | Không đổi hành vi |
| Văn bản thường, chưa liên kết | `UNKNOWN_TEXT` như hiện nay (chỉ `/start` trần có hướng dẫn) | Không có người dùng để kiểm quyền; không đổi hành vi |
| Ảnh, tài liệu, giọng nói, sticker (cờ bật, người dùng đủ điều kiện) | Inline, trả câu cố định "hiện chỉ đọc được tin nhắn văn bản" | 2C mới xử lý file |
| `edited_message` | Không nhận (ngoài `ALLOWED_UPDATES`) | Như hiện nay |
| Chat không `private` | Bỏ qua | Như hiện nay |

### 4.4 Hộp thư `bot_updates`

Migration additive, một bảng mới. Mọi mốc thời gian là `timestamptz`. Câu lệnh claim, lưu, hoàn tất nhận **`now` là tham số được truyền vào** (mặc định lấy từ đồng hồ UTC của worker; các container cùng một máy chủ nên lệch đồng hồ không đáng kể, suy luận), để test điều khiển được thời gian như tiền lệ ở `price_alert_sender.py`. `now` và mọi mốc thời gian đưa vào truy vấn **phải có múi giờ** (`datetime` có `tzinfo`): asyncpg coi `datetime` không múi giờ là giờ địa phương của tiến trình (S0(c): với `TZ=America/New_York`, 12:00 không múi giờ bị lưu thành 16:00Z).

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `update_id` | `BIGINT` PK | Cùng giá trị với `telegram_processed_updates.update_id`. Giữ bảng riêng để không trộn vai trò: bảng dedupe bị dọn sau 3 ngày |
| `chat_id` | `BIGINT NOT NULL` | |
| `telegram_user_id` | `BIGINT NOT NULL` | Dùng để kiểm liên kết còn hiệu lực mỗi lần claim |
| `user_id` | `UUID NOT NULL`, FK `users` `ON DELETE CASCADE` | Ghi rõ `ON DELETE` (RR-7). Xóa người dùng thì xóa luôn dữ liệu hội thoại tạm của họ (worker phải chịu được việc dòng biến mất giữa chừng nhờ rào chắn ở KT16) |
| `kind` | `VARCHAR(12) NOT NULL DEFAULT 'text'`, CHECK | Mở rộng `photo`, `document` ở 2C |
| `status` | `VARCHAR(12) NOT NULL`, CHECK | `queued`, `processing`, `replied`, `failed`, `dropped` |
| `payload_text` | `TEXT NULL` | Tối đa 4096 ký tự. **Xóa khi dòng vào trạng thái kết thúc** (mọi trạng thái kết thúc, kể cả `failed` và `dropped`) |
| `reply_text` | `TEXT NULL` | Đặt trước khi gửi. Xóa khi kết thúc |
| `sent_parts` | `SMALLINT NOT NULL DEFAULT 0` | Số phần đã gửi của câu trả lời nhiều phần, để gửi lại không lặp phần đầu |
| `attempts` | `SMALLINT NOT NULL DEFAULT 0` | Tăng mỗi lần claim; cũng là "mã rào chắn" của lần claim đó |
| `lease_until` | `TIMESTAMPTZ NULL` | Với dòng `processing`: hạn của lease. Với dòng `queued` đang chờ thử lại: "không sớm hơn" (backoff) |
| `error_category` | `VARCHAR(40) NULL` | Danh mục cố định (`engine_error`, `engine_timeout`, `send_failed`, `forbidden`, `unlinked`, `user_inactive`, `expired`, `lease_exhausted`, `quota_exceeded`), **không** lưu nguyên văn ngoại lệ |
| `reply_saved_at` | `TIMESTAMPTZ NULL` | Đặt khi lưu câu trả lời của engine (cùng câu lệnh có rào chắn). Là cơ sở đếm lượt đã tiêu tốn engine để tính hạn mức (mục 4.11) |
| `received_at`, `started_at`, `finished_at` | `timestamptz` | `received_at` mặc định `now()` |

Chỉ mục: `ix_bot_updates_chat_open (chat_id, update_id) WHERE status IN ('queued','processing')` (claim) `ix_bot_updates_status_received (status, received_at)` (cron quét và metric), và `ix_bot_updates_user_received (user_id, received_at)` (đếm hạn mức mỗi ngày).

Máy trạng thái:

```
queued ──claim──► processing ──complete──► replied
   ▲                  │
   │  lỗi tạm thời    ├── lease hết hạn ──► (claim lại, attempts + 1) ──► processing ...
   └── (backoff) ─────┤
                      ├──► failed   (lỗi cuối của engine, hoặc attempts đạt trần; gửi một câu xin lỗi)
queued/processing ───►│──► dropped  (người dùng không ACTIVE, liên kết hủy hoặc bị chặn, tin quá cũ)
```

Trạng thái kết thúc là `replied`, `failed`, `dropped`.

### 4.5 Vòng xử lý một chat

**Claim (một giao dịch ngắn, thuật toán cố định, đã chạy thật ở S0(c)).** Mọi mốc thời gian là tham số **có múi giờ**.
1. Lấy advisory lock theo giao dịch của chat: `SELECT pg_advisory_xact_lock(hashtextextended('bot:chat:' || CAST(:chat_id AS BIGINT), 0))`. **Phải ép kiểu `CAST(:chat_id AS BIGINT)`**: với asyncpg, nối chuỗi với số nguyên đã bind báo `DataError: expected str, got int`, còn `:c::text` là lỗi cú pháp trong `text()`. Khóa chỉ bao trùm giao dịch claim dài vài mili giây, **không** bao trùm lúc gọi LLM (khác với lý do bác bỏ advisory lock ở KT4).
2. Nếu chat đã có dòng `processing` với `lease_until > :now`: trả rỗng (đây là điều kiện loại trừ thật sự).
3. Chọn dòng chưa xong có `update_id` nhỏ nhất của chat (`queued`, hoặc `processing` đã hết lease). Nếu không có dòng nào: trả rỗng. Nếu dòng đó đang `queued` với `lease_until` (thời điểm thử lại) còn ở tương lai: trả rỗng, **không nhảy cóc** sang dòng sau.
4. Nếu dòng đó đã `attempts >= BOT_MAX_ATTEMPTS`: `UPDATE ... SET status='failed', error_category='lease_exhausted', finished_at=:now, payload_text=NULL, reply_text=NULL WHERE update_id=:id AND status IN ('queued','processing')`, ghi nhớ id vào danh sách "hết lượt", rồi quay lại bước 2 **trong cùng giao dịch**. Ngược lại: `UPDATE ... SET status='processing', lease_until=:now + lease, attempts=attempts+1, started_at=coalesce(started_at,:now) WHERE update_id=:id AND status IN ('queued','processing') RETURNING update_id, attempts`. **Điều kiện `status IN ('queued','processing')` là bắt buộc**: không có nó thì lệnh hoàn tất của một worker cũ chen vào giữa lúc đọc đầu hàng đợi và lúc nhận làm sẽ bị ghi đè, dòng đã xong bị "hồi sinh" (chaos run: 64 dòng bị hồi sinh, 98 dòng không hoàn tất đúng một lần). Nếu `UPDATE` trả 0 dòng thì quay lại bước 2, nếu không dòng kế tiếp phải chờ cron. Commit, nhả khóa.
5. Vì vòng lặp nằm trong giao dịch claim, hàm claim **trả về cho bên gọi danh sách các dòng bị chuyển `failed`**, và câu xin lỗi chỉ được gửi **sau khi commit**.
6. **Cấm `FOR UPDATE SKIP LOCKED`** trong claim: nó cho worker thứ hai claim dòng sau khi dòng đầu đang chạy (đã có hai chỗ khác trong repo dùng `SKIP LOCKED` cho mục đích khác, dễ sao chép nhầm). Cũng không dựa vào khóa dòng đầu hàng đợi đơn thuần: S0(c) thấy nó hỏng **cả khi không có tin lệch thứ tự** (300 trên 300 vòng có hai dòng cùng `processing`), và biến thể "khóa dòng đầu cộng kiểm tra dòng đầu" qua được bài đua thuần nhưng hỏng khi tin đến lệch thứ tự (dòng 101 đang chạy rồi dòng 100 mới commit), nên một bài test chỉ có đua thuần sẽ cho cảm giác an toàn giả. Phương án thay thế `FOR UPDATE` trên dòng đầu (vẫn hợp lệ trong advisory lock) làm bên claim luôn thắng nên tạo nhiều việc trùng hơn; đọc thường giữ được lệnh hoàn tất của worker đến muộn nên ít câu trả lời trùng hơn.

**Xử lý dòng đã claim:**
1. **Quá hạn tin** (`received_at` cũ hơn `BOT_MESSAGE_TTL_SECONDS`): `dropped` (`expired`) và gửi một thông báo ("Hệ thống vừa gián đoạn, vui lòng gửi lại câu hỏi") **tối đa một lần mỗi lần chạy drain** (không có cột theo dõi, nên giữa hai lần drain có thể lặp lại; chấp nhận).
2. **Kiểm liên kết và người dùng:** `telegram_user_id` còn gắn đúng `user_id` với trạng thái **`active`** (một dòng `blocked` nghĩa là sau tin này đã có `my_chat_member kicked`, tin đã cũ: `dropped` `forbidden`, không gọi engine) và người dùng còn `ACTIVE`. Sai thì `dropped` (`unlinked` hoặc `user_inactive`). Bước này thay cho việc phải móc vào `/stop` và hủy liên kết từ web.
3. **Nạp `BotPrincipal`** mới ở **mỗi tin**: quyền bị thu hồi giữa hai tin có hiệu lực ở tin kế tiếp.
4. Nếu dòng đã có `reply_text` (lần claim trước chết sau bước lưu): **bỏ qua engine và cổng hạn mức** (lượt đã được tính), nhảy sang bước gửi. Ngược lại, qua **cổng hạn mức** (mục 4.11): bị từ chối thì dòng chuyển `dropped` (`quota_exceeded`), gửi câu thông báo cố định (không gọi engine, không tính lượt), rồi tiếp tục dòng sau.
5. **Chỉ báo "đang gõ"**: gửi `sendChatAction typing` ngay, lặp mỗi `BOT_TYPING_INTERVAL_SECONDS` bằng một tác vụ nền trong lúc engine chạy, hủy khi xong. Lỗi gửi chỉ báo bị bỏ qua.
6. Gọi `ChatEngine.reply(turn)` bọc `asyncio.wait_for(BOT_ROW_TIMEOUT_SECONDS)`. **Không giữ kết nối DB** trong lúc này. Lỗi `ChatEngineTemporaryError` hoặc quá thời gian: đưa dòng về `queued` với `lease_until = now + BOT_RETRY_BACKOFF_SECONDS × attempts` (nếu chưa đạt trần lần thử). Lỗi `ChatEngineError` (lỗi cuối): `failed` ngay, gửi một câu xin lỗi.
7. **Lưu `reply_text`** và đặt `reply_saved_at` bằng câu lệnh có rào chắn (KT16).
8. **Kiểm lần cuối trước khi gửi** bằng một truy vấn: dòng vẫn thuộc về lần claim này, liên kết còn `active`, người dùng còn `ACTIVE`. Không thì bỏ, không gửi.
9. Gửi theo mục 4.7, rồi `complete` có rào chắn.
10. Dừng claim dòng mới khi vượt `BOT_DRAIN_BUDGET_SECONDS`. Phần còn lại do cron quét đánh chuông lại sau tối đa khoảng một phút. Job arq không tự đưa lại chính nó vào hàng đợi được vì khóa job còn tồn tại đến khi job kết thúc.

**Hủy và tắt (đã kiểm ở S0(b)):** khi worker nhận `SIGTERM` (deploy), job nhận `CancelledError` khoảng 20 ms sau và khối dọn dùng `asyncio.shield` chạy xong trước khi tiến trình thoát. Hàm drain bắt `CancelledError`, **nhả lease của dòng đang xử lý** bằng một `UPDATE` bọc `shield` rồi ném lại; nếu không, dòng bị kẹt đến hết lease (240 giây). Khóa "đang chạy" của arq bị xóa khi `SIGTERM`, còn khóa job và mục retry ở lại thành job mồ côi (worker khởi động lại sẽ báo "max retries exceeded" và không chạy lại hàm), nên `BotWorkerSettings` đặt `retry_jobs=False`: không còn mồ côi và id dùng lại ngay, đổi lại một dòng log ERROR cho `CancelledError` (chấp nhận). `job_completion_wait` có trong arq 0.26.3 (số nguyên giây, mặc định 0) nhưng **không dùng**, để 0: vòng drain không biết mình đang bị tắt nên sẽ vẫn claim dòng mới trong lúc chờ. `stop_grace_period` của service phải lớn hơn thời gian dọn (khoảng 1 giây) cộng dự phòng (đề xuất 30 giây); nếu `docker stop` hết hạn thì tiến trình bị `SIGKILL`, khóa "đang chạy" còn lại, id kẹt và dòng kẹt đến hết lease. Một lần deploy giữa chừng tốn một lần thử.

**Bên gửi (`BotDispatcher.notify`)** chạy **sau commit**, không bao giờ làm hỏng webhook: pool arq được **tạo lười** ở lần dùng đầu (như `get_telegram_runner`; tạo ở lifespan sẽ chặn khởi động backend khi Redis chưa sẵn sàng, vì `arq.create_pool` thử tối đa khoảng 5,4 giây rồi ném lỗi). Việc tạo pool và việc đánh chuông cùng nằm **trong một** `asyncio.wait_for(2 giây)`: S0(b) đo được `create_pool` **treo vô hạn** khi Redis nửa chết (`docker pause`) vì `conn_timeout` chỉ áp cho bước nối TCP còn lệnh `ping` đầu tiên không có timeout, trong khi `enqueue_job` trên pool sẵn có bị `wait_for` cắt đúng 2 giây và pool vẫn dùng được sau khi Redis chạy lại. Phải bắt `Exception` (ngoại lệ thuộc thư viện `redis`, không phải ngoại lệ dựng sẵn), mọi lỗi chỉ ghi log. Job dùng `_job_id="bot:<update_id>"`, **không** dùng id theo chat: sau `SIGKILL` khóa job mồ côi chặn cùng id đến `job_timeout + 10` giây tính từ lúc job bắt đầu, và đến 24 giờ nếu không có worker nào chạy để dọn (mục 2), và một id theo chat làm mất chuông khi tin mới đến lúc job cũ sắp kết thúc. Với id theo update, mỗi tin có chuông riêng; chuông thừa vô hại vì claim loại trừ (job thứ hai thấy dòng đang chạy và thoát ngay). Còn lại một cửa sổ rất hẹp (dòng mới commit đúng lúc job cũ vừa thấy hàng rỗng), được cron quét bù.

**Cron `sweep_bot_updates`** (mỗi 30 giây; trả sớm khi `CHATBOT_ENABLED=false`): tìm chat có dòng claim được (`queued` đến hạn, hoặc `processing` hết lease) cũ hơn `BOT_SWEEP_STALE_SECONDS`, và `notify` cho chat đó. Cron **không** tự đổi trạng thái dòng nào (việc tiếp quản lease do claim làm), nên chạy ở hai tiến trình vẫn an toàn.

**Công tắc tắt khẩn cấp:** `CHATBOT_ENABLED=false` làm backend ngừng hand-off (tin mới trả `UNKNOWN_TEXT`), `drain_chat` ngừng claim dòng mới (xong dòng đang chạy), cron không đánh chuông. Dòng đã `queued` **không mất**: khi bật lại, dòng quá `BOT_MESSAGE_TTL_SECONDS` bị loại (`expired`). Vì cờ đọc từ env lúc khởi động, tắt nhanh nhất là `docker compose stop bot-worker`; tắt đủ là đặt cờ `false` rồi tạo lại **cả `backend` và `bot-worker`**. Quy trình này ghi ở runbook mục 16.

**Cấu hình arq của `BotWorkerSettings`:** `queue_name="quotify:bot"`, `max_tries=1` (thử lại do claim và cron quyết định, không để arq tự thử lại chồng lên), `retry_jobs=False` (không để lại job mồ côi khi bị hủy), `keep_result=0` (**bắt buộc**: với mặc định 3600 giây, một job lỗi hay mồ côi chặn id của nó 1 giờ), `job_timeout` lớn hơn tổng ngân sách (mục 4.8), `health_check_interval` nhỏ (đề xuất 30 giây; mặc định 3600 làm worker chết trông khỏe một giờ), `timezone` theo `APP_TIMEZONE`, `redis_settings` dựng giống `WorkerSettings` (host và port), và `on_startup` phải gọi `configure_logging` (che token) như `worker.py:169-185`, có test. **`BotWorkerSettings` là lớp độc lập, khai báo đủ mọi thuộc tính trong chính thân lớp**: arq đọc `cls.__dict__` nên lớp con của `WorkerSettings` không thừa hưởng gì (thử thật báo "at least one function or cron_job must be registered" và `--check` rơi về `localhost:6379`). Không gian `arq:job:<id>` dùng chung giữa các hàng đợi, nên tiền tố `bot:` trong `_job_id` có ích. Các hành vi arq ở trên đã được S0(b) xác nhận trong Docker (Phụ lục A.2).

### 4.6 Cổng cắm và ngữ cảnh

Hình dạng dự kiến (hợp đồng với 5.2 đến 5.6, chốt khi làm S1 và S6):

```python
@dataclass(frozen=True, slots=True)
class ChatTurn:
    update_id: int
    chat_id: int
    telegram_user_id: int
    principal: BotPrincipal              # người dùng ACTIVE + quyền, nạp mới mỗi tin (S1)
    text: str
    received_at: datetime                # timezone-aware (UTC); đổi sang Asia/Ho_Chi_Minh ở nơi hiển thị
    readonly_session_factory: async_sessionmaker[AsyncSession] | None = None   # S6 bổ sung

@dataclass(frozen=True, slots=True)
class ChatReply:
    text: str                            # sẽ có thêm usage (token, chi phí) khi làm 5.6

class ChatEngineTemporaryError(Exception): ...   # thử lại được (hết thời gian, lỗi mạng, 5xx, 429 của nhà cung cấp)
class ChatEngineError(Exception): ...            # lỗi cuối (cấu hình, chính sách), không thử lại

class ChatEngine(Protocol):
    async def reply(self, turn: ChatTurn) -> ChatReply: ...
```

- 5.1 giao `StubChatEngine` (câu cố định tiếng Việt có dấu) và `FakeChatEngine` cho test (đếm số lần gọi, có thể chặn, ném lỗi). 5.5 chịu trách nhiệm ánh xạ lỗi nhà cung cấp sang hai loại lỗi trên.
- **`BotPrincipal`** bọc `User` đã nạp `roles -> permissions` bằng `AuthService.get_active_user(user_id=...)` và dùng lại `has_permission`, không tự cài lại bộ quyền. Mọi công cụ của 5.2 phải kiểm quyền qua principal, vì service không tự kiểm (RR-3).
- **Engine DB chỉ đọc riêng** (`app/db/readonly.py`): `create_async_engine` với `connect_args={"server_settings": {...}}` đặt `default_transaction_read_only=on`, `statement_timeout` (đề xuất 5000 ms) và `idle_in_transaction_session_timeout`, pool nhỏ riêng để một đợt hỏi đáp không làm cạn pool của API. Dùng `server_settings` thay vì `execution_options(postgresql_readonly=True)` (đã đo ở S0(a)): `server_settings` có hiệu lực suốt phiên, kể cả sau commit, sau rollback và khi kết nối được lấy lại từ pool, và gộp được cả `statement_timeout`; còn `postgresql_readonly` chạy được dưới READ COMMITTED nhưng chỉ đặt được trước khi giao dịch bắt đầu và không đặt được timeout. Tạo **lười** ở lần dùng đầu. Kết quả đo: ghi, DDL, bảng tạm và `SELECT ... FOR UPDATE` đều bị từ chối (SQLSTATE `25006`); truy vấn quá `statement_timeout` bị hủy đúng 5,00 giây (`57014`); phiên rảnh trong giao dịch bị cắt (`InterfaceError` với `connection_invalidated=True`, kết nối kế tiếp là kết nối mới); hai pool tách biệt không chặn nhau. **Đây là rào chắn, không phải ranh giới bảo mật** (RC-27): một phiên có thể chạy `SET TRANSACTION READ WRITE` hoặc `SET default_transaction_read_only=off`, và cài đặt đó rò sang kết nối được dùng lại trong pool (`SET statement_timeout=0` cũng vậy; `pg_advisory_lock` mức phiên vẫn được phép). An toàn vì vậy dựa vào việc **không công cụ nào nhận SQL từ model** (mục 5.2), còn ranh giới cứng là role Postgres chỉ có `SELECT` ở 2D.
- Mỗi lần gọi công cụ mở một session chỉ đọc ngắn, không commit.

### 4.7 Đường gửi trả lời

- **Văn bản thuần** (`parse_mode=None`) cho nội dung do engine sinh, tránh lỗi 400 vì HTML sai. Tin cố định của hệ thống vẫn dùng HTML như hiện nay.
- **Chia tin** ở ranh giới đoạn hoặc dòng khi vượt `TELEGRAM_MESSAGE_MAX_LENGTH` (4096), tối đa `BOT_REPLY_MAX_PARTS` phần, phần dư cắt kèm dấu "…". `sent_parts` ghi số phần đã gửi, gửi lại tiếp từ phần chưa gửi.
- **Toàn bộ nhánh gửi** bọc `asyncio.wait_for(BOT_SEND_BUDGET_SECONDS)`. **429:** chờ `min(retry_after, thời gian còn lại của ngân sách)` rồi thử lại; hết ngân sách thì dừng và để claim lại sau khi lease hết hạn. Ngân sách này, cộng với việc mỗi lời gọi HTTP có timeout 10 giây, bảo đảm lease không hết hạn khi đang gửi. **403:** gọi `mark_blocked` có sẵn, dòng `dropped` (`forbidden`). **400** (nội dung): lỗi cuối, `failed`, không thử lại.
- Ngữ nghĩa giao hàng: **at-least-once** cho câu trả lời (khác đường trả lời at-most-once của 1A/1C, vì mất câu trả lời tệ hơn nhận trùng). Cửa sổ trùng chỉ là khoảng giữa lúc Telegram nhận tin và lúc ghi `complete`, thu hẹp thêm bằng `sent_parts` và bước kiểm lần cuối ở 4.5.

### 4.8 Cấu hình và tham số

Thêm vào `Settings` và `.env.example`, `.env.production.example`. **Không** dùng `${VAR:?}` trong compose production cho các biến này (bài học của `make production-readiness-check`). Không có secret mới ở kế hoạch này; khóa nhà cung cấp LLM thuộc 5.5.

| Biến | Mặc định đề xuất | Ghi chú |
|---|---|---|
| `CHATBOT_ENABLED` | `false` | Cổng env. Cần `TELEGRAM_ENABLED=true`. Cờ DB (`chatbot_settings.is_enabled`) thêm ở 5.6 |
| `CHATBOT_PILOT_USER_EMAILS` | rỗng | Danh sách email, so không phân biệt hoa thường. **Rỗng (hoặc chỉ khoảng trắng) = mọi người đã liên kết** khi cờ bật; có giá trị = chỉ những người này được hand-off; có giá trị mà không có email nào (ví dụ chỉ dấu phẩy) thì **đóng**, không ai được hand-off. Tiền lệ: `PRICE_ALERT_RECIPIENT_EMAILS` của 1B. Cần thêm email vào kết quả tra liên kết hoặc một truy vấn nhỏ |
| `BOT_QUEUE_NAME` | `quotify:bot` | Khác `arq:queue` nên worker cũ không bao giờ lấy job bot |
| `BOT_WORKER_MAX_JOBS` | `8` | Việc chủ yếu chờ I/O, giới hạn thật nằm ở hạn mức nhà cung cấp LLM |
| `BOT_HEALTH_CHECK_INTERVAL_SECONDS` | `30` | Chu kỳ ghi khóa sức khỏe của arq; khóa sống `giá trị + 1` giây nên worker bị kill vẫn báo khỏe đến hết từng ấy (mặc định 3600 giây là 1 giờ, đo ở S0(b)). Healthcheck compose dùng `arq --check` |
| `BOT_JOB_TIMEOUT_SECONDS` | `300` | Phải lớn hơn `BOT_DRAIN_BUDGET_SECONDS + BOT_ROW_TIMEOUT_SECONDS + BOT_SEND_BUDGET_SECONDS` (90 + 120 + 60 = 270) |
| `BOT_DRAIN_BUDGET_SECONDS` | `90` | Ngừng claim dòng mới sau mức này |
| `BOT_ROW_TIMEOUT_SECONDS` | `120` | Trần cho một lần engine chạy |
| `BOT_SEND_BUDGET_SECONDS` | `60` | Trần **tổng** cho nhánh gửi một dòng (kể cả chờ 429 và gửi nhiều phần) |
| `BOT_LEASE_SECONDS` | `240` | Phải lớn hơn `BOT_ROW_TIMEOUT_SECONDS + BOT_SEND_BUDGET_SECONDS` (180), nếu không lease hết hạn khi đang xử lý và worker khác chạy chồng |
| `BOT_MAX_ATTEMPTS` | `3` | |
| `BOT_RETRY_BACKOFF_SECONDS` | `5` | Nhân với số lần thử |
| `BOT_MAX_PENDING_PER_CHAT` | `5` | Vượt thì trả lời lịch sự, không ghi hộp thư |
| `BOT_DAILY_TURN_LIMIT` | `20` | Số lượt hỏi AI mỗi người mỗi ngày (giờ Việt Nam), áp cho mọi loại tin. `0` nghĩa là không giới hạn lượt (trần ngân sách tháng ở 5.6 vẫn áp dụng). Mức mặc định thấp nhất của chuỗi cấu hình, xem mục 4.11 |
| `BOT_DAILY_FILE_LIMIT` | `5` | Số lượt dùng ảnh hoặc PDF mỗi người mỗi ngày (2C), là tập con của `BOT_DAILY_TURN_LIMIT`. `0` nghĩa là không giới hạn |
| `BOT_QUOTA_WARN_REMAINING_PERCENT` | `20` | Còn từng này phần trăm hạn mức thì thêm dòng nhắc ở cuối câu trả lời; `0` là tắt nhắc |
| `BOT_MESSAGE_TTL_SECONDS` | `1200` | Phải không nhỏ hơn `BOT_MAX_PENDING_PER_CHAT × (BOT_ROW_TIMEOUT_SECONDS + BOT_SEND_BUDGET_SECONDS)` (900), nếu không dòng hết hạn khi mới chỉ đang chờ |
| `BOT_SWEEP_STALE_SECONDS` | `30` | Bằng chu kỳ cron: dòng chờ lâu hơn mức này mà chưa ai nhận thì đánh chuông lại |
| `BOT_TYPING_INTERVAL_SECONDS` | `4` | Chỉ báo "đang gõ" của Telegram kéo dài khoảng 5 giây |
| `BOT_REPLY_MAX_PARTS` | `4` | |
| `BOT_TERMINAL_RETENTION_DAYS` | `30` | Xóa dòng đã kết thúc (nội dung đã bị xóa từ lúc kết thúc, chỉ còn siêu dữ liệu) |

Bạn đã đồng ý các giá trị này làm **giá trị khởi điểm** (2026-10-13), chưa đo: chạy thử trên dev rồi tinh chỉnh lại (S8), và đặt hạn mức token sau khi có số liệu thật của engine (5.5, 5.6).

### 4.9 Quan sát

Worker hiện không phơi metric và Prometheus chỉ scrape backend, nên dùng đúng mẫu `core/price_alert_metrics.py`: **gauge tính lúc scrape từ DB** ở backend.

- `quotify_bot_updates{status}` (số dòng theo trạng thái trong 24 giờ gần nhất), `quotify_bot_queued_oldest_age_seconds` (tuổi dòng claim được cũ nhất), `quotify_bot_quota_denied` (số dòng bị từ chối vì hết hạn mức trong 24 giờ gần nhất, để thấy hạn mức đặt quá chặt).
- Cảnh báo (nhóm mới trong `alert_rules.yml`, tiền tố `quotify_bot_*`): dòng chờ cũ nhất quá 120 giây kéo dài 5 phút; số dòng `failed` tăng. Hai luật cũ còn tên `fastapivue_*` (nợ RR-19) **không** sửa lan ở đây. Cảnh báo tuổi dòng chỉ nổ khi **đã có** người dùng chờ; để phát hiện worker chết sớm hơn, `bot-worker` có healthcheck container (mục 4.10).
- Log có cấu trúc chỉ chứa `update_id`, `status`, `attempts`, `duration_ms`, `error_category`. **Không bao giờ** log nội dung tin hay câu trả lời, `payload_text`, ngoại lệ nguyên văn từ engine (bài học rò token ở 1A). Có test "chuỗi mồi" bảo đảm điều này.

### 4.10 Triển khai

- **Compose:** thêm service `bot-worker` vào dev (profile `telegram`, cạnh `telegram-poller`, phụ thuộc backend đã migrate như poller), prod và test. Ở prod đặt dưới `profiles: ["chatbot"]` để triển khai các lát S1 đến S8 **không đổi gì ở runtime production** cho đến khi bật có chủ đích (reviewer đã thử: `build bot-worker` đích danh có build, `up -d` thường bỏ qua). Service dùng cùng Dockerfile và target `prod` như `worker`, nên dùng chung layer cache khi build (suy luận), nhưng tên image khác, nên **mọi danh sách build và recreate trong runbook phải thêm `bot-worker`** (mục 10) để không chạy image cũ. Đề xuất cho riêng `bot-worker` (các service hiện có chưa có): `restart: unless-stopped`, `stop_grace_period`, và healthcheck dùng `arq --check` (chờ bạn xác nhận, mục 9).
- **Runbook:** thêm mục 16 "Chatbot" (không đánh số lại 13 đến 15, vì script `check-price-alert-readiness.sh` kiểm tiêu đề đúng nguyên văn), kèm công tắc tắt khẩn cấp (mục 4.5), cách đọc metric, và cách đặt `CHATBOT_PILOT_USER_EMAILS`.
- **Dev:** `docker compose --profile telegram up -d telegram-poller bot-worker`. Poller phải nối cùng `BotDispatcher` (không còn là "nếu cần"). Worker không tự reload code, sau khi sửa phải restart.
- **Production:** thứ tự như mọi lần: backup, build có `bot-worker`, `run --rm backend uv run alembic upgrade head`, `up -d`, `restart reverse-proxy`. Chỉ thêm bảng, không đổi hay xóa gì, nên code cũ chạy được trên schema mới trong lúc chuyển container.

### 4.11 Hạn mức sử dụng mỗi người mỗi ngày

**Yêu cầu bổ sung (2026-10-13):** chatbot và nhập liệu bằng AI tốn token và tiền, nên phải cấu hình được giới hạn cho mỗi người dùng mỗi ngày.

**Đề xuất: kết hợp ba loại hạn mức, thực thi ở một cổng chung ngay trước khi gọi engine.**

| Hạn mức | Đo gì | Vì sao cần | Ai thấy |
|---|---|---|---|
| **Lượt hỏi mỗi ngày** (chính) | Số lần engine đã tạo ra câu trả lời, mọi loại tin | Người dùng hiểu ngay ("còn 5 lượt"), kiểm tra được **trước** khi gọi, không cần ước lượng | Người dùng thấy |
| **Lượt dùng file mỗi ngày** | Tin có ảnh hoặc PDF (2C) | Một lượt đọc file tốn gấp nhiều lần một câu hỏi chữ, nên cần trần riêng nhỏ hơn | Người dùng thấy |
| **Token mỗi ngày** (chốt chặn) | Tổng token vào và ra của mọi lần gọi LLM, kể cả lần thử lại và các vòng gọi công cụ | Chi phí thật: một lượt có thể gọi LLM nhiều lần, câu hỏi dài, kết quả công cụ lớn | Quản trị viên; người dùng chỉ thấy khi bị chặn |

Vì sao không chọn một loại duy nhất:

| Phương án | Ưu | Nhược | Kết luận |
|---|---|---|---|
| Chỉ đếm lượt | Đơn giản, dễ hiểu | Chi phí mỗi lượt chênh nhau hàng chục lần (vòng gọi công cụ, file, câu dài): có thể vượt ngân sách mà người dùng vẫn "còn lượt" | Không đủ |
| Chỉ đếm token | Sát chi phí thật | Người dùng khó hiểu; chỉ biết sau khi gọi, nên chỉ kiểm được "đã dùng bao nhiêu" chứ không biết "lượt này tốn bao nhiêu"; phụ thuộc cách đếm của nhà cung cấp | Không dùng làm hạn mức hiển thị |
| Chi phí VNĐ mỗi người mỗi ngày | Cùng đơn vị với trần tháng | Phụ thuộc đơn giá và tỷ giá thay đổi, khó giải thích | Không (trần tiền chỉ đặt ở cấp tháng, 5.6) |
| **Lượt + file + token** | Người dùng hiểu lượt; token chặn phần rủi ro còn lại | Nhiều tham số hơn | **Chọn** |

Cách hoạt động:

1. **Cấu hình** theo thứ tự ưu tiên giảm dần: (a) ghi đè theo từng người do **Admin** cấu hình (5.6, bảng `chatbot_user_limits`, cột rỗng nghĩa là dùng mặc định; quyền `chatbot.manage`, chỉ admin như QĐ-10; thực tế thường nâng hạn mức cho trưởng phòng), (b) mặc định toàn hệ thống do admin sửa trên trang "Chi phí chatbot" (5.6, thay cột `daily_user_limit` đơn lẻ bằng `daily_turn_limit`, `daily_file_limit`, `daily_token_limit`), (c) biến môi trường của 5.1 (`BOT_DAILY_TURN_LIMIT`, `BOT_DAILY_FILE_LIMIT`). Ở 5.1 chỉ có tầng (c); 5.6 thêm hai tầng trên mà không đổi cổng. Mọi thay đổi ở 5.6 ghi audit. Giá trị `0` là không giới hạn loại đó. **Quản trị viên không được miễn** (đã chốt 2026-10-13): cổng không bypass theo tên role như `has_permission`; quản trị viên chịu cùng hạn mức mặc định như người khác, muốn khác thì dùng ghi đè theo từng người.
2. **Cổng `UsageGate`** (cổng thứ hai của đường ống, cạnh `ChatEngine`): `check(principal, kind, now) -> QuotaDecision(allowed, reason, used, limit, resets_at)` và `summary(principal, now) -> QuotaSummary(turns_used, turns_limit, files_used, files_limit, resets_at)` (phục vụ lệnh `/limit`). 5.1 cài `TurnLimitGate` (lượt và file, đếm từ `bot_updates`). 5.6 cài `TokenLimitGate` (đếm từ `llm_usage_events`) và ghép bằng `CompositeUsageGate`, từ chối đầu tiên thắng. `resets_at` luôn là `timestamptz` có múi giờ.
3. **Đếm lượt** = số dòng `bot_updates` của người dùng có `reply_saved_at` khác rỗng và `received_at` thuộc ngày hiện tại. Dùng `reply_saved_at` thay vì `status='replied'` vì chi phí đã phát sinh ngay khi engine trả lời, kể cả khi gửi Telegram sau đó lỗi. Lượt bị từ chối hạn mức, lỗi engine, hoặc tin bị loại (`expired`, `unlinked`, `user_inactive`) thì **không** tính. Lượt file là tập con có `kind` là `photo` hoặc `document`.
4. **Ngày** là ngày nghiệp vụ theo `Asia/Ho_Chi_Minh`, đặt lại lúc 00:00 giờ Việt Nam (không theo UTC). Biên ngày tính ở Python rồi đổi sang UTC để truy vấn khoảng `received_at` (dùng chỉ mục `ix_bot_updates_user_received`). Tin nhận lúc 23:59 tính vào ngày hôm đó dù được trả lời sau 00:00. **Không** dùng `received_at::date`: không dùng được chỉ mục (28,7 ms so với 0,36 ms) và cho kết quả phụ thuộc múi giờ của phiên (cùng dữ liệu cho 3/5/0 ở UTC, 1/5/2 ở giờ Việt Nam, 4/4/0 ở Los Angeles); khoảng `[bắt đầu, kết thúc)` đã đổi sang UTC cho kết quả giống nhau ở mọi múi giờ phiên và cấu hình DB (đã đo ở S0(c)).
5. **Không có điều kiện đua.** Mỗi người chỉ có một liên kết Telegram đang giữ (ràng buộc duy nhất của 1A) và mỗi chat chạy một dòng tại một thời điểm (KT4), nên bước "kiểm tra rồi mới làm" của cùng một người luôn tuần tự, không cần khóa hay bộ đếm nguyên tử. **Ngoại lệ hẹp:** nếu người dùng đổi sang tài khoản Telegram khác đúng lúc chat cũ đang chạy engine thì hai chat của cùng một người có thể chạy chồng nhau trong khoảng một lượt (dòng của chat cũ bị loại ở lần claim kế tiếp nhờ kiểm liên kết); mức vượt tối đa một lượt, chấp nhận. Nếu sau này có kênh thứ hai (web) dùng chung hạn mức thì phải tính lại điểm này.
6. **Điểm kiểm tra** ở worker, ngay trước khi gọi engine (bước 4 của mục 4.5), vì đó là nơi duy nhất đáng tin về thứ tự; không kiểm ở webhook. Dòng đã có `reply_text` (gửi lại sau sự cố) bỏ qua cổng.
7. **Khi bị từ chối:** dòng thành `dropped` (`quota_exceeded`), gửi một câu cố định, không gọi LLM, không tính lượt. Ví dụ: "Bạn đã dùng hết 20/20 lượt hỏi hôm nay. Hạn mức được làm mới lúc 00:00 ngày 14/10/2026 (giờ Việt Nam). Cần thêm lượt, vui lòng liên hệ quản trị viên." Số liệu trong câu là số thật từ `QuotaDecision`. Lệnh inline (`/start`, `/stop`, `/help`, `/limit`) vẫn dùng được và không tốn hạn mức; bộ giới hạn tốc độ sẵn có (10 tin mỗi 60 giây) chặn việc gõ dồn để nhận câu từ chối liên tục.
8. **Nhắc trước khi hết:** khi phần còn lại không quá `BOT_QUOTA_WARN_REMAINING_PERCENT` thì thêm dòng cuối "Còn 3/20 lượt hôm nay." vào câu trả lời. Dòng này do cổng thêm, không do engine sinh, và được tính vào bước chia tin (không làm câu vượt 4096 ký tự).
9. **Giới hạn mức vượt trong một lượt.** Cổng chỉ biết token đã dùng **trước** lượt này, nên một lượt có thể vượt hạn mức token. Mức vượt tối đa bị giới hạn bởi các trần mỗi lượt do 5.2 và 5.5 áp: số vòng gọi công cụ tối đa mỗi lượt, `max_tokens` mỗi lần gọi, kích thước kết quả công cụ. Đây là **yêu cầu bắt buộc** với 5.2 và 5.5, không thuộc phạm vi 5.1 (RC-21).
10. **Cỡ hạn mức so với trần ngân sách tháng (QĐ-10).** Chi phí tối đa mỗi lượt để không chạm trần tháng khi mọi người dùng hết hạn mức bằng ngân sách tháng chia cho (số người × lượt mỗi ngày × 30). Với số liệu của tài liệu cha (2.000.000 VNĐ mỗi tháng, 12 người dùng ở bản sao ngày 2026-10-03, 20 lượt mỗi ngày) con số này khoảng 278 VNĐ mỗi lượt (khoảng 0,0105 USD ở tỷ giá 26.500). **Chi phí thật mỗi lượt chưa đo**, nên 20 lượt là mặc định chờ kiểm chứng ở 5.5 và 5.6: nếu đo ra trung bình cao hơn mức này thì giảm hạn mức hoặc nâng trần tháng. Hạn mức token đặt sau khi đo; gợi ý ban đầu bằng số lượt nhân token p95 mỗi lượt.
11. **Lệnh `/limit` (đã chốt 2026-10-13):** người dùng xem số lượt chữ và lượt file đã dùng, còn lại, cùng giờ làm mới (không hiện token). Lệnh inline, chỉ đọc DB, chỉ dành cho người đã liên kết và còn `ACTIVE`; khi `CHATBOT_ENABLED=false` hoặc người dùng ngoài danh sách thử thì như lệnh lạ. Đăng ký lệnh vào menu của bot (`set_my_commands`) là thao tác ngoại vi trên production, làm khi bật chatbot chính thức ở 2A và cần xác nhận lại lúc đó; trước đó vẫn gõ tay `/limit` được. Tên lệnh bằng tiếng Anh như các lệnh hiện có (`/start`, `/stop`, `/help`); phần mô tả hiện trong menu bot bằng tiếng Việt (ví dụ "Xem hạn mức sử dụng hôm nay").

**Phần thuộc 5.6, không nằm trong kế hoạch này:** bảng `chatbot_user_limits`, ba cột hạn mức trong `chatbot_settings`, `TokenLimitGate`, trang cấu hình (kể cả cảnh báo khi đặt hạn mức bất hợp lý), audit thay đổi hạn mức. Gợi ý (chưa chốt): nút "áp dụng cho nhiều người" chọn theo quyền `price_alerts.receive_all` (trưởng phòng) để không phải sửa từng người, vì tên role `manager` không cố định.

---

## 5. Quyết Định Kiến Trúc KT1 Đến KT21

| # | Quyết định | Lý do | Phương án đã loại |
|---|---|---|---|
| KT1 | Chỉ **văn bản thường** của người đã liên kết đi hand-off; lệnh, nút bấm, `my_chat_member` giữ inline | `callback_query` có hạn 4 giây và hết hạn khoảng 15 giây; `/start`, `/stop` nhanh và có thứ tự đặc biệt | Đưa toàn bộ update vào hàng đợi: làm vỡ nút duyệt giá |
| KT2 | Ghi hộp thư **cùng giao dịch** với dedupe | Loại hẳn rủi ro mất tin ở dòng 763 của tài liệu cha; lỗi DB vẫn 503 để Telegram gửi lại như cũ | Enqueue rồi commit: chuông kêu trước khi có dữ liệu. Commit rồi enqueue không có hộp thư: mất tin khi Redis lỗi |
| KT3 | Postgres là sự thật, arq chỉ đánh chuông; `max_tries=1`, `retry_jobs=False`, `keep_result=0`, **`_job_id="bot:<update_id>"`** | Redis không bền (volume chỉ snapshot mặc định, không mật khẩu), mất hàng đợi không được làm mất tin; một nguồn quyết định thử lại. Id theo chat làm chat kẹt sau `SIGKILL` cho đến khi một worker sống dọn job mồ côi (khoảng `job_timeout + 10` giây, và đến 24 giờ nếu không có worker nào chạy), và có thể mất chuông. `keep_result=0` là bắt buộc: mặc định 3600 giây chặn id 1 giờ sau một job lỗi (thực nghiệm S0(b)) | Để arq tự retry: hai cơ chế thử lại chồng nhau. `_job_id` theo chat: kẹt và mất chuông |
| KT4 | Mỗi chat một dòng chạy tại một thời điểm, bảo đảm bằng **claim trong Postgres**: advisory lock theo giao dịch chỉ quanh bước claim + điều kiện "không có dòng `processing` còn lease"; cấm `SKIP LOCKED` | Đã đo ở S0(c): 0 vi phạm trong 400 vòng với 5 dòng và 2 đến 4 bên claim (asyncio và tiến trình thật) và trong chaos run 1.500 dòng với 2.062 lần tiếp quản lease; khóa dòng đơn thuần hỏng 300 trên 300 vòng. Có tiền lệ `lease_until` ở bộ gửi 1B | Redis lock theo chat: không đảm bảo thứ tự, cần gia hạn, chưa có tiền lệ. Advisory lock **giữ suốt lúc gọi LLM**: chiếm kết nối. `SKIP LOCKED`: nhảy cóc |
| KT5 | Lưu `reply_text` trước khi gửi; engine gọi tối đa một lần **mỗi lần thử**, tối đa `BOT_MAX_ATTEMPTS` lần thử | Gửi lại luôn cùng nội dung; không gọi lại engine chỉ vì gửi lỗi. Chi phí 5.6 đếm theo lần thử | Gọi lại engine khi gửi lỗi: tốn tiền và đổi câu trả lời |
| KT6 | Module `app/bot_worker.py` với `BotWorkerSettings` (lớp độc lập, khai báo đủ thuộc tính trong thân lớp, không kế thừa `WorkerSettings`), queue `quotify:bot`, service riêng | `worker.py` quá lớn, test ghim `WorkerSettings`, tránh import vòng; cuộc gọi LLM dài không chiếm 10 slot của worker backup và import | Thêm vào `WorkerSettings`: hàng đợi chung, LLM chậm làm đói backup |
| KT7 | Pool arq chung cho bên gửi bot, **tạo lười** ở lần dùng đầu; tạo pool và đánh chuông cùng nằm trong một `wait_for` 2 giây | `arq.create_pool` thử 5 lần rồi ném lỗi nên tạo ở lifespan chặn khởi động; Redis nửa chết làm `create_pool` treo vô hạn (đo ở S0(b)), nên mọi thao tác Redis của bên gửi phải nằm trong `wait_for` | Tạo ở lifespan. Sửa `create_job_queue` ngay: chạm luồng import và backup đang chạy production |
| KT8 | Cổng `ChatEngine` + `ChatTurn` + `ChatReply` + hai loại lỗi; 5.1 giao `StubChatEngine` | Cho phép nghiệm thu đường ống không cần LLM; 5.2 đến 5.6 độc lập; phân biệt lỗi thử lại được và lỗi cuối | Chờ LLM xong mới thử đường ống: rủi ro tích hợp dồn về cuối |
| KT9 | `BotPrincipal` nạp mới mỗi tin, dùng lại `has_permission` | Quyền thu hồi có hiệu lực ngay; không tái cài RBAC | Đệm theo phiên hội thoại: quyền cũ sống lâu |
| KT10 | Engine DB chỉ đọc riêng bằng `server_settings`, pool nhỏ, tạo lười; **chỉ là rào chắn, không phải ranh giới bảo mật** | Hiệu lực suốt phiên và gộp được `statement_timeout`, cô lập pool, không cần role Postgres mới (đo ở S0(a)) | `execution_options(postgresql_readonly=True)`: chạy được dưới READ COMMITTED nhưng chỉ đặt được trước giao dịch và không có timeout. Role chỉ-`SELECT` và view whitelist (ranh giới cứng) để 2D |
| KT11 | Trả lời văn bản thuần, chia tin, `sent_parts`, trần tổng thời gian gửi | Tránh lỗi 400 do HTML sai; Telegram giới hạn 4096; lease không hết hạn lúc đang gửi | Cho model sinh HTML: 400 và chèn mã |
| KT12 | Metric tính lúc scrape từ DB ở backend | Worker không phơi metric, Prometheus không scrape worker | `start_http_server` trong worker kèm sửa `prometheus.yml` |
| KT13 | `CHATBOT_ENABLED` (env) mặc định tắt; tắt thì hành vi bằng hiện tại. Cờ DB ở 5.6 | Phát hành tắt rồi bật dần (nguyên tắc additive của dự án) | Cờ chỉ ở DB: không rollback được khi DB lỗi |
| KT14 | Không audit từng câu hỏi, không log nội dung | Audit cho thao tác ghi (2B); `content` đang nằm trong allow-list và khóa `session|token` bị che | Audit mọi tin: phình bảng, đưa nội dung vào audit |
| KT15 | Không xây bộ giới hạn Redis; giữ giới hạn runner và trần số tin chờ mỗi chat; hạn mức ngày đếm bằng DB (KT19 đến KT21) | Production một tiến trình uvicorn; chưa có hạ tầng Redis limiter | Redis limiter: thêm hạ tầng chưa cần |
| KT16 | **Rào chắn** cho mọi ghi kết quả: `UPDATE ... WHERE update_id=:id AND status='processing' AND attempts=:mine`, kiểm số dòng bị ảnh hưởng; một truy vấn kiểm lần cuối ngay trước khi gửi | Sau khi lease bị tiếp quản, worker cũ chậm không được ghi đè trạng thái của worker mới hay gửi trùng; cũng che trường hợp dòng bị `ON DELETE CASCADE` xóa giữa chừng | Tin vào lease: lease hết hạn khi worker còn chạy thì hai bên chồng nhau |
| KT17 | **Cổng bật dần** `CHATBOT_PILOT_USER_EMAILS` (rỗng = mọi người) và **công tắc tắt khẩn cấp** có ngữ nghĩa rõ cho dòng đang chờ | `CHATBOT_ENABLED` là cờ toàn cục nên không bật thử cho một tài khoản được; cần biết dòng đang chờ ra sao khi tắt | Chỉ cờ toàn cục: bật là gửi cho mọi người đã liên kết. Quyền `chatbot.use`: nặng hơn cần thiết ở giai đoạn thử |
| KT18 | Nhả lease khi worker nhận `SIGTERM`/hủy (bọc `shield`), kèm `stop_grace_period` và `retry_jobs=False` | Deploy giữa lúc đang xử lý không được làm kẹt chat đến hết lease | Để lease tự hết: kẹt tối đa 240 giây mỗi lần deploy |
| KT19 | Hạn mức mỗi người mỗi ngày gồm **ba loại: lượt, file, token**; lượt là hạn mức hiển thị chính, token là chốt chặn chi phí; ghi đè theo từng người ở 5.6 | Lượt dễ hiểu và kiểm được trước khi gọi; file tốn gấp nhiều lần chữ; một lượt có thể gọi LLM nhiều lần nên cần chốt chặn theo token; mỗi vai trò cần mức khác nhau | Chỉ lượt (có thể vượt ngân sách), chỉ token (khó hiểu, không biết trước), chi phí VNĐ theo người (đơn giá và tỷ giá đổi) |
| KT20 | Cổng `UsageGate` đặt ở worker ngay trước engine; **đếm lượt từ `bot_updates.reply_saved_at`**; token đếm từ `llm_usage_events` ở 5.6 | Một nơi duy nhất đáng tin về thứ tự; mỗi người một liên kết và mỗi chat tuần tự nên kiểm rồi làm không đua; `reply_saved_at` phản ánh đúng lúc chi phí phát sinh | Kiểm ở webhook (đua với các tin đang chờ); bộ đếm nguyên tử ở Redis (thêm hạ tầng); đếm theo `status='replied'` (bỏ sót lượt đã tốn tiền nhưng gửi lỗi) |
| KT21 | Ngày hạn mức là ngày nghiệp vụ `Asia/Ho_Chi_Minh`, làm mới 00:00; ưu tiên cấu hình: ghi đè theo người > mặc định toàn hệ thống (5.6) > env (5.1); `0` là không giới hạn | Quy tắc múi giờ tường minh (Rule 13); 5.1 giao trước nên cần giá trị env, 5.6 thêm tầng trên mà không đổi cổng | Theo UTC (lệch ngày so với người dùng); cửa sổ cuộn 24 giờ (khó giải thích với người dùng) |

---

## 6. Lát Cắt S0 Đến S10

Mỗi lát phát hành **tắt** bằng `CHATBOT_ENABLED=false`.

**Quy trình git và phát hành (chốt 2026-10-13):** không dùng nhánh dài hạn riêng cho toàn bộ Bước 2. Mỗi lát làm trên một nhánh ngắn từ `main`, qua tiêu chí chấp nhận của lát, rồi fast-forward vào `main` (như tiền lệ 1A và 1B). Merge vào `main` **không** tự deploy: VPS chỉ lấy code khi chạy `git pull --ff-only origin main` theo runbook. Production chỉ được cập nhật ở **S9** (cờ tắt, rồi pilot) và các bước sau của chatbot khi thật sự cần. Mọi lần commit, merge, push và deploy đều do bạn cho phép ngay lúc đó. Hệ quả của việc không dùng nhánh dài hạn ghi ở RC-25.

Thứ tự phụ thuộc:

```
S0 ──► S1 ──┬─► S2
            ├─► S3
            ├─► S4
            ├─► S5
            ├─► S6
            ├─► S7
            └─► S10
(S2 đến S7, S10) ──► S8 ──► S9
```

S1 đã chứa `BotPrincipal` (vì `ChatTurn.principal` bắt buộc) nên S6 chỉ thêm engine chỉ đọc. S1 dày (khoảng mười thành phần); nếu khó duyệt thì tách theo hai bước TDD nối tiếp: S1a (hộp thư, hand-off, worker, stub) rồi S1b (principal, cổng pilot).

### S0: Xác minh nền (HITL, không code sản phẩm)

Chặn bởi: không.

- [x] **(a) Engine chỉ đọc (ĐÃ CHẠY 2026-10-13, Phụ lục A.2)** trên Postgres 16 thật (`INTEGRATION_DATABASE_URL`): `server_settings` được asyncpg chấp nhận; `INSERT`, `UPDATE`, DDL bị từ chối (SQLSTATE `25006`); `pg_sleep` quá `statement_timeout` bị hủy (`57014`); chế độ chỉ đọc còn nguyên sau commit và rollback. Đồng thời thử `postgresql_readonly` dưới READ COMMITTED để đóng điểm cảnh báo của SQLAlchemy.
- [x] **(b) arq trên Redis 7 thật, chạy trong Docker (Python 3.12; CLI arq cục bộ lỗi trên Python 3.14), ĐÃ CHẠY 2026-10-13, kết quả ở Phụ lục A.2:** tái lập các thực nghiệm của reviewer (Phụ lục A): job bị kill chặn cùng `_job_id` đến `job_timeout + 10` giây; `SIGTERM` làm job bị hủy và không chạy lại; `max_tries=1`; `_queue_name="quotify:bot"` không bị `WorkerSettings` hiện có lấy; `job_completion_wait` có trong arq 0.26.3.
- [x] **(c) Claim bằng thực nghiệm (ĐÃ CHẠY 2026-10-13, Phụ lục A.2):** tái lập thí nghiệm hai phiên trên Postgres thật cho thuật toán claim mục 4.5 (dòng 101 đang chạy rồi dòng 100 mới đến; hai phiên đua nhau nhiều vòng) để có test hồi quy cho S2.
- [x] **(d) Telegram thật** với bot dev `@HHQuotifyBot`: hành vi `sendChatAction`. **ĐÃ CHẠY 2026-10-13** với chat riêng của tài khoản bạn cung cấp và bạn đã quan sát bằng mắt (Phụ lục A.2). Lỗi 403 khi bị chặn không đo riêng cho `sendChatAction` vì lỗi của chỉ báo bị bỏ qua theo thiết kế.
- [x] **(e) Hạ tầng: BỎ QUA theo quyết định của bạn (2026-10-13, "không cần").** Việc `curl` từ VPS ra endpoint LLM và `SHOW max_connections` không còn chặn S9 (S9 chỉ dùng `StubChatEngine`, không gọi LLM); chuyển thành điều kiện bắt buộc của 2A trước khi nối LLM thật (RC-5, RC-15 vẫn **[CHƯA XÁC MINH]**).
- [x] **(f) Chạy lại baseline** (pytest, mypy, bandit, vitest) để chốt mốc hồi quy thật. **ĐÃ CHẠY 2026-10-13, kết quả ở Phụ lục A.2; phát hiện cổng chất lượng gốc không xanh sẵn (RC-26).**
- [x] **(g)** Người dùng đã trả lời các điểm ở mục 9 (2026-10-13).

Trạng thái 2026-10-13: (a) đến (d), (f), (g) đã xong, (e) bỏ qua theo quyết định của bạn; **S1 không bị chặn**. Hoàn thành khi: Phụ lục A điền đủ cho (a) đến (d) và (f); điểm nào thất bại thì sửa thiết kế (KT3, KT4, KT10) trước khi qua S1.

### S1: Tracer bullet, một tin văn bản đi hết đường (AFK)

**Trạng thái 2026-10-13: ĐÃ XONG và đã commit trên nhánh `feat/telegram-chatbot` (`25e1ff4`, `58f8c2b`), chưa merge vào `main`.** Bằng chứng ở Phụ lục A.3.

Chặn bởi: S0.

Đã xây: migration và model `bot_updates` (đã gồm cột `reply_saved_at` và chỉ mục theo người dùng, dùng cho S10); `BotInbox` (ghi hàng, claim theo mục 4.5 **đầy đủ, kể cả vòng "hết số lần thử"**, lưu và hoàn tất có rào chắn); cờ `CHATBOT_ENABLED`, `CHATBOT_PILOT_USER_EMAILS` và nhóm tham số tối thiểu; hand-off trong `TelegramUpdateService` và `TelegramUpdateRunner` (loại outbound mới `BotWakeup`, chỉ phát sau commit); `BotDispatcher` (pool lười, giới hạn 2 giây), nối cả vào poller dev và webhook; `BotPrincipal`; `BotWorkerSettings` và `drain_chat`; `StubChatEngine`; service `bot-worker` trong compose dev.

**Hoãn có chủ đích (không có tiêu chí nào của S1 cần):** service `bot-worker-test` trong compose test và việc `fake-telegram` ghi `sendChatAction` chuyển sang S4 và S8. Đường ống đã được chứng minh bằng test trên Postgres thật, bằng Docker dev (`arq`) và bằng chạy thật với bot dev.

Test đầu tiên (tracer): qua harness `bot` có sẵn (đã mở rộng để dựng runner có dispatcher), người dùng đã liên kết gửi "xin chào" khi cờ bật, đúng một dòng `queued` xuất hiện, chạy `drain_chat` một lần, hộp thư ra của Telegram giả có đúng một câu trả lời tới chat đó, dòng thành `replied` và `payload_text`, `reply_text` bị xóa.

- [x] Cờ tắt: văn bản thường vẫn trả `UNKNOWN_TEXT` và **không** ghi dòng nào. Cờ bật nhưng email ngoài danh sách thử: như cờ tắt. Người chưa liên kết và người bị khóa: không hand-off. Cờ dựng từ `Settings` thật mặc định tắt và cần cả `TELEGRAM_ENABLED` (`tests/test_bot_policy.py`).
- [x] `/start`, `/stop`, `/help`, lệnh lạ, nút bấm không hợp lệ, `my_chat_member` với cờ bật giữ nguyên đường tại chỗ; toàn bộ test Telegram có sẵn xanh nguyên. Nút duyệt giá thật chưa chạy lại với cờ bật, nhưng nhánh `callback` trả về trước mọi logic chatbot.
- [x] Webhook không bị chặn khi engine bận (test với engine bị kẹt: tin của người khác và lệnh của chính người đó vẫn được trả lời ngay), vẫn 200 khi `notify` ném lỗi, treo, hoặc việc tạo pool treo; nhiều `notify` đồng thời chỉ tạo một pool.
- [x] Lỗi DB lúc commit: `TelegramTemporaryError` (webhook trả 503), không để lại dòng hộp thư và không ghi `update_id` đã xử lý.
- [x] Quyền bị thu hồi giữa hai tin: tin sau mất quyền đó (principal nạp mới mỗi tin).
- [x] `reply_saved_at` được đặt đúng lúc lưu câu trả lời của engine (cơ sở đếm hạn mức, S10).
- [x] `bot-worker` gọi `configure_logging` khi khởi động (test với hàm giả; việc che token do lớp logging đã có test riêng).
- [x] `arq app.bot_worker.BotWorkerSettings` khởi động được (lớp độc lập, khai báo đủ thuộc tính) và `arq --check` thoát 0 khi worker sống, 1 khi không có worker (kiểm trong Docker dev); `SIGTERM` tới được arq qua dạng `exec`.
- [x] Alembic còn đúng một head; up, down, up chạy được; không lệch giữa model và migration (reviewer).
- [x] **(thêm sau rà soát)** Nội dung tin và câu trả lời không bao giờ vào log hay thông điệp lỗi khi ghi hộp thư thất bại (`BotInboxError`, test chuỗi mồi ở đường webhook và đường worker; RC-28).
- [x] **(thêm sau rà soát)** Công tắc tắt khẩn cấp ở worker: `BotWorkerConfig.enabled=False` thì `drain_chat` trả 0 và dòng ở lại `queued`.
- [x] **(thêm sau rà soát)** Danh sách thử đã đặt nhưng không có email nào thì đóng, không mở cho mọi người.
- [x] **(thêm sau rà soát)** `BotInbox` có test trực tiếp trên Postgres thật: thứ tự và một dòng sống mỗi chat, rào chắn khi lease bị tiếp quản, hết số lần thử, đồng hồ phải có múi giờ.

**Hành vi cố ý chưa làm (S2 đến S4):** dòng bị kẹt `processing` (lỗi engine, lỗi gửi tin, người dùng bị khóa) chỉ được claim lại khi có chuông sau đó, và một dòng đã commit mà chuông không rung chờ đến khi có cron quét. S3 thêm cron quét, thử lại có backoff và `failed`; S4 thêm `dropped`, chia tin, chỉ báo "đang gõ". Đây chấp nhận được khi cờ tắt mặc định.

### S2: Một dòng chạy mỗi chat (AFK)

**Trạng thái 2026-10-13: ĐÃ XONG trên nhánh `feat/telegram-chatbot`.** Bằng chứng ở Phụ lục A.4.

Chặn bởi: S1.

Test thuộc tầng integration, Postgres thật. Hai kiểu "worker đồng thời": coroutine trong một tiến trình (bài đua claim và bài `drain_chat`), và **nhiều tiến trình thật** (bài chaos, 4 tiến trình con).

- [x] Năm tin liền nhau của một chat được trả lời lần lượt đúng thứ tự `update_id`, mỗi tin xử lý đúng một lần, kể cả khi ba worker cùng tranh (`test_five_messages_of_one_chat_are_answered_in_order_once_each_by_competing_workers`: engine không bao giờ chạy hai tin cùng lúc) và bài đua claim 40 vòng.
- [x] Hai chat khác nhau chạy song song (chat chậm không chặn chat khác; khóa của chat này không chặn claim của chat kia, nhưng cùng một chat thì chờ).
- [x] Dòng đầu đang `processing` với lease còn hạn thì worker thứ hai không claim được và không nhảy cóc sang dòng sau.
- [x] **Tin đến lệch thứ tự:** chèn dòng 101, claim, rồi mới chèn dòng 100: 100 không được claim trong lúc 101 còn lease; sau khi 101 xong thì 100 được xử lý (cả hai nửa đều có assert).
- [x] Dòng `queued` đang chờ thử lại (`lease_until` tương lai) chặn cả chat, không bị bỏ qua.
- [x] Tiếp quản lease hết hạn: claim lấy lại dòng và tăng `attempts`; bốn worker đua nhau chỉ một bên thắng.
- [x] Câu `UPDATE` của claim có điều kiện `status IN ('queued','processing')` và khi trả 0 dòng thì thử lại. Có **test xác định** (khóa dòng dựng sẵn: lệnh hoàn tất của worker cũ chưa commit trong lúc claim đang chờ, rồi claim phải chuyển sang dòng kế tiếp và dòng đã xong không bị hồi sinh) và test chaos nhiều tiến trình (lease 40 ms; bản thật có 70 lần tiếp quản trên 60 dòng mà mỗi dòng hoàn tất đúng một lần).
- [x] Hàm claim trả về danh sách dòng bị chuyển `failed` (`lease_exhausted`), và câu xin lỗi chỉ gửi **sau commit** (client giả đọc DB đúng lúc gửi và thấy dòng đã `failed`): đúng chat, một câu cho mỗi lần claim dù nhiều dòng cùng hết số lần thử, lỗi gửi (người dùng đã chặn bot) không làm hỏng vòng xử lý.
- [x] Các **biến thể sai phải fail**: khóa dòng đầu hàng đợi đơn thuần, `SKIP LOCKED`, advisory lock không có điều kiện lease, không khóa không rào chắn (bài đua); khóa dòng đầu cộng kiểm tra dòng đầu (kịch bản lệch thứ tự); nhận dòng đến hạn (kịch bản backoff); nhận dòng không có điều kiện `status` (bài chaos). Mỗi biến thể phải bị bắt bằng một vi phạm bất biến thật, không tính "quá hạn". Dùng lại biến thể của `docs/quotify/analysis-chatbot-5-1/s0/pg/claimlib.py` (viết lại thành `tests/integration/bot_claim_variants.py`, chỉ dùng trong test).
- [x] **(thêm sau rà soát)** `ORDER BY update_id` được bảo vệ bằng test tắt quét chỉ mục (chỉ mục từng phần tình cờ trả về dòng đã sắp xếp nên một test chèn lệch thứ tự thông thường không phát hiện mất `ORDER BY`).
- [x] **(thêm sau rà soát)** `complete` và `save_reply` không ghi được lên dòng đã kết thúc; dòng hết số lần thử ghi đúng `error_category`, `finished_at` và xóa nội dung.

**Chuyển sang S4:** câu xin lỗi hiện **không kiểm liên kết còn hiệu lực** (người dùng đã `/stop` hay đã chặn bot vẫn nhận) và không đánh dấu `blocked` khi Telegram trả 403 cho câu xin lỗi. Khi làm S4 dùng cùng bước kiểm lần cuối trước khi gửi cho cả câu xin lỗi.

### S3: Chịu lỗi (AFK)

Chặn bởi: S1.

- [ ] Redis hỏng lúc đánh chuông: webhook vẫn 200, dòng nằm `queued`, cron `sweep_bot_updates` đánh chuông lại và tin được trả lời.
- [ ] Worker chết sau bước lưu `reply_text`, trước khi gửi: sau khi lease hết hạn, câu đã lưu được gửi lại và `FakeChatEngine` **không** bị gọi thêm.
- [ ] Worker chết **trước** khi lưu: lần thử sau gọi engine lại (đếm đúng theo `attempts`).
- [ ] `ChatEngineTemporaryError` hoặc quá `BOT_ROW_TIMEOUT_SECONDS`: dòng về `queued` với backoff; đạt `BOT_MAX_ATTEMPTS` thì `failed` kèm đúng một câu xin lỗi, `error_category` thuộc danh mục cố định, không chứa nguyên văn ngoại lệ. `ChatEngineError` thì `failed` ngay.
- [ ] **Rào chắn:** sau khi lease bị tiếp quản, lời lưu/hoàn tất của worker cũ không ghi đè; kiểm lần cuối ngăn worker cũ gửi trùng; dòng bị xóa giữa chừng không làm worker lỗi.
- [ ] **Hủy (SIGTERM):** hủy tác vụ drain giữa lúc engine chạy thì lease được nhả ngay và dòng claim lại được tức thì.
- [ ] Dòng quá `BOT_MESSAGE_TTL_SECONDS`: `dropped` (`expired`), một thông báo mỗi lần chạy drain.
- [ ] Hai tiến trình chạy cron cùng lúc không tạo xử lý trùng.

### S4: Đường gửi (AFK)

Chặn bởi: S1.

Mở rộng giả lập (hiện `Outbox` và `fake_telegram_server` không thể tạo 429 có `retry_after`, không thể làm hỏng N lần gửi đầu hay thêm độ trễ):
- [ ] Tin dài hơn 4096 ký tự được chia ở ranh giới đoạn, không phần nào quá giới hạn, đúng thứ tự; chia nhiều phần thì gửi lại tiếp từ `sent_parts`.
- [ ] Nội dung engine gửi dạng văn bản thuần (không `parse_mode`).
- [ ] Chỉ báo "đang gõ" bắt đầu trước engine, dừng sau khi xong, lỗi của nó bị bỏ qua.
- [ ] 429: chờ `retry_after` trong giới hạn `BOT_SEND_BUDGET_SECONDS`; hết ngân sách thì dừng, không để lease hết hạn lúc đang gửi.
- [ ] 403: `mark_blocked` và dòng `dropped` (`forbidden`).
- [ ] Người dùng bị khóa, hủy liên kết, hoặc liên kết thành `blocked` trong lúc tin còn chờ: dòng `dropped`, không gọi engine.
- [ ] Câu xin lỗi của S2 cũng qua bước kiểm liên kết còn hiệu lực trước khi gửi, và 403 cho câu xin lỗi cũng gọi `mark_blocked`.

### S5: Chặn lũ và tin không phải văn bản (AFK)

Chặn bởi: S1.

- [ ] Vượt `BOT_MAX_PENDING_PER_CHAT` thì trả lời lịch sự và không ghi hộp thư.
- [ ] Ảnh, tài liệu, giọng nói, sticker (cờ bật, người dùng đủ điều kiện) nhận câu cố định "hiện chỉ đọc được tin nhắn văn bản".
- [ ] Chat nhóm bị bỏ qua; `edited_message` không nhận; người chưa liên kết gõ văn bản vẫn nhận `UNKNOWN_TEXT` như hiện nay, không hand-off.
- [ ] `parse_update` mở rộng tối thiểu để nhận biết loại message, không đọc nội dung file.

### S6: Engine chỉ đọc (AFK)

Chặn bởi: S1.

- [ ] `readonly_session_factory` (tạo lười): ghi bị từ chối, truy vấn chậm bị hủy đúng hạn, làm cạn pool chỉ đọc không chặn session của API.
- [ ] `ChatTurn.readonly_session_factory` được nối vào `drain_chat`; `FakeChatEngine` thử một truy vấn đọc và một lệnh ghi (ghi bị từ chối).
- [ ] Khi `CHATBOT_ENABLED=false` không mở kết nối nào của engine chỉ đọc.
- [ ] Pool nhỏ được đặt tường minh cho cả hai engine của `bot-worker` (RC-5).
- [ ] Không công cụ nào nhận SQL hay chuỗi truy vấn tự do từ model (test kiểm danh sách công cụ đã đăng ký). Engine chỉ đọc chỉ là rào chắn (RC-27), ranh giới cứng là role chỉ-`SELECT` ở 2D.
- [ ] Kiểm xem `SET default_transaction_read_only=off` ở một kết nối có rò sang kết nối kế tiếp của pool không (đã đo là có); nếu có thì thêm bước đặt lại khi trả kết nối về pool và test kèm theo.

### S7: Quan sát (AFK)

Chặn bởi: S1.

- [ ] Gauge tính lúc scrape; `/metrics` trả đúng số liệu trên dữ liệu mẫu.
- [ ] Nhóm luật cảnh báo mới `quotify_bot_*` trong `alert_rules.yml` (tên metric khớp mã thật).
- [ ] Log có cấu trúc chỉ chứa các trường đã liệt kê.
- [ ] Test "chuỗi mồi" (10 chữ số, tiền lệ `bugPatterns.md:844`): nội dung tin và câu trả lời không xuất hiện trong log, audit hay chuỗi ngoại lệ ở mọi nhánh lỗi.

### S8: Vận hành (AFK)

Chặn bởi: S2 đến S7 và S10.

- [ ] Compose dev, prod (profile `chatbot`; `restart: unless-stopped`, `stop_grace_period` và healthcheck `arq --check` cho `bot-worker`, đã chốt; `health_check_interval` nhỏ trong `BotWorkerSettings`, vì mặc định 3600 giây làm worker chết trông khỏe một giờ), test.
- [ ] `set_webhook` nhận tham số `max_connections` và `telegram_cli set-webhook` có tùy chọn tương ứng (có test); mặc định khi đăng ký trên production là `1` (đã chốt).
- [ ] Chạy thử toàn bộ trên dev với bot dev `@HHQuotifyBot`, ghi số đo thực tế (độ trễ từ lúc nhắn đến lúc trả lời, số lần thử lại, số tin chờ) và tinh chỉnh bảng 4.8 (đã chốt làm giá trị khởi điểm).
- [ ] `.env.example` và `.env.production.example` có các biến mục 4.8 (không `${VAR:?}`).
- [ ] Runbook mục 16 (không đánh số lại 13 đến 15) gồm công tắc tắt khẩn cấp, đọc metric, đặt danh sách thử; cập nhật mọi danh sách build/recreate nêu ở mục 10.
- [ ] Script kiểm sẵn sàng riêng cho chatbot, gọi từ `check-production-readiness.sh`; `make production-readiness-check` qua.
- [ ] `CONTEXT.md` (thuật ngữ "Hộp thư bot", "Chuông", "Lease"), `memory-bank/`, journal `.agent-memory`.

### S9: Triển khai production (HITL)

Chặn bởi: S1 đến S8 và S10.

- [ ] Backup, build `backend worker bot-worker` (**không** build `frontend`: 5.1 không đổi giao diện web), migrate bằng `run --rm`, `up -d`, `restart reverse-proxy` (cờ tắt). Giao diện web không đổi; API gián đoạn vài giây lúc tạo lại `backend`, như mọi lần deploy.
- [ ] Kiểm: tính năng giá và nút duyệt giá vẫn chạy như trước; `/metrics` có nhóm `quotify_bot_*`.
- [ ] Đặt `CHATBOT_PILOT_USER_EMAILS` là email một tài khoản thử (bạn cung cấp lúc làm S9), bật cờ, khởi động `bot-worker` (`--profile chatbot`), gửi tin, thấy câu trả lời của stub, đọc metric và log.
- [ ] Với tài khoản thử, đặt tạm `BOT_DAILY_TURN_LIMIT=2`, gửi 3 tin: tin thứ 3 nhận câu từ chối kèm giờ làm mới đúng múi giờ Việt Nam; sau đó trả về giá trị thật.
- [ ] Gõ tay `/limit` bằng tài khoản thử: thấy số lượt đã dùng và còn lại đúng.
- [ ] **Tắt lại** (hoặc để cờ tắt) cho đến khi engine thật của 2A sẵn sàng. Kiểm công tắc tắt khẩn cấp hoạt động đúng quy trình runbook.
- [ ] Sau khi các mục trên đạt: đăng ký lại webhook production với `max_connections=1` (`set_webhook`), kiểm bằng `getWebhookInfo` (`pending_update_count`), xác nhận nút duyệt giá và các lệnh vẫn phản hồi. **Thao tác ngoại vi trên production: bạn đã đồng ý ở mức kế hoạch, vẫn xin xác nhận lại ngay lúc làm** (RC-24).

### S10: Hạn mức sử dụng mỗi người mỗi ngày (AFK)

Chặn bởi: S1. (Đặt số cuối vì được bổ sung sau; thứ tự làm theo sơ đồ phụ thuộc.)

Xây: `UsageGate`, `QuotaDecision`, `TurnLimitGate` (đếm lượt và file từ `bot_updates`), `BOT_DAILY_TURN_LIMIT`, `BOT_DAILY_FILE_LIMIT`, `BOT_QUOTA_WARN_REMAINING_PERCENT`; bước kiểm hạn mức trong `drain_chat` (mục 4.5, bước 4); câu từ chối và dòng nhắc trong `telegram_bot_messages.py` (tiếng Việt có dấu); gauge `quotify_bot_quota_denied`; `UsageGate.summary` và lệnh `/limit` (inline).

Test đầu tiên (tracer): người dùng đã có 20 dòng `reply_saved_at` trong ngày hôm nay gửi tin thứ 21; `FakeChatEngine` **không** bị gọi, Telegram giả nhận đúng một câu từ chối có "20/20" và giờ làm mới `00:00` ngày kế tiếp, dòng thành `dropped` (`quota_exceeded`).

- [ ] Lượt thứ 20 vẫn được trả lời; lượt thứ 21 bị từ chối; engine không bị gọi ở lượt bị từ chối.
- [ ] Lỗi engine, lượt bị từ chối và tin bị loại (`expired`, `unlinked`, `user_inactive`) **không** tính lượt; lượt đã lưu câu trả lời nhưng gửi lỗi **có** tính.
- [ ] Biên ngày theo `Asia/Ho_Chi_Minh`: tin 23:59 và tin 00:01 (UTC+7) tính vào hai ngày khác nhau, không phụ thuộc múi giờ máy chủ (đồng hồ điều khiển được; chạy ở cả hệ thống UTC và UTC+7).
- [ ] Hạn mức file riêng: còn lượt chữ nhưng hết lượt file thì tin ảnh hoặc PDF bị từ chối (dùng loại tin giả vì 2C chưa có).
- [ ] `0` là không giới hạn loại đó; hai người dùng khác nhau đếm riêng.
- [ ] Dòng đã có `reply_text` (gửi lại sau sự cố) không bị cổng chặn và không tính thêm lượt.
- [ ] Nhắc "Còn N/M lượt" xuất hiện đúng ngưỡng, không do engine sinh, và được tính trong bước chia tin (không làm câu vượt 4096 ký tự).
- [ ] `/start`, `/stop`, `/help` không bị hạn mức chặn.
- [ ] Hai tin của cùng một người gửi liền nhau khi chỉ còn 1 lượt: đúng một tin được trả lời (chứng minh tuần tự, không đua).
- [ ] Gauge `quotify_bot_quota_denied` đúng trên dữ liệu mẫu.
- [ ] `/limit` hiển thị đúng lượt chữ và lượt file đã dùng, còn lại và giờ làm mới (không hiện token); người chưa liên kết, cờ tắt hoặc ngoài danh sách thử thì như lệnh lạ. Thêm `limit` vào `BOT_COMMANDS` trong code, **không** đăng ký lên production ở lát này (làm khi bật chính thức, cần xác nhận lại).
- [ ] Người dùng có vai trò `admin` bị áp hạn mức mặc định như người khác (cổng không bypass theo tên role), trừ khi có ghi đè theo từng người (5.6).

---

## 7. Chiến Lược Kiểm Thử

Theo skill `tdd`: lát cắt dọc, một test rồi một đoạn code, test đo hành vi qua giao diện công khai.

- **Giả lập chỉ ở ranh giới hệ thống:** HTTP Telegram (`Outbox` và `fake_telegram_server` có sẵn, cần mở rộng cho 429, lỗi N lần đầu, độ trễ), arq và Redis (bên gửi giả trong unit test, Redis thật ở S0 và S3), LLM (`FakeChatEngine`). **Không** giả lập `BotInbox` hay Postgres cho logic claim, lease, rào chắn: các test đó thuộc tầng `integration` với Postgres thật (đã có `INTEGRATION_DATABASE_URL` và marker `integration`). Lý do: test với session giả từng che lỗi thật nhiều lần (bài học `MissingGreenlet`, drift của `FakeSession`).
- **Harness cần mở rộng:** fixture `bot` trong `tests/integration/conftest.py` dựng runner **không có dispatcher**, và `tests/integration/bot_harness.py` chưa biết hộp thư. Cả hai nằm trong phạm vi S1.
- **Hồi quy bắt buộc từ S1:** nhóm test Telegram hiện có (`test_telegram_update_runner.py`, `test_telegram_webhook_api.py`, `test_telegram_poller.py`, các test tích hợp `test_telegram_*_db.py`, `test_price_alert_callback_db.py`) phải xanh nguyên, không sửa kỳ vọng.
- **Đồng thời:** S2 cần hai worker thật; tránh test dựa vào `sleep`. Thời gian dùng tham số `now` truyền vào.
- **E2E:** chạy bằng `make docker-test-e2e`, thêm một spec "người dùng liên kết nhắn tin, nhận câu trả lời của stub" trong stack test với `fake-telegram` và `bot-worker-test`. Không chạy Playwright rời. Đóng lát bằng kiểm chứng thật qua `curl` hoặc bot dev, không kết luận chỉ từ unit test. Spec e2e mới phải lấy URL cookie từ `baseURL`, không gắn cứng `127.0.0.1:4173` như 6 spec 1C và 1D đang lỗi sẵn trong Docker (Phụ lục A.2).
- **Mốc so sánh:** lấy bảng ở Phụ lục A.2, không lấy con số cũ trong `memory-bank/`. Các cổng gốc không xanh sẵn (RC-26) nên **so danh sách test fail và số lỗi với bảng đó**: pytest không có test fail mới ngoài 6 âm tính giả đã biết (hoặc chạy pytest trên host), `mypy app` không quá 15, ruff không quá 62, bandit không quá 17, ESLint không quá 69, vitest đúng 4 lỗi cũ (`--maxWorkers=4`), e2e Docker không có spec fail mới ngoài 31 spec đã biết.
- Thời gian trong test dùng múi giờ rõ ràng (`Asia/Ho_Chi_Minh`); không dùng "hôm nay" cứng. Biên ngày của hạn mức (S10) phải có test tại 23:59 và 00:01 giờ Việt Nam, chạy với cả hai múi giờ hệ thống UTC và UTC+7 (Rule 12 của `docs/agent-rules.md`).

---

## 8. Rủi Ro

| # | Rủi ro | Cách xử lý |
|---|---|---|
| RC-1 | Hand-off đụng đường webhook mà 1A đến 1D đang dùng ở production, dễ làm vỡ nút duyệt giá và `/start` | KT1; cờ tắt thì hành vi y hệt; test hồi quy bắt buộc ở S1; không đổi deadline 4 giây |
| RC-2 | Một dòng treo chặn cả chat (đầu hàng đợi) | Lease, `BOT_MAX_ATTEMPTS`, trạng thái kết thúc `failed`; trần số tin chờ mỗi chat |
| RC-3 | Ngữ nghĩa arq (khóa job mồ côi, `SIGTERM`, `keep_result=0`) | Đã đo ở S0(b) trong Docker (Phụ lục A.2); thiết kế đã đổi (KT3, KT7, KT18). Còn lại một điểm chưa kiểm: lệnh dev `sh -lc "uv sync && uv run arq ..."` có truyền `SIGTERM` tới arq không (prod dùng dạng exec đã kiểm) |
| RC-4 | Câu trả lời có thể trùng (at-least-once) | Chấp nhận, ghi rõ; thu hẹp bằng lưu trước khi gửi, `sent_parts`, kiểm lần cuối và rào chắn |
| RC-5 | Cạn kết nối Postgres: mỗi tiến trình bot có hai engine, mặc định 5 + 10 kết nối cho engine chính. `max_connections` của production **[CHƯA XÁC MINH]** | Bỏ qua kiểm `max_connections` theo quyết định 2026-10-13 (chuyển thành điều kiện của 2A); đặt `pool_size` nhỏ tường minh cho cả hai engine của worker bot (cần sửa `app/db/session.py`); không giữ kết nối trong lúc gọi LLM |
| RC-6 | PII nằm lại trong DB và backup (`payload_text`, `reply_text`) | Xóa nội dung ngay khi dòng kết thúc (mọi trạng thái); dòng chưa kết thúc giữ nội dung đến khi xong hoặc bị loại; dọn dòng cũ hằng ngày; chính sách lưu giữ hội thoại đầy đủ thuộc 5.4 |
| RC-7 | Redis chỉ có snapshot mặc định (có thể cũ), không mật khẩu | KT3: không lưu trạng thái nào ở Redis; **không** đổi Redis sang có mật khẩu khi chưa sửa worker (RR-18) |
| RC-8 | Worker không tự reload code, dễ chạy code cũ sau khi sửa | Runbook và `Makefile` nhắc restart; thêm `bot-worker` vào mọi danh sách build/recreate (nguy cơ chạy image cũ) |
| RC-9 | Webhook mất deadline ngầm nếu ai đó bỏ hand-off; hoặc Redis nửa chết làm treo webhook | Test "webhook trả 200 trước khi engine xong" và "notify treo quá 2 giây" ở S1; `notify` luôn có `wait_for` |
| RC-10 | Người dùng chặn bot khi tin còn chờ | S4: 403 thì `mark_blocked` có sẵn và `dropped`, không thử lại vô hạn; dòng của liên kết `blocked` bị loại khi claim |
| RC-11 | Khóa `session`/`token` bị che trong audit; `content` đang cho phép | KT14; không audit nội dung; nếu cần audit sau này (2B) đặt tên khóa tránh các từ bị che |
| RC-12 | Luật cảnh báo cũ còn tên `fastapivue_*`, không khớp metric thật | Không sửa lan (RR-19); nhóm luật mới dùng `quotify_bot_*` |
| RC-13 | Chuỗi người dùng nhìn thấy thiếu dấu tiếng Việt | Mọi chuỗi mới nằm ở `telegram_bot_messages.py`, tiếng Việt có dấu (Rule 21), có test kiểm |
| RC-14 | K15: liên kết hiện không có bước xác nhận trong chat; ai có đường dẫn liên kết trong 10 phút gắn được Telegram vào tài khoản người khác, và đường ống này cho phép hỏi dữ liệu nhân danh tài khoản đó | Đường ống chỉ **đọc**, và dữ liệu giá vốn đã hiển thị cho mọi người có `quotes.read` trên web, nên rủi ro bị giới hạn. Bước xác nhận vẫn là **điều kiện chặn** của việc ghi dữ liệu ở 2B |
| RC-15 | Production không ra được endpoint LLM (VPS đã không ra được Docker Hub) | Bạn đã quyết không kiểm ở S0 (2026-10-13); **chuyển thành điều kiện bắt buộc trước khi nối LLM thật ở 2A**; không chặn S1 đến S10 |
| RC-16 | Thay đổi chạm `TelegramUpdateService` đang lớn dần | Giữ phần hand-off trong một hàm nhỏ, tách module `bot_inbox.py`, `bot_dispatcher.py`, `bot_worker.py`; tránh sửa lan các nhánh hiện có |
| RC-17 | Telegram giao tin lệch thứ tự: webhook không đặt `max_connections` (mặc định 40) nên các request song song; webhook trả 503 rồi Telegram gửi lại làm tin N đến sau N+1 | Claim chỉ bảo đảm "một dòng chạy mỗi chat" (cứng), còn thứ tự là nỗ lực tốt nhất; đã chốt đặt `max_connections=1` ở S8 và S9, xem RC-24 cho mặt trái |
| RC-18 | Deploy giữa lúc đang xử lý làm kẹt chat đến hết lease | KT18 (nhả lease khi hủy, `stop_grace_period`); S3 có test hủy |
| RC-19 | Cửa sổ chuông hẹp: dòng mới commit đúng lúc job cũ vừa thấy hàng rỗng | Mỗi tin có chuông riêng (`_job_id` theo update) và cron quét bù; chấp nhận độ trễ tối đa khoảng một phút trong trường hợp hiếm |
| RC-20 | Worker chậm bị tiếp quản lease rồi ghi đè hoặc gửi trùng | KT16 (rào chắn theo `attempts` và kiểm lần cuối) |
| RC-21 | Một lượt vượt hạn mức token vì cổng chỉ biết số đã dùng **trước** lượt (tool loop nhiều lần gọi LLM, kết quả công cụ lớn, file) | Trần mỗi lượt là yêu cầu bắt buộc của 5.2 và 5.5 (số vòng công cụ, `max_tokens`, kích thước kết quả); chốt chặn token theo ngày; trần ngân sách tháng ở 5.6 là chốt cuối |
| RC-22 | Đếm lệch ngày vì múi giờ (UTC so với giờ Việt Nam), tin gần nửa đêm | KT21; biên ngày tính ở Python rồi đổi sang UTC; test 23:59 và 00:01 ở hai múi giờ hệ thống (S10) |
| RC-23 | Hạn mức đặt sai: quá chặt thì chặn nhầm người dùng, `0` (không giới hạn) đặt nhầm thì mất chốt chặn theo người | Mặc định 20 lượt và 5 file; trần tháng ở 5.6 vẫn là chốt cuối; gauge `quotify_bot_quota_denied`; trang cấu hình ở 5.6 cảnh báo khi giá trị bất hợp lý |
| RC-24 | `max_connections=1`: Telegram giao một update tại một thời điểm, nên một request webhook chậm làm mọi update khác (kể cả nút duyệt giá, hạn khoảng 15 giây) xếp hàng phía sau | Webhook không còn gọi LLM (hand-off); lệnh và nút bấm chỉ dùng DB và có deadline 4 giây; theo dõi `getWebhookInfo.pending_update_count` sau khi đặt; hoàn tác bằng cách đăng ký lại webhook với giá trị mặc định (thao tác ngoại vi, xin xác nhận) |
| RC-25 | Vì không dùng nhánh dài hạn, các lát đã vào `main` trước S9 sẽ được **bất kỳ** lần `git pull` deploy nào mang lên production (kể cả hotfix không liên quan): code hand-off (cờ tắt) và migration `bot_updates` | Mọi lát phát hành tắt và additive; test hồi quy ở S1 chứng minh cờ tắt thì hành vi y hệt; migration chỉ thêm bảng; lát nào chưa đủ tin cậy thì chưa merge vào `main` |
| RC-26 | Các cổng chất lượng gốc của repo không xanh sẵn (S0(f)): `make docker-test-backend` có 6 âm tính giả nên không bao giờ tới ruff, mypy, bandit; `mypy .` dừng vì trùng tên module; `make docker-test-frontend` dừng ở ESLint (12 lỗi cũ); vitest mặc định treo khi máy thiếu bộ nhớ; e2e Docker 31 trên 40 spec fail. Dễ che lỗi mới hoặc báo lỗi giả | Dùng bảng baseline ở Phụ lục A.2: so **danh sách test fail** thay vì kỳ vọng xanh, chạy pytest trên host cho 6 test đọc file ngoài `backend/`, dùng `mypy app`, vitest với `--maxWorkers=4`; spec e2e mới của chatbot lấy URL cookie từ `baseURL`. Ghi nợ, không sửa lan trong phạm vi chatbot |
| RC-27 | Engine DB chỉ đọc chỉ là rào chắn: một câu `SET default_transaction_read_only=off` hoặc `SET TRANSACTION READ WRITE` tắt được chế độ chỉ đọc, cài đặt đó rò sang kết nối dùng lại trong pool (cả `SET statement_timeout=0`), và `pg_advisory_lock` mức phiên vẫn được phép (đo ở S0(a)) | Không công cụ nào nhận SQL hay chuỗi truy vấn tự do từ model (5.2); test ở S6; kiểm xem cần đặt lại cài đặt khi trả kết nối về pool không; ranh giới cứng là role chỉ-`SELECT` ở 2D |
| RC-28 | Thông điệp ngoại lệ của SQLAlchemy kèm **tham số của câu lệnh lỗi**, tức nội dung tin hay câu trả lời (reviewer tái hiện với ký tự NUL), và log lỗi hoặc log của arq in ra | Mọi lệnh DB mang nội dung bọc `BotInboxError` không chứa tham số (S1, có test chuỗi mồi ở cả đường webhook và đường worker); `repr` của `ChatTurn`, `ClaimedRow`, `BotPrincipal` che nội dung; S7 mở rộng sang mọi nhánh lỗi. Chưa đặt `hide_parameters` ở engine chung vì đổi hành vi toàn ứng dụng |
| RC-29 | Test đua và chaos dễ **xanh giả** hoặc **chập chờn**: lần chạy đầu của bài chaos chỉ có 5 lần tiếp quản trên 120 dòng (trải 4 tiến trình trên 24 chat nên hiếm khi tranh cùng một chat) và biến thể sai chỉ bị bắt 1 trong 3 lượt; sau rà soát còn 6 đột biến trên code thật mà bộ test không bắt được | Tập trung tranh chấp vào vài chat (70 lần tiếp quản trên 60 dòng) kèm sàn `takeovers >= 10` trong test; mọi biến thể sai phải bị bắt đúng bằng một vi phạm thật (không tính quá hạn); thêm test xác định cho các lớp bảo vệ mà chaos chỉ che xác suất; mọi chờ đều có thời hạn và tiến trình con luôn bị kill; URL có mật khẩu không làm tham số test |

---

## 9. Quyết Định Của Bạn Và Điểm Còn Mở

**Đã chốt bởi bạn (2026-10-13), hạn mức sử dụng mỗi người mỗi ngày (mục 4.11):**
- Hướng kết hợp **lượt hỏi, lượt dùng file và token** (lượt là hạn mức hiển thị, token là chốt chặn). Mặc định ban đầu **20 lượt và 5 lượt file mỗi ngày**; hạn mức token đặt sau khi đo chi phí thật.
- **Admin cấu hình hạn mức theo từng người** ở 5.6 (thường nâng cho vai trò trưởng phòng). Câu hỏi trước của tôi gộp thêm việc quản trị viên có bị áp hạn mức không; bạn không nói khác, nên tôi giữ cách hiểu **quản trị viên không được miễn**: chịu cùng mặc định, muốn khác thì ghi đè theo người. Nếu hiểu sai xin báo lại.
- **Lệnh `/limit`** để người dùng xem số lượt còn lại (trong phạm vi S10). Việc đăng ký lệnh vào menu bot trên production vẫn cần xác nhận lại lúc bật chatbot chính thức.

**Đã chốt bởi bạn (2026-10-13), sáu điểm mở của bản nháp:**

| # | Điểm | Quyết định |
|---|---|---|
| 1 | Lưu tạm nội dung tin trong `bot_updates` | **Có** (xóa ngay khi dòng kết thúc) |
| 2 | Cổng bật dần | Dùng `CHATBOT_PILOT_USER_EMAILS`. Email tài khoản thử do bạn cung cấp lúc làm S9 |
| 3 | `restart: unless-stopped`, `stop_grace_period`, healthcheck `arq --check` cho `bot-worker` | **Đồng ý** |
| 4 | `set_webhook` với `max_connections=1` | **Đồng ý.** Thực hiện ở S9; xin xác nhận lại lúc làm vì là thao tác ngoại vi (RC-24) |
| 5 | Bảng tham số mục 4.8 | **Đồng ý** làm giá trị khởi điểm; chạy thử trên dev rồi tinh chỉnh (S8) |
| 6 | Kiểm VPS ra endpoint LLM và `max_connections` của Postgres (S0(e)) | **Không cần.** Không còn chặn S9; trở thành điều kiện của 2A (RC-5, RC-15) |

**Đã chốt bởi bạn (2026-10-13), cách đưa code lên:** bỏ ý định dùng nhánh dài hạn riêng cho toàn bộ Bước 2; làm theo kế hoạch (mục 6, quy trình git). Lý do của bạn: lo đẩy sớm lên production ảnh hưởng giao diện web, trong khi 5.1 gần như chỉ đổi backend. Các bước cần lên production (S9 trở đi) vẫn đưa lên theo kế hoạch.

**Đã quyết theo bằng chứng (nêu để bạn phản đối nếu không đồng ý):**
- **KT4:** thay "Redis lock theo chat" của mục 5.1 bằng claim trong Postgres. Khóa Redis không đảm bảo thứ tự, chưa có tiền lệ trong repo; thuật toán claim đã được thử nghiệm.
- **KT6:** `BotWorkerSettings` ở `app/bot_worker.py` thay vì `app/worker.py` (test ghim `WorkerSettings`, sự cố import vòng sau deploy 1D).
- **Production dưới profile `chatbot`:** đã kiểm `build` đích danh và `up` thường.
- **Phạm vi:** 5.1 chỉ là đường ống với `StubChatEngine`. Mục 3, dòng 7 đến 11, là các điểm cần sửa ở kế hoạch 5.2 và 5.4.

**Điểm còn mở:**
- Email tài khoản thử cho S9 (bạn cung cấp lúc làm S9).
- Xác nhận lại ngay lúc làm hai thao tác ngoại vi: đăng ký lại webhook với `max_connections=1` (S9) và đăng ký `/limit` vào menu bot (khi bật chatbot chính thức, 2A).
- Quản trị viên không được miễn hạn mức: diễn giải của tôi, chờ bạn xác nhận nếu sai.
- Chi phí thật mỗi lượt và hạn mức token: đặt sau khi đo (5.5, 5.6).

---

## 10. Tập Tin Sẽ Chạm Vào

**File mới, backend (dự kiến):**
- `alembic/versions/2026MMDD_HHMM_create_bot_updates.py` (đặt `down_revision` bằng head tại thời điểm làm; hiện là `20261007_0900`)
- `app/models/bot_update.py`, `app/schemas/bot.py` (nếu cần)
- `app/services/bot_inbox.py`, `app/services/bot_dispatcher.py`, `app/services/bot_principal.py`, `app/services/bot_reply_sender.py`, `app/services/chat_engine.py` (cổng, hai loại lỗi, `StubChatEngine`), `app/services/bot_usage_gate.py` (`UsageGate`, `TurnLimitGate`)
- `app/bot_worker.py` (`BotWorkerSettings`, `drain_chat`, `sweep_bot_updates`, `cleanup_bot_updates`)
- `app/db/readonly.py`
- `app/core/bot_metrics.py` (theo mẫu `price_alert_metrics.py`)
- `scripts/compliance/check-chatbot-readiness.sh`
- Test: `tests/test_bot_*.py`, `tests/integration/test_bot_*_db.py`; mở rộng `tests/telegram_fakes.py`, `tests/integration/conftest.py`, `tests/integration/bot_harness.py`, `scripts/fake_telegram_server.py` (ghi `sendChatAction`, hỗ trợ 429, lỗi N lần đầu, độ trễ)

**File hiện có chỉ sửa tối thiểu:**
- `app/services/telegram_update_service.py`, `app/services/telegram_update_runner.py` (nhánh hand-off, loại outbound mới), `app/services/telegram_bot_messages.py` (chuỗi mới), `app/services/telegram_link_service.py` (trả thêm email nếu chọn cách đó cho cổng pilot)
- `app/integrations/telegram.py` (`send_chat_action`; `set_webhook` thêm `max_connections`)
- `app/telegram_cli.py` (`BOT_COMMANDS` thêm `limit`; `set-webhook` thêm tùy chọn `max_connections`; sửa cả dòng thông báo liệt kê lệnh đã đăng ký, hiện ghi cứng "/start, /stop, /help")
- `app/api/v1/telegram.py`, `app/telegram_poller.py` (nối `BotDispatcher`, bắt buộc), `app/core/application.py` (đóng pool arq của bên gửi khi tắt)
- `app/db/session.py` (pool tường minh cho engine của worker bot)
- `app/core/config.py`, `app/models/__init__.py`, `app/db/base.py`, `.env.example`, `.env.production.example`
- `docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.test.yml`, `docker/observability/alert_rules.yml`
- `docs/runbooks/deploy-vps-production.md`: thêm mục 16; cập nhật danh sách build và recreate tại §3 (dòng 188), §9.4 (394-398), §9.7 (426), §12.8 (768), §13 (843, 853, 887), §14 (901, 912, 914, 939), §15 (950, 961, 963, 993, 995-1016)
- `scripts/compliance/check-production-readiness.sh` (gọi script mới)
- `CONTEXT.md`, `memory-bank/activeContext.md`, `memory-bank/progress.md`, `memory-bank/systemPatterns.md`, `memory-bank/bugPatterns.md` (khi có bug mới)

**Không sửa:** `app/worker.py`, `create_job_queue`, `quotes.py`, `quote_service.py`, các service báo giá và dashboard.

---

## 11. Phụ Lục A: Kết Quả Thực Nghiệm

### A.1 Thực nghiệm của reviewer độc lập (2026-10-13, ngoài S0)

Do agent rà soát chạy trên Postgres 16 và Redis 7 tạm (đã xóa sạch sau khi chạy), chưa được tôi tái lập; S0(b), S0(c) chạy lại trong Docker.

| Câu hỏi | Kết quả |
|---|---|
| Claim "khóa dòng đầu hàng đợi" đơn thuần, dòng 101 đang chạy rồi dòng 100 mới commit | **Sai:** worker thứ hai nhận dòng 100, hai dòng chạy cùng lúc |
| Claim có advisory lock theo giao dịch + điều kiện "không có dòng `processing` còn lease" | Đúng: 300 vòng đua nhau, 0 vi phạm |
| Bỏ điều kiện trạng thái/lease khỏi câu `UPDATE` | Hai phiên cùng claim dòng 1 (`attempts=2`) |
| `FOR UPDATE SKIP LOCKED` | Worker thứ hai claim dòng 2 trong lúc dòng 1 đang `processing`: cấm |
| arq 0.26.3 sau `SIGKILL`, cùng `_job_id` | `enqueue_job` trả `None` đến `job_timeout + 10` giây (đo được 16,1 giây với `job_timeout=6`, tương đương khoảng 310 giây ở production, và đến 24 giờ nếu không có worker nào chạy; đo lại ở A.2); job mồ côi bị báo hết số lần thử, hàm không chạy lại |
| arq 0.26.3 sau `SIGTERM` | Job bị hủy (`CancelledError` tính là retryable vì `retry_jobs=True`); khóa "đang chạy" của arq bị xóa còn khóa job thành mồ côi; worker khởi động lại báo hết số lần thử và không chạy lại hàm (đo lại ở A.2) |
| `docker compose build bot-worker` với service trong profile không kích hoạt | Có build khi gọi đích danh; `up` thường bỏ qua |
| CLI `arq` trong `.venv` cục bộ | Lỗi `get_event_loop` trên Python 3.14; image Docker (3.12) không bị |

### A.2 Kết quả S0

Do các agent chạy ngày 2026-10-13; tôi chưa tái lập các con số. Mỗi agent dùng container riêng (`s0-*`), không đụng stack dev và production.

**S0(b), arq 0.26.3 trong Docker.** Image `quotify-backend:latest` (Python 3.12.12, arq 0.26.3, redis-py 5.3.1) với `redis:7-alpine` (7.4.11) riêng; arq chạy dạng exec như production.

| Kiểm tra | Kết quả |
|---|---|
| `_job_id` trùng | `None` khi đang chờ hoặc đang chạy. `keep_result=0`: dùng lại id ngay sau khi xong (kể cả job lỗi). Mặc định 3600 giây: id bị chặn 1 giờ |
| id khác nhau | Chạy song song được (ba job cùng bắt đầu trong 1 ms khi `max_jobs` đủ lớn) |
| `SIGKILL`, `job_timeout=6`, `max_tries=1` | Khóa "đang chạy" hết hạn ở lúc bắt đầu job + 16 giây; khóa job sống 24 giờ. Có worker sống thì job mồ côi bị báo "max retries exceeded", **hàm không chạy lại**, cùng id dùng lại được sau 16,1 giây. Không có worker nào chạy thì cùng id bị chặn đến 24 giờ. Id khác chạy bình thường (0,07 giây) |
| `SIGTERM` | Job nhận `CancelledError` sau khoảng 20 ms; khối dọn bọc `asyncio.shield` (1 giây) chạy xong trước khi thoát; `docker stop` trả về sau khoảng 3 giây. Khóa "đang chạy" bị xóa, khóa job và mục retry còn lại; worker khởi động lại báo hết số lần thử và không chạy lại hàm |
| `retry_jobs=False` và `SIGTERM` | Khối dọn vẫn chạy, log ERROR kèm traceback `CancelledError`, **không còn khóa nào**, id dùng lại ngay |
| `job_completion_wait` | Có trong 0.26.3 (số nguyên, mặc định 0): chờ tối đa N giây cho job đang chạy rồi mới hủy. Nếu `docker stop -t` ngắn hơn thì bị `SIGKILL` (khóa "đang chạy" còn lại, id kẹt) |
| `job_timeout` hết hạn | Hàm nhận `CancelledError`, khối dọn chạy, job thất bại `TimeoutError`, không để lại khóa |
| Cách ly hàng đợi | Worker mặc định chỉ lấy hàng đợi mặc định, worker `quotify:bot` chỉ lấy `quotify:bot`; `create_pool(default_queue_name=...)` đúng; khóa sức khỏe tách riêng; không gian `arq:job:<id>` dùng chung |
| `create_pool` khi Redis tắt | `ConnectionError` sau 5,0 đến 5,4 giây; địa chỉ không phản hồi: `TimeoutError` sau 11 giây; `conn_retries=0`: 0,06 giây. Ngoại lệ thuộc thư viện `redis` |
| Redis `pause` (nửa chết) | `wait_for(enqueue_job, 2)` bị cắt đúng 2 giây (4 lần liên tiếp), pool vẫn dùng được sau khi Redis chạy lại, job bị hủy không vào Redis. **`create_pool` mới thì treo vô hạn** (còn treo ở 8 giây) |
| `arq --check` | Thoát 1 khi không có worker, 0 khi sống; sau `SIGTERM` thoát 1 ngay; sau `SIGKILL` vẫn thoát 0 đến hết TTL = `health_check_interval + 1` giây (mặc định 3600 giây, khoảng 1 giờ); sau `FLUSHALL` báo hỏng đến lần ghi kế tiếp |
| `keep_result=0` + `max_tries=1` + `queue_name` | Sau 55 job chỉ còn khóa sức khỏe |
| Kế thừa `WorkerSettings` | Lớp con không thừa hưởng gì (arq đọc `cls.__dict__`): `arq <module>.Child` báo "at least one function or cron_job must be registered" |

Chưa kiểm: lệnh dev `sh -lc "uv sync && uv run arq ..."` có truyền `SIGTERM` tới arq không (production dùng dạng exec, đã kiểm). Một container worker trong lúc đo health check ngừng ghi khóa sức khỏe mà không rõ nguyên nhân (không tái hiện sau ba lần chạy lại).

**S0(f), baseline cổng chất lượng (HEAD `7eb64e9`).**

| Chỉ số | Hiện tại | Ghi chép cũ | Giống? |
|---|---|---|---|
| pytest | 1.281 pass, 6 fail, 1 skip, 0 lỗi (1.288 test) | 1.250 pass (`progress.md:289`) | Không |
| Tầng integration | 428 test chạy và qua, không skip (dùng `DATABASE_URL` của `postgres-test`; compose test không đặt `INTEGRATION_DATABASE_URL`) | chưa ghi | Không áp dụng |
| ruff | 62 (51 E501) | 61 | Hơn 1 E501 (`audit_log_admin.py`, commit `5cecbea`) |
| mypy `.` | dừng: "Duplicate module named conftest" | 13 | Không áp dụng |
| mypy `app` | 15 lỗi ở 6 file (11 do thiếu `types-openpyxl`) | 13 | Hơn 2 (`audit_log_admin.py:124-125`, commit `5cecbea`) |
| bandit | 17 (16 low, 1 medium) | 16 | Hơn 1 (đã là 17 ở `5b9d4fb`) |
| vitest | 468 test, 464 pass, 4 fail (`--maxWorkers=4`) | 4 fail | Đúng 4 lỗi cũ, số test tăng |
| ESLint | 69 (12 lỗi, 57 cảnh báo) | 69 | Giống |
| vue-tsc | 0 | 0 | Giống |
| Prettier | 86 file | 74 | Hơn 12 |
| e2e Docker | 9 pass, 31 fail trên 40 | 9 pass, 4 fail | Không |

- **6 test pytest fail là âm tính giả:** `test_price_alert_alert_rules.py` (6 test) đọc `docker/observability/alert_rules.yml`, `scripts/compliance/*.sh`, `docs/runbooks/...` mà image backend-only không có. Trên host cả hai file test qua (12 pass). Một test bị skip (`test_permission_inventory.py:69`) cùng lý do. Hệ quả: `make docker-test-backend` **không bao giờ xanh** và không đi tới ruff, mypy, bandit.
- **e2e:** 31 fail gồm 4 lỗi cũ (`audit-logs.spec.ts:47`, `quote-detail-filters.spec.ts:31`, `smoke.spec.ts:3`, `suppliers.spec.ts:30`) và 27 lỗi của 6 spec 1C và 1D (alert-preferences 4, material-freshness 7, price-alert-anomalies 3, price-alert-settings 9, quote-price-alert-status 1, users-page-layout 3), đều gắn cứng URL cookie `http://127.0.0.1:4173` trong khi `baseURL` Docker là `http://frontend-e2e:4173`. Tôi chưa chạy chúng trên host để xác nhận.
- **vitest:** lệnh gốc `npx vitest run --coverage` treo hai lần ("Failed to start forks worker") khi máy tải cao; dùng `--maxWorkers=4`. Bốn test fail: `audit-logs.page.spec.ts` (nhóm điều hướng sidebar) và ba test trong `useQuotifySettingsPage.spec.ts`.
- **Thời gian:** `make docker-test-backend` 265 giây (pytest 236 giây), `make docker-test-frontend` 25 giây (dừng ở ESLint), vitest 24 giây, e2e 429 giây.

Lệnh tái hiện (từ thư mục gốc): `make docker-test-backend` (pytest); `docker compose -f docker-compose.test.yml run --no-deps --rm backend-test sh -lc '.venv/bin/ruff check .; .venv/bin/mypy app --cache-dir=/dev/null; .venv/bin/bandit -c pyproject.toml -s B104 -r app'`; `cd backend && .venv/bin/pytest tests/test_price_alert_alert_rules.py tests/test_permission_inventory.py -o addopts="" -p no:cacheprovider` (6 test trên host); `make docker-test-frontend` (ESLint); `docker compose -f docker-compose.test.yml run -T --no-deps --rm frontend-test sh -lc 'npm install >/dev/null 2>&1; npx vitest run --coverage --maxWorkers=4'`; `make docker-test-e2e`.

**S0(a), engine DB chỉ đọc** (Postgres 16.14 tạm, asyncpg 0.31.0, SQLAlchemy 2.0.50):

| Kiểm tra | Kết quả |
|---|---|
| Đọc, ghi | `SELECT` chạy; `INSERT`, `UPDATE`, `DELETE`, `CREATE TABLE`, bảng tạm, `SELECT ... FOR UPDATE` và `FOR SHARE` đều bị từ chối (`ReadOnlySQLTransactionError`, 25006); `AsyncSession` ORM giống vậy |
| `statement_timeout` | `pg_sleep(7)` bị hủy đúng 5,00 giây (`QueryCanceledError`, 57014); kết nối dùng lại được sau `rollback()` (không rollback thì lỗi 25P02) |
| Cài đặt còn hiệu lực | Giữ nguyên sau commit, sau rollback, qua 6 lần lấy kết nối lần lượt từ pool |
| `idle_in_transaction_session_timeout` | Server cắt phiên; SQLAlchemy báo `InterfaceError` bọc lỗi asyncpg `connection is closed`, `connection_invalidated=True`, kết nối kế tiếp là kết nối mới. SQLSTATE 25P03 chỉ thấy ở log server |
| `postgresql_readonly` dưới READ COMMITTED | **Chạy được** (`transaction_read_only=on`, `iso=read committed`, ghi bị từ chối), không lỗi, không cảnh báo; asyncpg 0.31 phát `BEGIN READ ONLY` ở mọi mức cô lập. Đặt sau khi giao dịch đã bắt đầu thì `InvalidRequestError`. Cảnh báo trong tài liệu SQLAlchemy là lỗi thời |
| Pool tách biệt | Giữ 3 kết nối chỉ đọc thì kết nối thứ 4 hết hạn sau 2,00 giây (`TimeoutError`), engine chính vẫn phục vụ trong 0,023 giây; chiều ngược lại cũng đúng |
| **Không phải ranh giới bảo mật** | `SET TRANSACTION READ WRITE` rồi `INSERT` thành công; `SET default_transaction_read_only=off; COMMIT` cho phép `INSERT` sau đó và cài đặt **rò sang kết nối kế tiếp trong pool**; `SET statement_timeout=0` rò tương tự; `pg_advisory_lock` mức phiên vẫn được phép |

**S0(c), thuật toán claim** (mục 4.5):

| Kiểm tra | Kết quả |
|---|---|
| Đua đồng thời, 5 dòng mỗi vòng | **Đạt:** 400 vòng với 2, 3, 4 bên claim bằng asyncio và bằng tiến trình thật, cộng các lần chạy với thứ tự đến bị xáo trộn: 0 vi phạm, mỗi dòng claim đúng một lần theo thứ tự, `attempts=1` |
| Tin đến lệch thứ tự | **Đạt:** claim 101 xong, chèn 100: 100 không claim được ở +1 giây và +2 giây; claim được sau khi 101 hoàn tất |
| Tiếp quản lease hết hạn | **Đạt:** `attempts` 1, 2, 3; ở lần thứ 3 dòng thành `failed/lease_exhausted`, nội dung bị xóa, và cùng lời gọi claim tiếp dòng 2 |
| Backoff chặn dòng sau | **Đạt:** dòng `queued` có `lease_until` tương lai khiến claim trả rỗng dù dòng 2, 3 đang chờ |
| Ghi có rào chắn | **Đạt:** worker cũ ghi lưu, đưa lại hàng đợi, hoàn tất đều trả 0 dòng; chủ sở hữu trả 1. Chaos run (lease 40 ms, 4 tiến trình, 1.500 dòng): 2.062 lần tiếp quản, 2.062 lần hoàn tất của worker cũ trả 0, mỗi dòng hoàn tất đúng một lần |
| Biến thể sai **phải fail** | **Đạt (chúng đều fail):** khóa dòng đầu đơn thuần 300/300 vòng có hai dòng cùng chạy (kể cả không lệch thứ tự); advisory lock không có điều kiện lease 300/300; `SKIP LOCKED` 300/300 và hỏng thứ tự khoảng 255 vòng; không khóa không rào chắn 30/30 (2.559 lần claim cho 150 dòng); "khóa dòng đầu cộng kiểm tra dòng đầu" qua bài đua thuần (600 vòng) nhưng **hỏng khi tin lệch thứ tự**; "nhận dòng tiếp theo đến hạn" claim dòng 2 trong lúc dòng 1 đang backoff; nhận dòng không có điều kiện `status` làm 64 dòng bị hồi sinh |
| Các chat độc lập | **Đạt:** chat 32 claim trong 9,6 ms khi khóa của chat 31 đang bị giữ; 500 chat claim trong 0,4 đến 0,75 giây; 2 triệu `chat_id` cho 2 triệu khóa `hashtextextended` khác nhau |
| EXPLAIN, 200.000 dòng đã đóng + 2.000 dòng mở, 500 chat | **Đạt:** truy vấn chọn dòng đầu dùng `ix_bot_updates_chat_open`: 0,013 ms, 3 buffer (đối chứng không có chỉ mục riêng: 28,5 ms, lọc 200.000 dòng); kiểm lease còn hạn 0,05 đến 0,10 ms; nhận dòng theo khóa chính 0,33 ms |
| Truy vấn hạn mức (mục 4.11) | **Đạt:** dùng `ix_bot_updates_user_received`: 0,36 ms với người có 16.900 dòng; dạng `received_at::date` mất 28,7 ms và không dùng được chỉ mục |
| Biên ngày giờ Việt Nam | **Đạt:** cận Python cho ngày 13/10 là `[2026-10-12T17:00Z, 2026-10-13T17:00Z)`; dòng 23:59:59 và 23:59:59,999999 (+07) tính vào ngày 13, dòng 00:00:00 ngày 14 thì không; số đếm ngày 12/13/14 là 1/5/2 giống nhau ở múi giờ phiên UTC, Asia/Ho_Chi_Minh, America/Los_Angeles và khi đặt múi giờ của database; `received_at::date` cho 3/5/0, 1/5/2, 4/4/0 |

Thuật toán đã qua thực nghiệm nằm ở mục 4.5. Quy mô tệ nhất của kế hoạch là khoảng 7.200 dòng (12 người, 20 lượt, 30 ngày), nên bảng thử 200.000 dòng là phép thử gấp khoảng 30 lần. Script và kết quả thô lưu ở [analysis-chatbot-5-1](analysis-chatbot-5-1/README.md).

**S0(d), `sendChatAction` với bot dev thật** (`@HHQuotifyBot`, chat riêng của tài khoản bạn cung cấp; script và kết quả ở `analysis-chatbot-5-1/s0/telegram/`):

| Kiểm tra | Kết quả |
|---|---|
| `typing` tới chat hợp lệ | `ok: true`, 398 ms |
| `action` không hợp lệ | HTTP 400 `Bad Request: wrong parameter action in request` |
| Chat không tồn tại | HTTP 400 `Bad Request: chat not found` (760 ms) |
| Chuỗi 6 lần cách nhau 4 giây trong 22,5 giây | Cả 6 lần `ok: true`, 397 đến 477 ms mỗi lần |

Ý nghĩa cho S1 và S4: mỗi lời gọi tốn khoảng 0,4 giây nên tác vụ nền "đang gõ" không được chặn đường xử lý chính; lỗi 400 của chỉ báo là `TelegramApiError` và bị bỏ qua theo thiết kế; 403 khi người dùng chặn bot không đo riêng cho `sendChatAction` (1A đã đo `sendMessage`: `bot was blocked by the user`) vì lỗi của chỉ báo bị bỏ qua và việc đánh dấu `blocked` do đường gửi tin chính hoặc `my_chat_member` đảm nhiệm. **Quan sát bằng mắt của bạn (2026-10-13, lần thử thứ hai, script `s0d_typing_observation.py`, giờ Việt Nam):** chỉ báo "đang gõ" **có hiện**, nhưng ở **tiêu đề chat, dưới tên bot**, không phải trong khung tin nhắn. Đây là cách Telegram hiển thị trạng thái này ở chat riêng, không phải lỗi. Chưa ghi nhận độ liên tục của chuỗi 6 lần, thời gian tắt sau khi ngừng gửi và việc tắt ngay khi tin tới (con số 5 giây là theo tài liệu Telegram, chưa đo).

Hai điều rút ra cho S4: (1) chỉ báo ở tiêu đề khá kín đáo, nên với câu trả lời mất hàng chục giây người dùng có thể vẫn tưởng bot không phản hồi; có thể cân nhắc thêm một tin tạm "Đang xử lý..." cho lượt chậm (quyết định UX riêng, chưa chốt); (2) log cho thấy hai lần gửi liên tiếp cách nhau khoảng 4,4 giây (4 giây chờ cộng 0,4 giây độ trễ lời gọi) trong khi chỉ báo sống tối đa khoảng 5 giây, biên chỉ khoảng 0,6 giây, nên khi tinh chỉnh `BOT_TYPING_INTERVAL_SECONDS` ở S4 nên thử 3 giây (chưa đổi giá trị đã chốt).

### A.3 Kiểm chứng S1 (2026-10-13)

| Hạng mục | Kết quả |
|---|---|
| Test mới của S1 | 42 test: 19 tích hợp đường ống (`test_bot_pipeline_db.py`), 4 `BotInbox` trực tiếp, 2 migration, 8 chính sách và nối từ `Settings`, 6 bên đánh chuông, 3 cấu hình worker (cộng harness và fixture dùng chung) |
| Toàn bộ bộ test backend (máy host, Postgres dev tạm `it_*`) | **1.330 qua, 0 fail** (143 giây). Mốc trước S1 là 1.288 trên cùng môi trường, nên đúng 42 test thêm |
| Độ nhạy của test | Đột biến có chủ đích, mỗi lần chỉ một test fail rồi hoàn nguyên: cổng pilot, cờ bật, xóa nội dung khi hoàn tất, tin báo `BotWakeup`, `reply_saved_at`, kill switch, làm sạch lỗi DB, danh sách thử rỗng, khóa tạo pool, điều kiện lease khi claim, rào chắn `attempts`, `retry_jobs`, `keep_result`, chu kỳ health check, `configure_logging`, `_job_id` theo chat, hàng đợi, `ON DELETE CASCADE` (18 đột biến, đều bị bắt) |
| Cổng chất lượng so với `main` (worktree sạch) | ruff 62 = 62, `mypy app` 15 = 15, bandit 16 low và 1 medium = giống; mọi file tôi sửa sạch ruff và đã định dạng |
| Docker dev (`bot-worker`) | `arq` khởi động ("Starting worker for 1 functions: drain_chat"), `arq --check` thoát 0 khi sống và 1 ("no health check sentinel value found") khi dừng; `SIGTERM` tới arq và hook tắt chạy; job thật qua `ArqBotDispatcher` vào đúng hàng đợi `quotify:bot` trong 8 ms, chỉ `bot-worker` nhận (worker thường không thấy), xử lý xong, hàng đợi trống và không còn khóa kết quả |
| Chạy thật với bot dev (`@HHQuotifyBot`, chỉ email bạn trong danh sách thử) | Tin gửi lúc poller còn tắt được giao khi poller bật: poller, hộp thư, arq, `bot-worker`, câu trả lời của `StubChatEngine` tới Telegram; dòng `replied`, `attempts=1`, nội dung và câu trả lời đã bị xóa, `reply_saved_at` được đặt, 1,07 giây; log chỉ có `bot.row_done update_id=... duration_ms=...` |
| Rà soát độc lập (agent) | Không có lỗi BLOCKER; hành vi cũ không đổi khi chatbot tắt; claim giống hệt bản S0 (đua 3 bên × 60 vòng không bao giờ hai bên cùng sống); không lệch model và migration. Bốn lỗi MAJOR và các lỗi nhỏ đã sửa trong S1 (rò nội dung qua tham số SQLAlchemy, kill switch ở worker, hai test không bắt được gì, thiếu test `from_settings` và nối webhook) |

| Bạn thử trên Telegram thật (ảnh chụp, giờ Việt Nam) | 16:24 câu trả lời của stub khi poller vừa bật; 16:49 "xin chào" nhận câu trả lời ngay (bản mã sau rà soát); 16:50 "một" và "hai" liền nhau nhận đủ hai câu trả lời (thứ tự không phân biệt được bằng mắt vì nội dung stub giống nhau; thứ tự đã có test); `/help` trả lời tại chỗ bằng hướng dẫn cũ |

Chưa kiểm: nút duyệt giá thật với cờ bật; `arq --check` và `SIGTERM` trên image production (chỉ kiểm trên image dev).

### A.4 Kiểm chứng S2 (2026-10-13)

| Hạng mục | Kết quả |
|---|---|
| Test mới của S2 | 22 test: 14 claim (đua, kịch bản xác định, đối chứng), 2 chaos nhiều tiến trình, 5 `drain_chat` dưới tranh chấp, thêm 1 test rào chắn ở `BotInbox` (cộng `bot_claim_variants.py` và `bot_claim_chaos_worker.py` hỗ trợ) |
| Toàn bộ bộ test backend (máy host) | **1.352 qua, 0 fail** (143,6 giây trên máy yên tĩnh); mốc trước S2 là 1.330, nên đúng 22 test thêm |
| Cổng chất lượng | ruff 62, `mypy app` 15, bandit 16 low và 1 medium: bằng baseline; mọi file đụng tới sạch ruff và đã định dạng |
| Độ nhạy trên code thật | Đột biến claim: bỏ advisory lock (4 test fail), bỏ kiểm lease còn sống (7 fail), bỏ điều kiện `status` (bài chaos bắt), bỏ chặn dòng đang chờ thử lại, bỏ câu xin lỗi, xin lỗi trước commit: **6 trên 6 bị bắt** |
| Rà soát độc lập (agent) | Không có lỗi BLOCKER; tìm ra **6 đột biến còn sống** (xin lỗi sai chat, không bắt lỗi gửi xin lỗi, bỏ vòng thử lại khi `UPDATE` 0 dòng, bỏ `ORDER BY`, `complete` thiếu điều kiện `status`, không ghi `error_category`); đã thêm test cho cả sáu và **sáu đột biến đó nay đều bị bắt** |
| Độ ổn định | Reviewer: 8 lần chạy mỗi file khi yên tĩnh (24/24 qua), 12 lõi CPU bị đốt (6/6 qua), Python bị ghim 2 lõi (6/6 qua); sàn tranh chấp `takeovers >= 10` có biên 3,6 lần (36 đến 71 lần tiếp quản); biến thể thiếu điều kiện `status` bị bắt ngay lượt đầu 18/18; các biến thể trong bài đua bị bắt ở vòng đầu 140/140. Tôi: 3 lần chạy dưới tải; một lần mất 205 giây thay vì 24 giây vì biến thể sai kẹt đến hết hạn mỗi vòng, đã chặn bằng "dừng ở vi phạm đầu tiên" và thời hạn 8 giây mỗi vòng (còn khoảng 8 giây cho cả file) |
| Điểm yếu tìm thấy ở chính bài chaos của tôi | Lần chạy đầu chỉ có 5 lần tiếp quản trên 120 dòng (bản S0 có 2.062 trên 1.500 dòng) và biến thể sai chỉ lộ 1 trong 3 lượt. Sau khi dồn tranh chấp vào vài chat: 70 lần tiếp quản trên 60 dòng, biến thể sai lộ ngay lượt đầu (RC-29) |
| Vệ sinh test | Mật khẩu DB không còn là tham số test (pytest in tham số khi test fail); tiến trình con luôn bị kill kể cả khi quá hạn; mọi vòng chờ có thời hạn; đồng hồ giữa các tiến trình dùng `time.monotonic()` |

Chưa kiểm: môi trường `backend-test` của compose, Postgres bị đói CPU, chạy song song bằng xdist, và nút duyệt giá thật với cờ bật.

---

## 12. Nhật Ký Soạn Và Rà Soát

- **2026-10-13, bản 1.** Soạn sau khi đọc: `AGENTS.md`, `docs/agent-rules.md`, `docs/agent-memory-integration.md`, `memory-bank/quick-start.md`, `activeContext.md`, `progress.md` (toàn bộ), `projectRules.md`, `techContext.md`, tài liệu cha (mục 0 đến 7, 9, 10) và đầu kế hoạch 1A; `systemPatterns.md` và `bugPatterns.md` do agent đọc đầy đủ. `memory-bank/activeContext.md` dừng ở 1B Slice 2, nên mốc Telegram lấy từ `progress.md` (dòng 229 đến 306).
- **2026-10-13, bản 2, sau rà soát độc lập.** Reviewer đối chiếu khoảng 28 trích dẫn (đúng gần hết; sửa các chỗ sai: số hàm của `WorkerSettings`, mô tả persistence của Redis, nguồn của các con số baseline, số dòng runbook §12.8/§14.4/§15.5, hành vi của người chưa liên kết, vài số dòng) và chạy thực nghiệm (Phụ lục A.1). Các sửa đổi lớn đã áp dụng:
  - **Claim:** thêm advisory lock theo giao dịch và điều kiện lease; cấm `SKIP LOCKED`; claim tiếp quản lease hết hạn, cron chỉ đánh chuông (KT4).
  - **Chuông:** `_job_id` theo update, không theo chat; bên gửi tạo lười, giới hạn 2 giây (KT3, KT7).
  - **Ngữ nghĩa engine:** "tối đa một lần mỗi lần thử, tối đa `BOT_MAX_ATTEMPTS` lần" thay cho "tối đa một lần" (KT5); thêm hai loại lỗi engine.
  - **Rào chắn** theo `attempts` và kiểm lần cuối trước khi gửi (KT16); nhả lease khi `SIGTERM` (KT18).
  - **Cổng pilot** và công tắc tắt khẩn cấp (KT17), vì cờ env toàn cục không cho phép "bật cho một tài khoản thử".
  - **Tham số:** thêm `BOT_SEND_BUDGET_SECONDS`, nâng `BOT_LEASE_SECONDS` lên 240 và `BOT_MESSAGE_TTL_SECONDS` lên 1200, thống nhất chính sách xóa nội dung khi dòng kết thúc.
  - **Lát cắt:** S1 chứa `BotPrincipal` (sửa phụ thuộc S1 và S6), mọi lát S2 đến S9 có danh sách tiêu chí chấp nhận.
  - **Câu hỏi mở:** thêm cổng pilot, `restart`/healthcheck, `max_connections=1`; chuyển các điểm đã quyết được theo bằng chứng sang mục "Đã quyết theo bằng chứng".
- **2026-10-13, bản 3, yêu cầu bổ sung.** Thêm hạn mức sử dụng mỗi người mỗi ngày vì chatbot và nhập liệu bằng AI tốn token và tiền. Đề xuất kết hợp lượt, file và token (mục 4.11, KT19 đến KT21): cổng `UsageGate` ở worker trước engine, đếm lượt từ `bot_updates.reply_saved_at`, ngày theo `Asia/Ho_Chi_Minh`, cấu hình ưu tiên ghi đè theo người > mặc định hệ thống > env. Thêm lát S10, cột `reply_saved_at` và chỉ mục theo người dùng, ba biến cấu hình, hai câu hỏi ở mục 9, ba rủi ro RC-21 đến RC-23, và ghi lệch của 5.6 vào mục 3 (dòng 13). Phần đếm token, bảng ghi đè theo người và trang cấu hình thuộc 5.6. Chưa qua rà soát độc lập riêng.
- **2026-10-13, bản 4.** Bạn chốt ba điểm hạn mức: hướng kết hợp lượt, file, token (mặc định 20 lượt và 5 file); ghi đè theo từng người ở 5.6; lệnh `/hanmuc`. Quản trị viên không được miễn (diễn giải của tôi, nêu ở mục 9). Cập nhật mục 4.3, 4.11, S9, S10, mục 9, mục 10; thêm QĐ-21 và H16 vào tài liệu cha.
- **2026-10-13, bản 5.** Bạn trả lời các điểm mở: (1) lưu tạm nội dung tin: có; (2) cổng pilot `CHATBOT_PILOT_USER_EMAILS`; (3) `restart`, `stop_grace_period`, healthcheck cho `bot-worker`: đồng ý; (4) webhook `max_connections=1`: đồng ý; (5) tham số 4.8 làm giá trị khởi điểm, chạy thử dev rồi tinh chỉnh; (6) kiểm VPS ra LLM và `max_connections` Postgres: không cần. Bạn cũng làm rõ: **Admin cấu hình hạn mức từng người**, thường nâng cho vai trò trưởng phòng. Hệ quả đã áp dụng: S0(e) bị bỏ qua và không còn chặn S9, RC-5 và RC-15 chuyển thành điều kiện của 2A, thêm RC-24 (mặt trái của `max_connections=1`), thêm việc `set_webhook` nhận `max_connections` vào S8, thêm bước đăng ký lại webhook vào S9 (xin xác nhận lại lúc làm).
- **2026-10-13, bản 6.** Đổi tên lệnh `/hanmuc` thành `/limit` theo góp ý của bạn: các lệnh hiện có (`/start`, `/stop`, `/help`) đều có tên tiếng Anh, chỉ phần mô tả trong menu là tiếng Việt (`BOT_COMMANDS` ở `app/telegram_cli.py`). Các mục nhật ký trước đó giữ nguyên tên cũ như đã ghi lúc đó.
- **2026-10-13, bản 7.** Bạn bỏ ý định dùng nhánh riêng dài hạn và chọn làm theo kế hoạch. Đã thêm quy trình git ở mục 6, RC-25, và ghi rõ S9 không build `frontend`. Bắt đầu S0.
- **2026-10-13, bản 8, kết quả S0.** Chạy S0(a), (b), (c), (f) bằng ba agent (Phụ lục A.2). Thiết kế qua thực nghiệm; sửa các điểm sau: câu lệnh claim (ép kiểu `CAST(:chat_id AS BIGINT)`, điều kiện `status IN ('queued','processing')` bắt buộc và thử lại khi 0 dòng, trả danh sách dòng hết lượt để gửi câu xin lỗi sau commit); mọi mốc thời gian truyền vào truy vấn phải có múi giờ; không dùng `received_at::date` cho hạn mức; cảnh báo `READ COMMITTED` của SQLAlchemy là lỗi thời nhưng engine chỉ đọc chỉ là rào chắn (RC-27); hành vi `SIGTERM` và `SIGKILL` của arq (`retry_jobs=False`, `keep_result=0` bắt buộc, `health_check_interval` nhỏ, `BotWorkerSettings` không kế thừa); `create_pool` phải nằm trong `wait_for`; baseline cổng chất lượng không xanh sẵn (RC-26) và mốc mới ở A.2. Script và kết quả thô lưu ở `docs/quotify/analysis-chatbot-5-1/`.
- **2026-10-13, bản 9, S1 xong.** Cài S1 theo TDD (tracer bullet rồi từng hành vi), rà soát độc lập, sửa các lỗi rà soát tìm ra, chạy thật trên Docker dev và bot dev. Thêm RC-28 (rò nội dung qua tham số SQLAlchemy), bốn tiêu chí S1 sau rà soát, Phụ lục A.3. Hoãn compose test và `sendChatAction` của fake Telegram sang S4 và S8.
- **2026-10-13, bản 10, S2 xong.** S2 chủ yếu là test chứng minh claim của S1, cộng việc gửi câu xin lỗi sau commit. Port các biến thể sai và kịch bản đua của S0 thành test hồi quy, thêm chaos nhiều tiến trình thật; rà soát độc lập tìm 6 đột biến sống sót, đã đóng hết; phát hiện bài chaos ban đầu yếu và sửa (RC-29). Dồn việc xin lỗi theo liên kết sang S4. Phụ lục A.4.
- **Chưa xác minh:** các điểm đánh dấu **[CHƯA XÁC MINH]** ở trên; các con số ở Phụ lục A.2 do agent đo, tôi chưa tái lập; quan sát bằng mắt chỉ báo "đang gõ" của S0(d) chờ bạn xác nhận; hành vi `SIGTERM` của lệnh dev `sh -lc "uv sync && uv run arq ..."`.
