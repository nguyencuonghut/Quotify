import { describe, expect, it } from 'vitest'

import {
  formatAuditLogDateTime,
  mapAuditLogDtoToDomain,
  mapAuditLogListDtoToDomain,
} from '@/api/audit-logs.mappers'
import type { AuditLogDto } from '@/types/audit-logs'

describe('audit log mappers', () => {
  it('maps audit log dto to frontend domain fields', () => {
    const dto: AuditLogDto = {
      id: 'log-1',
      actor_user_id: 'user-1',
      actor_email: 'admin@example.com',
      action: 'users.user_updated',
      entity_type: 'user',
      entity_id: 'target-user',
      request_id: 'req-1',
      ip_address: '127.0.0.1',
      metadata: {
        changes: [
          {
            field: 'full_name',
            label: 'Họ và tên',
            old_value: 'Nguyễn Văn A',
            new_value: 'Nguyễn Văn B',
          },
          {
            field: 'avatar_url',
            label: 'Ảnh đại diện',
            old_value: null,
            new_value: '/api/v1/files/avatar/download',
          },
        ],
        email: 'user@example.com',
      },
      created_at: '2026-07-24T02:00:00+00:00',
    }

    const result = mapAuditLogDtoToDomain(dto)

    expect(result).toMatchObject({
      id: 'log-1',
      actorUserId: 'user-1',
      actorEmail: 'admin@example.com',
      action: 'users.user_updated',
      actionLabel: 'Cập nhật người dùng',
      entityType: 'user',
      entityTypeLabel: 'Người dùng',
      entityId: 'target-user',
      targetLabel: 'user@example.com',
      requestId: 'req-1',
      ipAddress: '127.0.0.1',
      metadata: {
        changes: [
          {
            field: 'full_name',
            label: 'Họ và tên',
            old_value: 'Nguyễn Văn A',
            new_value: 'Nguyễn Văn B',
          },
          {
            field: 'avatar_url',
            label: 'Ảnh đại diện',
            old_value: null,
            new_value: '/api/v1/files/avatar/download',
          },
        ],
        email: 'user@example.com',
      },
      changeSummary: '2 thay đổi: Họ và tên, Ảnh đại diện',
      createdAt: '2026-07-24T02:00:00+00:00',
    })
    expect(result.createdAtLabel).toBe(
      formatAuditLogDateTime('2026-07-24T02:00:00+00:00'),
    )
  })

  it('maps list response and keeps next cursor', () => {
    const dto = {
      items: [
        {
          id: 'log-1',
          actor_user_id: null,
          actor_email: null,
          action: 'auth.login_failed',
          entity_type: 'auth_session',
          entity_id: null,
          request_id: null,
          ip_address: null,
          metadata: null,
          created_at: '2026-07-24T02:00:00+00:00',
        },
      ],
      next_cursor: 'cursor-2',
      total: 30,
    }

    const result = mapAuditLogListDtoToDomain(dto)

    expect(result.total).toBe(30)
    expect(result.nextCursor).toBe('cursor-2')
    expect(result.items[0].action).toBe('auth.login_failed')
    expect(result.items[0].actionLabel).toBe('Đăng nhập thất bại')
    expect(result.items[0].changeSummary).toBe('Không thay đổi dữ liệu')
  })
})
