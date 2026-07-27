import { apiRequest } from '@/api/http'
import { mapUserDtoToDomain, mapUserListDtoToDomain } from '@/api/users.mappers'
import type {
  UserCreatePayload,
  UserAvatarUploadDto,
  UserDto,
  UserDomain,
  UserListDto,
  UserListDomain,
  UserListQueryParams,
  UserUpdatePayload,
} from '@/types/users'

export function listUsers(
  params: UserListQueryParams,
  accessToken?: string | null,
): Promise<UserListDomain> {
  const query = new URLSearchParams()
  query.append('limit', String(params.limit))
  query.append('offset', String(params.offset))
  if (params.search) {
    query.append('search', params.search)
  }
  if (params.status_filter) {
    query.append('status_filter', params.status_filter)
  }
  query.append('sort_by', params.sort_by)
  query.append('sort_order', params.sort_order)

  return apiRequest<UserListDto>(`/users?${query.toString()}`, {
    accessToken,
  }).then(mapUserListDtoToDomain)
}

export function getUser(
  userId: string,
  accessToken?: string | null,
): Promise<UserDomain> {
  return apiRequest<UserDto>(`/users/${userId}`, {
    accessToken,
  }).then(mapUserDtoToDomain)
}

export function createUser(
  payload: UserCreatePayload,
  accessToken?: string | null,
): Promise<UserDomain> {
  return apiRequest<UserDto>('/users', {
    method: 'POST',
    body: JSON.stringify(payload),
    accessToken,
  }).then(mapUserDtoToDomain)
}

export function updateUser(
  userId: string,
  payload: UserUpdatePayload,
  accessToken?: string | null,
): Promise<UserDomain> {
  return apiRequest<UserDto>(`/users/${userId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
    accessToken,
  }).then(mapUserDtoToDomain)
}

export function deleteUser(
  userId: string,
  accessToken?: string | null,
): Promise<void> {
  return apiRequest<void>(`/users/${userId}`, {
    method: 'DELETE',
    accessToken,
  })
}

export function uploadUserAvatar(
  file: File,
  accessToken?: string | null,
): Promise<string> {
  const formData = new FormData()
  formData.append('file', file)

  return apiRequest<UserAvatarUploadDto>('/users/avatar-upload', {
    method: 'POST',
    body: formData,
    accessToken,
  }).then((dto) => dto.avatar_url)
}
