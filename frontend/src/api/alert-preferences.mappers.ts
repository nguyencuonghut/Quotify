import type {
  AlertLevel,
  AlertPreferencesDomain,
  AlertPreferencesDto,
  AlertPreferencesUpdatePayload,
} from '@/types/alert-preferences'

export const ALERT_LEVEL_LABELS: Record<AlertLevel, string> = {
  light: 'Nhẹ',
  medium: 'Trung bình',
  large: 'Lớn',
}

export function mapAlertPreferencesDtoToDomain(
  dto: AlertPreferencesDto,
): AlertPreferencesDomain {
  return {
    isEnabled: dto.is_enabled,
    minLevelChoice: dto.min_level ?? 'default',
    effectiveMinLevel: dto.effective_min_level,
    adminReceiveAll: dto.admin_receive_all,
  }
}

export function mapAlertPreferencesToPayload(
  values: Pick<
    AlertPreferencesDomain,
    'isEnabled' | 'minLevelChoice' | 'adminReceiveAll'
  >,
  isAdmin: boolean,
): AlertPreferencesUpdatePayload {
  return {
    is_enabled: values.isEnabled,
    min_level:
      values.minLevelChoice === 'default' ? null : values.minLevelChoice,
    // Backend trả 403 nếu người không phải admin gửi true.
    admin_receive_all: isAdmin ? values.adminReceiveAll : false,
  }
}
