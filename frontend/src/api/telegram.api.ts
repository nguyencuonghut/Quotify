import { apiRequest } from '@/api/http'
import {
  mapTelegramLinkStatusDto,
  mapTelegramLinkTokenDto,
} from '@/api/telegram.mappers'
import type {
  TelegramLinkStatus,
  TelegramLinkStatusDto,
  TelegramLinkToken,
  TelegramLinkTokenDto,
} from '@/types/telegram'

export function getTelegramLinkStatus(
  accessToken?: string | null,
): Promise<TelegramLinkStatus> {
  return apiRequest<TelegramLinkStatusDto>('/users/me/telegram', {
    accessToken,
  }).then(mapTelegramLinkStatusDto)
}

export function createTelegramLinkToken(
  accessToken?: string | null,
): Promise<TelegramLinkToken> {
  return apiRequest<TelegramLinkTokenDto>('/users/me/telegram/link-token', {
    method: 'POST',
    accessToken,
  }).then(mapTelegramLinkTokenDto)
}

export function cancelTelegramLinkRequest(
  accessToken?: string | null,
): Promise<void> {
  return apiRequest<void>('/users/me/telegram/link-token', {
    method: 'DELETE',
    accessToken,
  })
}

export function unlinkTelegram(accessToken?: string | null): Promise<void> {
  return apiRequest<void>('/users/me/telegram', {
    method: 'DELETE',
    accessToken,
  })
}
