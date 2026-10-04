import { shallowRef, watch, type Ref } from 'vue'

import { buildQrPath, type QrPath } from '@/utils/qr-path'

/**
 * Sinh mã QR cho một chuỗi. Thư viện `uqr` chỉ được tải khi thật sự có chuỗi cần mã hóa (nạp lười),
 * và lỗi mã hóa chỉ làm mất mã QR chứ không ảnh hưởng phần còn lại của trang.
 */
export function useQrCode(text: Ref<string | null>) {
  const qr = shallowRef<QrPath | null>(null)
  // Chỉ kết quả của lần gọi mới nhất được dùng, tránh mã của một chuỗi cũ ghi đè chuỗi mới.
  let latest = 0

  watch(
    text,
    async (value) => {
      const current = ++latest
      qr.value = null
      if (!value) return

      try {
        const { encode } = await import('uqr')
        if (current !== latest) return
        qr.value = buildQrPath(encode(value, { ecc: 'M', border: 0 }).data)
      } catch {
        if (current === latest) qr.value = null
      }
    },
    { immediate: true },
  )

  return { qr }
}
