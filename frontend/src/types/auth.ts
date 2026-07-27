export interface LoginRequestPayload {
  email: string
  password: string
}

export interface AccessTokenDto {
  access_token: string
  token_type: 'bearer'
  expires_in: number
}

export interface CurrentUserDto {
  id: string
  email: string
  status: string
  roles: string[]
  permissions: string[]
  last_login_at: string | null
  full_name: string
  avatar_url?: string | null
}

export interface AuthSession {
  accessToken: string
  tokenType: 'bearer'
  expiresInSeconds: number
}

export interface CurrentUser {
  id: string
  email: string
  status: string
  roles: string[]
  permissions: string[]
  lastLoginAt: string | null
  fullName: string
  avatarUrl?: string | null
}

export interface LoginFormValues {
  email: string
  password: string
}
