import type {
  TelegramLinkStatus,
  TelegramLinkStatusDto,
  TelegramLinkToken,
  TelegramLinkTokenDto,
} from '@/types/telegram'

const TELEGRAM_LINK_PREFIX = 'https://t.me/'

export function mapTelegramLinkStatusDto(
  dto: TelegramLinkStatusDto,
): TelegramLinkStatus {
  return {
    enabled: dto.enabled,
    botUsername: dto.bot_username,
    account: dto.account
      ? {
          status: dto.account.status,
          username: dto.account.username,
          firstName: dto.account.first_name,
          linkedAt: dto.account.linked_at,
        }
      : null,
    pending: dto.pending_link
      ? {
          expiresAt: dto.pending_link.expires_at,
          expiresInSeconds: dto.pending_link.expires_in_seconds,
        }
      : null,
  }
}

export function mapTelegramLinkTokenDto(
  dto: TelegramLinkTokenDto,
): TelegramLinkToken {
  // `deepLink` được dùng làm `href`, nên chỉ chấp nhận đúng đường dẫn Telegram.
  if (
    typeof dto.deep_link !== 'string' ||
    !dto.deep_link.startsWith(TELEGRAM_LINK_PREFIX)
  ) {
    throw new Error('Đường dẫn Telegram không hợp lệ.')
  }

  return {
    deepLink: dto.deep_link,
    expiresAt: dto.expires_at,
    expiresInSeconds: dto.expires_in_seconds,
    botUsername: dto.bot_username,
  }
}
