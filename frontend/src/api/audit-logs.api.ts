import { apiRequest } from '@/api/http'
import { mapAuditLogListDtoToDomain } from '@/api/audit-logs.mappers'
import type {
  AuditLogListDomain,
  AuditLogListDto,
  AuditLogListQueryParams,
} from '@/types/audit-logs'

export function listAuditLogs(
  params: AuditLogListQueryParams,
  accessToken?: string | null,
): Promise<AuditLogListDomain> {
  const query = new URLSearchParams()
  query.append('limit', String(params.limit))

  if (params.cursor) {
    query.append('cursor', params.cursor)
  }
  if (params.actor_user_id) {
    query.append('actor_user_id', params.actor_user_id)
  }
  if (params.action) {
    query.append('action', params.action)
  }
  if (params.entity_type) {
    query.append('entity_type', params.entity_type)
  }
  if (params.entity_id) {
    query.append('entity_id', params.entity_id)
  }
  if (params.request_id) {
    query.append('request_id', params.request_id)
  }
  if (params.created_from) {
    query.append('created_from', params.created_from)
  }
  if (params.created_to) {
    query.append('created_to', params.created_to)
  }

  return apiRequest<AuditLogListDto>(`/audit-logs?${query.toString()}`, {
    accessToken,
  }).then(mapAuditLogListDtoToDomain)
}
