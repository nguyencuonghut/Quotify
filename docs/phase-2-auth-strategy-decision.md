# Quyết Định Auth Strategy Cho Phase 2

Ngày chốt: 10/06/2026

## Kết luận

Phase 2 sẽ dùng **hybrid token strategy**:

- `access token`: JWT ngắn hạn, frontend giữ trong memory state và gửi qua `Authorization: Bearer <token>`
- `refresh token`: token dài hạn hơn, backend phát qua `httpOnly cookie`

Đây là baseline chính thức cho boilerplate ở giai đoạn hiện tại.

## Lý do chọn

Repository này là browser-first admin boilerplate, không phải public API platform thuần machine-to-machine.

Hybrid strategy phù hợp vì:

1. Giữ được ergonomics của SPA:
   - frontend vẫn gọi API bằng Bearer access token ngắn hạn
   - router guard và auth store đơn giản, dễ debug
2. Tăng bảo mật cho refresh token:
   - refresh token không nằm trong localStorage/sessionStorage
   - giảm blast radius nếu UI bị XSS
3. Hợp với production architecture hiện có:
   - production dùng reverse proxy, frontend và API có thể cùng site
   - cookie auth cho refresh flow tự nhiên hơn trong môi trường này
4. Vẫn để ngỏ hướng mở rộng:
   - có thể thêm CSRF hardening, rotation, device/session tracking ở phase sau
   - có thể tách API client strategy riêng nếu sau này cần external clients

## Không chọn phương án nào

### Không chọn Bearer-only làm baseline

Bearer-only đơn giản hơn trong dev, nhưng không phải baseline tốt nhất cho enterprise admin browser app vì refresh token sẽ dễ bị kéo về local storage/session storage hoặc rơi vào vùng quản lý secret yếu hơn.

### Không chọn cookie-only cho toàn bộ access flow

Cookie-only cho mọi request bảo mật tốt hơn ở một số mô hình, nhưng sẽ đẩy complexity lên CORS/CSRF từ quá sớm ở scaffold SPA này. Với frontend Vue admin hiện tại, hybrid là điểm cân bằng tốt hơn.

## Contract Kỹ Thuật Được Chốt

### Access token

- Dạng: JWT
- TTL baseline: `15 phút`
- Được trả trong response body của `login` và `refresh`
- Frontend chỉ giữ trong memory store
- Không ghi vào localStorage/sessionStorage

### Refresh token

- Không trả raw token ra body response
- Backend set qua `Set-Cookie`
- Thuộc tính baseline:
  - `HttpOnly`
  - `SameSite=Lax` cho dev baseline
  - `Secure=true` ở production HTTPS
  - `Path=/api/v1/auth`
- TTL baseline: `7 ngày`
- Refresh token phải có persistence/revocation strategy
- Không lưu raw token trong database; chỉ lưu token id hoặc hash

### Logout

- Backend revoke refresh token đang active
- Backend clear cookie refresh token
- Frontend clear access token state và current user state

### Auth bootstrap

- Frontend khi app load:
  1. chưa có access token trong memory thì thử `refresh`
  2. nếu refresh thành công thì nạp `me`
  3. nếu refresh fail thì coi là anonymous

## Time Policy Cho Auth

Tất cả các mốc thời gian auth phải explicit:

- token issue time
- token expire time
- refresh revoke time
- audit log timestamp

Policy baseline:

- lưu trữ runtime timestamp theo UTC nếu thư viện/token library yêu cầu
- business-facing display và điều tra log theo `Asia/Ho_Chi_Minh` (`GMT+7`)
- tuyệt đối không dùng datetime naive mơ hồ cho expire/revoke/audit

## CSRF Và CORS

### CSRF

Phase 2 chưa bắt buộc implement full CSRF layer cho toàn hệ thống, nhưng strategy phải để sẵn chỗ cho nó.

Baseline:

- refresh/logout là cookie-aware endpoints
- nếu production dùng cross-site auth pattern hoặc mở rộng mutation qua cookie, phải thêm CSRF protection ở phase hardening

### CORS

Dev hiện tại là:

- frontend: `127.0.0.1:5173`
- backend: `127.0.0.1:8000`

Nghĩa là refresh flow bằng cookie trong dev sẽ cần:

- `credentials: 'include'` phía frontend
- CORS cho phép credential
- cookie config phù hợp môi trường local

Production ưu tiên same-site qua reverse proxy để giảm complexity.

## API Shape Baseline

### `POST /api/v1/auth/login`

Request:

```json
{
  "email": "admin@example.com",
  "password": "secret"
}
```

Response body:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 900
}
```

Cookie:

- set refresh token cookie

### `POST /api/v1/auth/refresh`

Request:

- không cần refresh token trong body
- backend đọc refresh token từ cookie

Response body:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 900
}
```

Cookie:

- rotation allowed
- có thể set refresh token mới nếu dùng rotation

### `POST /api/v1/auth/logout`

Request:

- backend đọc refresh token từ cookie hoặc session reference

Response:

- `204 No Content` hoặc response tối giản
- cookie bị clear

### `GET /api/v1/auth/me`

Response:

- user profile tối giản
- roles
- permissions đã resolve hoặc đủ dữ liệu để frontend resolve

## Cấu Hình Baseline

Các biến cấu hình phase 2 nên tồn tại:

- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_DAYS`
- `AUTH_TOKEN_TRANSPORT=hybrid`
- `AUTH_REFRESH_COOKIE_NAME`
- `AUTH_REFRESH_COOKIE_SECURE`
- `AUTH_REFRESH_COOKIE_SAMESITE`
- `AUTH_REFRESH_COOKIE_PATH`

## Quy Tắc Không Được Vi Phạm

1. Không lưu access token vào localStorage/sessionStorage.
2. Không trả refresh token raw trong JSON response.
3. Không lưu refresh token raw trong database.
4. Không dùng error message phân biệt “email sai” với “password sai”.
5. Không dựa vào frontend để thực thi permission thật.

## Deferred Items

Những phần sau được defer sang bước implementation tiếp theo hoặc phase hardening:

- CSRF protection đầy đủ
- refresh token rotation chi tiết
- device/session management
- brute-force/rate-limit policy đầy đủ
- MFA/SSO
