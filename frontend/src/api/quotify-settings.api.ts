import { apiRequest } from '@/api/http'
import { mapQuotifySettingsDtoToDomain } from '@/api/quotify-settings.mappers'
import type {
  ConversionCostUpdatePayload,
  QuotifySettingsDomain,
  QuotifySettingsDto,
} from '@/types/quotify-settings'

export function getQuotifySettings(
  accessToken?: string | null,
): Promise<QuotifySettingsDomain> {
  return apiRequest<QuotifySettingsDto>('/quotify-settings', {
    accessToken,
  }).then(mapQuotifySettingsDtoToDomain)
}

export function updateConversionCost(
  payload: ConversionCostUpdatePayload,
  accessToken?: string | null,
): Promise<QuotifySettingsDomain> {
  return apiRequest<QuotifySettingsDto>(
    '/quotify-settings/conversion-cost',
    {
      method: 'PUT',
      body: JSON.stringify(payload),
      accessToken,
    },
  ).then(mapQuotifySettingsDtoToDomain)
}
