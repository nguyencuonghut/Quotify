import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiRequest = vi.hoisted(() => vi.fn())

vi.mock('@/api/http', () => ({ apiRequest }))

import { listUsers } from '@/api/users.api'

function lastQuery(): URLSearchParams {
  const path = apiRequest.mock.calls.at(-1)?.[0] as string
  return new URLSearchParams(path.split('?')[1])
}

describe('listUsers query', () => {
  beforeEach(() => {
    apiRequest.mockReset()
    apiRequest.mockResolvedValue({ items: [], total: 0 })
  })

  const base = { limit: 10, offset: 0, sort_by: 'created_at', sort_order: 'desc' as const }

  it('sends the role and Telegram filters when they are set', async () => {
    await listUsers({ ...base, role_filter: 'manager', telegram_filter: 'none' })

    expect(lastQuery().get('role_filter')).toBe('manager')
    expect(lastQuery().get('telegram_filter')).toBe('none')
  })

  it('leaves the filters out when they are empty', async () => {
    await listUsers({ ...base, role_filter: '', telegram_filter: '' })

    expect(lastQuery().has('role_filter')).toBe(false)
    expect(lastQuery().has('telegram_filter')).toBe(false)
  })
})
