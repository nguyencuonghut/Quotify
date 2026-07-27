import type {
  PermissionDto,
  PermissionDomain,
  RoleDto,
  RoleDomain,
  RoleListDto,
  RoleListDomain,
} from '@/types/roles'

export function mapRoleDtoToDomain(dto: RoleDto): RoleDomain {
  return {
    id: dto.id,
    name: dto.name,
    description: dto.description,
    isSystem: dto.is_system,
    permissions: dto.permissions || [],
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}

export function mapRoleListDtoToDomain(dto: RoleListDto): RoleListDomain {
  return {
    items: dto.items.map(mapRoleDtoToDomain),
    total: dto.total,
  }
}

export function mapPermissionDtoToDomain(dto: PermissionDto): PermissionDomain {
  return {
    code: dto.code,
    description: dto.description,
  }
}
