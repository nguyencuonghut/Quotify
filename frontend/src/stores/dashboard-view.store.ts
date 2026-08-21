import { defineStore } from 'pinia'

export type DashboardMainTab = 'overview' | 'charts'
export type DashboardChartKey = 'period' | 'history' | 'seasonal'

export interface DashboardPeriodViewState {
  selectedMaterialId: string | null
  deliveryMonth: string | null
  receivedDateStart: string | null
  receivedDateEnd: string | null
  showCnfOnly: boolean
  periodRangeKey: string
}

export interface DashboardHistoryViewState {
  historyDeliveryMonth: string | null
  historyMaterialIds: string[]
  historyShowCnfOnly: boolean
}

export interface DashboardSeasonalViewState {
  seasonalMaterialId: string | null
  seasonalMonth: number | null
  seasonalYears: number[]
  seasonalShowCnfOnly: boolean
}

export interface DashboardViewState {
  activeMainTab: DashboardMainTab
  activeChartKey: DashboardChartKey
  period: DashboardPeriodViewState
  history: DashboardHistoryViewState
  seasonal: DashboardSeasonalViewState
}

const STORAGE_KEY = 'quotify-dashboard-view'

/** Dùng `sessionStorage` (không phải Pinia store thuần in-memory) để trạng
 * thái vẫn còn sau khi refresh trang — chỉ mất khi đóng tab, không mất khi
 * back/forward hay F5 — theo phản hồi người dùng ngày 20/08/2026 (bấm back
 * từ Bảng báo giá phải quay lại đúng chart/bộ lọc đang xem dở, kể cả khi
 * giữa chừng có refresh). Không dùng `localStorage` vì trạng thái xem dở
 * này chỉ có ý nghĩa trong 1 phiên, không nên "dính" mãi giữa các lần mở
 * app khác nhau. */
function resolveInitialSnapshot(): DashboardViewState | null {
  if (typeof window === 'undefined') {
    return null
  }

  const raw = window.sessionStorage.getItem(STORAGE_KEY)
  if (!raw) {
    return null
  }

  try {
    return JSON.parse(raw) as DashboardViewState
  } catch {
    return null
  }
}

/** Ghi nhớ tab/chart/bộ lọc đang xem dở trên trang Dashboard — thuần túy
 * phục vụ việc khôi phục lại đúng view khi bấm nút back của trình duyệt sau
 * khi click-through 1 điểm trên chart sang trang Bảng báo giá (điều hướng
 * bằng `router.push` hủy mất toàn bộ state cục bộ của `DashboardPage.vue`
 * khi component unmount). KHÔNG can thiệp vào router/history — chỉ là nơi
 * `DashboardPage.vue` đọc giá trị khởi tạo khi mount và ghi lại mỗi khi bộ
 * lọc thay đổi, nên không ảnh hưởng tới hành vi back của các trang khác. */
export const useDashboardViewStore = defineStore('dashboardView', {
  state: () => ({
    snapshot: resolveInitialSnapshot() as DashboardViewState | null,
  }),
  actions: {
    save(snapshot: DashboardViewState) {
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
