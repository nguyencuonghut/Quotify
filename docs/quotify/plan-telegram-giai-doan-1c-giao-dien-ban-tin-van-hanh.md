# Kế Hoạch Chi Tiết Giai Đoạn 1C: Giao Diện Cấu Hình, Bản Tin 08:00, Duyệt Giá Bất Thường Trên Web Và Vận Hành

## Trạng Thái

BẢN ĐÃ CHỐT (bản 2, 2026-10-06: Q1 đến Q7 đã chốt, xem mục "Câu Hỏi Đã Chốt"). Soạn 2026-10-06. **Chưa có dòng code nào của 1C.** Giai đoạn 1A (liên kết Telegram) và 1B (engine biến động giá, tin ảnh, giá bất thường, nút duyệt, nhắc, hết hạn, dọn dữ liệu) đã chạy trên production từ 2026-10-06 (pilot: `nguyencuonghut55@gmail.com`; `lethihong@honghafeed.com.vn` chưa liên kết).

Kế hoạch này triển khai chi tiết "Giai đoạn 1C" trong [plan-telegram-bien-dong-gia-va-chatbot-ai.md](plan-telegram-bien-dong-gia-va-chatbot-ai.md) (mục 7, 4.6, 4.8, 4.9) và nối tiếp [plan-telegram-giai-doan-1b-engine-bien-dong-gia.md](plan-telegram-giai-doan-1b-engine-bien-dong-gia.md). Chatbot AI (Giai đoạn 2) **không** thuộc kế hoạch này.

Cách soạn:
- Local skill `to-issues`: chia lát cắt dọc (tracer bullet), mỗi slice đi qua đủ các tầng cần thiết, tự xác minh được, có loại **HITL** (cần người quyết hoặc thao tác ngoài code) hoặc **AFK** (agent làm và merge được), "chặn bởi" và tiêu chí chấp nhận. Không đăng issue lên tracker nào.
- Local skill `tdd`: trong mỗi slice, test đầu tiên là **tracer bullet**, sau đó từng hành vi nhỏ; phần SQL, khóa, savepoint kiểm trên PostgreSQL thật.
- Local agent: hai agent đọc song song ngày 2026-10-06 (hiện trạng frontend và quy ước giao diện; hiện trạng API backend, bản tin, quan sát) và số liệu bản tin đo lại trên replay 1B (Phụ lục A).

## Mục Tiêu

Biến 1B từ "chạy được bằng API và SQL" thành tính năng vận hành được bởi người dùng nghiệp vụ và theo dõi được:

1. **Bản tin tổng hợp 08:00** cho các thay đổi mức Nhẹ (hiện được lưu `digest_queued` nhưng chưa ai nhận, nên nhân viên mặc định "từ mức Nhẹ" chưa nhận gì).
2. **Giao diện web:** trang cấu hình ngưỡng (`/price-alert-settings`), tùy chọn cá nhân trong Hồ sơ, trang duyệt giá bất thường (cùng logic với nút Telegram).
3. **Vận hành:** metric và cảnh báo (watermark trễ, tin kẹt), kiểm tra tuân thủ, runbook cho 1C.
4. **Chỉnh theo dữ liệu pilot thật:** các cờ giả của giá bất thường (26 cờ thị trường, 4 điểm Khô cọ trong replay) và những điểm đã hoãn ở 1B.
5. (Tùy chọn, Q2) **Nhãn trạng thái giá** trên phiếu (nghi nhập sai, đã xác nhận) để người nhập phiếu thấy kết quả duyệt trên web.

## Ngoài Scope

- Chatbot AI và nhập liệu qua Telegram (Giai đoạn 2).
- Cảnh báo ngay lúc nhập phiếu (USD gõ vào ô VNĐ/KG) và loại ngày lễ khỏi ngày làm việc: backlog đã ghi ở tài liệu cha (mục 9.2, QĐ-11).
- Giới hạn tốc độ bằng Redis (Q6: hoãn, production vẫn một tiến trình).
- Outbox hoặc enqueue sau commit thay cho cron quét 30 giây (QĐ-20): không cần khi chưa có sự cố.

## Căn Cứ Đã Xác Minh (2026-10-06)

Đọc trực tiếp code và dữ liệu ngày 2026-10-06. Chỗ nào lệch với kế hoạch trước được ghi rõ.

**Backend đã có (không cần làm lại):**

| Mục | Hiện trạng |
|---|---|
| `GET/PUT /price-alert-settings` | Có, quyền `price_alerts.manage`; trả `enabled_since`; PUT thay toàn bộ trường (422 khi sai thứ tự ngưỡng); audit `price_alerts.settings_updated` |
| `GET/PUT/DELETE /price-alert-settings/materials[/{material_id}]` | Có: danh sách `{items, total}` với `limit` 1 đến 100, `offset`, `search`; mỗi mục có `override` (có thể null) và `effective`; audit `price_alerts.threshold_updated` |
| `GET/PUT /users/me/alert-preferences` | Có, chỉ cần đăng nhập; `is_enabled`, `min_level` (`light`, `medium`, `large`, null), `effective_min_level`, `admin_receive_all` (PUT trả 403 nếu không phải admin) |
| Quyền | `price_alerts.manage` và `price_alerts.receive_all` đã có trong `BASE_PERMISSION_CODES`, migration `20261004_1300` gán cho `manager` và `admin` |
| `PriceAlertReviewService.review(...)` | Có, đã gồm kiểm quyền, cập nhật nguyên tử, điểm gắn kèm, audit. Hiện chỉ nút Telegram gọi |
| `compose_review_edit`, `edit_expired_cards` | Có, dùng để sửa tin Telegram của thẻ; tái dùng được khi duyệt trên web |
| Cron worker | `poll_price_alerts` (30 giây), `send_price_alerts` (lệch pha), `remind_price_alerts` (phút 5 các giờ 8 đến 17), `cleanup_price_alerts` (03:30), múi giờ VN |

**Chưa có (1C phải làm):**

| Mục | Hiện trạng |
|---|---|
| `GET /price-alerts/anomalies`, `POST /price-alerts/anomalies/{id}/review` | Chưa có router, schema nào (tài liệu cha 4.6) |
| Bản tin tổng hợp | Không code nào đọc `digest_queued`; `price_alert_settings.digest_hour_local` chỉ được lưu và trả qua API; `price_alert_scan_state.last_digest_local_date` không được đọc hay ghi; chưa có cron `send_price_alert_digest` |
| API xem tin, sự kiện, lần quét | Không có; `price_alert_scan_runs` chỉ được ghi |
| Metric của engine | Không có; `core/observability.py` chỉ có `quotify_http_*` và `quotify_readiness_*`; Prometheus chỉ scrape `backend:8000`; worker không xuất metric |
| Luật cảnh báo | `docker/observability/alert_rules.yml` còn tên `fastapivue_*` (nợ cũ RR-19), nên không khớp metric `quotify_*` |
| Kiểm tra tuân thủ | `scripts/compliance/check-production-readiness.sh` chưa có mục cho thông báo giá |
| Giao diện | Chưa có trang cấu hình, panel tùy chọn cá nhân, trang duyệt giá bất thường; chỉ có panel liên kết Telegram trong `ProfilePage.vue` |
| Nhãn audit | `audit-logs.mappers.ts` và bộ lọc `AuditLogsPage.vue` chưa có nhãn `telegram.*` và `price_alerts.*` |

**Quy ước frontend (từ agent khảo sát):**

- Trang quản trị chia lớp: `pages/XxxPage.vue`, `composables/useXxxPage.ts`, `api/xxx.api.ts` (dùng `apiRequest` với `accessToken`), `api/xxx.mappers.ts` (nhãn tiếng Việt, `Intl.DateTimeFormat('vi-VN', {timeZone})`), `types/xxx.ts` (`Dto` snake_case và `Domain` camelCase). Mẫu: trang Nhật ký hoạt động (`AuditLogsPage`) và `useTelegramLink`.
- Router phẳng, mỗi route có `meta.requiredPermission`, tiêu đề tiếng Việt viết cứng; sidebar `navGroups` viết cứng trong `AdminLayout.vue`, mục ẩn theo `permissionStore.can(...)`. Có test khẳng định route và sidebar.
- Nút theo quyền luôn hiện nhưng `:disabled` kèm `:title` giải thích, không ẩn bằng `v-if`.
- Form dùng vee-validate với zod, thông báo tiếng Việt, ràng buộc chéo bằng `.refine`; số dùng `InputNumber locale="vi-VN"`; dấu `*` đỏ qua lớp `required`; mẫu gần nhất `QuotifySettingsPage` (không dùng cho trang này vì role `manager` không có `quotify_settings.read`).
- Không dùng Toast: thông báo inline (`role=alert`/`role=status`, `data-testid`), xác nhận bằng `Dialog`.
- Bảng phân trang theo `offset` cho API `limit/offset` (mẫu `MaterialsPage`): `lazyParams` reactive, tìm kiếm debounce và đặt `offset = 0`; thẻ mobile riêng hoặc `overflow-x: auto`.
- Không `<style>` trong `.vue` (lint chặn); SCSS ở `styles/pages/_<tên>.scss` đăng ký trong `main.scss`; token `--app-*`; mobile bắt buộc (Rule 11); không Tailwind hay PrimeFlex.
- Test: vitest (đơn vị, `tests/unit/**/*.spec.ts`, store mock composable), Playwright e2e (`tests/e2e`, `page.route` giả API, kiểm cả khung mobile 390×844). Cổng chất lượng: `make frontend-check`. Nợ cũ: ghi nhận 4 test lỗi sẵn (1 ở `audit-logs.page.spec.ts`, 3 ở `useQuotifySettingsPage.spec.ts`) từ 22/08/2026; **đo lại baseline trước khi bắt đầu** (Slice 0).

**Số liệu bản tin (Phụ lục A):** trong replay 12 tuần, mức Nhẹ có 129 sự kiện, rơi vào 26 ngày; bản tin trung bình 3,2 vật tư mỗi ngày (trung vị 2, lớn nhất 10), khoảng 3,7 ngày có bản tin mỗi tuần, 3 trong 26 ngày có bản tin rơi vào cuối tuần.

**Bài học từ 1B ảnh hưởng 1C:**
- Tài khoản seed (`AUTH_SEED_ADMIN_EMAIL`) không bao giờ nhận tin hay sinh tin; trang cấu hình cá nhân phải nói rõ điều này cho admin (L28 của 1B, Q7).
- Một script sửa code từng làm mất điều kiện `WHERE` của câu `UPDATE` hàng loạt (hotfix `9efc03a`): mọi thay đổi `UPDATE`/`DELETE` hàng loạt trong 1C cần test có ít nhất một hàng không được ảnh hưởng.

## Nguyên Tắc Bắt Buộc

Như 1B, thêm:
1. Mọi slice có commit riêng, build và test không hỏng; production không đổi hành vi cho tới Slice 9.
2. Frontend: tuân thủ `AGENTS.md` và `memory-bank/projectRules.md` (Rule 4A không `<style>`, 9, 11, 12, 13, 20, 21); xác minh bằng trình duyệt thật hoặc e2e (Rule 14).
3. Mọi migration additive, viết tay, không `--autogenerate`, không `downgrade` trên production.
4. Test PostgreSQL thật cho phần SQL; dữ liệu thử phải được ghi nhận đã quét (`record_scanned_version`) và tránh thao tác hàng loạt theo thời gian với `now` giả xa giờ thật (bài học 2026-10-05).
5. Không thêm khóa metadata audit chứa `token`, `secret`, `session`.

## Quyết Định Kỹ Thuật Cho 1C

| Mã | Chủ đề | Quyết định |
|---|---|---|
| M1 | Cron bản tin | `send_price_alert_digest` chạy mỗi giờ (phút 10, giờ VN), chỉ làm việc khi giờ địa phương đã tới `digest_hour_local` và `last_digest_local_date` chưa phải hôm nay, nên worker tắt lúc 08:00 vẫn gửi bù trong ngày. Khóa advisory, ghi `last_digest_local_date` trong cùng giao dịch với việc tạo tin. **Không gửi khi rỗng**, vẫn gửi cuối tuần nếu có |
| M2 | Nguồn của bản tin | Các tin `status='digest_queued'`, `status_reason='light'` (không lấy `cap`: sự kiện đó đã nằm trong tin tóm tắt tràn trần). Gom theo người nhận, một tin `kind='digest'` mỗi người mỗi ngày. Tin quá 3 ngày địa phương không còn gửi: chuyển `suppressed` (lý do `stale`) |
| M3 | Phân biệt bản tin | Thêm cột nullable `price_alert_messages.digest_kind` (`'daily'`) kèm CHECK; tin tóm tắt tràn trần (không `audience`) và cụm giá bất thường (có `audience`) giữ nguyên. Chỉ mục duy nhất một phần `(user_id, local_date) WHERE digest_kind='daily'` làm khóa idempotent. Không dùng `status_reason` để phân loại (bị ghi đè khi thử lại) |
| M4 | Trạng thái sau khi đưa vào bản tin | Các tin `digest_queued/light` chuyển thành `sent` với `status_reason='in_digest'` ngay khi tạo tin bản tin, cùng giao dịch. Giữ trạng thái "đã tính" để chống lặp D5(a) và leo thang cùng ngày vẫn đếm đúng (`suppressed` không nằm trong `_COUNTED_STATUSES`). Chấp nhận: bản tin gửi hỏng thì mất các thay đổi Nhẹ đó (mức thấp; bản tin vẫn được thử lại theo cơ chế của sender) |
| M5 | Nội dung bản tin | Văn bản thuần HTML, không ảnh: tiêu đề "📋 Bản tin giá · DD/MM", mỗi vật tư một dòng (chiều ▲/▼, % theo kỳ có \|%\| lớn nhất, giá mới, dòng ≤ 34 ký tự theo quy ước 1B), tối đa 30 dòng rồi "và N vật tư nữa, xem trên web", cuối là liên kết `/quotes`. Gửi có âm báo (người dùng chờ tin giờ này) |
| M6 | API duyệt giá bất thường | `GET /price-alerts/anomalies` (`price_alerts.receive_all`): `status` (`pending`, `resolved`, `all`), `material_id`, `limit`/`offset`, trả `{items, total}`; mỗi mục gồm vật tư, kỳ giao hàng, giá, trung vị, % lệch, các giá tham chiếu, ngày nhận, phiếu, người nhập, số điểm gắn kèm, tuổi theo ngày làm việc, và (khi đã duyệt) người duyệt, giờ duyệt. Chỉ điểm gốc (không gắn kèm). `POST /price-alerts/anomalies/{id}/review` với `{decision: 'accepted'|'rejected'}`: ánh xạ sang `ok`/`no` của service; 200 trả trạng thái mới, 409 khi đã duyệt (kèm người duyệt, giờ), 404, 403 |
| M7 | Đồng bộ với Telegram | Sau khi duyệt trên web (và commit), best-effort sửa các tin Telegram đã gửi của thẻ đó để bỏ nút, tái dùng `compose_review_edit` (đổi tên chung `edit_cards_for_events`); lỗi sửa chỉ được ghi nhận, không làm hỏng yêu cầu. Cần xác minh tiến trình backend có `TelegramClient` (webhook runner đã có khi bật Telegram) |
| M8 | Cấu hình web | Trang `/price-alert-settings` (`price_alerts.manage`, sidebar nhóm "Hệ thống"): cờ bật/tắt tính năng (cảnh báo rõ "bật lại đặt mốc quét là bây giờ, dữ liệu cũ không sinh tin"), cờ giá bất thường, các tham số ở 4.5 của tài liệu cha, và bảng "Ngưỡng theo vật tư" (phân trang offset, tìm kiếm, sửa bằng Dialog, "Dùng mặc định"). Kiểm tra `0 < Nhẹ < Trung bình < Lớn < Bất thường` bằng zod `.refine`, thông báo tiếng Việt |
| M9 | Tùy chọn cá nhân | Panel trong Hồ sơ cạnh liên kết Telegram: bật/tắt, mức tối thiểu (hiện `effective_min_level` và nhãn "mặc định theo vai trò"), `admin_receive_all` chỉ hiện cho admin kèm ghi chú tài khoản seed không nhận tin. Ẩn khi Telegram tắt |
| M10 | Quan sát | Gauge tính khi Prometheus scrape (truy vấn DB nhẹ, cache 15 giây) thay vì chạy server metric trong worker: `quotify_price_alert_scan_lag_seconds`, `quotify_price_alert_watermark_lag_seconds`, `quotify_price_alert_messages{status}` (chỉ `pending`, `sending`, `failed` trong 24 giờ), `quotify_price_alert_anomalies_pending`. Chỉ phát khi `is_enabled`. Luật cảnh báo mới (tên `quotify_*`): quét trễ quá 2 phút kéo dài 5 phút, tin `pending` quá 10 phút, có tin `failed` mới. Luật `fastapivue_*` cũ không sửa ở đây (nợ riêng RR-19) |
| M11 | Nhãn nhiều điểm (nếu làm Q2) | Trạng thái giá hiển thị ở trang chi tiết phiếu, theo `quote_line_id` của sự kiện mới nhất: "Giá nghi nhập sai, chờ duyệt", "Đã đánh dấu nhập sai", "Giá đã được xác nhận". Chỉ đọc, không tác dụng lên dữ liệu |
| M12 | Audit | Thêm nhãn tiếng Việt và bộ lọc cho `telegram.*`, `price_alerts.settings_updated`, `price_alerts.threshold_updated`, `price_alerts.anomaly_reviewed` vào `audit-logs.mappers.ts` và `AuditLogsPage.vue` |
| M13 | Phát hành | **Một đợt duy nhất** (Q4, đã chốt): deploy sau khi xong Slice 1 đến 7 (Slice 8 chờ dữ liệu pilot nên có thể sau đó). Một lần deploy gồm migration `digest_kind`, build `backend`, `worker` và `frontend`; theo runbook mục 13 và mục 14 (viết ở Slice 7), có chế độ bảo trì `docker/nginx/maintenance.conf` |

## Câu Hỏi Đã Chốt (2026-10-06)

| Mã | Câu hỏi | Đề xuất | Đổi lại thì sao |
|---|---|---|---|
| Q1 (đã chốt) | **Bản tin 08:00**: một tin mỗi người mỗi ngày gồm mọi vật tư mức Nhẹ; không gửi khi rỗng; gửi cả cuối tuần nếu có; bù tối đa 3 ngày; có âm báo | Đúng như tài liệu cha D5(c) | Tắt âm báo hoặc bỏ cuối tuần: ít làm phiền hơn nhưng có thể bỏ sót thay đổi Nhẹ |
| Q2 (đã chốt) | **Nhãn trạng thái giá trên phiếu** (M11): làm hay hoãn? | Làm bản nhỏ, chỉ ở trang chi tiết phiếu (Slice 6), vì người nhập phiếu hiện không thấy kết quả duyệt ở đâu trên web | Hoãn: giảm một slice nhưng người nhập vẫn phải hỏi trưởng phòng |
| Q3 (đã chốt) | **Trang duyệt giá bất thường**: chỉ danh sách chờ duyệt, hay thêm lịch sử 30 ngày đã duyệt (chỉ đọc)? | Có lịch sử 30 ngày để truy vết ai duyệt gì | Chỉ danh sách chờ: đơn giản hơn nhưng khó đối chiếu |
| Q4 (đã chốt) | **Cách phát hành**: hai đợt (1C-a backend và worker; 1C-b giao diện) hay một đợt cuối cùng? | Hai đợt: bản tin và quan sát có giá trị ngay và không đụng frontend, giao diện cần nhiều vòng thử | Một đợt: ít lần deploy hơn nhưng nhân viên chờ bản tin lâu hơn |
| Q5 (đã chốt) | **Metric**: gauge tính khi scrape trong backend (M10) hay chạy server metric trong worker? | Gauge trong backend: không thêm cổng, không đổi `prometheus.yml` nhiều | Server trong worker: đo đúng tiến trình quét hơn nhưng thêm cổng và job scrape |
| Q6 (đã chốt) | **Giới hạn tốc độ Redis**: làm ở 1C hay hoãn? | Hoãn tới khi có nhiều tiến trình backend (RR-9, RR-18) | Làm ngay: tốn công mà chưa có nhu cầu |
| Q7 (đã chốt) | **Khi nào bỏ giới hạn pilot** (`PRICE_ALERT_RECIPIENT_EMAILS`)? | Sau tối thiểu 2 tuần không lỗi và khi `lethihong@` đã liên kết; việc này là bước HITL của Slice 9 | Sớm hơn: nhân viên nhận tin sớm nhưng chưa có dữ liệu cờ giả để chỉnh |

Kết quả chốt (trả lời của bạn):

- **Q1:** đồng ý đề xuất (bản tin một tin mỗi người mỗi ngày, không gửi khi rỗng, gửi cả cuối tuần nếu có, bù tối đa 3 ngày, có âm báo).
- **Q2:** làm bản nhỏ (Slice 6, chỉ trang chi tiết phiếu).
- **Q3:** có lịch sử 30 ngày đã duyệt để truy vết ai duyệt (Slice 2 và 3).
- **Q4:** **một đợt phát hành duy nhất** (khác đề xuất hai đợt): mọi slice trừ Slice 8 vào một lần deploy; hệ quả ghi ở M13 và Slice 9.
- **Q5:** gauge tính khi scrape trong backend (M10).
- **Q6:** hoãn giới hạn tốc độ Redis tới khi production có nhiều tiến trình.
- **Q7:** bỏ giới hạn pilot sau tối thiểu 2 tuần không lỗi (không bắt buộc chờ `lethihong@` liên kết).

## Slice 0: Chuẩn Bị Và Đo Baseline

**Loại:** AFK | **Chặn bởi:** không | **Cỡ:** nhỏ

### Mục tiêu

Biết trạng thái xuất phát thật của frontend và dữ liệu pilot trước khi thêm code.

### Việc cần làm

1. Chạy `make frontend-check` và `make backend-check` (hoặc từng thành phần) trên nhánh mới; ghi lại baseline (lỗi frontend cũ, ruff, mypy, bandit hiện tại) vào `memory-bank/progress.md`.
2. Lấy số liệu pilot đã có trên production (chỉ đọc, qua truy vấn runbook 13.3): số sự kiện theo mức, số thẻ giá bất thường và trạng thái, số tin theo trạng thái. Ghi vào Phụ lục B của tài liệu này. Nếu dữ liệu quá ít thì ghi "chưa đủ" và để Slice 8 chờ.
3. Tạo nhánh `feat/telegram-1c`.

### Tiêu chí chấp nhận

- [ ] Baseline frontend và backend được ghi lại, kể cả các test cũ đang lỗi.
- [ ] Phụ lục B có số liệu pilot (hoặc ghi rõ chưa đủ).

### Rollback

Không có thay đổi sản phẩm.

---

## Slice 1: Bản Tin Tổng Hợp 08:00 (Mức Nhẹ)

**Loại:** AFK (có bước thử thật với Telegram, HITL) | **Chặn bởi:** Slice 0 | **Cỡ:** vừa

### Mục tiêu

Mọi người có mức tối thiểu "Nhẹ" (nhân viên mặc định, trưởng phòng tự chọn) nhận mỗi sáng một bản tin các thay đổi nhẹ hôm trước, chỉ khi có.

### Việc cần làm

1. Migration `20261006_…`: thêm `price_alert_messages.digest_kind varchar(12)` nullable, CHECK `digest_kind IS NULL OR digest_kind = 'daily'`, chỉ mục duy nhất một phần `(user_id, local_date) WHERE digest_kind = 'daily'` (M3).
2. `services/price_alert_digest.py`: lấy các tin `digest_queued/light` còn hạn, gom theo người nhận, tạo một tin `kind='digest'`, `digest_kind='daily'` nối với các sự kiện, chuyển các tin nguồn sang `sent/in_digest` (M4), bỏ các tin quá 3 ngày (M2), cập nhật `last_digest_local_date`, tất cả trong một giao dịch với khóa advisory (M1).
3. `services/price_alert_digest_formatter.py` (hàm thuần): dựng nội dung bản tin (M5): sắp xếp theo \|%\| giảm dần, tối đa 30 dòng, dòng ≤ 34 ký tự, thoát HTML, liên kết `/quotes`.
4. `price_alert_sender.py`: nhận diện `digest_kind='daily'` và dựng nội dung từ sự kiện; giữ nguyên hai loại digest còn lại.
5. Cron `send_price_alert_digest` (phút 10 mỗi giờ, giờ VN) trong `worker.py`; chỉ chạy khi `telegram_enabled` và `is_enabled`; log INFO chỉ khi có việc.

### Thứ tự test (tracer trước)

1. **Tracer (PostgreSQL thật):** hai tin `digest_queued/light` của một người trong hôm qua, chạy job lúc 08:10 giờ VN: tạo đúng một tin bản tin nối cả hai sự kiện, hai tin nguồn thành `sent/in_digest`, `last_digest_local_date` là hôm nay.
2. Chạy lại trong cùng ngày: không tạo thêm tin (idempotent).
3. Không có tin nguồn: không tạo tin, `last_digest_local_date` vẫn cập nhật hoặc không (chốt: cập nhật để không quét lại cả ngày; có test).
4. Trước 08:00: không chạy; worker tắt lúc 08:00 rồi bật lúc 09:30: gửi bù cùng ngày.
5. Cuối tuần có tin nguồn: vẫn gửi; ngày không có: không gửi.
6. Tin `cap` không vào bản tin; tin nguồn quá 3 ngày thành `suppressed/stale`.
7. Nhiều người nhận: mỗi người một tin riêng, không lẫn tin của người khác; người ngoài danh sách pilot hoặc đã tắt cờ cá nhân: không nhận (kiểm lại ở sender).
8. Định dạng: giới hạn 30 dòng và "và N vật tư nữa", thoát HTML, dòng ≤ 34 ký tự (test hàm thuần).
9. Leo thang cùng ngày vẫn đếm các tin `sent/in_digest` (chống hồi quy M4).
10. Đăng ký cron: phút 10, múi giờ VN (test `next_cron`).

### Cách xác minh thật (HITL)

Trên dev, đặt `digest_hour_local` về giờ hiện tại, tạo một vài thay đổi mức Nhẹ bằng phiếu thử, chờ cron; kiểm tin đến điện thoại (nội dung, thứ tự, liên kết).

### Tiêu chí chấp nhận

- [ ] Bản tin đến điện thoại thật đúng nội dung, không gửi khi rỗng.
- [ ] Idempotent, gửi bù trong ngày và cuối tuần có test PostgreSQL thật.
- [ ] Baseline không xấu hơn.

### Rollback

Tắt cờ `is_enabled` hoặc gỡ cron (trả lại code cũ): tin `digest_queued` vẫn nằm đó, không mất. Không `downgrade` migration (cột nullable, tương thích code cũ).

---

## Slice 2: API Duyệt Giá Bất Thường

**Loại:** AFK | **Chặn bởi:** Slice 0 | **Cỡ:** vừa

### Mục tiêu

Người có `price_alerts.receive_all` xem danh sách thẻ bất thường và duyệt bằng API, cùng logic với nút Telegram, và tin Telegram tương ứng được sửa theo.

### Việc cần làm

1. `schemas/price_alert_anomalies.py`, `api/v1/price_alert_anomalies.py` (prefix `/price-alerts/anomalies`), `services/price_alert_anomaly_query.py` (M6). Đăng ký router. `GET` có `status`, `material_id`, `limit`, `offset`, trả `{items, total}`; `POST /{id}/review` gọi `PriceAlertReviewService`, commit, rồi sửa tin Telegram (M7).
2. Đổi tên và tách `edit_expired_cards` thành hàm chung `edit_cards_for_events` (giữ test cũ).
3. Dependency lấy `TelegramClient` cho tiến trình backend (nếu tắt Telegram thì bỏ qua bước sửa tin).

### Thứ tự test (tracer trước)

1. **Tracer (PostgreSQL thật):** trưởng phòng `GET` thấy một thẻ chờ; `POST` `accepted` trả 200, trạng thái `accepted`, dòng hợp lệ trở lại, audit `price_alerts.anomaly_reviewed`.
2. `rejected`: dòng vẫn bị loại.
3. Người không có quyền: 403, không đổi trạng thái; chưa đăng nhập: 401.
4. Duyệt lần hai: 409 kèm người duyệt và giờ; `id` lạ hoặc điểm gắn kèm: 404.
5. Hai yêu cầu cùng lúc: đúng một 200, một 409.
6. Duyệt trên web sau khi thẻ đã bị bấm trên Telegram (và ngược lại): nhận 409 và 200 đúng; tin Telegram được sửa bỏ nút (giả lập transport), lỗi sửa không làm hỏng yêu cầu.
7. Lọc theo `status` và `material_id`, phân trang; chỉ điểm gốc, `attached_count` đúng; thẻ phiếu đã hủy không hiện ở "chờ duyệt".
8. Giá trị `decision` sai: 422.

### Tiêu chí chấp nhận

- [ ] Vòng khứ hồi `GET` và `POST` có test PostgreSQL thật; hai người duyệt cùng lúc chỉ một thắng.
- [ ] Tin Telegram được sửa sau khi duyệt trên web; lỗi Telegram không phá yêu cầu.
- [ ] Baseline không xấu hơn.

### Rollback

Gỡ router (thêm mới, không có dữ liệu mới). Production giữ nguyên.

---

## Slice 3: Trang Duyệt Giá Bất Thường (Frontend)

**Loại:** AFK (có bước xem thật trên trình duyệt) | **Chặn bởi:** Slice 2 | **Cỡ:** vừa

### Mục tiêu

Trưởng phòng mở trang, thấy các điểm chờ duyệt, xem bằng chứng (giá, trung vị, các giá tham chiếu, người nhập, link phiếu) và bấm Giá đúng hoặc Nhập sai; (Q3) xem lịch sử 30 ngày đã duyệt.

### Việc cần làm

1. Tầng dữ liệu: `types/price-alert-anomalies.ts`, `api/price-alert-anomalies.api.ts` và `.mappers.ts` (nhãn trạng thái tiếng Việt, định dạng ngày giờ theo múi giờ VN), `composables/usePriceAlertAnomaliesPage.ts` (danh sách theo `offset`, chuyển tab chờ duyệt và lịch sử, hành động có khóa `isBusy`, xử lý 409 bằng thông báo "đã được xử lý bởi ...").
2. `pages/PriceAlertAnomaliesPage.vue`: DataTable lazy, thẻ mobile, Dialog xác nhận trước khi duyệt; route `/price-alert-anomalies` với `requiredPermission: 'price_alerts.receive_all'`; mục sidebar; SCSS `_price-alert-anomalies-page.scss`.
3. Nút hiện luôn nhưng `:disabled` kèm `:title` cho người không có quyền (quy ước dự án).

### Thứ tự test (tracer trước)

1. **Tracer (vitest):** composable tải danh sách, duyệt một điểm, danh sách cập nhật.
2. 409 hiển thị người đã duyệt; lỗi mạng và 403 có thông báo cố định (không lộ `detail`).
3. Page spec: render bảng, tab, nút bị khóa khi đang xử lý, dữ liệu rỗng.
4. Router và sidebar: route có `requiredPermission`, mục sidebar ẩn với người không có quyền.
5. **Playwright e2e:** mở trang với API giả, duyệt một điểm, kiểm khung mobile 390×844.

### Tiêu chí chấp nhận

- [ ] Duyệt được trên giao diện thật với backend dev; thẻ cũng đổi trong Telegram.
- [ ] `make frontend-check` không xấu hơn baseline; e2e desktop và mobile pass.

### Rollback

Gỡ route và mục sidebar (không có dữ liệu mới).

---

## Slice 4: Trang Cấu Hình Thông Báo Giá (Frontend)

**Loại:** AFK | **Chặn bởi:** Slice 0 | **Cỡ:** vừa

### Mục tiêu

Trưởng phòng và admin chỉnh ngưỡng, tham số, cờ bật/tắt và ngưỡng theo vật tư trên web, không cần API hay SQL.

### Việc cần làm

1. Tầng dữ liệu: `types/price-alert-settings.ts`, `api/price-alert-settings.api.ts` và `.mappers.ts` (Decimal là chuỗi, chuyển sang số khi hiển thị), `composables/usePriceAlertSettingsPage.ts` (form vee-validate và zod với `.refine` thứ tự ngưỡng; bảng vật tư theo `offset`, tìm kiếm debounce).
2. `pages/PriceAlertSettingsPage.vue` (M8): phần cờ và tham số, phần "Ngưỡng theo vật tư" (hiển thị mờ "mặc định", Dialog sửa, nút "Dùng mặc định"); route `/price-alert-settings` với `requiredPermission: 'price_alerts.manage'`; sidebar nhóm "Hệ thống"; SCSS `_price-alert-settings-page.scss`.
3. Cảnh báo trước khi bật lại `is_enabled` và giải thích `enabled_since`.

### Thứ tự test (tracer trước)

1. **Tracer (vitest):** composable tải cấu hình, sửa một ngưỡng, `PUT` đúng toàn bộ trường, form được đặt lại.
2. Sai thứ tự ngưỡng bị chặn ở client bằng thông báo tiếng Việt; 422 từ server hiển thị cố định.
3. Bảng vật tư: tìm kiếm debounce, đổi trang, sửa ghi đè, "Dùng mặc định" xóa ghi đè; kiểm tra ngưỡng bất thường lớn hơn ngưỡng Lớn.
4. Người không có `price_alerts.manage`: route bị chặn, mục sidebar ẩn.
5. **Playwright e2e:** đổi một ngưỡng và một ghi đè vật tư với API giả; mobile 390×844.

### Tiêu chí chấp nhận

- [ ] Đổi ngưỡng trên web có hiệu lực ở lần quét sau (kiểm trên dev với phiếu thử).
- [ ] `make frontend-check` không xấu hơn baseline; e2e pass.

### Rollback

Gỡ route và mục sidebar.

---

## Slice 5: Tùy Chọn Cá Nhân Và Nhãn Audit (Frontend)

**Loại:** AFK | **Chặn bởi:** Slice 0 | **Cỡ:** nhỏ

### Mục tiêu

Mỗi người tự bật/tắt thông báo và chọn mức tối thiểu ngay trong Hồ sơ; nhật ký hoạt động hiển thị đúng nhãn các sự kiện Telegram và thông báo giá.

### Việc cần làm

1. `api/alert-preferences.api.ts`, `.mappers.ts`, `types`, mở rộng `useTelegramLink` hoặc composable riêng `useAlertPreferences`; panel mới trong `ProfilePage.vue` (M9), ẩn khi Telegram tắt; SCSS `_profile-page.scss`.
2. Nhãn audit và bộ lọc (M12) trong `audit-logs.mappers.ts` và `AuditLogsPage.vue`.

### Thứ tự test (tracer trước)

1. **Tracer (vitest):** composable tải, đổi mức tối thiểu, `PUT` đúng.
2. `admin_receive_all` chỉ hiện cho admin và có ghi chú tài khoản seed; non-admin không thấy; 403 từ server có thông báo cố định.
3. Mức mặc định hiển thị nhãn "mặc định theo vai trò"; chọn lại "mặc định" gửi `min_level = null`.
4. Mapper audit: mọi `action` mới có nhãn; bộ lọc có các mục mới.
5. **Playwright e2e:** đổi mức tối thiểu trong Hồ sơ (API giả), kiểm mobile.

### Tiêu chí chấp nhận

- [ ] Đổi mức tối thiểu trong Hồ sơ có tác dụng ở tin kế tiếp (kiểm trên dev).
- [ ] `make frontend-check` không xấu hơn baseline.

### Rollback

Gỡ panel; backend không đổi.

---

## Slice 6: Nhãn Trạng Thái Giá Trên Phiếu (Tùy Chọn, Q2)

**Loại:** AFK | **Chặn bởi:** Slice 2 | **Cỡ:** nhỏ

### Mục tiêu

Người nhập phiếu thấy trên trang chi tiết phiếu dòng nào đang bị nghi nhập sai, đã được xác nhận hay đã bị đánh dấu nhập sai.

### Việc cần làm

1. Backend: thêm trường chỉ đọc `price_alert_status` (`pending`, `accepted`, `rejected`, `expired` hoặc null) cho từng dòng ở phản hồi chi tiết phiếu (theo sự kiện bất thường mới nhất của `quote_line_id`); không đổi schema DB.
2. Frontend: nhãn (`Tag`) cạnh dòng giá ở `QuoteDetailPage` kèm tooltip; mapper nhãn tiếng Việt; không thêm vào danh sách phiếu ở slice này.

### Thứ tự test (tracer trước)

1. **Tracer (PostgreSQL thật):** dòng có sự kiện `pending` trả `price_alert_status = 'pending'`, dòng thường trả null.
2. Nhiều sự kiện cho một dòng: lấy cái mới nhất; phiếu đã hủy vẫn đọc được.
3. Không phát sinh truy vấn N+1 (một truy vấn gộp cho các dòng của phiếu).
4. Frontend: mapper và render nhãn; không có nhãn khi null.

### Tiêu chí chấp nhận

- [ ] Nhãn hiển thị đúng sau khi duyệt từ Telegram hoặc web.
- [ ] Không ảnh hưởng tốc độ trang chi tiết phiếu (đo truy vấn).

### Rollback

Gỡ trường và nhãn (chỉ đọc).

---

## Slice 7: Quan Sát, Cảnh Báo, Tuân Thủ Và Runbook

**Loại:** AFK | **Chặn bởi:** Slice 0 | **Cỡ:** vừa

### Mục tiêu

Biết ngay khi engine ngừng quét, tin kẹt hoặc gửi hỏng, không phải chờ người dùng báo.

### Việc cần làm

1. `core/observability.py` (hoặc module riêng): các gauge ở M10, tính khi scrape với cache 15 giây, chỉ phát khi `is_enabled`; không truy vấn nặng.
2. `docker/observability/alert_rules.yml`: nhóm luật mới theo tên `quotify_price_alert_*` (quét trễ, tin `pending` quá 10 phút, có tin `failed` mới); giữ nguyên luật cũ.
3. `scripts/compliance/check-production-readiness.sh`: thêm kiểm tra sự có mặt của `docker/nginx/maintenance.conf`, mục 13 của runbook và các biến `PRICE_ALERT_RECIPIENT_EMAILS`, `APP_PUBLIC_URL` trong `.env.production.example`.
4. Runbook `docs/runbooks/deploy-vps-production.md`: bổ sung mục giám sát bằng metric; viết mục 14 cho phát hành 1C (một đợt, dùng ở Slice 9).

### Thứ tự test (tracer trước)

1. **Tracer:** với `is_enabled=true` và `last_run_at` cách đây 3 phút, `/metrics` có `quotify_price_alert_scan_lag_seconds` khoảng 180.
2. `is_enabled=false`: không có gauge của engine.
3. Gauge tin theo trạng thái đếm đúng (`pending`, `sending`, `failed` 24 giờ); `anomalies_pending` đếm điểm gốc chờ duyệt.
4. Lỗi DB khi scrape không làm hỏng `/metrics` của các metric khác (cô lập, có log cảnh báo).
5. Luật cảnh báo hợp lệ cú pháp (`promtool check rules` nếu có trong CI, hoặc test cấu trúc YAML); kiểm tra tuân thủ mới pass và fail đúng khi thiếu mục.

### Tiêu chí chấp nhận

- [ ] Gauge xuất hiện ở `/metrics` trên dev; luật cảnh báo nạp được (kiểm bằng stack observability nếu có).
- [ ] `make production-readiness-check` pass.
- [ ] Baseline không xấu hơn.

### Rollback

Gỡ gauge và luật; không đụng dữ liệu.

---

## Slice 8: Chỉnh Giá Bất Thường Theo Dữ Liệu Pilot

**Loại:** HITL (cần dữ liệu thật và quyết định của bạn) | **Chặn bởi:** Slice 0, và tối thiểu 3 đến 4 tuần pilot trên production | **Cỡ:** vừa

### Mục tiêu

Giảm cờ giả của giá bất thường dựa trên dữ liệu thật thay vì replay, trước khi bỏ giới hạn pilot.

### Việc cần làm

1. Lấy số liệu pilot: số thẻ mỗi tuần, tỷ lệ Giá đúng so với Nhập sai, thẻ hết hạn, thời gian từ lúc có thẻ đến lúc duyệt (truy vấn chỉ đọc trên production; ghi vào Phụ lục B).
2. Trình bày với bạn các ứng viên chỉnh, mỗi mục kèm số đo trên replay lẫn dữ liệu thật, rồi chọn:
   - Ngưỡng bất thường riêng theo vật tư biến động mạnh (đã có cơ chế, chỉ cần dùng; Slice 4 giúp chỉnh).
   - Tính điểm đang chờ vào trung vị sau lần xác nhận đầu để chuỗi thị trường tăng liên tục (Choline Chloride) không sinh thẻ lặp.
   - Xử lý điểm đầu chuỗi (hiện không bao giờ bị cờ, nên tham chiếu 187 của Khô cọ bị "nhiễm độc" từ đầu).
   - Nhắc cả người nhập (hiện chỉ nhắc trưởng phòng).
3. Với mục được chọn: TDD theo từng mục, đo lại bằng `python -m app.price_alert_replay --anomaly --simulate-correct` và so với Phụ lục C của kế hoạch 1B.

### Tiêu chí chấp nhận

- [ ] Có bảng số liệu pilot và quyết định của bạn cho từng ứng viên.
- [ ] Mục được chọn có test và số đo replay cải thiện, không làm mất việc bắt các lỗi nhập sai thật (Threonine, Lysine, Arginin, Tryptophan).

### Rollback

Mỗi mục là một thay đổi nhỏ có thể hoàn nguyên bằng commit; tham số nằm trong cấu hình.

---

## Slice 9: Phát Hành 1C Lên Production

**Loại:** HITL (thao tác trên VPS) | **Chặn bởi:** Slice 1 đến 7 (một đợt duy nhất, Q4) | **Cỡ:** nhỏ

### Mục tiêu

Đưa từng đợt 1C lên production an toàn, kèm kiểm tra bằng dữ liệu thật.

### Việc cần làm

1. Dùng runbook mục 14 (viết ở Slice 7, theo mục 13): backup, pull, build `backend`, `worker`, `frontend`, chế độ bảo trì `docker/nginx/maintenance.conf`, migrate (một migration additive `digest_kind`), `up -d`, tắt bảo trì, kiểm.
2. Kiểm sau deploy: gauge xuất hiện ở `/metrics` production; các trang mới (duyệt giá bất thường, cấu hình, tùy chọn cá nhân) dùng được bằng tài khoản người thật; duyệt trên web làm tin Telegram đổi theo.
3. Bản tin đầu tiên: đến người pilot vào 08:00 sáng hôm sau nếu có thay đổi mức Nhẹ (có thể phải chờ vài ngày); kiểm nội dung trên điện thoại thật.
4. Bỏ giới hạn pilot (Q7): sau tối thiểu 2 tuần không lỗi kể từ lần deploy này, để trống `PRICE_ALERT_RECIPIENT_EMAILS`, tạo lại `worker`, nhắc mọi người liên kết Telegram, theo dõi tải tin tuần đầu bằng metric.
5. Cập nhật runbook, `memory-bank/`, tài liệu cha; chạy `agent-task-close.sh`.

### Tiêu chí chấp nhận

- [ ] Một bản tin thật đến người pilot; không có tin đến người ngoài danh sách (khi còn giới hạn).
- [ ] Các trang mới dùng được bằng tài khoản người thật trên production; chức năng cũ không đổi.
- [ ] Token không có trong log; `scan_runs` không lỗi; luật cảnh báo không báo nhầm.

### Rollback

Tắt cờ `is_enabled` (hiệu lực 30 giây) hoặc quay về image trước (build lại từ commit cũ); schema additive, không `downgrade`.

---

## Thứ Tự Và Phụ Thuộc

```
S0 ─┬─ S1 (bản tin) ───────────────────────┐
    ├─ S7 (quan sát + runbook mục 14) ─────┤
    ├─ S2 (API duyệt) ─ S3 (trang duyệt) ──┼─ S9 (một lần deploy)
    │                   └─ S6 (nhãn phiếu) ┤
    ├─ S4 (trang cấu hình) ────────────────┤
    └─ S5 (cá nhân + nhãn audit) ──────────┘
S8 (chỉnh giá bất thường, HITL) sau 3 đến 4 tuần pilot, độc lập với giao diện
```

S1, S2, S4, S5, S7 làm song song được (khác file). Mỗi slice merge riêng được và không làm hỏng build hay test; production không đổi hành vi nhìn thấy được cho tới Slice 9.

## Ma Trận Kiểm Thử

| Lớp | Nội dung | Slice |
|---|---|---|
| Hàm thuần (TDD) | Định dạng bản tin (30 dòng, ≤ 34 ký tự, thoát HTML), nhãn trạng thái | 1, 6 |
| PostgreSQL thật | Bản tin idempotent, gửi bù, cuối tuần, tin quá hạn; API duyệt, đua hai người duyệt; nhãn phiếu; gauge | 1, 2, 6, 7 |
| Sender với transport giả | Bản tin đến đúng người, sửa tin Telegram sau duyệt trên web | 1, 2 |
| Đơn vị frontend (vitest) | Composable, mapper, page, router, sidebar | 3, 4, 5, 6 |
| Playwright e2e | Duyệt, cấu hình, tùy chọn cá nhân, khung mobile 390×844 | 3, 4, 5 |
| Cron và múi giờ | `next_cron` cho bản tin phút 10 giờ VN | 1 |
| Vận hành | `make production-readiness-check`, luật cảnh báo | 7 |
| Thử thật | Bản tin lên điện thoại, nút và trang web đồng bộ | 1, 3, 9 |

## Rủi Ro Và Cách Giảm

| Mã | Rủi ro | Giảm |
|---|---|---|
| RC-1 | Bản tin hỏng làm mất các thay đổi Nhẹ vì tin nguồn đã chuyển `sent/in_digest` (M4) | Mức Nhẹ có ý nghĩa thấp; sender vẫn thử lại bản tin; ghi rõ ở runbook |
| RC-2 | Cron bản tin chạy hai lần cùng lúc tạo hai bản tin | Khóa advisory và chỉ mục duy nhất `(user_id, local_date)` cho `digest_kind='daily'` |
| RC-3 | Bản tin quá dài vượt giới hạn Telegram | Tối đa 30 dòng và cắt an toàn, có test hàm thuần |
| RC-4 | Duyệt trên web và Telegram cùng lúc | Cập nhật nguyên tử chỉ khi còn `pending`; 409 rõ ràng; test đua |
| RC-5 | Sửa tin Telegram thất bại sau khi duyệt trên web làm nút còn hiện | Nút bấm sau đó trả "đã được xử lý" và dựng lại tin (hành vi 1B); lỗi chỉ ghi nhận |
| RC-6 | Gauge Prometheus truy vấn DB mỗi lần scrape gây tải | Cache 15 giây, truy vấn đếm nhẹ có chỉ mục, cô lập lỗi |
| RC-7 | Hiểu nhầm cờ bật lại đặt mốc quét làm mất tin | Cảnh báo rõ trên trang cấu hình, hiển thị `enabled_since` |
| RC-8 | Người dùng sửa ngưỡng sai gây bão tin hoặc mất tin | Kiểm tra thứ tự ngưỡng ở client và server, trần tin sẵn có, audit mọi thay đổi |
| RC-9 | Frontend có test lỗi sẵn che lỗi mới | Slice 0 ghi baseline; so sánh theo tên test, không theo tổng số |
| RC-10 | Tài khoản seed bị dùng nhầm làm người pilot hoặc người nhập (bài học 1B) | Ghi chú trên giao diện tùy chọn cá nhân và trong runbook; không sửa quy tắc Q7 |
| RC-11 | Điểm tồn đọng của 1B: dọn `scanned_versions` quá 180 ngày làm phiếu cũ sửa lại coi mọi dòng là ứng viên; dọn sự kiện bị bác quá 180 ngày để giá sai quay lại nếu cửa sổ tra cứu dài hơn 180 ngày; tin chờ gửi lúc thẻ hết hạn vẫn kèm nút | Đã chấp nhận ở 1B; xem lại ở Slice 8 nếu dữ liệu pilot cho thấy xảy ra |

## Lệnh Chuẩn

```bash
# Backend (thư mục backend)
INTEGRATION_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:55432/app \
  uv run pytest <file> -q --no-cov -p no:cacheprovider
uv run ruff check <file> --output-format concise
uv run mypy app --cache-dir=/dev/null

# Frontend
make frontend-check            # lint (gồm kiểm không có <style>), format:check, vue-tsc, vitest
npm --prefix frontend run test:e2e

# Đo lại giá bất thường
docker compose exec -T backend python -m app.price_alert_replay --weeks 12 --anomaly --simulate-correct

# Giám sát dev
bash scripts/ops/price-alert-dev-state.sh [số ngày]
```

## Phụ Lục A: Số Liệu Bản Tin (Replay 12 Tuần, DB Dev, 2026-10-06)

| Chỉ số | Giá trị |
|---|---|
| Sự kiện mức Nhẹ | 129 |
| Số ngày địa phương có bản tin | 26 (khoảng 3,7 ngày mỗi tuần) |
| Vật tư mỗi bản tin | trung bình 3,2; trung vị 2; lớn nhất 10 |
| Bản tin rơi vào cuối tuần | 3 trong 26 ngày |

Kết luận: bản tin ngắn, giới hạn 30 dòng dư sức; không cần phân trang hay chia nhiều tin.

## Phụ Lục B: Số Liệu Pilot Production

Để trống: điền ở Slice 0 và Slice 8 bằng các truy vấn chỉ đọc ở runbook mục 13.3.
