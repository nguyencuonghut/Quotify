import { defineStore } from 'pinia'

export interface QuotesViewState {
  globalSearch: string
  supplierId: string | null
  materialId: string | null
  materialTypeId: string | null
  receivedDateStart: string | null
  receivedDateEnd: string | null
  deliveryMonth: string | null
  purchased: boolean | null
  cancelled: boolean | null
  limit: number
  offset: number
  sortField: string
  sortOrder: string
}

const STORAGE_KEY = 'quotify-quotes-view'

/** Dùng `sessionStorage` (không phải Pinia store thuần in-memory) để trạng
 * thái vẫn còn sau khi refresh trang — chỉ mất khi đóng tab, không mất khi
 * back/forward hay F5 — cùng lý do và cùng khuôn với `dashboard-view.store.ts`
 * (theo phản hồi người dùng ngày 20/08/2026 áp dụng cho Dashboard, giờ lặp
 * lại đúng bug này ở Bảng báo giá ngày 24/08/2026). Không dùng `localStorage`
 * vì trạng thái xem dở này chỉ có ý nghĩa trong 1 phiên. */
function resolveInitialSnapshot(): QuotesViewState | null {
  if (typeof window === 'undefined') {
    return null
  }

  const raw = window.sessionStorage.getItem(STORAGE_KEY)
  if (!raw) {
    return null
  }

  try {
    return JSON.parse(raw) as QuotesViewState
  } catch {
    return null
  }
}

/** Ghi nhớ bộ lọc/trang/sắp xếp đang xem dở trên Bảng báo giá — thuần túy
 * phục vụ việc khôi phục lại đúng view khi bấm nút back của trình duyệt sau
 * khi click vào 1 dòng để xem chi tiết phiếu báo giá (điều hướng bằng
 * `router.push` hủy mất toàn bộ state cục bộ của `QuotesPage.vue` khi
 * component unmount, vì không có `<KeepAlive>` bọc `<RouterView>`). KHÔNG
 * can thiệp vào router/history — chỉ là nơi `QuotesPage.vue` đọc giá trị
 * khởi tạo khi mount và ghi lại mỗi khi bộ lọc/trang/sắp xếp thay đổi. */
export const useQuotesViewStore = defineStore('quotesView', {
  state: () => ({
    snapshot: resolveInitialSnapshot() as QuotesViewState | null,
  }),
  actions: {
    save(snapshot: QuotesViewState) {
      this.snapshot = snapshot
      if (typeof window !== 'undefined') {
        window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot))
      }
    },
    clear() {
      this.snapshot = null
      if (typeof window !== 'undefined') {
        window.sessionStorage.removeItem(STORAGE_KEY)
      }
    },
  },
})
