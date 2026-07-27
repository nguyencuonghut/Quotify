import { mapRoleDtoToDomain } from '@/api/roles.mappers'
import type {
  UserDto,
  UserDomain,
  UserListDto,
  UserListDomain,
} from '@/types/users'

export function mapUserDtoToDomain(dto: UserDto): UserDomain {
  return {
    id: dto.id,
    email: dto.email,
    status: dto.status,
    roles: dto.roles,
    permissions: dto.permissions,
    lastLoginAt: dto.last_login_at,
    fullName: dto.full_name,
    avatarUrl: dto.avatar_url,
  }
}

export function mapUserListDtoToDomain(dto: UserListDto): UserListDomain {
  return {
    items: dto.items.map(mapUserDtoToDomain),
    total: dto.total,
  }
}

export { mapRoleDtoToDomain }
