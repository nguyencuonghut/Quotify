import { apiRequest } from '@/api/http'
import { mapAlertPreferencesDtoToDomain } from '@/api/alert-preferences.mappers'
import type {
  AlertPreferencesDomain,
  AlertPreferencesDto,
  AlertPreferencesUpdatePayload,
} from '@/types/alert-preferences'

export function getAlertPreferences(
  accessToken?: string | null,
): Promise<AlertPreferencesDomain> {
  return apiRequest<AlertPreferencesDto>('/users/me/alert-preferences', {
    accessToken,
  }).then(mapAlertPreferencesDtoToDomain)
}

export function updateAlertPreferences(
  payload: AlertPreferencesUpdatePayload,
  accessToken?: string | null,
): Promise<AlertPreferencesDomain> {
  return apiRequest<AlertPreferencesDto>('/users/me/alert-preferences', {
    method: 'PUT',
    body: JSON.stringify(payload),
    accessToken,
  }).then(mapAlertPreferencesDtoToDomain)
}
