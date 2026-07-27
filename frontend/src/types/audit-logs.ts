export type AuditLogMetadata = Record<string, unknown>

export interface AuditLogDto {
  id: string
  actor_user_id: string | null
  actor_email: string | null
  action: string
  entity_type: string
  entity_id: string | null
  request_id: string | null
  ip_address: string | null
  metadata: AuditLogMetadata | null
  created_at: string
}

export interface AuditLogListDto {
  items: AuditLogDto[]
  next_cursor: string | null
  total: number
}

export interface AuditLogDomain {
  id: string
  actorUserId: string | null
  actorEmail: string | null
  action: string
  actionLabel: string
  entityType: string
  entityTypeLabel: string
  entityId: string | null
  targetLabel: string
  requestId: string | null
  ipAddress: string | null
  metadata: AuditLogMetadata | null
  changeSummary: string
  createdAt: string
  createdAtLabel: string
}

export interface AuditLogListDomain {
  items: AuditLogDomain[]
  nextCursor: string | null
  total: number
}

export interface AuditLogListQueryParams {
  limit: number
  cursor?: string | null
  actor_user_id?: string
  action?: string
  entity_type?: string
  entity_id?: string
  request_id?: string
  created_from?: string
  created_to?: string
}
