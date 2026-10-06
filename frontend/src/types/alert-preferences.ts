export type AlertLevel = 'light' | 'medium' | 'large'
/** Lựa chọn trên giao diện: `default` nghĩa là mức mặc định theo vai trò (gửi `null`). */
export type AlertLevelChoice = 'default' | AlertLevel

export interface AlertPreferencesDto {
  is_enabled: boolean
  min_level: AlertLevel | null
  effective_min_level: AlertLevel
  admin_receive_all: boolean
}

export interface AlertPreferencesDomain {
  isEnabled: boolean
  minLevelChoice: AlertLevelChoice
  effectiveMinLevel: AlertLevel
  adminReceiveAll: boolean
}

export interface AlertPreferencesUpdatePayload {
  is_enabled: boolean
  min_level: AlertLevel | null
  admin_receive_all: boolean
}
