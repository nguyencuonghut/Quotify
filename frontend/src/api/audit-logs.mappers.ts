import type {
  AuditLogDomain,
  AuditLogDto,
  AuditLogListDomain,
  AuditLogListDto,
} from '@/types/audit-logs'

const AUDIT_LOG_TIMEZONE =
  import.meta.env.VITE_APP_TIMEZONE || 'Asia/Ho_Chi_Minh'

const auditLogDateTimeFormatter = new Intl.DateTimeFormat('vi-VN', {
  dateStyle: 'short',
  timeStyle: 'medium',
  timeZone: AUDIT_LOG_TIMEZONE,
})

const ACTION_LABELS: Record<string, string> = {
  'auth.login_failed': 'Đăng nhập thất bại',
  'auth.login_succeeded': 'Đăng nhập thành công',
  'auth.session_refreshed': 'Làm mới phiên',
  'backups.manual_backup_triggered': 'Chạy backup thủ công',
  'backups.run_completed': 'Hoàn tất backup',
  'backups.run_failed': 'Backup thất bại',
  'backups.schedule_created': 'Tạo lịch backup',
  'backups.schedule_deleted': 'Xóa lịch backup',
  'backups.schedule_updated': 'Cập nhật lịch backup',
  'users.avatar_uploaded': 'Tải ảnh đại diện',
  'users.export_completed': 'Xuất danh sách người dùng',
  'users.export_failed': 'Xuất người dùng thất bại',
  'users.import_completed': 'Nhập danh sách người dùng',
  'users.import_failed': 'Nhập người dùng thất bại',
  'users.roles_updated': 'Cập nhật vai trò',
  'users.user_created': 'Tạo người dùng',
  'users.user_deleted': 'Xóa người dùng',
  'users.user_updated': 'Cập nhật người dùng',
  'roles.role_created': 'Tạo vai trò',
  'roles.role_deleted': 'Xóa vai trò',
  'roles.role_updated': 'Cập nhật vai trò',
  'telegram.link_requested': 'Yêu cầu liên kết Telegram',
  'telegram.linked': 'Liên kết Telegram',
  'telegram.link_rejected': 'Từ chối liên kết Telegram',
  'telegram.unlinked': 'Hủy liên kết Telegram',
  'price_alerts.settings_updated': 'Cập nhật cấu hình thông báo giá',
  'price_alerts.threshold_updated': 'Cập nhật ngưỡng theo vật tư',
  'price_alerts.anomaly_reviewed': 'Duyệt giá bất thường',
}

const ENTITY_TYPE_LABELS: Record<string, string> = {
  auth_session: 'Phiên đăng nhập',
  backup_log: 'Lần backup',
  backup_schedule: 'Lịch backup',
  export_job: 'Lượt xuất dữ liệu',
  file: 'Tệp',
  import_job: 'Lượt nhập dữ liệu',
  role: 'Vai trò',
  telegram_account: 'Liên kết Telegram',
  telegram_link_token: 'Mã liên kết Telegram',
  price_alert_setting: 'Cấu hình thông báo giá',
  price_alert_material_threshold: 'Ngưỡng thông báo theo vật tư',
  price_alert_event: 'Điểm giá bất thường',
  user: 'Người dùng',
}

export function formatAuditLogDateTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return auditLogDateTimeFormatter.format(date)
}

export function getAuditActionLabel(action: string): string {
  return ACTION_LABELS[action] || action
}

export function getAuditEntityTypeLabel(entityType: string): string {
  return ENTITY_TYPE_LABELS[entityType] || entityType
}

export function getAuditTargetLabel(dto: AuditLogDto): string {
  if (dto.metadata) {
    const email = readStringMetadata(dto.metadata, 'email')
    if (email) {
      return email
    }

    const name = readStringMetadata(dto.metadata, 'name')
    if (name) {
      return name
    }

    const filename = readStringMetadata(dto.metadata, 'filename')
    if (filename) {
      return filename
    }
  }

  return dto.entity_id || 'Không xác định'
}

export function getAuditChangeSummary(dto: AuditLogDto): string {
  const changes = Array.isArray(dto.metadata?.changes)
    ? dto.metadata.changes
    : []
  const labels = changes
    .map((change) => readStringMetadata(change, 'label'))
    .filter((label): label is string => Boolean(label))

  if (labels.length > 0) {
    return `${labels.length} thay đổi: ${labels.slice(0, 3).join(', ')}`
  }

  if (dto.action === 'users.avatar_uploaded') {
    return 'Tệp ảnh đã được tải lên'
  }

  if (dto.action.startsWith('auth.')) {
    return 'Không thay đổi dữ liệu'
  }

  return 'Xem chi tiết'
}

export function mapAuditLogDtoToDomain(dto: AuditLogDto): AuditLogDomain {
  return {
    id: dto.id,
    actorUserId: dto.actor_user_id,
    actorEmail: dto.actor_email,
    action: dto.action,
    actionLabel: getAuditActionLabel(dto.action),
    entityType: dto.entity_type,
    entityTypeLabel: getAuditEntityTypeLabel(dto.entity_type),
    entityId: dto.entity_id,
    targetLabel: getAuditTargetLabel(dto),
    requestId: dto.request_id,
    ipAddress: dto.ip_address,
    metadata: dto.metadata,
    changeSummary: getAuditChangeSummary(dto),
    createdAt: dto.created_at,
    createdAtLabel: formatAuditLogDateTime(dto.created_at),
  }
}

export function mapAuditLogListDtoToDomain(
  dto: AuditLogListDto,
): AuditLogListDomain {
  return {
    items: dto.items.map(mapAuditLogDtoToDomain),
    nextCursor: dto.next_cursor,
    total: dto.total,
  }
}

function readStringMetadata(source: unknown, key: string): string | null {
  if (!source || typeof source !== 'object') {
    return null
  }

  const value = (source as Record<string, unknown>)[key]
  return typeof value === 'string' && value.trim() ? value : null
}
