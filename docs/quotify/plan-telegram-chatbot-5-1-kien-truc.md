# Kế Hoạch Triển Khai Chatbot, Mục 5.1: Kiến Trúc Đường Ống Bot

## Trạng Thái

**ĐÃ CHỐT CÁC ĐIỂM CẦN QUYẾT (2026-10-13, sau rà soát độc lập; nhật ký đến bản 16, 2026-10-14). S0 ĐẾN S8 ĐÃ XONG trên nhánh `feat/telegram-chatbot` (chưa merge vào `main`); S0, S1, S3, S4, S5 và S6 bạn đã xác nhận trên Telegram thật (S6 không đổi hành vi nhìn thấy nên chỉ xác nhận đường ống đầu-cuối vẫn trả lời; phần engine chỉ đọc được kiểm trên database dev thật, Phụ lục A.8); S7 không đổi hành vi người dùng nhìn thấy nên được kiểm trên `/metrics` của backend dev thật và bằng `promtool` (Phụ lục A.9); S8 (vận hành) cũng không đổi hành vi nhìn thấy nên được kiểm trên Docker dev thật (`bot-worker` healthy, `quotify_bot_enabled 1`) và trong một dự án compose test tách biệt (Phụ lục A.10), bạn đã nhắn 5 tin trên Telegram thật sau khi tạo lại container và đường ống vẫn trả lời đủ (Phụ lục A.10).** Các điểm "đã quyết theo bằng chứng" ở mục 9 chưa gặp phản đối nhưng chưa được xác nhận riêng. Cơ sở: commit `7eb64e9` trên `main`, cây git sạch, Alembic head `20261007_0900`.

Kế hoạch này là phần triển khai chi tiết của **mục 5.1** (và phần hạ tầng của Giai đoạn 2A) trong [plan-telegram-bien-dong-gia-va-chatbot-ai.md](plan-telegram-bien-dong-gia-va-chatbot-ai.md). Nó chỉ xây **đường ống**: nhận tin, xếp hàng, xử lý ở worker riêng, trả lời. Phần "bộ não" (LLM, công cụ, bộ nhớ, ngân sách) cắm vào đường ống qua một cổng duy nhất (`ChatEngine`, mục 4.6) và thuộc các kế hoạch riêng của 5.2 đến 5.6.

Cách soạn:
- Local skill `to-issues`: chia lát cắt dọc (tracer bullet), mỗi lát có loại **HITL/AFK**, "chặn bởi" và tiêu chí chấp nhận. Không đăng issue lên tracker nào.
- Local skill `tdd`: trong mỗi lát, test đầu tiên là tracer bullet đi hết đường, rồi mới tới từng hành vi, một test một đoạn code. Test đo hành vi qua giao diện công khai (webhook vào, request Telegram ra, trạng thái DB), chỉ giả lập ranh giới hệ thống (Telegram, Redis, LLM).
- Local agent: 4 agent Explore chỉ đọc chạy song song ngày 2026-10-13 (luồng webhook và update; worker, Redis, compose; service, DB, quyền; lịch sử bug và memory-bank), cộng ba điểm tôi tự kiểm trực tiếp (ngữ nghĩa `_job_id` của arq, `parse_mode=None` của client Telegram, khối `worker` trong compose production). Sau đó **một agent rà soát độc lập** kiểm lại trích dẫn, tấn công thiết kế và chạy thực nghiệm; kết quả và các sửa đổi đã áp dụng ở mục 12 và Phụ lục A.

Quy ước: `KT1` đến `KT21` là quyết định kiến trúc (mục 5). `RC-1` đến `RC-38` là rủi ro (mục 8). `S0` đến `S10` là lát cắt (mục 6). Mục nào chưa kiểm chứng ghi **[CHƯA XÁC MINH]**.

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
| Ảnh, tài liệu, giọng nói, sticker, GIF, vị trí, danh thiếp, bình chọn (cờ bật, người dùng đủ điều kiện) | Inline, trả câu cố định "hiện chỉ đọc được tin nhắn văn bản" (`NON_TEXT_TEXT`), không vào hộp thư; mỗi chat nhận **một** thông báo trong 10 giây (album 10 ảnh không thành 10 câu) và có bộ giới hạn tốc độ riêng 30 tin mỗi phút để không ăn suất của tin văn bản | 2C mới xử lý file |
| Tin dịch vụ (ghim tin, đổi hẹn giờ tự xóa...) | `UNKNOWN_TEXT` như hiện nay | Không phải nội dung người dùng gõ |
| Văn bản thường khi chat đã có `BOT_MAX_PENDING_PER_CHAT` tin đang chờ | Inline, trả câu lịch sự `PENDING_LIMIT_TEXT`, **không** ghi hộp thư, không đánh chuông (một thông báo trong 10 giây) | Chống lũ, giữ TTL còn đủ cho hàng chờ |
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
6. Gọi `ChatEngine.reply(turn)` bọc `asyncio.wait_for(BOT_ROW_TIMEOUT_SECONDS)`. **Không giữ kết nối DB** trong lúc này. Lỗi `ChatEngineTemporaryError` hoặc quá thời gian: đưa dòng về `queued` với `lease_until = now + BOT_RETRY_BACKOFF_SECONDS × attempts` (nếu chưa đạt trần lần thử). Lỗi `ChatEngineError` (lỗi cuối): `failed` ngay, gửi một câu xin lỗi. Mọi lỗi khác (kể cả lỗi bất ngờ) coi là thử lại được. `error_category` luôn là chuỗi cố định (`engine_error`, `engine_timeout`, `send_failed`, `lease_exhausted`, `expired`), không bao giờ là nguyên văn ngoại lệ. Kết quả lỗi chỉ được **ghi nhận** trong khối `except` và xử lý sau khi đã thoát khối (RC-30).
7. **Lưu `reply_text`** và đặt `reply_saved_at` bằng câu lệnh có rào chắn (KT16).
8. **Kiểm lần cuối trước khi gửi** bằng một truy vấn: dòng vẫn thuộc về lần claim này, liên kết còn `active`, người dùng còn `ACTIVE`. Không thì bỏ, không gửi.
9. Gửi theo mục 4.7, rồi `complete` có rào chắn.
10. Dừng claim dòng mới khi vượt `BOT_DRAIN_BUDGET_SECONDS`. Phần còn lại do cron quét đánh chuông lại sau tối đa khoảng một phút. Job arq không tự đưa lại chính nó vào hàng đợi được vì khóa job còn tồn tại đến khi job kết thúc.

**Hủy và tắt (đã kiểm ở S0(b)):** khi worker nhận `SIGTERM` (deploy), job nhận `CancelledError` khoảng 20 ms sau và khối dọn dùng `asyncio.shield` chạy xong trước khi tiến trình thoát. Hàm drain bắt **mọi** ngoại lệ thoát khỏi một dòng (`CancelledError` lẫn lỗi bất ngờ, ví dụ DB đứt lúc lưu câu trả lời), **nhả lease của dòng đang xử lý** bằng một `UPDATE` bọc `shield` rồi ném lại nguyên vẹn; nếu không, dòng bị kẹt đến hết lease (240 giây). Vùng này phủ cả đoạn claim: dòng chỉ được coi là của mình sau khi claim đã commit, nên `SIGTERM` rơi vào bước đóng phiên sau commit vẫn nhả được. Còn một cửa sổ cỡ mili giây không phủ được: hủy đúng lúc đang chờ kết quả commit của chính claim (RC-30). Khóa "đang chạy" của arq bị xóa khi `SIGTERM`, còn khóa job và mục retry ở lại thành job mồ côi (worker khởi động lại sẽ báo "max retries exceeded" và không chạy lại hàm), nên `BotWorkerSettings` đặt `retry_jobs=False`: không còn mồ côi và id dùng lại ngay, đổi lại một dòng log ERROR cho `CancelledError` (chấp nhận). `job_completion_wait` có trong arq 0.26.3 (số nguyên giây, mặc định 0) nhưng **không dùng**, để 0: vòng drain không biết mình đang bị tắt nên sẽ vẫn claim dòng mới trong lúc chờ. `stop_grace_period` của service phải lớn hơn thời gian dọn (khoảng 1 giây) cộng dự phòng (đề xuất 30 giây); nếu `docker stop` hết hạn thì tiến trình bị `SIGKILL`, khóa "đang chạy" còn lại, id kẹt và dòng kẹt đến hết lease. Một lần deploy giữa chừng tốn một lần thử.

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
    readonly_session_factory: Callable[[], AsyncSession] | None = None   # S6: ReadonlySessionFactory

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
- **Đã cài ở S6** (`app/db/readonly.py`, `app/services/chat_tools.py`):
  - `ReadonlySessionFactory`: gọi như `async_sessionmaker`, **engine tạo lười** ở lần gọi đầu (chatbot tắt hay công cụ chưa gọi thì không có engine, không có kết nối), `aclose()` đóng thật và quên engine **trước** khi đóng (một lần gọi chen vào không tạo engine mồ côi). Kết nối mang nhãn `application_name = quotify-bot-readonly` để nhận ra trong `pg_stat_activity`. Pool riêng 2 + 1, chờ kết nối tối đa 3 giây, `pool_pre_ping`. Không áp `instrument_sqlalchemy_engine`: `SQLAlchemyInstrumentor` là singleton nên lần gọi thứ hai bị bỏ qua im lặng (muốn có span cho công cụ phải gọi một lần với cả hai engine, việc của 5.2 hay S7).
  - **Khôi phục khi trả kết nối về pool** (sự kiện `reset`, chạy SAU rollback; đo ở S6): kết nối bị một phiên cố tình `SET default_transaction_read_only=off` rồi commit thì phiên kế tiếp ghi được và `statement_timeout` về 0 (xác nhận lại). Mỗi lần trả kết nối chạy `RESET SESSION AUTHORIZATION` (cũng đưa vai trò về mặc định), `RESET ALL` (trả `server_settings` về đúng giá trị lúc khởi tạo), `UNLISTEN *`, `CLOSE ALL` (cursor `WITH HOLD`), `pg_advisory_unlock_all()`, `DISCARD TEMP`, rồi commit. **Không** dùng `DISCARD ALL` hay `DEALLOCATE ALL`: chúng xóa cả prepared statement mà asyncpg đang cache và làm truy vấn kế tiếp hỏng. Còn sót có chủ đích: `PREPARE` do người dùng tạo (chỉ gọi được khi biết tên). Bỏ qua khi kết nối chỉ bị thu gom rác (`reset_state.terminate_only`); lỗi trong bước khôi phục làm SQLAlchemy hủy kết nối thay vì đưa lại kết nối bẩn vào pool. Chi phí: khoảng 5 vòng gọi thêm mỗi lần mở phiên (0,2 đến 0,7 ms trên localhost).
  - **Cho 5.2:** công cụ phải bắt lỗi ở cả câu lệnh lẫn lúc thoát `async with` (server cắt phiên rảnh quá 10 giây thì `session.close()` cũng ném `InterfaceError`); không giữ phiên chỉ đọc mở qua lúc gọi LLM; cân lại cỡ pool chỉ đọc (2 + 1, chờ 3 giây) khi có công cụ thật chạy song song nhiều lệnh chậm (tối đa 5 giây mỗi lệnh).
  - **`ToolRegistry`** (sổ rỗng ở 5.1): công cụ đăng ký qua `register` bị từ chối nếu có tham số trông như SQL hay truy vấn tự do (tên đã chuẩn hóa NFKD, bỏ dấu, gồm tiếng Việt và chữ toàn-rộng; chuỗi con `sql`; các từ `query`, `where`, `clause`, `expr`, `raw`, `command`...), chuỗi tự do phải là enum hay `max_length` tối đa 200, enum không rỗng, `max_length` dương, tên công cụ là định danh ASCII, tên không trùng (không phân biệt hoa thường), danh sách tham số bất biến. Công cụ chỉ được gọi qua `call`: **kiểm lúc gọi** từ chối khóa lạ, thiếu đối số bắt buộc, sai kiểu (bool không phải số), sai enum, quá dài, UUID và ngày sai định dạng trước khi handler thấy. Danh sách tên chỉ là rào nhẹ; chốt thật là handler luôn truyền tham số qua bind và role chỉ-`SELECT` ở 2D.

### 4.7 Đường gửi trả lời

Cài ở `app/services/bot_reply_sender.py` (chia tin, gửi tuần tự) và `app/bot_worker.py` (phân loại lỗi, kiểm người nhận).

- **Văn bản thuần** (`parse_mode=None`) cho nội dung do engine sinh, tránh lỗi 400 vì HTML sai. Tin cố định của hệ thống (xin lỗi, tin quá cũ) vẫn dùng HTML như hiện nay.
- **Chia tin** khi vượt 4096 đơn vị. Độ dài **đếm theo đơn vị UTF-16** (emoji ngoài BMP chiếm 2) nên một phần không bao giờ vượt giới hạn. Ranh giới ưu tiên đoạn, rồi dòng, rồi khoảng trắng, **ở nửa sau của cửa sổ** (không thì một tiêu đề ngắn rồi danh sách dài bị tách thành tin vài ký tự và phần cuối bị cắt cụt vô lý); không có ranh giới nào thì cắt cứng. Tối đa `BOT_REPLY_MAX_PARTS` phần, phần dư cắt kèm dấu "…" (vẫn trong giới hạn). Hàm chia là hàm thuần và xác định, nên lần gửi lại chia y như lần trước. Fuzz 100.000 ca: không có phần rỗng, không vượt giới hạn, không mất nội dung.
- **`sent_parts`** ghi số phần đã gửi sau **mỗi** phần bằng câu lệnh có rào chắn (`status='processing' AND attempts=:mine`). Lần claim sau gửi tiếp từ phần chưa gửi (không gọi lại engine, không gửi lại phần đã gửi). Nếu ghi `sent_parts` thấy dòng đã thuộc về worker khác thì dừng ngay, không gửi tiếp và không hoàn tất.
- **Toàn bộ nhánh gửi** bọc `asyncio.wait_for(BOT_SEND_BUDGET_SECONDS)`. **429:** chờ `max(1, retry_after)` rồi gửi lại cùng phần đó, miễn là còn trong ngân sách; nếu `retry_after` lớn hơn phần còn lại thì dừng ngay (không chờ vô ích) và hẹn lần thử sau **không sớm hơn `retry_after`**. Telegram không kèm hay kèm 0 thì chờ tối thiểu 1 giây để không gọi liên tục.
- **Phân loại lỗi gửi** (sau khi thoát khối `except`, RC-30): **403** → `mark_blocked` có sẵn và dòng `dropped` (`forbidden`), không thử lại, không xin lỗi; **4xx khác 429** (vd 400) → `failed` (`send_rejected`) ngay kèm một câu xin lỗi; **lỗi mạng, 5xx, hết ngân sách** → thử lại có backoff (`send_failed`, hay `send_timeout`), hết lượt thì `failed` kèm một câu xin lỗi. Câu trả lời **rỗng** của engine bị coi là lỗi engine thử lại được (không thì dòng thành `replied` mà không gửi gì).
- **Chỉ báo "đang gõ":** tác vụ nền gửi `sendChatAction typing` **ngay** rồi lặp mỗi `BOT_TYPING_INTERVAL_SECONDS` chỉ trong lúc engine chạy, hủy khi engine xong, lỗi hay bị hủy. Lỗi của chỉ báo bị bỏ qua và vòng lặp vẫn tiếp tục. Không có engine chạy (chỉ gửi lại câu đã lưu) thì không báo.
- **Kiểm người nhận ba lần:** trước khi gọi engine (liên kết còn `active` và đúng người dùng, người dùng còn `ACTIVE`; sai thì `dropped` với `unlinked`, `forbidden` hoặc `user_inactive`, nội dung bị xóa, không tốn lượt engine), ngay trước khi gửi (cùng kiểm tra cộng `owns`), và cho **cả câu xin lỗi lẫn thông báo tin quá cũ** (`_notify` bỏ qua nếu liên kết không còn; 403 thì `mark_blocked`). `_notify` dùng `telegram_user_id = chat_id` vì hand-off chỉ nhận chat riêng.
- **Tin quá hạn nhưng đã gửi dở** thì gửi nốt phần còn lại thay vì loại và bắt người dùng hỏi lại.
- Ngữ nghĩa giao hàng: **at-least-once** cho câu trả lời (khác đường trả lời at-most-once của 1A/1C, vì mất câu trả lời tệ hơn nhận trùng). Cửa sổ trùng chỉ là khoảng giữa lúc Telegram nhận tin và lúc ghi `sent_parts` hay `complete` (kể cả khi `wait_for` hủy đúng lúc Telegram đã nhận), thu hẹp thêm bằng `sent_parts` và bước kiểm lần cuối ở 4.5.

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
| `BOT_SEND_BUDGET_SECONDS` | `60` | Trần **tổng** cho nhánh gửi một dòng (kể cả chờ 429 và gửi nhiều phần). Phải lớn hơn 0 |
| `BOT_LEASE_SECONDS` | `240` | Phải lớn hơn `BOT_ROW_TIMEOUT_SECONDS + BOT_SEND_BUDGET_SECONDS` (180), nếu không lease hết hạn khi đang xử lý và worker khác chạy chồng |
| `BOT_MAX_ATTEMPTS` | `3` | |
| `BOT_RETRY_BACKOFF_SECONDS` | `5` | Nhân với số lần thử |
| `BOT_MAX_PENDING_PER_CHAT` | `5` | Đếm dòng `queued` và `processing` của chat; vượt thì trả lời lịch sự, không ghi hộp thư. Tối thiểu 1. Trần **chính xác** nhờ khóa dòng `telegram_accounts` (`touch_linked_identity` luôn ghi `last_seen_at`): đừng bỏ lần ghi đó, có test chạy đồng thời |
| `BOT_DAILY_TURN_LIMIT` | `20` | Số lượt hỏi AI mỗi người mỗi ngày (giờ Việt Nam), áp cho mọi loại tin. `0` nghĩa là không giới hạn lượt (trần ngân sách tháng ở 5.6 vẫn áp dụng). Mức mặc định thấp nhất của chuỗi cấu hình, xem mục 4.11 |
| `BOT_DAILY_FILE_LIMIT` | `5` | Số lượt dùng ảnh hoặc PDF mỗi người mỗi ngày (2C), là tập con của `BOT_DAILY_TURN_LIMIT`. `0` nghĩa là không giới hạn |
| `BOT_QUOTA_WARN_REMAINING_PERCENT` | `20` | Còn từng này phần trăm hạn mức thì thêm dòng nhắc ở cuối câu trả lời; `0` là tắt nhắc |
| `BOT_MESSAGE_TTL_SECONDS` | `1200` | Phải không nhỏ hơn `BOT_MAX_PENDING_PER_CHAT × (BOT_ROW_TIMEOUT_SECONDS + BOT_SEND_BUDGET_SECONDS)` (900), nếu không dòng hết hạn khi mới chỉ đang chờ |
| `BOT_SWEEP_STALE_SECONDS` | `30` | Bằng chu kỳ cron: dòng chờ lâu hơn mức này mà chưa ai nhận thì đánh chuông lại |
| `BOT_TYPING_INTERVAL_SECONDS` | `4` | Chỉ báo "đang gõ" của Telegram kéo dài khoảng 5 giây. Phải lớn hơn 0 (0 làm vòng lặp chạy không nghỉ) |
| `BOT_REPLY_MAX_PARTS` | `4` | Tối thiểu 1 |
| `BOT_TERMINAL_RETENTION_DAYS` | `30` | Xóa dòng đã kết thúc (nội dung đã bị xóa từ lúc kết thúc, chỉ còn siêu dữ liệu) |
| `BOT_DB_POOL_SIZE` | `4` | Pool **tường minh** của engine chính trong `bot-worker` (RC-5; mặc định chung 5 + 10 là quá nhiều). Tối thiểu 1 |
| `BOT_DB_MAX_OVERFLOW` | `4` | Tràn của engine chính. Tối thiểu 0: SQLAlchemy hiểu `-1` là không giới hạn nên không cho phép. 4 + 4 bằng đúng `BOT_WORKER_MAX_JOBS` (8), mỗi job chỉ giữ một kết nối tại một thời điểm |
| `BOT_READONLY_POOL_SIZE` | `2` | Pool engine chỉ đọc. Tối thiểu 1 |
| `BOT_READONLY_MAX_OVERFLOW` | `1` | Tràn của engine chỉ đọc. Tối thiểu 0. Tổng kết nối tối đa của một `bot-worker`: 8 + 3 = 11 (trước S6 là 15 + engine chỉ đọc) |
| `BOT_READONLY_POOL_TIMEOUT_SECONDS` | `3` | Chờ kết nối chỉ đọc tối đa từng này giây rồi báo lỗi. Phải lớn hơn 0 |
| `BOT_READONLY_STATEMENT_TIMEOUT_MS` | `5000` | Truy vấn công cụ chạy quá mức này bị hủy (SQLSTATE `57014`). Phải lớn hơn 0 |
| `BOT_READONLY_IDLE_IN_TRANSACTION_TIMEOUT_MS` | `10000` | Phiên chỉ đọc rảnh trong giao dịch quá mức này bị server cắt. Phải lớn hơn 0; nên lớn hơn `BOT_READONLY_STATEMENT_TIMEOUT_MS` để một lệnh chậm không bị cắt oan (khuyến nghị, cấu hình không kiểm chéo) |
| `BOT_STUB_DELAY_SECONDS` | `0` | **Chỉ để thử trên dev**: engine giả đợi từng này giây rồi mới trả lời (để thử `SIGTERM` giữa lượt, chỉ báo "đang gõ"). Worker **bỏ qua** giá trị này khi `APP_ENV=production`; có test |

Bạn đã đồng ý các giá trị này làm **giá trị khởi điểm** (2026-10-13), chưa đo: chạy thử trên dev rồi tinh chỉnh lại (S8), và đặt hạn mức token sau khi có số liệu thật của engine (5.5, 5.6).

### 4.9 Quan sát

Worker hiện không phơi metric và Prometheus chỉ scrape backend, nên dùng đúng mẫu `core/price_alert_metrics.py`: **gauge tính lúc scrape từ DB** ở backend (`app/core/bot_metrics.py`, cài ở S7). Cache 15 giây, hạn chờ 2 giây, hai nguồn (thông báo giá và chatbot) đọc song song; lỗi chỉ làm `quotify_bot_metrics_up` về 0, không làm hỏng `/metrics` và không phát số cũ như số mới.

- `quotify_bot_updates{status}` (đủ 5 trạng thái, kể cả bằng 0): dòng **đang mở** (`queued`, `processing`) tính dù cũ đến đâu, dòng **đã kết thúc** chỉ tính trong 24 giờ gần nhất theo `received_at`.
- `quotify_bot_queued_oldest_age_seconds`: tuổi (từ lúc nhận tin) của dòng claim được cũ nhất. Dùng **cùng định nghĩa với cron quét** (`BotInbox.oldest_claimable_received_at`): dòng xếp sau một dòng đang chạy còn lease hay đang chờ backoff **không** tính, nếu không một hàng chờ hợp lệ sẽ làm cảnh báo nổ oan. Chỉ có khi có người đang chờ. Tuổi tính từ `received_at` nên một dòng đang thử lại cũng cộng dồn; với 1 đến vài chat nó chỉ cao từng quãng ngắn (không vượt `for: 5m`), còn khi LLM ngưng hẳn và tải từ khoảng 5 tin mỗi phút thì luôn có dòng nằm trong khoảng chờ và cảnh báo có thể nổ: đó là tín hiệu thật.
- `quotify_bot_recent_failures`: số dòng `failed` **kết thúc trong 30 phút gần nhất**. Là cơ sở của cảnh báo lỗi, thay cho `delta` trên gauge 24 giờ (gauge 24 giờ vừa tăng vừa giảm khi dòng cũ rơi khỏi cửa sổ nên `delta` bỏ sót hay báo trễ một lỗi mới; đã chứng minh bằng `promtool`).
- `quotify_bot_quota_denied`: số dòng `dropped` kèm `error_category='quota_exceeded'` trong 24 giờ gần nhất (để thấy hạn mức đặt quá chặt; bằng 0 cho đến khi S10 tạo ra loại dòng này).
- `quotify_bot_metrics_up` và `quotify_bot_enabled`. **Chatbot tắt (cờ môi trường và cờ Telegram) thì chỉ có hai số này** (`enabled=0`): dòng còn nằm lại hộp thư sau khi tắt công tắc khẩn cấp (mục 4.5) không được làm cảnh báo hàng đợi nổ mãi. Cờ đọc từ **môi trường của backend**: compose dev (từ S8) chuyển `CHATBOT_ENABLED` và `CHATBOT_PILOT_USER_EMAILS` cho `backend` qua `environment` như cho `telegram-poller` và `bot-worker` (biến shell, mặc định tắt); production đọc từ `.env`.
- Cảnh báo (nhóm `quotify-chatbot` trong `alert_rules.yml`, tiền tố `quotify_bot_*`): `ChatbotQueueStuck` (`quotify_bot_queued_oldest_age_seconds > 120` kéo dài 5 phút), `ChatbotUpdatesFailing` (`quotify_bot_recent_failures > 0` kéo dài 1 phút, tự hết sau 30 phút nếu không có lỗi mới), `ChatbotMetricsUnavailable` (`quotify_bot_metrics_up == 0` kéo dài 10 phút), đều mức `warning`. Hai nhóm luật cũ (còn tên `fastapivue_*`, nợ RR-19) **không** sửa lan. Cảnh báo tuổi dòng chỉ nổ khi **đã có** người dùng chờ; để phát hiện worker chết sớm hơn, `bot-worker` có healthcheck container (mục 4.10, S8). Luật được kiểm bằng `promtool check rules` và `promtool test rules` (`make alert-rules-check`; test pytest tương ứng tự bỏ qua khi máy không có `promtool`).
- **Log có cấu trúc.** Mọi dòng `bot.*` chỉ có các trường `update_id`, `status`, `attempts`, `duration_ms`, `category` (danh mục lỗi cố định; tên trường trong log là `category`, không phải `error_category`), `error` (tên lớp ngoại lệ), `kind`, `reason`, `target`, `rang`, `deleted` và (ở `bot.policy`) `enabled`, `pilot`, với giá trị thuộc tập cố định. **Không bao giờ** log nội dung tin hay câu trả lời, `payload_text`, ngoại lệ nguyên văn từ engine (bài học rò token ở 1A). Hợp đồng được kiểm bằng test `test_bot_logs_db.py` chạy 29 kịch bản (mọi nhánh lỗi của worker, bên đánh chuông, chỉ số và `bot.policy`; đo bằng coverage thì mọi vị trí `logger.*` của `bot_worker.py`, `bot_dispatcher.py` và `bot_metrics.py` đều được chạy, trừ câu khởi động cố định "Bot worker started up successfully.") với một chuỗi mồi 10 chữ số trong tin hỏi, câu trả lời và thông điệp ngoại lệ: không được xuất hiện trong log, chuỗi ngoại lệ, **bất kỳ cột nào** của audit hay của dòng đã kết thúc. Một danh mục lỗi mới (vd `quota_exceeded` của S10) làm test đỏ cho tới khi được thêm có chủ đích vào tập cho phép.

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

**Trạng thái 2026-10-14: ĐÃ XONG trên nhánh `feat/telegram-chatbot`.** Bằng chứng ở Phụ lục A.5.

Chặn bởi: S1.

Test thuộc tầng integration, Postgres thật (`test_bot_resilience_db.py`, `test_bot_sweep_db.py`, cộng `tests/test_bot_worker.py`). Tình huống "worker khác tiếp quản" dùng cổng `asyncio.Event` đặt đúng chỗ; các chỗ chờ đều có thời hạn, không ngủ cứng để đồng bộ.

- [x] Redis hỏng lúc đánh chuông (bên đánh chuông giả ném lỗi kết nối): webhook vẫn 200, dòng nằm `queued`, cron `sweep_bot_updates` đánh chuông lại đúng chat và tin được trả lời.
- [x] Worker chết sau bước lưu `reply_text`, trước khi gửi: lần sau câu đã lưu được gửi lại và engine **không** bị gọi thêm.
- [x] Worker chết **trước** khi lưu: lần thử sau gọi engine lại (đếm đúng theo `attempts`).
- [x] `ChatEngineTemporaryError`, lỗi bất ngờ, hoặc quá `BOT_ROW_TIMEOUT_SECONDS`: dòng về `queued` với backoff `BOT_RETRY_BACKOFF_SECONDS × attempts` (có test lần 1 và lần 2); đạt `BOT_MAX_ATTEMPTS` thì `failed` kèm đúng một câu xin lỗi, `error_category` thuộc danh mục cố định, không chứa nguyên văn ngoại lệ. `ChatEngineError` thì `failed` ngay.
- [x] **Rào chắn:** sau khi lease bị tiếp quản, lời lưu/hoàn tất của worker cũ không ghi đè; kiểm lần cuối ngăn worker cũ gửi trùng (cổng đặt đúng giữa bước lưu và bước gửi); dòng bị xóa giữa chừng không làm worker lỗi. **(thêm sau rà soát)** cả bốn lệnh `requeue`, `end`, `release_lease`, `owns` bị chặn bằng token cũ **khi worker mới còn sống**, và worker cũ thất bại muộn không gửi thêm câu xin lỗi sau khi worker mới đã trả lời.
- [x] **Hủy (SIGTERM):** hủy tác vụ drain giữa lúc engine chạy thì lease được nhả ngay và dòng claim lại được tức thì; **(thêm sau rà soát)** lần hủy thứ hai giữa lúc đang nhả không cắt ngang việc nhả (`shield`), và hủy rơi vào bước đóng phiên sau commit của claim vẫn nhả được lease.
- [x] **(thêm sau rà soát)** Lỗi bất ngờ thoát khỏi vòng xử lý (DB đứt đúng lúc lưu câu trả lời) cũng nhả lease rồi ném lại, thay vì giữ chat 240 giây.
- [x] **(thêm sau rà soát)** Thông điệp ngoại lệ của engine hay của bước gửi không lọt vào traceback (`__context__`) khi DB lỗi ngay sau đó, và nội dung câu hỏi lẫn câu trả lời không xuất hiện trong log ở cả đường thành công lẫn đường gửi lỗi.
- [x] Dòng quá `BOT_MESSAGE_TTL_SECONDS`: `dropped` (`expired`), một thông báo mỗi lần chạy drain.
- [x] Lỗi gửi Telegram: dòng về `queued` với câu trả lời đã lưu, lần sau chỉ gửi lại câu đó; hết lượt thì `failed` (`send_failed`) **không** xin lỗi (xem "Chuyển sang S4").
- [x] Cron quét chỉ rung cho chat có dòng claim được: bỏ chat đang có dòng chạy còn lease hoặc dòng đầu đang chờ thử lại; chờ đủ `BOT_SWEEP_STALE_SECONDS` mới rung dòng mới vào; mỗi chat một chuông gắn với dòng cũ nhất; tắt cờ thì không rung; hai tiến trình quét cùng lúc không tạo xử lý trùng.
- [x] Cron dọn xóa dòng `replied`, `failed`, `dropped` quá `BOT_TERMINAL_RETENTION_DAYS` (có test sát biên 29 và 31 ngày) và không bao giờ xóa dòng còn mở.
- [x] Lịch cron và ánh xạ cấu hình được ghim bằng test (quét giây 10 và 40 mỗi phút; dọn 03:40 mỗi ngày; mặc định và đường từ `Settings` sang `BotWorkerConfig`), và `BOT_STUB_DELAY_SECONDS` bị bỏ qua ở production.

**Chuyển sang S4:** (1) lỗi gửi vĩnh viễn (tin dài quá 4096 ký tự khi chưa chia, 400) hiện đi cùng đường thử lại với lỗi mạng và kết thúc `failed` mà người dùng **không nhận gì**, kể cả câu xin lỗi; S4 phải phân loại 400, 403, 429, mạng và xin lỗi khi lỗi không phải 403. (2) Tổng thời gian chịu được Telegram lỗi chỉ khoảng 15 giây (backoff 5 + 10 giây với 3 lần thử): tinh chỉnh lúc chạy thử dev. (3) `principal is None` (người dùng không còn hoạt động) vẫn để dòng `processing` đến hết lease rồi `failed`: chuyển `dropped` ở S4.

### S4: Đường gửi (AFK)

**Trạng thái 2026-10-14: ĐÃ XONG trên nhánh `feat/telegram-chatbot`.** Bằng chứng ở Phụ lục A.6.

Chặn bởi: S1.

Mở rộng giả lập đã làm: `Outbox.script(method, (mã, thân JSON)…)` lên kịch bản phản hồi theo phương thức (vd 429 kèm `retry_after`), `Outbox.chat_actions()`, `FakeClock` (đồng hồ giả cho vòng chờ 429, không ngủ thật), `RecordingClient` nhận kịch bản từng lần gửi, và `fake_telegram_server` ghi `sendChatAction` (`/__chat_actions`), làm `count` lần gửi kế tiếp trả lỗi kèm `retry_after` (`/__fail_next`) và làm chậm mỗi lần gửi (`/__delay`). **Hoãn có chủ đích:** service `bot-worker-test` trong compose test chuyển sang S8 (không có tiêu chí nào của S4 cần).

- [x] Tin dài hơn 4096 đơn vị được chia ở ranh giới đoạn, không phần nào quá giới hạn, đúng thứ tự; chia nhiều phần thì gửi lại tiếp từ `sent_parts`, không gọi lại engine và không gửi lại phần đã gửi. Worker khác tiếp quản giữa các phần thì dừng, không gửi tiếp và không hoàn tất.
- [x] Nội dung engine gửi dạng văn bản thuần (không `parse_mode`); `BOT_REPLY_MAX_PARTS` của cấu hình worker thật sự giới hạn câu trả lời.
- [x] Chỉ báo "đang gõ" bắt đầu ngay trước engine (không phải chờ hết một chu kỳ), lặp theo chu kỳ, dừng sau khi xong, lỗi của nó bị bỏ qua mà vòng lặp vẫn sống tiếp; không báo khi chỉ gửi lại câu đã lưu.
- [x] 429: chờ `retry_after` trong giới hạn `BOT_SEND_BUDGET_SECONDS` (tổng các lần chờ không vượt ngân sách, chờ vừa đúng phần còn lại vẫn được); `retry_after` lớn hơn phần còn lại thì dừng ngay và hẹn lần sau không sớm hơn mức đó; thiếu hay bằng 0 thì chờ 1 giây; qua client HTTP thật `parameters.retry_after` tới được vòng chờ; một lần gửi bị treo bị `wait_for` cắt và tính là `send_timeout`.
- [x] 403: `mark_blocked` và dòng `dropped` (`forbidden`), không thử lại, không xin lỗi.
- [x] Người dùng bị khóa, hủy liên kết, liên kết `blocked` hay liên kết chuyển sang người khác, trong lúc tin còn chờ **hoặc trong lúc engine chạy**: dòng `dropped` (`unlinked`, `forbidden`, `user_inactive`), không gọi engine (trường hợp trước) và không gửi (trường hợp sau).
- [x] Câu xin lỗi và thông báo tin quá cũ qua bước kiểm liên kết còn hiệu lực trước khi gửi, và 403 cho chúng gọi `mark_blocked` (hệ quả: test S2 "người dùng chặn bot" nay thấy dòng sau bị `dropped` thay vì được trả lời).
- [x] Phân loại lỗi gửi: mạng, 5xx và hết ngân sách thử lại; 400 và 4xx khác 429 là `failed` (`send_rejected`) kèm xin lỗi; hết lượt vì lỗi gửi thì `failed` kèm xin lỗi (chat còn tới được thì không để im lặng); bảng phân loại có test riêng.
- [x] `principal is None` chuyển dòng sang `dropped` (`user_inactive`) thay vì để `processing` đến hết lease.
- [x] **(thêm)** Câu trả lời rỗng của engine được thử lại thay vì thành `replied` mà không gửi gì; tin quá hạn nhưng đã gửi dở thì được gửi nốt; `BOT_REPLY_MAX_PARTS`, `BOT_SEND_BUDGET_SECONDS`, `BOT_TYPING_INTERVAL_SECONDS` bị chặn ở giá trị dương; mặc định và ánh xạ cấu hình có test; `job_timeout` phải chứa cả hai câu xin lỗi tệ nhất.

**Chuyển sang các lát sau:** dựng `bot-worker-test` để chạy `fake_telegram_server` trong e2e Docker (S8); chỉ số cho số lần 429, số tin chia nhiều phần và số dòng `dropped` theo lý do (S7).

### S5: Chặn lũ và tin không phải văn bản (AFK)

**Trạng thái 2026-10-14: ĐÃ XONG trên nhánh `feat/telegram-chatbot`.** Bằng chứng ở Phụ lục A.7.

Chặn bởi: S1.

- [x] Vượt `BOT_MAX_PENDING_PER_CHAT` thì trả lời lịch sự (`PENDING_LIMIT_TEXT`) và không ghi hộp thư, không đánh chuông. Trần đúng ở biên (đủ trần thì tin kế tiếp bị từ chối), đếm cả `queued` lẫn `processing`, không đếm dòng đã kết thúc, tính theo từng chat, giải phóng khi worker trả lời xong; update bị từ chối vẫn được ghi dedupe nên phát lại không trả lời lần hai; **6 update của cùng một người chạy đồng thời với trần 2 vẫn chỉ ghi đúng 2 dòng**.
- [x] Ảnh, tài liệu, giọng nói, sticker, GIF (và vị trí, danh thiếp, bình chọn, xúc xắc) của người dùng đủ điều kiện nhận câu cố định `NON_TEXT_TEXT` và không vào hộp thư; có `caption` cũng vậy (chú thích không được coi là câu hỏi). Cờ tắt, ngoài danh sách thử hay chưa liên kết thì giữ nguyên `UNKNOWN_TEXT`; tin dịch vụ (ghim tin...) cũng giữ `UNKNOWN_TEXT`; văn bản chỉ có khoảng trắng không hand-off.
- [x] Chat nhóm bị bỏ qua (cả văn bản lẫn ảnh, kể cả từ người đã liên kết); `edited_message` không nhận; người chưa liên kết gõ văn bản vẫn nhận `UNKNOWN_TEXT`, không hand-off.
- [x] `parse_update` mở rộng tối thiểu: `TelegramMessage.kind` (`text`, loại nội dung, hay `other`), không đọc nội dung tệp. `animation` đứng trước `document` vì Bot API đặt cả hai khóa cho GIF.
- [x] **(thêm sau rà soát)** Mỗi chat chỉ nhận **một** thông báo giới hạn (không phải văn bản hay quá trần) trong 10 giây: album 10 ảnh thành một câu, 4 tin văn bản dồn dập sau khi đủ trần thành một câu; hết 10 giây thì thông báo lại; khoảng lặng tính riêng từng chat.
- [x] **(thêm sau rà soát)** Tin không phải văn bản có bộ giới hạn tốc độ riêng (30 tin mỗi 60 giây mỗi người): một album ảnh rồi câu hỏi thật không còn làm câu hỏi bị bỏ im lặng vì bộ giới hạn tin văn bản (10 tin mỗi phút) đã cạn.
- [x] `BOT_MAX_PENDING_PER_CHAT` tối thiểu 1, mặc định 5, ánh xạ từ `Settings` sang `ChatbotPolicy`; TTL mặc định chứa đủ hàng đầy (900 giây trong 1.200 giây); hai chuỗi mới là tiếng Việt có dấu.

**Chuyển sang S7 và S8:** (1) chat đủ trần mà worker không chạy thì mọi tin mới nhận câu "đợi tôi trả lời" cho đến khi worker sống lại, vì dòng `queued` chỉ hết hạn TTL khi được claim (RC-33): S7 cảnh báo dòng `queued` quá cũ. (2) Compose dev chỉ chuyển `CHATBOT_ENABLED` và `CHATBOT_PILOT_USER_EMAILS` vào poller, nên thử trần khác mặc định phải sửa `.env`; `.env.example` và `.env.production.example` chưa có các biến `BOT_*` (S8).

### S6: Engine chỉ đọc (AFK)

**Trạng thái 2026-10-14: ĐÃ XONG trên nhánh `feat/telegram-chatbot`.** Bằng chứng ở Phụ lục A.8.

Chặn bởi: S1.

- [x] `ReadonlySessionFactory` (tạo lười): `INSERT`, `UPDATE`, `DELETE`, `CREATE TABLE`, bảng tạm, `SELECT ... FOR UPDATE` và `FOR SHARE` đều bị từ chối (SQLSTATE `25006`); truy vấn chậm bị hủy đúng hạn (`57014`, khoảng 0,3 giây với timeout 300 ms); phiên rảnh trong giao dịch bị cắt và kết nối kế tiếp là kết nối mới; làm cạn pool chỉ đọc báo lỗi nhanh và **không** chặn engine chính của API.
- [x] `ChatTurn.readonly_session_factory` được nối vào `drain_chat` qua `ctx`; engine thử một truy vấn đọc (chạy) và một lệnh ghi (bị từ chối `25006`); ngữ cảnh không có factory thì lượt vẫn chạy.
- [x] Khi `CHATBOT_ENABLED=false` (hay công cụ chưa gọi) không tạo engine chỉ đọc, không mở kết nối nào; `drain_chat` và cron quét đều thoát sớm.
- [x] Pool nhỏ đặt tường minh cho **cả hai** engine của `bot-worker` (RC-5): `create_bot_engine` (4 + 4) thay cho engine toàn cục 5 + 10, `ReadonlySessionFactory` (2 + 1); `startup` thật sự dùng engine riêng, `shutdown` đóng cả hai và mỗi bước đóng độc lập (một bước lỗi không làm các bước sau kẹt).
- [x] Không công cụ nào nhận SQL hay chuỗi truy vấn tự do từ model: `ToolRegistry` rỗng ở 5.1 (có test), từ chối khai báo vi phạm và kiểm mọi đối số lúc gọi. Engine chỉ đọc chỉ là rào chắn (RC-27), ranh giới cứng là role chỉ-`SELECT` ở 2D.
- [x] **Rò cài đặt giữa các kết nối của pool** (đã đo ở S0, nay đo lại và đóng): phiên cố tình tắt chế độ chỉ đọc, bỏ `statement_timeout`, đổi vai trò (`SET ROLE`, `SET SESSION AUTHORIZATION`), `LISTEN`, cursor `WITH HOLD`, bảng tạm, khóa advisory đều bị đặt lại khi kết nối trở về pool; bước khôi phục bỏ qua kết nối chỉ bị thu gom rác.
- [x] **(thêm)** Kết nối chỉ đọc có nhãn `application_name`; `aclose` đóng thật kết nối và quên engine ngay; cấu hình `BOT_DB_*` và `BOT_READONLY_*` có ràng buộc (tràn không âm, thời gian dương) và ánh xạ đúng từng tham số.

**Chuyển sang 5.2 và các lát sau:** (1) công cụ phải bắt lỗi cả ở lúc thoát `async with`, không giữ phiên qua lúc gọi LLM, và cân lại cỡ pool chỉ đọc (RC-34); (2) span DB cho truy vấn công cụ (S7 hay 5.2); (3) `.env.example` và `.env.production.example` chưa có các biến mới (S8).

### S7: Quan sát (AFK)

**Trạng thái 2026-10-14: ĐÃ XONG trên nhánh `feat/telegram-chatbot`.** Bằng chứng ở Phụ lục A.9.

Chặn bởi: S1.

- [x] Gauge tính lúc scrape; `/metrics` (route thật, qua `install_observability`) trả đúng số liệu trên dữ liệu mẫu: đếm theo trạng thái với biên 24 giờ (23 giờ 50 phút tính, 24 giờ 10 phút không), tuổi dòng claim được cũ nhất (cùng định nghĩa với cron quét, có test nhất quán giữa hai bên), lỗi gần đây trong 30 phút, hạn mức bị từ chối; chatbot tắt thì chỉ báo `enabled=0`; lỗi DB, DB treo (cắt bằng hạn chờ), cache TTL, số cũ không phát như số mới, tuổi không âm khi đồng hồ lệch; nguồn thông báo giá cùng route không bị rớt; mỗi lần scrape phục vụ số của đúng app được scrape.
- [x] Nhóm luật cảnh báo mới `quotify-chatbot` trong `alert_rules.yml` (tên metric khớp mã thật, kiểm bằng test; `promtool check rules` và `promtool test rules` qua, và các test đó đỏ khi đổi ngưỡng, bỏ `for` hay đổi biểu thức).
- [x] Log có cấu trúc chỉ chứa các trường đã liệt kê với giá trị thuộc tập cố định (test hợp đồng có "răng": bắt trường lạ, văn bản tự do, danh mục lạ).
- [x] Test "chuỗi mồi" (10 chữ số, tiền lệ `bugPatterns.md`): nội dung tin và câu trả lời không xuất hiện trong log, audit hay chuỗi ngoại lệ ở mọi nhánh lỗi của worker, bên đánh chuông, chỉ số và `bot.policy` (29 kịch bản; coverage xác nhận mọi vị trí `logger.*` của `bot_worker.py`, `bot_dispatcher.py` và `bot_metrics.py` đều được chạy, trừ câu khởi động cố định).
- [x] **(thêm sau rà soát)** Cảnh báo lỗi dùng gauge 30 phút thay cho `delta` trên gauge 24 giờ; `make alert-rules-check` chạy `promtool` trong image Prometheus; test bom hẹn giờ (dữ liệu mẫu tính theo giờ cố định trong khi route dùng giờ thật) đã sửa.

**Chuyển sang S8:** backend (webhook và `/metrics`) phải nhận `CHATBOT_ENABLED` và `CHATBOT_PILOT_USER_EMAILS`; dev đọc từ `.env`. Cảnh báo "worker chết khi không ai chờ" là healthcheck container của `bot-worker`.

### S8: Vận hành (AFK)

Chặn bởi: S2 đến S7 và S10. **Làm trước S10 theo yêu cầu của bạn (2026-10-14)**; hệ quả: runbook và `.env` mẫu chưa có `BOT_DAILY_*` và `quotify_bot_quota_denied` luôn 0 (test `test_chatbot_env_examples.py` sẽ buộc S10 thêm các biến đó vào hai file mẫu).

- [x] Compose dev, prod (profile `chatbot`; `restart: unless-stopped`, `stop_grace_period` và healthcheck `arq --check` cho `bot-worker`, đã chốt; `health_check_interval` nhỏ trong `BotWorkerSettings`, vì mặc định 3600 giây làm worker chết trông khỏe một giờ), test. Test: `test_chatbot_compose.py` (19). Chạy thật: Docker dev (healthy sau 20 giây, `arq --check` thoát 1 khi không có khóa và 0 khi có) và `bot-worker-test` trong dự án compose tách biệt (Phụ lục A.10).
- [x] `set_webhook` nhận tham số `max_connections` và `telegram_cli set-webhook` có tùy chọn tương ứng (có test); mặc định khi đăng ký trên production là `1` (đã chốt). Thêm theo rà soát: `info` và bản xem trước của `set` in `max_connections` hiện tại.
- [~] Chạy thử toàn bộ trên dev với bot dev `@HHQuotifyBot`, ghi số đo thực tế (độ trễ từ lúc nhắn đến lúc trả lời, số lần thử lại, số tin chờ) và tinh chỉnh bảng 4.8 (đã chốt làm giá trị khởi điểm). **Một phần:** đã ghi số đo từ các lần thử thật của S3 đến S7 (Phụ lục A.10); engine hiện là engine giả nên số đo chỉ là độ trễ của đường ống, **bảng 4.8 giữ nguyên** làm giá trị khởi điểm cho đến khi có engine thật (2A).
- [x] `.env.example` và `.env.production.example` có các biến mục 4.8 (không `${VAR:?}`), gồm `CHATBOT_ENABLED` và `CHATBOT_PILOT_USER_EMAILS` cho **backend** (webhook và `/metrics`, vì compose chỉ chuyển hai biến này cho `telegram-poller` và `bot-worker` qua `environment`). Test `test_chatbot_env_examples.py` (7): mọi biến `BOT_*`/`CHATBOT_*` của `Settings` có mặt ở cả hai file, giá trị bằng mặc định, production không có biến chỉ dành cho dev.
- [x] Runbook mục 16 (không đánh số lại 13 đến 15) gồm công tắc tắt khẩn cấp, đọc metric, đặt danh sách thử; cập nhật mọi danh sách build/recreate nêu ở mục 10. **Phạm vi:** các danh sách dùng lại (§3, §9.4, §9.7, §15.6) có `bot-worker`; các trình tự phát hành đã làm một lần (§12.8, §13, §14, §15.2) giữ nguyên và ghi rõ là lịch sử ở 16.1. Khối SQL của mục 16 được lấy nguyên văn và chạy trên Postgres thật (`test_bot_runbook_db.py`).
- [x] Script kiểm sẵn sàng riêng cho chatbot, gọi từ `check-production-readiness.sh` (kèm `config --profile chatbot`); `make production-readiness-check` qua. Các kiểm compose khóa vào khối service `bot-worker` và bỏ dòng ghi chú.
- [x] `CONTEXT.md` (thuật ngữ "Hộp thư bot", "Chuông", "Lease"), `memory-bank/`, journal `.agent-memory`.

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
| RC-5 | Cạn kết nối Postgres: mỗi tiến trình bot có hai engine, mặc định 5 + 10 kết nối cho engine chính. `max_connections` của production **[CHƯA XÁC MINH]** | Bỏ qua kiểm `max_connections` theo quyết định 2026-10-13 (chuyển thành điều kiện của 2A); đặt `pool_size` nhỏ tường minh cho cả hai engine của worker bot (**đã làm ở S6**: `create_bot_engine` với `BOT_DB_*`, engine chỉ đọc với `BOT_READONLY_*`, tổng tối đa 11 kết nối mỗi `bot-worker`); không giữ kết nối trong lúc gọi LLM |
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
| RC-27 | Engine DB chỉ đọc chỉ là rào chắn: một câu `SET default_transaction_read_only=off` hoặc `SET TRANSACTION READ WRITE` tắt được chế độ chỉ đọc, cài đặt đó rò sang kết nối dùng lại trong pool (cả `SET statement_timeout=0`), và `pg_advisory_lock` mức phiên vẫn được phép (đo ở S0(a)) | Không công cụ nào nhận SQL hay chuỗi truy vấn tự do từ model (5.2); test ở S6; **đã làm ở S6**: sự kiện `reset` của pool đặt lại cài đặt, vai trò, LISTEN, cursor, khóa advisory và bảng tạm mỗi lần trả kết nối (còn sót `PREPARE` do người dùng tạo, có chủ đích); `ToolRegistry` từ chối khai báo và lời gọi nhận SQL; ranh giới cứng là role chỉ-`SELECT` ở 2D |
| RC-28 | Thông điệp ngoại lệ của SQLAlchemy kèm **tham số của câu lệnh lỗi**, tức nội dung tin hay câu trả lời (reviewer tái hiện với ký tự NUL), và log lỗi hoặc log của arq in ra | Mọi lệnh DB mang nội dung bọc `BotInboxError` không chứa tham số (S1, có test chuỗi mồi ở cả đường webhook và đường worker); `repr` của `ChatTurn`, `ClaimedRow`, `BotPrincipal` che nội dung; S7 mở rộng sang mọi nhánh lỗi. Chưa đặt `hide_parameters` ở engine chung vì đổi hành vi toàn ứng dụng |
| RC-29 | Test đua và chaos dễ **xanh giả** hoặc **chập chờn**: lần chạy đầu của bài chaos chỉ có 5 lần tiếp quản trên 120 dòng (trải 4 tiến trình trên 24 chat nên hiếm khi tranh cùng một chat) và biến thể sai chỉ bị bắt 1 trong 3 lượt; sau rà soát còn 6 đột biến trên code thật mà bộ test không bắt được | Tập trung tranh chấp vào vài chat (70 lần tiếp quản trên 60 dòng) kèm sàn `takeovers >= 10` trong test; mọi biến thể sai phải bị bắt đúng bằng một vi phạm thật (không tính quá hạn); thêm test xác định cho các lớp bảo vệ mà chaos chỉ che xác suất; mọi chờ đều có thời hạn và tiến trình con luôn bị kill; URL có mật khẩu không làm tham số test |
| RC-30 | Lỗi bất ngờ thoát khỏi vòng xử lý giữ lease của chat đến 240 giây (mất cả câu trả lời đã trả tiền nếu lỗi rơi vào bước lưu), hoặc thông điệp ngoại lệ của engine lọt vào log qua chuỗi `__context__` khi DB lỗi ngay sau đó; còn một cửa sổ cỡ mili giây khi `SIGTERM` rơi đúng lúc chờ commit của claim | `drain_chat` nhả lease với mọi ngoại lệ (không chỉ `CancelledError`) và phủ cả đoạn claim; xử lý lỗi engine và lỗi gửi ngoài khối `except`; test tái hiện cả ba (S3, rà soát độc lập). Cửa sổ còn lại chấp nhận: lease tự hết hạn như `SIGKILL` |
| RC-31 | Cron quét lấy tối đa 500 chat mỗi lần, sắp theo `chat_id`: nếu hàng trăm chat cùng chờ thì chat có id lớn được rung muộn hơn một chu kỳ | Chưa chạm trần ở quy mô hiện tại; đổi sang sắp theo `update_id` hoặc đặt giới hạn thành tham số khi số người dùng chatbot đủ lớn (S8, sau khi chạy thử dev). Test sweep dọn dòng còn mở của test khác để không phụ thuộc trần này |
| RC-32 | Bộ giới hạn tốc độ có sẵn của runner (10 tin văn bản mỗi 60 giây mỗi người) bỏ tin **im lặng**, không ghi dedupe và không trả lời: người gõ quá 10 tin trong một phút thấy tin thứ 11 trở đi biến mất và phải tự gõ lại | Chấp nhận (hành vi có từ 1A, KT15 giữ nguyên). S5 giảm đụng độ: trần tin chờ ở 5 cho câu lịch sự sớm hơn, tin không phải văn bản có suất riêng 30 mỗi phút, thông báo giới hạn tối đa một câu mỗi 10 giây. Có thể báo `TOO_FAST_TEXT` một lần khi bộ giới hạn chặn người dùng chatbot nếu dev thấy cần |
| RC-33 | Chat đủ `BOT_MAX_PENDING_PER_CHAT` dòng `queued` mà worker không chạy (hỏng, hay tắt công tắc trong lúc API còn bật chatbot): mọi tin mới nhận "đợi tôi trả lời các câu trước" vì dòng `queued` chỉ hết hạn TTL khi được claim | Không kẹt vĩnh viễn: worker sống lại thì dòng quá TTL bị `dropped` (`expired`) kèm một thông báo; dòng `processing` chết lease thì claim tiếp quản tối đa `BOT_MAX_ATTEMPTS` lần rồi `lease_exhausted`. Trước S5 các dòng cứ tích lũy im lặng. S7 thêm cảnh báo dòng `queued` quá cũ; có thể chỉ đếm dòng trong hạn TTL nếu thấy cần |
| RC-34 | Khi công cụ thật của 5.2 tới, cỡ pool chỉ đọc (2 + 1, chờ 3 giây) và hai hạn thời gian của phiên chỉ đọc (lệnh tối đa 5 giây, rảnh trong giao dịch tối đa 10 giây) có thể làm lượt hỏi chờ hay bị cắt oan nếu công cụ chạy song song nhiều lệnh chậm hoặc giữ phiên mở qua lúc gọi LLM; lỗi cắt phiên rảnh còn ném cả ở `session.close()` | Ở 5.1 chưa xảy ra (không ai giữ phiên chỉ đọc qua lúc gọi LLM, kiểm bằng đọc code: `_process_row` đóng mọi phiên trước `_ask_engine`). 5.2 phải mở phiên ngắn cho mỗi lần gọi công cụ, bắt lỗi ở cả câu lệnh lẫn thoát `async with`, và đo lại cỡ pool bằng tải thật khi chạy thử dev |
| RC-35 | Giới hạn của lớp quan sát: (a) truy vấn đếm theo trạng thái quét tuần tự bảng `bot_updates` (đo: khoảng 4 ms với 50 nghìn dòng, 30 đến 55 ms với 570 nghìn dòng, mỗi 15 giây); (b) cảnh báo lỗi chỉ thấy dòng `failed` kết thúc trong 30 phút, nên một lỗi xảy ra khi Prometheus không scrape quá 30 phút sẽ không báo; (c) không có cảnh báo "worker chết" khi không ai đang chờ; (d) backend không nhận cờ chatbot thì `quotify_bot_enabled=0` và mọi cảnh báo im | (a) Quy mô dự kiến vài nghìn dòng vì dòng kết thúc bị xóa sau `BOT_TERMINAL_RETENTION_DAYS`; nếu cần thì tách hai truy vấn (đang mở / kết thúc theo cửa sổ) để dùng chỉ mục. (b) Chấp nhận (Prometheus scrape mỗi vài chục giây). (c) Healthcheck container `bot-worker` và runbook ở S8. (d) S8 thêm hai cờ vào `.env.example` cho backend và script kiểm sẵn sàng |
| RC-36 | arq và bên đánh chuông đọc `REDIS_HOST` và `REDIS_PORT`, **không** đọc `REDIS_URL`; compose test chỉ đặt `REDIS_URL`, nên `worker-test` và `backend-e2e` nối tới host `redis` (lấy từ `.env` của dev) chứ không phải `redis-test`. Phát hiện khi một phép thử "âm" (đổi `REDIS_URL` để chứng minh `arq --check` hỏng) vẫn qua | Đã đặt `REDIS_HOST: redis-test` ở `bot-worker-test` và `backend-e2e`, có test; `worker-test` và `backend-test` còn lại là nợ hiện hữu, không sửa lan (không E2E nào dùng hàng đợi) |
| RC-37 | `restart: unless-stopped` chỉ chạy khi tiến trình **thoát**; worker **treo** (vòng lặp bị chặn, mất Redis) chỉ làm container `unhealthy` và không ai khởi động lại (repo không có autoheal) | Runbook 16.4 nói rõ phải `restart bot-worker` bằng tay khi `ChatbotQueueStuck` nổ; chưa có cảnh báo theo trạng thái container (cần nguồn số đo container, chưa có) |
| RC-38 | Chatbot tắt thì worker không chạy, nên dòng còn mở giữ nguyên nội dung tin (`payload_text`, `reply_text`) vô thời hạn | Runbook 16.5 có câu lệnh dọn (đã chạy thử trên Postgres thật, người gửi không nhận thông báo); chưa tự động hóa |

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

### A.5 Kiểm chứng S3 (2026-10-14)

| Hạng mục | Kết quả |
|---|---|
| Test mới của S3 | 35 test: 23 ở `test_bot_resilience_db.py` (thử lại, `failed`, tiếp tục từ câu đã lưu, rào chắn, hủy, lỗi bất ngờ, rò nội dung), 8 ở `test_bot_sweep_db.py` (quét và dọn), 4 ở `tests/test_bot_worker.py` (lịch cron, mặc định và ánh xạ cấu hình, độ trễ giả chỉ ở dev) |
| Toàn bộ bộ test backend (máy host) | **1.387 qua, 0 fail** (158,6 giây); mốc trước S3 là 1.352, nên đúng 35 test thêm. Lần chạy có coverage báo `INTERNALERROR` lúc ghi `htmlcov/` vì một file cũ thuộc người dùng khác (nhiều khả năng là dấu vết của một lần chạy Docker trước); đó là lỗi môi trường, không liên quan code, lần chạy kết quả dùng `--no-cov` |
| Cổng chất lượng | ruff 62, `mypy app` 15, bandit 16 low và 1 medium: bằng baseline; 9 file đụng tới đúng định dạng. `.ruff_cache` bị chặn quyền nên chạy `--no-cache` |
| Chạy thật trên Docker dev và bot dev (bạn nhắn tin) | **(1) `SIGTERM` giữa lượt:** engine giả đợi 25 giây; dòng 678129877 bị dừng lúc 08:18:40, ngay sau đó trong DB là `processing`, `attempts=1`, lease **đã nhả**, nội dung còn nguyên; log worker có `CancelledError` và "Bot worker shutting down". Khởi động lại: cron quét rung chuông (`bot.sweep rang=1`) lúc 08:19:10, dòng được claim lần 2, xử lý 1,46 giây, `replied`, bạn nhận **một** câu trả lời, 29 giây sau khi khởi động lại. **(2) Mất chuông:** tắt worker, bạn nhắn tin, tôi xóa `arq:job:bot:678129878` và mục tương ứng khỏi `quotify:bot` (DB vẫn `queued`, `attempts=0`); khởi động worker: lần quét đầu tiên rung lại, dòng `replied` sau 39 giây, `attempts=1`. Đường bình thường (dòng 678129876, engine giả 25 giây): `replied` sau 26,12 giây |
| Độ nhạy trên code thật | Đột biến lần đầu: **13 trên 13 bị bắt** (trước rà soát) |
| Rà soát độc lập (agent) | Chạy 68 đột biến trên bản sao, 42 bị bắt, 26 sống (1 tương đương). Phát hiện thật: **(1a)** lỗi bất ngờ giữ lease 240 giây (tái hiện: `save_reply` ném `BotInboxError`), **(1b)** `SIGTERM` rơi vào bước đóng phiên sau commit của claim giữ lease, **(2)** thông điệp ngoại lệ của engine lọt vào traceback qua `__context__` khi DB lỗi ngay sau đó. **Cả ba đã sửa theo TDD** (test đỏ trước, rồi mới sửa code). Đã thêm test cho các đột biến sống: bốn lệnh có rào chắn `attempts` (chỉ lộ khi worker mới còn sống), `shield` (hủy lần hai), `DISTINCT ON` và `ORDER BY` của quét, backoff nhân `attempts`, điều kiện `changed` của câu xin lỗi, lịch cron, ánh xạ và mặc định cấu hình, biên 30 ngày của dọn, rò nội dung ở đường thành công và đường gửi lỗi. **27 đột biến đại diện của tôi nay đều bị bắt**. Còn sống và **chấp nhận**: bỏ `status='processing'` khỏi `requeue` và `release_lease` (gần tương đương khi còn rào `attempts`), nhánh `if not saved` (gần tương đương vì `owns()` ở dòng sau chặn thay), `>` thành `>=` ở hạn TTL (đột biến biên) |
| Quyết định giữ nguyên | Lỗi gửi cuối cùng không xin lỗi (chuyển S4 với phân loại lỗi); không thêm validator `ge` cho các biến mới (ý kiến, không phải lỗi); giới hạn 500 chat của cron quét ghi thành RC-31 |
| Độ ổn định | Ba lần chạy liên tiếp và hai lần chạy khi 12 lõi CPU bị đốt: 5 trên 5 qua (38 test, 4,6 đến 11,6 giây). Test race dùng `asyncio.Event` và `wait_for(5)`; các assert về backoff dùng biên 5 giây trở lên. Test sweep nay dọn dòng còn mở của test khác trước mỗi test |
| Điểm đáng nhớ | Các test "worker cũ" ban đầu để worker mới xong trước (`replied`), lúc đó điều kiện `status` đã chặn thay nên **không chứng minh được** rào chắn `attempts` của từng câu lệnh; chỉ test giữ worker mới còn sống mới lộ được (bài học dùng được cho mọi test rào chắn) |

Chưa kiểm: `SIGTERM` và mất chuông trên image production (chỉ kiểm trên image dev), Redis nửa chết thật cho đường quét, `max_connections` Postgres khi nhiều worker, và cron quét ở quy mô vài trăm chat.

### A.6 Kiểm chứng S4 (2026-10-14)

| Hạng mục | Kết quả |
|---|---|
| Test mới của S4 | **74 test ròng** (toàn bộ bộ test từ 1.387 lên 1.461): 28 ở `test_bot_send_db.py` (chia và gửi tiếp, phân loại lỗi, 429 và ngân sách, "đang gõ", câu rỗng), 9 ở `test_bot_recipient_db.py` (ai còn được nhận tin), 19 ở `test_bot_reply_sender.py` (hàm chia tin), cộng test cho cấu hình và bảng phân loại lỗi (`test_bot_worker.py`), `send_chat_action` (`test_telegram_client.py`) và giả lập Telegram (`test_fake_telegram_server.py`) |
| Toàn bộ bộ test backend (máy host) | **1.461 qua, 0 fail** (161 giây) |
| Cổng chất lượng | ruff 62, `mypy app` 15, bandit 16 low và 1 medium: bằng baseline; 18 file đụng tới đúng định dạng |
| Chạy thật trên Docker dev với bot dev (bạn xác nhận bằng mắt) | **(1) "Đang gõ":** engine giả đợi 25 giây; bạn thấy "typing…" dưới tên bot suốt khoảng 25 giây rồi nhận câu trả lời; server ghi dòng 678129879 xử lý 25,5 giây, `replied`, `sent_parts=1`. **(2) Tin dài:** một câu trả lời khoảng 9.000 ký tự (6 đoạn đánh số, có emoji) gửi qua client thật: bạn nhận **đúng 3 tin liên tiếp, đúng thứ tự, emoji đúng**, chỗ nối tin nằm ở ranh giới đoạn (tin đầu hết trọn câu ở "Đoạn 2/6", tin sau bắt đầu từ "Đoạn 3/6"); server ghi `replied`, `sent_parts=3`, một lần thử. Chưa thử trên Telegram thật: 429 (không gây được một cách tin cậy; đã kiểm bằng client HTTP giả có `parameters.retry_after`) và 403 khi người dùng chặn bot |
| Độ nhạy trên code thật | **49 đột biến đại diện đều bị bắt** (rào chắn `sent_parts`, ranh giới chia tin, biên ngân sách, nhánh 403 và 400, kiểm người nhận ba lần, `_notify`, tác vụ "đang gõ", rò log, giá trị mặc định và ràng buộc cấu hình). Lần chạy đầu có 6 đột biến sống và 1 mốc không khớp; đã thêm test cho cả sáu (biên đúng bằng giới hạn, khoảng trắng sau chỗ cắt cứng và trước dấu "…", chờ 429 vừa đúng phần còn lại, nhận biết mất quyền giữa các phần qua log, rò thông điệp ngoại lệ qua `_notify`) |
| Rà soát độc lập (agent) | Không có lỗi nghiêm trọng, không có race hay rò log mới. Fuzz 200.000 ca bộ chia (không mất, không trùng, không vượt giới hạn), khoảng 100 đột biến trên bản sao (62 bị bắt, 37 sống). Phát hiện đáng sửa và **đã sửa theo TDD**: **(A1)** chọn dấu ngắt đoạn sớm nhất làm một tiêu đề 8 ký tự chiếm cả một tin và cắt cụt 3.000 ký tự cuối (tái hiện bằng "tiêu đề rồi 150 dòng"); **(A2)** 429 với `retry_after` lớn hơn ngân sách chỉ requeue với backoff cố định nên cạn lượt thử trong khoảng 15 giây; **(A3)** `retry_after` bằng 0 và `BOT_TYPING_INTERVAL_SECONDS` bằng 0 làm vòng lặp chạy không nghỉ (đo được 282.000 và 152.000 lần gọi); **(A4)** tin đã gửi dở mà quá hạn bị loại kèm "vui lòng gửi lại". Đã gỡ nhánh chết `TelegramMessageTooLongError` (chia tin bảo đảm không xảy ra). Các điểm còn lại chấp nhận: lỗi 4xx lạ rơi vào "bị từ chối" thay vì thử lại, `wait_for` hủy đúng lúc Telegram đã nhận tin có thể gửi trùng (at-least-once) |
| Lỗi do chính tôi gây ra trong lúc làm | Lệnh `ruff check --fix` chạy trên cả thư mục `app` tự sắp xếp lại import ở ba file ngoài phạm vi (`db/base.py`, `models/quote.py`, `services/quote_pricing.py`); phát hiện qua `git status`, đã khôi phục đúng ba file đó. Chỉ chạy `--fix` trên từng file đã sửa |
| Độ ổn định | Ba lần chạy liên tiếp (106 test, 8,4 đến 8,6 giây) và hai lần khi 12 lõi CPU bị đốt (17 đến 19 giây): 5 trên 5 qua. Vòng chờ 429 dùng đồng hồ giả, không ngủ thật; các chỗ chờ khác đều có thời hạn |
| Điểm đáng nhớ | Bản chia tin đầu tiên (ranh giới đoạn cuối cùng trong cửa sổ) cho kết quả đúng ở mọi test ban đầu mà vẫn tệ với "tiêu đề ngắn rồi danh sách dài": test chỉ có ví dụ đẹp thì không thấy. Fuzz với bất biến (không rỗng, không vượt giới hạn, không mất nội dung) cộng ví dụ thực tế bắt được cả hai loại lỗi |

### A.7 Kiểm chứng S5 (2026-10-14)

| Hạng mục | Kết quả |
|---|---|
| Test mới của S5 | **56 test ròng** (toàn bộ bộ test từ 1.461 lên 1.517): 30 ở `test_bot_limits_db.py` (tin không phải văn bản, trần tin chờ, thông báo một lần, bộ giới hạn riêng, chat nhóm, tin bị sửa, đồng thời), phần còn lại ở `test_telegram_update_parsing.py` (nhận biết loại tin, GIF, tin dịch vụ) và `test_bot_policy.py` (trần, TTL, chuỗi tiếng Việt có dấu); mở rộng `make_media_update` (ảnh nhiều cỡ, `media_group_id`, cặp `animation` và `document` như payload thật, bản sao sâu) và factory dựng bot nhận tham số runner (bộ giới hạn, đồng hồ giả) |
| Toàn bộ bộ test backend (máy host) | **1.517 qua, 0 fail** (181 giây) |
| Cổng chất lượng | ruff 62, `mypy app` 15, bandit 16 low và 1 medium: bằng baseline; 11 file đụng tới đúng định dạng; không có thay đổi ngoài phạm vi |
| Chạy thật trên Docker dev với bot dev (bạn xác nhận bằng ảnh chụp) | Một album ảnh (4 update) nhận **đúng một** câu "chỉ đọc được văn bản"; câu "xin chào" ngay sau đó **vẫn được nhận** và trả lời; 7 tin "1" đến "7" gửi liền: 5 tin đầu xếp hàng và được trả lời lần lượt (mỗi 20 giây, engine giả), tin 6 và 7 nhận **chung một** câu "nhiều câu hỏi cùng lúc" và không được trả lời sau đó. Server khớp: dòng hộp thư chỉ có "xin chào" và tin 1 đến 5 (`replied`, một lần thử), 12 update ghi dedupe |
| Độ nhạy trên code thật | **23 đột biến đại diện đều bị bắt** (nhánh loại tin, cổng pilot, `command is None`, `>=` của trần, từng trạng thái trong phép đếm, lọc theo chat, `text` không phải chuỗi, thứ tự `animation` và `document`, tin dịch vụ, giữ trần ở chính sách, ràng buộc cấu hình, giảm tần suất thông báo và khóa theo chat, bộ giới hạn riêng và suất của nó, khoảng lặng 10 giây, chuỗi tiếng Việt, và **bỏ lần ghi `last_seen_at`** làm trần thành mềm). Lần chạy đầu có 1 đột biến sống (khóa giảm tần suất theo độ dài chuỗi thay vì theo chat); đã thêm test hai chat cùng gửi ảnh |
| Rà soát độc lập (agent) | Không có lỗi đúng-sai ở nhánh xử lý hay phép đếm trần; đo thật 20 update đồng thời: trần 1, 2, 5 nhận đúng 1, 2, 5. Phát hiện và **đã sửa theo TDD**: **(A)** album ảnh rồi hỏi tiếp làm câu hỏi bị bỏ im lặng (10 ảnh ăn hết suất 10 tin mỗi phút của bộ giới hạn, tái hiện: 9 câu "chỉ đọc văn bản" giống hệt rồi câu hỏi thật biến mất); **(B)** GIF bị gắn nhãn `document` vì thứ tự khóa; **(D)** tin dịch vụ (ghim tin) nhận câu "chỉ đọc văn bản" nghe vô lý, nay giữ `UNKNOWN_TEXT`. Ghi nhận không sửa: **(C)** trần chính xác nhờ khóa dòng `last_seen_at` (nay có test chạy đồng thời và comment đúng thực tế), **(E)** chat kẹt ở trần khi worker không chạy (RC-33), bộ giới hạn bỏ tin im lặng (RC-32), TTL chỉ kiểm ở giá trị mặc định (như các biến `BOT_*` khác, không có kiểm tra chéo) |
| Độ ổn định | Ba lần chạy liên tiếp (105 test, 5,6 đến 5,8 giây) và hai lần khi 12 lõi CPU bị đốt (10,7 đến 12,6 giây): 5 trên 5 qua. Test thông báo một lần dùng đồng hồ giả của runner, không ngủ thật |
| Điểm đáng nhớ | Hai chuỗi mới ban đầu định đặt tên `BUSY_TEXT`; tên đó **đã tồn tại** với nghĩa khác (báo "bấm lại sau" cho nút duyệt giá) và test đỏ vì lý do khác với dự kiến nhờ thứ tự viết test trước. Đã đổi sang `PENDING_LIMIT_TEXT` để không đụng chuỗi cũ. Và: một chức năng thông báo "thân thiện" phải xét cả đường bị chặn phía trước nó (bộ giới hạn bỏ tin im lặng) thì mới thật sự thân thiện |

Chưa kiểm: gửi album thật rất lớn (nhiều chục ảnh) và hành vi khi `max_connections=1` ở production (S9).

### A.8 Kiểm chứng S6 (2026-10-14)

| Hạng mục | Kết quả |
|---|---|
| Test mới của S6 | **116 test ròng** (toàn bộ bộ test từ 1.517 lên 1.633): 25 ở `test_readonly_db.py` (Postgres thật: ghi bị từ chối, hủy đúng hạn, cô lập pool, cắt phiên rảnh, tạo lười, các vector tấn công vào cài đặt phiên, nối vào worker, cấu hình), 74 ở `test_chat_tools.py` (kiểm định khai báo và kiểm lúc gọi), 5 ở `test_readonly_reset.py` (các nhánh của bước khôi phục, không cần DB), và 12 ở `test_bot_worker.py` (pool tường minh, cấu hình, `shutdown`) |
| Toàn bộ bộ test backend (máy host) | **1.633 qua, 0 fail** (176 giây) |
| Cổng chất lượng | ruff 62, `mypy app` 15, bandit 16 low và 1 medium: bằng baseline; 11 file đụng tới đúng định dạng; không có thay đổi ngoài phạm vi |
| Thực nghiệm đầu lát (rò cài đặt giữa các kết nối) | Xác nhận lại trên Postgres dev: không có gì thì kết nối kế tiếp là `default_transaction_read_only=off`, `statement_timeout=0` và tạo được bảng tạm. `RESET ALL` trả đúng giá trị lúc khởi tạo kết nối (`on`, `5s`, `10s`); khôi phục khi trả về pool (sự kiện `reset`) và khôi phục khi lấy ra (`checkout`) cũng đúng, chọn `reset` vì kết nối nằm rảnh trong pool cũng sạch |
| Chạy thật trên Docker dev (database `app` thật, trong container `bot-worker`) | Engine chưa tồn tại trước lần gọi đầu; đọc được; ghi bị từ chối `25006`; trạng thái phiên `('on', '5s', '10s', 0 khóa, không bảng tạm)`; sau một phiên tấn công (`SET TRANSACTION READ WRITE`, tắt chế độ chỉ đọc, `statement_timeout=0`, bảng tạm, khóa advisory) phiên kế tiếp vẫn `('on', '5s', '10s', 0, False)`; `aclose` quên engine. Sau khi tạo lại worker bằng code S6 cuối cùng, bạn nhắn "kiểm tra" trên Telegram và nhận câu trả lời của stub ngay (đường ống đầu-cuối với engine và pool mới của worker vẫn đúng; stub engine không dùng engine chỉ đọc nên phần đó chỉ kiểm bằng script trên database dev) |
| Độ nhạy trên code thật | **66 đột biến đại diện đều bị bắt** (bỏ `event.listen`, từng lệnh khôi phục, bảo vệ thu gom rác, chế độ chỉ đọc và hai timeout trong `server_settings`, `pool_timeout`, `pool_pre_ping`, hoán đổi tham số, nhãn kết nối, `aclose` không đóng hay quên muộn, `ChatTurn` không nhận factory, `startup` không dùng engine riêng, `shutdown` không đóng hay nuốt lỗi, mặc định và ràng buộc cấu hình, và toàn bộ nhánh của `validate_tool`, `validate_arguments`, `ToolRegistry`). Lần chạy đầu có 4 đột biến sống: `RESET ROLE` (thừa vì `RESET SESSION AUTHORIZATION` đã đưa vai trò về mặc định, nên bỏ lệnh đó), `aclose` không đóng kết nối (thêm nhãn `application_name` và test đếm kết nối trong `pg_stat_activity`), bỏ bước bỏ dấu và bước gấp chữ `đ` trong chuẩn hóa tên (thêm test `điều_kiện`, `quéry`) |
| Rà soát độc lập (agent) | Không có lỗi mức cao. Phát hiện thật và **đã sửa theo TDD**: **(1)** bước khôi phục chưa dọn `SET ROLE`, `SET SESSION AUTHORIZATION`, `LISTEN`, cursor `WITH HOLD` (tái hiện cả bốn; `PREPARE` còn sót có chủ đích, và `DEALLOCATE ALL` bị cấm vì làm hỏng cache asyncpg); **(2)** handler chạy I/O cả khi kết nối chỉ bị thu gom rác (log ERROR nhiễu); **(3)** `aclose` quên engine sau khi đóng nên một lần gọi chen vào để lại một backend mồ côi; **(4)** `shutdown` dừng ở bước lỗi đầu tiên và bỏ sót đóng dispatcher và client; **(5)** cổng công cụ chỉ kiểm khai báo: `handler(sql="drop table users")` vẫn chạy, nhiều tên lọt qua (`where_clause`, `ma_truy_van`, chữ toàn-rộng...), khai báo suy biến (`enum=()`, `max_length=0`), danh sách tham số sửa được sau khi dựng, tên công cụ tùy ý. Cộng các khoảng trống test (startup có dùng pool riêng không, `max_overflow=-1` nghĩa là không giới hạn nên phá RC-5, `pool_pre_ping`, chưa kiểm ánh xạ timeout). Không phải lỗi, ghi nhận: OTel singleton làm engine chỉ đọc không có span (không áp instrument), lỗi cắt phiên rảnh ném cả ở `session.close()`, cỡ pool chỉ đọc cần đo lại khi có công cụ thật (RC-34) |
| Độ ổn định | Ba lần chạy liên tiếp (183 test, 9,9 đến 11,3 giây) và hai lần khi 12 lõi CPU bị đốt (15,4 và 19,0 giây): 5 trên 5 qua. Test dùng `sleep` thật chỉ một chỗ (cắt phiên rảnh, chờ 0,9 giây), chỉ cần server cắt sớm hơn nên không phụ thuộc tải |
| Điểm đáng nhớ | Test đầu tiên giả lập "kẻ tấn công" bằng hai giao dịch liên tiếp và **tự bị chính bước khôi phục hoàn tác** (commit trả kết nối về pool): phải làm trong một giao dịch duy nhất, đúng như kẻ tấn công thật. Và: một kiểm tra chỉ ở khai báo không ngăn được model đưa đối số lạ vào handler, nên phải kiểm cả lúc gọi |

Chưa kiểm: Postgres production (`max_connections`, role chỉ-`SELECT` ở 2D), việc gọi thật nhiều công cụ song song (5.2), và tối ưu gộp bước khôi phục thành một vòng gọi (tùy chọn, dùng API nội bộ của adapter).

### A.9 Kiểm chứng S7 (2026-10-14)

| Hạng mục | Kết quả |
|---|---|
| Test mới của S7 | **39 test ròng** (toàn bộ bộ test từ 1.633 lên 1.671 qua cộng 1 bỏ qua có chủ đích): 29 ở `test_bot_metrics_db.py` (Postgres thật: truy vấn dòng claim được cũ nhất, số đo, gauge lỗi gần đây, hạn mức, cổng tắt chatbot, lỗi và treo DB, cache, route `/metrics` thật, hai app), 2 ở `test_bot_logs_db.py` (hợp đồng log và chuỗi mồi 29 kịch bản; kiểm hợp đồng có răng), 8 ở `test_bot_alert_rules.py` (luật khớp số đo thật, ngưỡng và `for` chính xác, và test gọi `promtool` khi máy có sẵn) |
| Toàn bộ bộ test backend (máy host) | **1.671 qua, 1 bỏ qua, 0 fail** (179 giây). Test bỏ qua là test gọi `promtool` (máy host không cài); đã chạy riêng qua Docker: `make alert-rules-check` (10 luật hợp lệ, kiểm thử luật qua) và chạy test pytest đó với một shim gọi Docker (qua) |
| Cổng chất lượng | ruff 62 (sau khi sửa 3 dòng quá dài tôi đã để lọt), `mypy app` 15, bandit 16 low và 1 medium: bằng baseline; 6 file Python đụng tới đúng định dạng |
| Kiểm thử luật cảnh báo bằng `promtool` | `docker/observability/tests/chatbot_alert_rules_test.yml` mô phỏng chuỗi số đo: hàng đợi kẹt báo sau 5 phút và không báo với một đợt chờ ngắn hay khi series vắng; lỗi gần đây báo sau 1 phút, hết sau cửa sổ, không báo khi bằng 0; một dòng lỗi cũ rơi khỏi cửa sổ 24 giờ đúng lúc có lỗi mới vẫn báo (điều `delta` bỏ sót); không đọc được hộp thư báo sau 10 phút. Kiểm "răng": đổi ngưỡng 600, bỏ `for`, đổi `delta` thành mức, đổi `up==1` đều làm bài kiểm đỏ |
| Chạy thật trên Docker dev (backend dev, chatbot bật bằng file override tạm ngoài repo) | `/metrics` trả `quotify_bot_metrics_up 1`, `quotify_bot_enabled 1`, `quotify_bot_updates{status="replied"} 16` (khớp 16 dòng `replied` trong DB), các trạng thái khác bằng 0, `quotify_bot_quota_denied 0`; khi chưa bật cờ trong môi trường backend thì `quotify_bot_enabled 0` và không có số đo hàng đợi. Phát hiện: compose dev không chuyển `CHATBOT_ENABLED` cho backend (chỉ cho poller và bot-worker), đã ghi cho S8 |
| Độ nhạy trên code thật | **53 đột biến đại diện: 51 bị bắt và 2 chấp nhận** (một đột biến sống thật đã được bắt sau khi thêm test hai app) (cửa sổ 24 giờ và 30 phút ở mọi biên, bộ lọc trạng thái, `finished_at` thay `received_at`, hạn mức, cổng tắt, cache, hạn chờ, đủ 5 trạng thái, đổi tên số đo và nhãn, từng nhánh của SQL dòng claim được, route thiếu một nguồn hay thiếu gán collector, rò thông điệp ngoại lệ hay nội dung vào log và vào cột `error_category`, trường lạ và văn bản tự do trong log, ngưỡng và `for` trong YAML). Chấp nhận: điều kiện `lease_until <= now` của dòng `processing` (tương đương vì `NOT EXISTS` đã loại sẵn dòng đang chạy) và việc gán collector lúc cài đặt (thừa vì mỗi scrape gán lại). Đột biến sống thật là bỏ việc gán collector ở mỗi scrape (hai app trong một tiến trình thì app cài sau chiếm collector), đã bắt bằng test hai app |
| Rà soát độc lập (agent) | Không có lỗi đúng-sai ở sản phẩm. Chạy 800 ca ngẫu nhiên so `claim()` thật với truy vấn tuổi (không lệch ca nào), EXPLAIN ở 50 nghìn và 570 nghìn dòng, 92 đột biến (56 bị bắt, 36 sống trong đó nhiều tương đương hay ngoài phạm vi). Phát hiện và **đã sửa**: **(1)** test endpoint là bom hẹn giờ (dữ liệu mẫu tính theo giờ cố định, route dùng giờ thật; sẽ hỏng từ 09:59 ngày hôm sau); **(2)** `ChatbotUpdatesFailing` dùng `delta` trên gauge 24 giờ bỏ sót hay báo trễ một lỗi mới (probe: lỗi thật chỉ báo trễ 21 phút) nên đổi sang gauge `quotify_bot_recent_failures`; **(3)** các kẽ hở test (hạn chờ không được kiểm bằng thời gian, `/metrics` thiếu số của thông báo giá không bị bắt, biên 24 giờ, cổng cấu hình thật, các luật YAML chỉ `promtool` mới bắt, chuỗi mồi nằm ở cột khác như `error_category`, và các vị trí log chưa được chạy: nay đóng bằng 8 kịch bản và đo lại bằng coverage); **(4)** tài liệu nói khác code (4.9). Ghi nhận: cảnh báo tuổi dòng đo từ `received_at` nên dòng thử lại cộng dồn (4.9), truy vấn đếm quét tuần tự bảng ở quy mô lớn (RC-35) |
| Độ ổn định | Ba lần chạy liên tiếp (59 test, 11,2 đến 11,7 giây) và hai lần khi 12 lõi CPU bị đốt (16,9 và 25,6 giây): 5 trên 5 qua; reviewer chạy song song 8 phiên (mỗi phiên một DB tạm) đều xanh. Không có `sleep` thật trong test của S7 |
| Điểm đáng nhớ | Cảnh báo "tăng" trên một gauge cửa sổ trượt không đáng tin: một lỗi mới có thể bị một lỗi cũ rơi khỏi cửa sổ triệt tiêu. Cảnh báo nên dựa vào một gauge đếm sự kiện vừa xảy ra trong cửa sổ ngắn, và phải được kiểm bằng mô phỏng chuỗi số đo (`promtool test rules`), vì pytest chỉ so được chuỗi biểu thức. Ngoài ra: ba cảnh báo `Found 1 error` của ruff tôi bỏ qua giữa chừng đã làm số lỗi toàn repo vượt baseline cho tới khi so lại ở cuối |

Chưa kiểm: Prometheus và Grafana thật nạp nhóm luật mới (cần dựng `docker-compose` quan sát), cảnh báo gửi tới kênh nào, và `/metrics` ở production.

### A.10 Kiểm chứng S8 (2026-10-14)

| Hạng mục | Kết quả |
|---|---|
| Test mới của S8 | **61 test ròng** (toàn bộ bộ test từ 1.671 lên 1.732 qua, 1 bỏ qua như cũ): 19 ở `test_chatbot_compose.py` (profile, restart, grace, lệnh dạng danh sách, healthcheck, phụ thuộc, không có `${VAR:?}`, không cố định cờ chatbot ở production, `REDIS_HOST`, `bot-worker-test` chỉ nói chuyện với fake-telegram và chờ `backend-e2e`), 7 ở `test_chatbot_env_examples.py`, 14 ở `test_chatbot_readiness.py` (script, các kiểm trong mục 16 và khối service, danh sách build), 3 ở `integration/test_bot_runbook_db.py` (SQL của runbook chạy trên Postgres thật), 17 cho `max_connections` ở CLI và client (mặc định production, giá trị rõ thắng mặc định, hai đầu miền 1 và 100, chữ hoa của `APP_ENV`, `main` đến `_run` đến lệnh, `info` và bản xem trước in giá trị hiện tại) |
| Cổng chất lượng | ruff 62, `mypy app` 15, bandit 16 low và 1 medium: bằng baseline; 8 file Python đụng tới sạch ruff, định dạng và mypy; `make production-readiness-check` qua |
| Chạy thật trên Docker dev | Tạo lại `backend`, `telegram-poller`, `bot-worker` giữ nguyên cờ và danh sách thử của lần thử trước: `bot-worker` từ `starting` sang `healthy` trong 20 giây; `/metrics` của backend báo `quotify_bot_enabled 1` (trước S8: 0, vì backend không nhận cờ). `arq --check` thoát 0 khi có khóa sức khỏe và thoát 1 ("no health check sentinel value found") khi đổi `BOT_QUEUE_NAME` sang hàng đợi không có worker. `telegram_webhook.py info` in `max_connections` (dev dùng polling nên là `None`) |
| Chạy thật `bot-worker-test` | Trong dự án compose riêng (`-p quotify-s8check`, xóa sạch sau đó; compose test dùng chung tên dự án và volume `backend_venv` với dev nên không chạy thẳng): worker lên `healthy` sau khoảng 10 giây, đọc `redis-test`, token giả và `fake-telegram`. Lần đầu cron quét báo `relation "bot_updates" does not exist` vì `app_test` chưa migrate; thêm phụ thuộc `backend-e2e` (service chạy migration) rồi chạy lại: 8 lần quét trong 70 giây, 0 lỗi |
| Thử Telegram thật sau khi tạo lại container (bạn nhắn 5 tin, engine giả, không độ trễ giả) | Cả 5 dòng `replied` ngay lần thử đầu (`attempts` 1, mỗi tin một phần): nhận → bắt đầu **0,1 đến 0,4 giây**, bắt đầu → xong 0,5 đến 1,3 giây, tổng **0,6 đến 1,8 giây**. Ba tin cuối đến cách nhau 1 giây và được xử lý lần lượt (mỗi tin bắt đầu ngay khi tin trước xong; số tin chờ cao nhất 3, dưới trần 5). Worker 0 dòng lỗi trong 30 phút. Đây là số đo sạch đầu tiên của đường ống không có thử nghiệm lỗi chen vào |
| Số đo từ các lần thử thật (engine giả, bot dev) | Dòng `replied` còn lại trong DB dev (16): tin đơn giản (không độ trễ giả) nhận → bắt đầu xử lý **0,0 đến 1,0 giây**, bắt đầu → xong **0,4 đến 1,3 giây** (với các dòng sau S4 gồm cả gọi `sendMessage`), tin tách 3 phần 3,6 giây. Các dòng dài hơn đều là thực nghiệm có chủ đích: engine giả đợi 20 đến 25 giây; 5 tin dồn dập thì chạy lần lượt cách nhau 20 giây (một dòng một chat); mất chuông cứu sau 40 giây (cron quét :10 và :40, `BOT_SWEEP_STALE_SECONDS` 30); `SIGTERM` giữa lượt thì dòng thử lại ngay (`attempts` 2, nhận lại sau 0,1 giây). Số tin chờ cao nhất: 5 (đúng `BOT_MAX_PENDING_PER_CHAT`). **Kết luận:** chưa có lý do chỉnh bảng 4.8 từ các số này; nó cần số đo của engine thật (độ trễ LLM, lượng token, tỷ lệ lỗi). Không phải mẫu lưu lượng thật: 16 dòng, chủ yếu thử lỗi |
| Độ nhạy trên code thật | **86 lượt đột biến, 0 sống sau khi bổ sung test.** 10 đột biến sống ở lượt đầu: ở CLI `max_connections` (hai biên của miền, hai chỗ truyền tham số từ `main` đến lệnh, chữ hoa của `APP_ENV`) và ở runbook (hai danh sách build chỉ kiểm bằng "có từ `bot-worker` đâu đó trong mục", ba từ khóa xuất hiện nhiều lần nên đột biến một chỗ không đủ); đã thêm test và đột biến từng loại. Thêm: đột biến đủ loại cho compose (profile chuyển sang service khác, bỏ restart, đổi lệnh sang dạng shell, đổi healthcheck sang worker khác...), `.env` mẫu (lệch mặc định, thiếu biến, biến dev trong file production), script, SQL của runbook (bỏ `where`, thiếu trạng thái, giữ nội dung) |
| Rà soát độc lập (agent) | Không có lỗi mức cao; cấu hình production **y hệt `HEAD`** cho 8 service cũ có hay không có profile; 81 test của S8 qua. 10 phát hiện, đều đã xử lý: **(1)** runbook nói `restart: unless-stopped` khởi động lại worker `unhealthy` (sai: chỉ khi thoát; RC-37); **(2)** "webhook chỉ ghi DB nên nhanh" sai (lệnh và nút bấm gửi trả lời Telegram ngay trong request, tối đa 10 giây mỗi lần gọi), nên với `max_connections=1` Telegram chậm làm cả hàng chậm; **(3)** CLI không cho biết `max_connections` hiện tại (nay `info` và bản xem trước in nó); **(4)** tắt khẩn cấp để nguyên nội dung tin của dòng còn mở, runbook nói ngược (RC-38, thêm bước dọn có SQL chạy thử); **(5)** công tắc tắt Telegram ở 12.5 không dừng `bot-worker` (worker đọc cờ lúc khởi động); **(6)** script sẵn sàng qua oan khi chuyển profile sang service khác hay comment dòng healthcheck (nay khóa vào khối `bot-worker`, bỏ dòng ghi chú, kiểm thêm restart và grace); **(7)** test compose không kiểm `REDIS_HOST` và việc không cố định `CHATBOT_ENABLED` ở production; **(8)** danh sách build lịch sử chưa được ghi rõ là lịch sử, và các công thức `set --yes` ở 12.4 và 12.8 nay cũng đặt `max_connections=1` ở production; **(9)** backend còn đọc `BOT_QUEUE_NAME` và `BOT_MAX_PENDING_PER_CHAT` nên đổi `BOT_*` phải tạo lại cả backend; **(10)** `bot-worker-test` không cố định `BOT_STUB_DELAY_SECONDS`. Reviewer đã xác nhận: `build --print bot-worker` chạy được khi profile tắt (tag `quotify-bot-worker`, khác `quotify-worker`), arq 0.26.3 đặt khóa `quotify:bot:health-check` sống `interval + 1` giây và `Worker.close()` xóa khóa khi `SIGTERM`, `.env` mẫu nạp qua `Settings` không lệch mặc định nào |
| Điểm đáng nhớ | **(a)** Phép thử "âm" phải thật sự được nối vào thứ nó nói là kiểm: đổi `REDIS_URL` để chứng minh `arq --check` hỏng vẫn cho kết quả qua vì arq không đọc `REDIS_URL`, và chính điều đó lộ ra RC-36 (cấu hình Redis có hai cách khai báo, compose chỉ đặt một). **(b)** Gọi đích danh một service thuộc profile là **kích hoạt** profile, nên một dòng `up -d --force-recreate bot-worker` chép nhầm sẽ khởi động chatbot. **(c)** Dưới `set -o pipefail`, `sed ... \| grep -q` báo thiếu oan vì `grep -q` thoát sớm làm `sed` nhận SIGPIPE: gom vào biến rồi grep. **(d)** Một test chỉ kiểm "có từ khóa trong mục" thì đột biến một chỗ không bắt được khi từ khóa xuất hiện nhiều lần: kiểm đúng dòng lệnh, hoặc đột biến mọi chỗ |

Chưa kiểm: Docker thật khởi động lại hay không khi `unhealthy` (reviewer không được chạy container; kết luận dựa trên ngữ nghĩa của restart policy), `arq --check` trong image `prod` (image `dev` đã chạy thật; image `prod` dùng cùng Dockerfile và `PATH`), E2E Playwright với `REDIS_HOST` mới của `backend-e2e`, luồng tin nhắn đầu-cuối trong dự án compose test (mới kiểm worker lên và cron chạy), `docker compose` trên VPS, và tải thật (cần engine thật).

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
- **2026-10-14, bản 11, S3 xong.** Cài S3 (chịu lỗi) theo TDD: thử lại có backoff, `failed` với danh mục cố định, tiếp tục từ câu đã lưu, rào chắn, nhả lease khi hủy, TTL, cron quét và cron dọn; chạy thật trên Docker dev với bot dev (tắt worker giữa lượt và mất chuông đều được cứu). Rà soát độc lập tìm ba lỗi thật (lease bị giữ khi lỗi bất ngờ, khi hủy rơi vào đoạn claim, rò thông điệp qua `__context__`) và nhiều đột biến sống; đã sửa và thêm test, ghi RC-30, RC-31 và hai mục chuyển sang S4. Thêm `BOT_STUB_DELAY_SECONDS` (chỉ dev, production bỏ qua). Phụ lục A.5.
- **2026-10-14, bản 12, S4 xong.** Cài đường gửi theo TDD: chia tin theo UTF-16 và ranh giới nửa sau cửa sổ, `sent_parts` có rào chắn, 429 trong ngân sách gửi, phân loại lỗi gửi (403 chặn, 4xx từ chối, mạng và 5xx thử lại) kèm xin lỗi khi hết lượt, chỉ báo "đang gõ", kiểm người nhận ba lần (trước engine, trước khi gửi, cho câu xin lỗi), `principal is None` thành `dropped`, giả lập Telegram mở rộng. Rà soát độc lập không thấy lỗi nghiêm trọng nhưng chỉ ra bốn điểm đáng sửa (chia tin chọn ranh giới quá sớm, `retry_after` lớn bị bỏ qua khi hẹn lần sau, hai giá trị 0 gây vòng lặp nóng, tin gửi dở quá hạn bị loại); đã sửa và thêm test. Phụ lục A.6.
- **2026-10-14, bản 13, S5 xong.** Cài chặn lũ và tin không phải văn bản theo TDD: trần `BOT_MAX_PENDING_PER_CHAT` (chính xác nhờ khóa dòng `telegram_accounts`), câu cố định cho ảnh, tài liệu, giọng nói, sticker, GIF, vị trí..., `TelegramMessage.kind`, chat nhóm và tin bị sửa không vào đường ống. Rà soát độc lập không thấy lỗi đúng-sai nhưng chỉ ra vấn đề trải nghiệm đáng sửa (album ảnh rồi hỏi tiếp bị bỏ im lặng) cùng hai điểm nhỏ (nhãn GIF, tin dịch vụ); đã sửa bằng thông báo một lần mỗi 10 giây mỗi chat và bộ giới hạn riêng cho tin không phải văn bản. Thêm RC-32, RC-33. Phụ lục A.7.
- **2026-10-14, bản 14, S6 xong.** Cài engine DB chỉ đọc theo TDD: `ReadonlySessionFactory` (tạo lười, `server_settings`, pool riêng, nhãn `application_name`), khôi phục trạng thái phiên mỗi lần trả kết nối (đóng rò cài đặt của S0, mở rộng sang vai trò, LISTEN, cursor), pool tường minh cho engine chính của `bot-worker` (RC-5), nối `ChatTurn.readonly_session_factory`, `shutdown` chịu lỗi từng bước, và `ToolRegistry` kiểm cả khai báo lẫn lời gọi. Rà soát độc lập không thấy lỗi mức cao nhưng chỉ ra năm điểm thật và nhiều khoảng trống test; đã sửa và bịt hết. Thêm 7 biến cấu hình vào bảng 4.8, RC-34. Phụ lục A.8.
- **2026-10-14, bản 15, S7 xong.** Cài quan sát theo TDD: `BotMetrics` tính lúc scrape (đếm theo trạng thái, tuổi dòng claim được cũ nhất cùng định nghĩa với cron quét, lỗi trong 30 phút, hạn mức bị từ chối, bật/tắt), nối vào `/metrics` song song với thông báo giá, nhóm luật `quotify-chatbot` có kiểm thử luật bằng `promtool` (và `make alert-rules-check`), hợp đồng log và bài chuỗi mồi 29 kịch bản. Rà soát độc lập không thấy lỗi sản phẩm nhưng chỉ ra bom hẹn giờ trong test và điểm yếu của cảnh báo `delta` trên gauge 24 giờ; đã sửa (gauge lỗi 30 phút) cùng các kẽ hở test. Viết lại 4.9 cho khớp code, thêm RC-35 và ghi cho S8 việc cấp cờ chatbot cho backend. Phụ lục A.9.
- **2026-10-14, bản 16, S8 xong.** Vận hành: compose prod (`bot-worker` sau profile `chatbot`, `restart`, `stop_grace_period`, healthcheck `arq --check`), dev (backend nhận cờ chatbot, healthcheck) và test (`bot-worker-test` opt-in); `.env` mẫu đủ biến mục 4.8 có test đối chiếu `Settings`; script `check-chatbot-readiness.sh` nối vào `check-production-readiness.sh`; runbook mục 16 (bật, `max_connections`, theo dõi, tắt khẩn cấp và dọn dòng còn mở); `set_webhook` và CLI nhận `max_connections` (mặc định 1 ở production), `info` in giá trị hiện tại; ba thuật ngữ vào `CONTEXT.md`. Theo bạn yêu cầu làm S8 trước S10. Rà soát độc lập không thấy lỗi mức cao nhưng chỉ ra 10 điểm (restart không xử lý worker treo, "webhook chỉ ghi DB" sai, tắt khẩn cấp để lại nội dung tin, kill switch Telegram không dừng worker, script sẵn sàng qua oan...), đã xử lý hết. Thêm RC-36 đến RC-38; chưa có số đo với engine thật nên bảng 4.8 giữ nguyên. Phụ lục A.10.
- **Chưa xác minh:** các điểm đánh dấu **[CHƯA XÁC MINH]** ở trên; các con số ở Phụ lục A.2 do agent đo, tôi chưa tái lập; quan sát bằng mắt chỉ báo "đang gõ" của S0(d) chờ bạn xác nhận; hành vi `SIGTERM` của lệnh dev `sh -lc "uv sync && uv run arq ..."`.
