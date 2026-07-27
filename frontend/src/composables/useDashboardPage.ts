import { computed } from 'vue'

import type { DashboardAction, HealthRow, SummaryCard } from '@/types/dashboard'
import { usePermissionStore } from '@/stores/permission.store'

const summaryCards: SummaryCard[] = [
  {
    title: 'Tài khoản & phân quyền',
    value: 'RBAC',
    detail:
      'Quản lý tài khoản, vai trò và quyền truy cập từ một nguồn dữ liệu tập trung.',
    tone: 'success',
  },
  {
    title: 'Tệp tin nội bộ',
    value: 'MinIO',
    detail:
      'Theo dõi vùng lưu trữ tệp tin phục vụ hồ sơ, ảnh đại diện và nghiệp vụ nội bộ.',
    tone: 'info',
  },
  {
    title: 'Sao lưu & audit',
    value: 'Kiểm soát',
    detail:
      'Theo dõi sao lưu, khôi phục và lịch sử thao tác quan trọng của người dùng.',
    tone: 'warn',
  },
]

const moduleRows: HealthRow[] = [
  {
    id: 1,
    domain: 'Tài khoản người dùng',
    status: 'Đang dùng',
    mode: 'CRUD + phân quyền',
    note: 'Quản trị tài khoản, trạng thái, vai trò và ảnh đại diện.',
  },
  {
    id: 2,
    domain: 'Vai trò & quyền',
    status: 'Đang dùng',
    mode: 'RBAC',
    note: 'Quản lý vai trò và danh sách permission gắn với từng vai trò.',
  },
  {
    id: 3,
    domain: 'Tệp tin',
    status: 'Sẵn sàng',
    mode: 'MinIO',
    note: 'Upload, liệt kê và tải xuống tệp qua API bảo mật.',
  },
  {
    id: 4,
    domain: 'Sao lưu',
    status: 'Theo dõi',
    mode: 'Postgres backup',
    note: 'Tạo backup thủ công, lịch tự động và theo dõi trạng thái xử lý.',
  },
  {
    id: 5,
    domain: 'Nhật ký audit',
    status: 'Đang dùng',
    mode: 'Server-driven',
    note: 'Tra cứu lịch sử thao tác, metadata thay đổi và thông tin request.',
  },
]

const dashboardActions: DashboardAction[] = [
  {
    label: 'Quản lý tài khoản',
    description: 'Thêm, sửa, khóa và phân vai trò cho người dùng.',
    icon: 'pi pi-users',
    to: '/users',
    permission: 'users.read',
  },
  {
    label: 'Quản lý vai trò',
    description: 'Kiểm soát nhóm quyền truy cập hệ thống.',
    icon: 'pi pi-key',
    to: '/roles',
    permission: 'roles.read',
  },
  {
    label: 'Quản lý tệp tin',
    description: 'Upload, tìm kiếm và tải xuống tệp nội bộ.',
    icon: 'pi pi-file',
    to: '/files',
    permission: 'files.read',
  },
  {
    label: 'Sao lưu dữ liệu',
    description: 'Kiểm tra lịch sử backup và tạo backup thủ công.',
    icon: 'pi pi-database',
    to: '/backups',
    permission: 'backups.read',
  },
  {
    label: 'Nhật ký audit',
    description: 'Xem ai đã thay đổi dữ liệu nào và thay đổi ra sao.',
    icon: 'pi pi-history',
    to: '/audit-logs',
    permission: 'audit.read',
  },
]

export function useDashboardPage() {
  const permissionStore = usePermissionStore()

  const visibleActions = computed(() =>
    dashboardActions.filter((action) => permissionStore.can(action.permission)),
  )

  return {
    moduleRows,
    summaryCards,
    visibleActions,
  }
}
