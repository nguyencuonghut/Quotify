const DEFAULT_AVATAR_PATHS = [
  '/default-avatars/avatar-01.svg',
  '/default-avatars/avatar-02.svg',
  '/default-avatars/avatar-03.svg',
  '/default-avatars/avatar-04.svg',
  '/default-avatars/avatar-05.svg',
  '/default-avatars/avatar-06.svg',
] as const

type AvatarUserLike = {
  id?: string | null
  email?: string | null
  fullName?: string | null
  avatarUrl?: string | null
}

export function getDefaultAvatarUrl(seed: string | null | undefined): string {
  const normalizedSeed = seed?.trim() || 'quotify-user'
  const index = (hashString(normalizedSeed) >>> 0) % DEFAULT_AVATAR_PATHS.length
  return DEFAULT_AVATAR_PATHS[index]
}

export function getUserAvatarUrl(user: AvatarUserLike | null | undefined): string {
  if (user?.avatarUrl?.trim()) {
    return user.avatarUrl
  }

  return getDefaultAvatarUrl(
    [user?.id, user?.email, user?.fullName].filter(Boolean).join(':'),
  )
}

function hashString(value: string): number {
  let hash = 0
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) | 0
  }
  return hash
}
