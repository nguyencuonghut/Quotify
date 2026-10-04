export type TelegramAccountStatus = 'active' | 'blocked'

export interface TelegramAccountDto {
  status: TelegramAccountStatus
  username: string | null
  first_name: string | null
  linked_at: string
}

export interface TelegramPendingLinkDto {
  expires_at: string
  expires_in_seconds: number
}

export interface TelegramLinkStatusDto {
  enabled: boolean
  bot_username: string | null
  account: TelegramAccountDto | null
  pending_link: TelegramPendingLinkDto | null
}

export interface TelegramLinkTokenDto {
  deep_link: string
  expires_at: string
  expires_in_seconds: number
  bot_username: string
}

export interface TelegramAccount {
  status: TelegramAccountStatus
  /** Không có `@`; giao diện tự thêm. */
  username: string | null
  firstName: string | null
  linkedAt: string
}

export interface TelegramPendingLink {
  expiresAt: string
  /** Do server tính tại lúc trả lời, để đếm ngược không phụ thuộc đồng hồ máy khách. */
  expiresInSeconds: number
}

export interface TelegramLinkStatus {
  enabled: boolean
  botUsername: string | null
  account: TelegramAccount | null
  pending: TelegramPendingLink | null
}

export interface TelegramLinkToken {
  deepLink: string
  expiresAt: string
  expiresInSeconds: number
  botUsername: string
}
