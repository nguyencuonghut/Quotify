import { describe, expect, it } from 'vitest'

import {
  formatAuditLogDateTime,
  getAuditActionLabel,
  getAuditEntityTypeLabel,
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

  it.each([
    [
      'telegram.link_requested',
      'telegram_link_token',
      'Yêu cầu liên kết Telegram',
      'Mã liên kết Telegram',
    ],
    [
      'telegram.linked',
      'telegram_account',
      'Liên kết Telegram',
      'Liên kết Telegram',
    ],
    [
      'telegram.link_rejected',
      'telegram_link_token',
      'Từ chối liên kết Telegram',
      'Mã liên kết Telegram',
    ],
    [
      'telegram.unlinked',
      'telegram_account',
      'Hủy liên kết Telegram',
      'Liên kết Telegram',
    ],
  ])(
    'labels the Telegram event %s in Vietnamese',
    (action, entityType, actionLabel, entityTypeLabel) => {
      const result = mapAuditLogDtoToDomain({
        id: 'log-tg',
        actor_user_id: 'user-1',
        actor_email: 'an@example.com',
        action,
        entity_type: entityType,
        entity_id: 'entity-1',
        request_id: 'tg-update-1',
        ip_address: null,
        metadata: { channel: 'telegram', reason: 'stop_command' },
        created_at: '2026-10-04T02:00:00+00:00',
      })

      expect(result.actionLabel).toBe(actionLabel)
      expect(result.entityTypeLabel).toBe(entityTypeLabel)
      expect(result.targetLabel).toBe('entity-1')
    },
  )

  it('labels the price alert and telegram actions and their entity types in Vietnamese', () => {
    expect(getAuditActionLabel('price_alerts.settings_updated')).toBe(
      'Cập nhật cấu hình thông báo giá',
    )
    expect(getAuditActionLabel('price_alerts.threshold_updated')).toBe(
      'Cập nhật ngưỡng theo vật tư',
    )
    expect(getAuditActionLabel('price_alerts.freshness_updated')).toBe(
      'Cập nhật theo dõi độ mới của giá',
    )
    expect(getAuditActionLabel('price_alerts.anomaly_reviewed')).toBe(
      'Duyệt giá bất thường',
    )
    expect(getAuditActionLabel('telegram.linked')).toBe('Liên kết Telegram')
    expect(getAuditEntityTypeLabel('price_alert_setting')).toBe(
      'Cấu hình thông báo giá',
    )
    expect(getAuditEntityTypeLabel('price_alert_material_threshold')).toBe(
      'Ngưỡng thông báo theo vật tư',
    )
    expect(getAuditEntityTypeLabel('price_freshness_material')).toBe(
      'Theo dõi độ mới của giá theo vật tư',
    )
    expect(getAuditEntityTypeLabel('price_alert_event')).toBe(
      'Điểm giá bất thường',
    )
  })

  describe('target label of price alert events', () => {
    function dto(overrides: Partial<AuditLogDto>): AuditLogDto {
      return {
        id: 'log-1',
        actor_user_id: 'user-1',
        actor_email: 'admin@example.com',
        action: 'price_alerts.settings_updated',
        entity_type: 'price_alert_setting',
        entity_id: '00000000-0000-4000-8000-0000000000a1',
        request_id: null,
        ip_address: null,
        metadata: null,
        created_at: '2026-10-07T06:37:22+00:00',
        ...overrides,
      }
    }

    it('shows "Cấu hình chung" instead of the singleton id for the general settings', () => {
      const result = mapAuditLogDtoToDomain(dto({ metadata: { changes: [] } }))

      expect(result.targetLabel).toBe('Cấu hình chung')
      expect(result.entityId).toBe('00000000-0000-4000-8000-0000000000a1')
    })

    it.each(['price_alert_material_threshold', 'price_freshness_material'])(
      'shows the material code and name for %s',
      (entityType) => {
        const result = mapAuditLogDtoToDomain(
          dto({
            action: 'price_alerts.freshness_updated',
            entity_type: entityType,
            entity_id: 'c6f3c0de-0000-4000-8000-000000000001',
            metadata: { material_code: 'LM3', material_name: 'Lúa mỳ 3' },
          }),
        )

        expect(result.targetLabel).toBe('LM3 · Lúa mỳ 3')
      },
    )

    it('falls back to the code alone for older records that only stored the code', () => {
      const result = mapAuditLogDtoToDomain(
        dto({
          entity_type: 'price_alert_material_threshold',
          entity_id: 'c6f3c0de-0000-4000-8000-000000000001',
          metadata: { material_code: 'LM3' },
        }),
      )

      expect(result.targetLabel).toBe('LM3')
    })

    it('shows the material for a reviewed anomaly card', () => {
      const result = mapAuditLogDtoToDomain(
        dto({
          action: 'price_alerts.anomaly_reviewed',
          entity_type: 'price_alert_event',
          entity_id: 'e1e1e1e1-0000-4000-8000-000000000002',
          metadata: {
            status: 'accepted',
            material_code: 'NGO',
            material_name: 'Ngô hạt',
          },
        }),
      )

      expect(result.targetLabel).toBe('NGO · Ngô hạt')
    })

    it('still falls back to the id when nothing readable was recorded', () => {
      const result = mapAuditLogDtoToDomain(
        dto({
          entity_type: 'price_freshness_material',
          entity_id: 'c6f3c0de-0000-4000-8000-000000000001',
          metadata: { changes: [] },
        }),
      )

      expect(result.targetLabel).toBe('c6f3c0de-0000-4000-8000-000000000001')
    })

    it('does not change the label of other entities', () => {
      expect(
        mapAuditLogDtoToDomain(
          dto({
            entity_type: 'user',
            entity_id: 'u-1',
            metadata: { email: 'a@b.c' },
          }),
        ).targetLabel,
      ).toBe('a@b.c')
    })
  })
})
