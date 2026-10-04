import { describe, expect, it } from 'vitest'

import {
  mapTelegramLinkStatusDto,
  mapTelegramLinkTokenDto,
} from '@/api/telegram.mappers'
import type {
  TelegramLinkStatusDto,
  TelegramLinkTokenDto,
} from '@/types/telegram'

function statusDto(
  overrides: Partial<TelegramLinkStatusDto> = {},
): TelegramLinkStatusDto {
  return {
    enabled: true,
    bot_username: 'quotify_bot',
    account: null,
    pending_link: null,
    ...overrides,
  }
}

function tokenDto(
  overrides: Partial<TelegramLinkTokenDto> = {},
): TelegramLinkTokenDto {
  return {
    deep_link: 'https://t.me/quotify_bot?start=abc_DEF-123',
    expires_at: '2026-10-04T10:10:00Z',
    expires_in_seconds: 600,
    bot_username: 'quotify_bot',
    ...overrides,
  }
}

describe('telegram mappers', () => {
  it('maps the status DTO to camelCase domain objects', () => {
    const domain = mapTelegramLinkStatusDto(
      statusDto({
        account: {
          status: 'blocked',
          username: 'an_nguyen',
          first_name: 'An',
          linked_at: '2026-10-01T03:00:00Z',
        },
        pending_link: {
          expires_at: '2026-10-04T10:10:00Z',
          expires_in_seconds: 420,
        },
      }),
    )

    expect(domain).toEqual({
      enabled: true,
      botUsername: 'quotify_bot',
      account: {
        status: 'blocked',
        username: 'an_nguyen',
        firstName: 'An',
        linkedAt: '2026-10-01T03:00:00Z',
      },
      pending: { expiresAt: '2026-10-04T10:10:00Z', expiresInSeconds: 420 },
    })
  })

  it('maps a missing pending link and a disabled feature', () => {
    const domain = mapTelegramLinkStatusDto(
      statusDto({ enabled: false, bot_username: null }),
    )

    expect(domain.enabled).toBe(false)
    expect(domain.botUsername).toBeNull()
    expect(domain.account).toBeNull()
    expect(domain.pending).toBeNull()
  })

  it('maps the link token DTO', () => {
    expect(mapTelegramLinkTokenDto(tokenDto())).toEqual({
      deepLink: 'https://t.me/quotify_bot?start=abc_DEF-123',
      expiresAt: '2026-10-04T10:10:00Z',
      expiresInSeconds: 600,
      botUsername: 'quotify_bot',
    })
  })

  it.each([
    'javascript:alert(1)',
    'http://t.me/quotify_bot?start=abc',
    'https://t.me.evil.example/quotify_bot',
    'https://t.me@evil.example/',
    'data:text/html,<script>1</script>',
    '',
  ])('rejects the unsafe deep link %j', (deepLink) => {
    expect(() =>
      mapTelegramLinkTokenDto(tokenDto({ deep_link: deepLink })),
    ).toThrow()
  })
})
