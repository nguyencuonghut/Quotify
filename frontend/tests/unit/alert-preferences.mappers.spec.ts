import { describe, expect, it } from 'vitest'

import {
  mapAlertPreferencesDtoToDomain,
  mapAlertPreferencesToPayload,
} from '@/api/alert-preferences.mappers'

describe('alert preference mappers', () => {
  it('shows a missing personal level as the role default', () => {
    expect(
      mapAlertPreferencesDtoToDomain({
        is_enabled: true,
        min_level: null,
        effective_min_level: 'medium',
        admin_receive_all: false,
      }),
    ).toEqual({
      isEnabled: true,
      minLevelChoice: 'default',
      effectiveMinLevel: 'medium',
      adminReceiveAll: false,
    })
    expect(
      mapAlertPreferencesDtoToDomain({
        is_enabled: false,
        min_level: 'light',
        effective_min_level: 'light',
        admin_receive_all: true,
      }),
    ).toMatchObject({
      isEnabled: false,
      minLevelChoice: 'light',
      adminReceiveAll: true,
    })
  })

  it('sends null for the role default and never asks for "receive all" unless admin', () => {
    const values = {
      isEnabled: true,
      minLevelChoice: 'default' as const,
      adminReceiveAll: true,
    }

    expect(mapAlertPreferencesToPayload(values, false)).toEqual({
      is_enabled: true,
      min_level: null,
      admin_receive_all: false,
    })
    expect(
      mapAlertPreferencesToPayload(
        { ...values, minLevelChoice: 'large' },
        true,
      ),
    ).toEqual({ is_enabled: true, min_level: 'large', admin_receive_all: true })
  })
})
