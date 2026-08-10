import { apiRequest } from '@/api/http'
import { mapQuotifySettingsDtoToDomain } from '@/api/quotify-settings.mappers'
import type {
  QuotifySettingsDomain,
  QuotifySettingsDto,
  QuotifySettingsUpdatePayload,
} from '@/types/quotify-settings'

export function getQuotifySettings(
  accessToken?: string | null,
): Promise<QuotifySettingsDomain> {
  return apiRequest<QuotifySettingsDto>('/quotify-settings', {
    accessToken,
  }).then(mapQuotifySettingsDtoToDomain)
}

export function updateQuotifySettings(
  payload: QuotifySettingsUpdatePayload,
  accessToken?: string | null,
): Promise<QuotifySettingsDomain> {
  return apiRequest<QuotifySettingsDto>('/quotify-settings', {
    method: 'PUT',
    body: JSON.stringify(payload),
    accessToken,
  }).then(mapQuotifySettingsDtoToDomain)
}
