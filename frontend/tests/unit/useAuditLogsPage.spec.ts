import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuditLogsPage } from '@/composables/useAuditLogsPage'
import { useAuthStore } from '@/stores/auth.store'

const auditLogsApiMock = vi.hoisted(() => ({
  listAuditLogs: vi.fn(),
}))

vi.mock('@/api/audit-logs.api', () => auditLogsApiMock)

describe('useAuditLogsPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.accessToken = 'access-token'
  })

  it('fetches the first page with default rows and stores results', async () => {
    auditLogsApiMock.listAuditLogs.mockResolvedValue({
      items: [
        {
          id: 'log-1',
          actorUserId: 'user-1',
          actorEmail: 'admin@example.com',
          action: 'users.user_updated',
          actionLabel: 'Cập nhật người dùng',
          entityType: 'user',
          entityTypeLabel: 'Người dùng',
          entityId: 'target-user',
          targetLabel: 'u1@example.com',
          requestId: 'req-1',
          ipAddress: '127.0.0.1',
          metadata: null,
          changeSummary: 'Xem chi tiết',
          createdAt: '2026-07-24T02:00:00+00:00',
          createdAtLabel: '24/07/2026 09:00:00',
        },
      ],
      nextCursor: 'cursor-2',
      total: 30,
    })

    const page = useAuditLogsPage()
    await page.fetchAuditLogs()

    expect(auditLogsApiMock.listAuditLogs).toHaveBeenCalledWith(
      {
        limit: 10,
        cursor: null,
        actor_user_id: undefined,
        action: undefined,
        entity_type: undefined,
        entity_id: undefined,
        request_id: undefined,
        created_from: undefined,
        created_to: undefined,
      },
      'access-token',
    )
    expect(page.auditLogs.value).toHaveLength(1)
    expect(page.totalAuditLogs.value).toBe(30)
    expect(page.nextCursor.value).toBe('cursor-2')
  })

  it('applies filters and resets paging before fetching', async () => {
    auditLogsApiMock.listAuditLogs.mockResolvedValue({
      items: [],
      nextCursor: null,
      total: 0,
    })

    const page = useAuditLogsPage()
    page.filters.action = ' users.user_updated '
    page.filters.entityType = 'user'
    page.filters.createdFrom = '2026-07-24'
    page.filters.createdTo = '2026-07-24'

    await page.applyFilters()

    expect(page.first.value).toBe(0)
    expect(auditLogsApiMock.listAuditLogs).toHaveBeenCalledWith(
      expect.objectContaining({
        action: 'users.user_updated',
        entity_type: 'user',
        created_from: '2026-07-24',
        created_to: '2026-07-25',
      }),
      'access-token',
    )
  })

  it('uses stored cursor when moving to the next page', async () => {
    auditLogsApiMock.listAuditLogs
      .mockResolvedValueOnce({
        items: [],
        nextCursor: 'cursor-2',
        total: 30,
      })
      .mockResolvedValueOnce({
        items: [],
        nextCursor: 'cursor-3',
        total: 30,
      })

    const page = useAuditLogsPage()
    await page.fetchAuditLogs()
    await page.onPageChange({ first: 10, rows: 10 })

    expect(auditLogsApiMock.listAuditLogs).toHaveBeenLastCalledWith(
      expect.objectContaining({
        limit: 10,
        cursor: 'cursor-2',
      }),
      'access-token',
    )
    expect(page.first.value).toBe(10)
  })

  it('does not synthesize cursor requests when page jumps beyond known cursors', async () => {
    auditLogsApiMock.listAuditLogs.mockResolvedValue({
      items: [],
      nextCursor: 'cursor-2',
      total: 100,
    })

    const page = useAuditLogsPage()
    await page.fetchAuditLogs()
    await page.onPageChange({ first: 90, rows: 10 })

    expect(auditLogsApiMock.listAuditLogs).toHaveBeenCalledTimes(1)
    expect(page.first.value).toBe(0)
  })

  it('shows a Vietnamese error when API loading fails', async () => {
    auditLogsApiMock.listAuditLogs.mockRejectedValue(new Error('failed'))

    const page = useAuditLogsPage()
    await page.fetchAuditLogs()

    expect(page.generalError.value).toBe('Không thể tải nhật ký audit.')
    expect(page.loading.value).toBe(false)
  })

  it('clears stale rows when a reload fails', async () => {
    auditLogsApiMock.listAuditLogs
      .mockResolvedValueOnce({
        items: [
          {
            id: 'log-1',
            actorUserId: 'user-1',
            actorEmail: 'admin@example.com',
            action: 'users.user_updated',
            actionLabel: 'Cập nhật người dùng',
            entityType: 'user',
            entityTypeLabel: 'Người dùng',
            entityId: 'target-user',
            targetLabel: 'u1@example.com',
            requestId: 'req-1',
            ipAddress: '127.0.0.1',
            metadata: null,
            changeSummary: 'Xem chi tiết',
            createdAt: '2026-07-24T02:00:00+00:00',
            createdAtLabel: '24/07/2026 09:00:00',
          },
        ],
        nextCursor: null,
        total: 1,
      })
      .mockRejectedValueOnce(new Error('failed'))

    const page = useAuditLogsPage()
    await page.fetchAuditLogs()
    await page.fetchAuditLogs()

    expect(page.auditLogs.value).toEqual([])
    expect(page.totalAuditLogs.value).toBe(0)
    expect(page.nextCursor.value).toBeNull()
  })
})
