export interface SummaryCard {
  title: string
  value: string
  detail: string
  tone: 'info' | 'success' | 'warn'
}

export interface HealthRow {
  id: number
  domain: string
  status: 'Đang dùng' | 'Sẵn sàng' | 'Theo dõi'
  mode: string
  note: string
}

export interface DashboardAction {
  label: string
  description: string
  icon: string
  to: string
  permission: string
}
