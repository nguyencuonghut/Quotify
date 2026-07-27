import type {
  AccessTokenDto,
  AuthSession,
  CurrentUser,
  CurrentUserDto,
} from '@/types/auth'

export function mapAccessTokenDtoToSession(dto: AccessTokenDto): AuthSession {
  return {
    accessToken: dto.access_token,
    tokenType: dto.token_type,
    expiresInSeconds: dto.expires_in,
  }
}

export function mapCurrentUserDto(dto: CurrentUserDto): CurrentUser {
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
