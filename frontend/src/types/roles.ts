export interface RoleDto {
  id: string
  name: string
  description: string | null
  is_system: boolean
  permissions: string[]
  created_at: string
  updated_at: string
}

export interface RoleDomain {
  id: string
  name: string
  description: string | null
  isSystem: boolean
  permissions: string[]
  createdAt: string
  updatedAt: string
}

export interface RoleCreatePayload {
  name: string
  description: string | null
  permissions: string[]
}

export interface RoleUpdatePayload {
  name: string
  description: string | null
  permissions: string[]
}

export interface RoleListQueryParams {
  limit: number
  offset: number
  search?: string
  sort_by: string
  sort_order: string
}

export interface RoleListDto {
  items: RoleDto[]
  total: number
}

export interface RoleListDomain {
  items: RoleDomain[]
  total: number
}

export interface PermissionDto {
  code: string
  description: string | null
}

export interface PermissionDomain {
  code: string
  description: string | null
}
