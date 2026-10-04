/** Vùng trắng bao quanh mã QR, tính bằng số ô. Chuẩn QR yêu cầu tối thiểu 4 ô để quét được. */
export const QR_QUIET_ZONE = 4

export interface QrPath {
  /** Giá trị cho thuộc tính `d` của `<path>`; mỗi đoạn ô đen liền nhau là một hình chữ nhật. */
  path: string
  /** Cạnh của `viewBox`, đã gồm vùng trắng hai bên. */
  size: number
}

/**
 * Đổi ma trận ô (true là ô đen) thành đường vẽ SVG. Chỉ sinh số nguyên và lệnh vẽ cố định, nên
 * có thể gán thẳng vào `<path :d>` mà không cần `v-html`.
 */
export function buildQrPath(
  matrix: ReadonlyArray<ReadonlyArray<boolean>>,
  border: number = QR_QUIET_ZONE,
): QrPath {
  const segments: string[] = []

  matrix.forEach((row, y) => {
    let x = 0
    while (x < row.length) {
      if (!row[x]) {
        x += 1
        continue
      }
      const start = x
      while (x < row.length && row[x]) {
        x += 1
      }
      const length = x - start
      segments.push(`M${start + border} ${y + border}h${length}v1h-${length}z`)
    }
  })

  return { path: segments.join(''), size: matrix.length + 2 * border }
}
