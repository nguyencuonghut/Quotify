import { apiRequest } from '@/api/http'
import {
  mapAccessTokenDtoToSession,
  mapCurrentUserDto,
} from '@/api/auth.mappers'
import type {
  AccessTokenDto,
  AuthSession,
  CurrentUser,
  CurrentUserDto,
  LoginRequestPayload,
} from '@/types/auth'

export function login(payload: LoginRequestPayload) {
  return apiRequest<AccessTokenDto>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
    // Sai email/mật khẩu cũng trả 401 — không phải trường hợp access token
    // hết hạn cần tự refresh, nên bỏ qua cơ chế retry-on-401.
    skipAuthRetry: true,
  }).then(mapAccessTokenDtoToSession)
}

export function refreshSession(): Promise<AuthSession> {
  return apiRequest<AccessTokenDto>('/auth/refresh', {
    method: 'POST',
    // `keepalive` lets the browser finish this request (and apply the
    // rotated refresh-token cookie) even if the page navigates away mid-flight,
    // e.g. the user hitting Ctrl+R/F5 again before the response returns.
    // Without it, the response — and its Set-Cookie — can be dropped, leaving
    // the browser holding an already-rotated (revoked) cookie for the next reload.
    keepalive: true,
    // Bắt buộc: nếu bỏ, 1 refresh thất bại (refresh token cũng hết hạn) sẽ
    // gọi lại chính unauthorizedHandler → gọi lại refreshSession → vòng lặp
    // vô hạn.
    skipAuthRetry: true,
  }).then(mapAccessTokenDtoToSession)
}

export function logout(accessToken?: string | null) {
  return apiRequest<void>('/auth/logout', {
    method: 'POST',
    accessToken,
    // Đăng xuất không cần (và không nên) tự refresh lại token rồi thử logout
    // lần nữa — chỉ cần xóa state phía client dù request có thất bại.
    skipAuthRetry: true,
  })
}

export function getCurrentUser(accessToken: string): Promise<CurrentUser> {
  return apiRequest<CurrentUserDto>('/auth/me', {
    accessToken,
  }).then(mapCurrentUserDto)
}
