import { describe, expect, it } from 'vitest'

import { getDefaultAvatarUrl, getUserAvatarUrl } from '@/utils/default-avatars'

describe('default avatar helpers', () => {
  it('uses uploaded avatar when available', () => {
    expect(getUserAvatarUrl({
      id: 'user-1',
      email: 'user@example.com',
      fullName: 'User One',
      avatarUrl: '/api/v1/files/avatar/download',
    })).toBe('/api/v1/files/avatar/download')
  })

  it('uses user id as the stable fallback seed', () => {
    const first = getUserAvatarUrl({
      id: 'user-1',
      email: 'first@example.com',
      fullName: 'First Name',
    })
    const second = getUserAvatarUrl({
      id: 'user-1',
      email: 'second@example.com',
      fullName: 'Second Name',
    })

    expect(first).toBe(second)
    expect(first).toBe(getDefaultAvatarUrl('user-1'))
  })
})
