import { apiRequest } from '@/api/http'
import {
  mapPermissionDtoToDomain,
  mapRoleDtoToDomain,
  mapRoleListDtoToDomain,
} from '@/api/roles.mappers'
import type {
  PermissionDto,
  PermissionDomain,
  RoleCreatePayload,
  RoleDto,
  RoleDomain,
  RoleListDto,
  RoleListDomain,
  RoleListQueryParams,
  RoleUpdatePayload,
} from '@/types/roles'

export function listRoles(
  params: RoleListQueryParams,
  accessToken?: string | null,
): Promise<RoleListDomain> {
  const query = new URLSearchParams()
  query.append('limit', String(params.limit))
  query.append('offset', String(params.offset))
  if (params.search) {
    query.append('search', params.search)
  }
  query.append('sort_by', params.sort_by)
  query.append('sort_order', params.sort_order)

  return apiRequest<RoleListDto>(`/roles?${query.toString()}`, {
    accessToken,
  }).then(mapRoleListDtoToDomain)
}

export function listRolesLookup(
  accessToken?: string | null,
): Promise<RoleDomain[]> {
  return apiRequest<RoleListDto>(
    '/roles?limit=100&sort_by=name&sort_order=asc',
    {
      accessToken,
    },
  ).then((dto) => dto.items.map(mapRoleDtoToDomain))
}

export function getRole(
  roleId: string,
  accessToken?: string | null,
): Promise<RoleDomain> {
  return apiRequest<RoleDto>(`/roles/${roleId}`, {
    accessToken,
  }).then(mapRoleDtoToDomain)
}

export function createRole(
  payload: RoleCreatePayload,
  accessToken?: string | null,
): Promise<RoleDomain> {
  return apiRequest<RoleDto>('/roles', {
    method: 'POST',
    body: JSON.stringify(payload),
    accessToken,
  }).then(mapRoleDtoToDomain)
}

export function updateRole(
  roleId: string,
  payload: RoleUpdatePayload,
  accessToken?: string | null,
): Promise<RoleDomain> {
  return apiRequest<RoleDto>(`/roles/${roleId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
    accessToken,
  }).then(mapRoleDtoToDomain)
}

export function deleteRole(
  roleId: string,
  accessToken?: string | null,
): Promise<void> {
  return apiRequest<void>(`/roles/${roleId}`, {
    method: 'DELETE',
    accessToken,
  })
}

export function listPermissions(
  accessToken?: string | null,
): Promise<PermissionDomain[]> {
  return apiRequest<PermissionDto[]>('/permissions', {
    accessToken,
  }).then((dtos) => dtos.map(mapPermissionDtoToDomain))
}
