export interface UserDto {
  id: string
  email: string
  status: string
  roles: string[]
  permissions: string[]
  last_login_at: string | null
  full_name: string
  avatar_url?: string | null
}

export interface UserListDto {
  items: UserDto[]
  total: number
}

export interface UserDomain {
  id: string
  email: string
  status: string
  roles: string[]
  permissions: string[]
  lastLoginAt: string | null
  fullName: string
  avatarUrl?: string | null
}

export interface UserAvatarUploadDto {
  avatar_url: string
  filename: string
}

export interface UserListDomain {
  items: UserDomain[]
  total: number
}

export interface UserCreatePayload {
  email: string
  password?: string
  status: string
  role_names: string[]
  full_name: string
  avatar_url?: string
}

export interface UserUpdatePayload {
  email: string
  status: string
  password?: string
  role_names: string[]
  full_name: string
  avatar_url?: string
}

export interface UserListQueryParams {
  limit: number
  offset: number
  search?: string
  status_filter?: string
  sort_by: string
  sort_order: 'asc' | 'desc'
}
