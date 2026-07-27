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
  }).then(mapAccessTokenDtoToSession)
}

export function refreshSession(): Promise<AuthSession> {
  return apiRequest<AccessTokenDto>('/auth/refresh', {
    method: 'POST',
  }).then(mapAccessTokenDtoToSession)
}

export function logout(accessToken?: string | null) {
  return apiRequest<void>('/auth/logout', {
    method: 'POST',
    accessToken,
  })
}

export function getCurrentUser(accessToken: string): Promise<CurrentUser> {
  return apiRequest<CurrentUserDto>('/auth/me', {
    accessToken,
  }).then(mapCurrentUserDto)
}
