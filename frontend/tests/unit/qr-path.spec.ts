import { describe, expect, it } from 'vitest'

import { QR_QUIET_ZONE, buildQrPath } from '@/utils/qr-path'

describe('buildQrPath', () => {
  it('draws each run of dark modules as one rectangle, offset by the quiet zone', () => {
    const { path, size } = buildQrPath(
      [
        [true, true, false],
        [false, true, true],
        [false, false, false],
      ],
      1,
    )

    expect(size).toBe(5)
    expect(path).toBe('M1 1h2v1h-2zM2 2h2v1h-2z')
  })

  it('merges only consecutive modules and splits runs separated by a light module', () => {
    const { path } = buildQrPath([[true, false, true, true]], 0)

    expect(path).toBe('M0 0h1v1h-1zM2 0h2v1h-2z')
  })

  it('returns an empty path for a matrix with no dark modules', () => {
    const { path, size } = buildQrPath(
      [
        [false, false],
        [false, false],
      ],
      4,
    )

    expect(path).toBe('')
    expect(size).toBe(10)
  })

  it('uses the standard 4-module quiet zone by default', () => {
    const { size } = buildQrPath([[true]])

    expect(QR_QUIET_ZONE).toBe(4)
    expect(size).toBe(1 + 2 * QR_QUIET_ZONE)
  })

  it('produces a path made only of drawing commands and integers', () => {
    const matrix = Array.from({ length: 21 }, (_, y) =>
      Array.from({ length: 21 }, (_, x) => (x * 7 + y * 3) % 5 < 2),
    )

    const { path } = buildQrPath(matrix)

    expect(path).toMatch(/^(M\d+ \d+h\d+v1h-\d+z)+$/)
  })
})
