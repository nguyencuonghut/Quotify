import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, ref, type EffectScope } from 'vue'

import { useQrCode } from '@/composables/useQrCode'
import { buildQrPath } from '@/utils/qr-path'

const uqrMock = vi.hoisted(() => ({ encode: vi.fn() }))

vi.mock('uqr', () => uqrMock)

const MATRIX = [
  [true, false],
  [false, true],
]

describe('useQrCode', () => {
  let scope: EffectScope

  beforeEach(() => {
    vi.resetAllMocks()
    uqrMock.encode.mockReturnValue({ data: MATRIX, size: 2 })
    scope = effectScope()
  })

  afterEach(() => scope.stop())

  function mount(text: ReturnType<typeof ref<string | null>>) {
    const result = scope.run(() => useQrCode(text))
    if (!result) throw new Error('scope không chạy')
    return result
  }

  it('encodes the text lazily and exposes the SVG path', async () => {
    const text = ref<string | null>('https://t.me/quotify_bot?start=abc')
    const { qr } = mount(text)

    await flushPromises()

    expect(uqrMock.encode).toHaveBeenCalledWith(
      'https://t.me/quotify_bot?start=abc',
      { ecc: 'M', border: 0 },
    )
    expect(qr.value).toEqual(buildQrPath(MATRIX))
  })

  it('stays empty and never loads the library without a text', async () => {
    const { qr } = mount(ref<string | null>(null))

    await flushPromises()

    expect(qr.value).toBeNull()
    expect(uqrMock.encode).not.toHaveBeenCalled()
  })

  it('clears the code when the text goes away', async () => {
    const text = ref<string | null>('https://t.me/quotify_bot?start=abc')
    const { qr } = mount(text)
    await flushPromises()
    expect(qr.value).not.toBeNull()

    text.value = null
    await flushPromises()

    expect(qr.value).toBeNull()
  })

  it('follows the latest text', async () => {
    const text = ref<string | null>('https://t.me/quotify_bot?start=first')
    const { qr } = mount(text)
    await flushPromises()
    uqrMock.encode.mockReturnValue({
      data: [[true, true]],
      size: 2,
    })

    text.value = 'https://t.me/quotify_bot?start=second'
    await flushPromises()

    expect(qr.value).toEqual(buildQrPath([[true, true]]))
  })

  it('degrades to no QR code when encoding fails', async () => {
    uqrMock.encode.mockImplementation(() => {
      throw new Error('data too long')
    })
    const { qr } = mount(
      ref<string | null>('https://t.me/quotify_bot?start=abc'),
    )

    await flushPromises()

    expect(qr.value).toBeNull()
  })
})
