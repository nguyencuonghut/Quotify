import { createRouter, createWebHistory } from 'vue-router'

import AuditLogsPage from '@/pages/AuditLogsPage.vue'
import DashboardPage from '@/pages/DashboardPage.vue'
import ForbiddenPage from '@/pages/ForbiddenPage.vue'
import LoginPage from '@/pages/LoginPage.vue'
import MaterialTypesPage from '@/pages/MaterialTypesPage.vue'
import MaterialsPage from '@/pages/MaterialsPage.vue'
import NotFoundPage from '@/pages/NotFoundPage.vue'
import ProfilePage from '@/pages/ProfilePage.vue'
import QuotifySettingsPage from '@/pages/QuotifySettingsPage.vue'
import RolesPage from '@/pages/RolesPage.vue'
import SuppliersPage from '@/pages/SuppliersPage.vue'
import UsersPage from '@/pages/UsersPage.vue'
import BackupsPage from '@/pages/BackupsPage.vue'
import QuoteEditorPage from '@/pages/QuoteEditorPage.vue'
import QuoteDetailPage from '@/pages/QuoteDetailPage.vue'
import QuotesPage from '@/pages/QuotesPage.vue'


export const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    }

    return {
      left: 0,
      top: 0,
    }
  },
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginPage,
      meta: {
        guestOnly: true,
        title: 'Đăng nhập',
        description: 'Đăng nhập hệ thống phân tích báo giá nguyên liệu Quotify.',
      },
    },
    {
      path: '/',
      name: 'dashboard',
      component: DashboardPage,
      meta: {
        requiresAuth: true,
        requiredPermission: 'dashboard.read',
        title: 'Bảng điều khiển',
        description:
          'Bảng điều khiển phân tích báo giá, xu hướng giá và chỉ số nhập liệu Quotify.',
      },
    },
    {
      path: '/catalog/material-types',
      name: 'material-types',
      component: MaterialTypesPage,
      meta: {
        requiresAuth: true,
        requiredPermission: 'material_types.read',
        title: 'Loại vật tư',
        description: 'Quản lý danh mục loại vật tư cho hệ thống Quotify.',
      },
    },
    {
      path: '/catalog/materials',
      name: 'materials',
      component: MaterialsPage,
      meta: {
        requiresAuth: true,
        requiredPermission: 'materials.read',
        title: 'Vật tư',
        description: 'Quản lý danh mục vật tư và loại vật tư tương ứng.',
      },
    },
    {
      path: '/catalog/suppliers',
      name: 'suppliers',
      component: SuppliersPage,
      meta: {
        requiresAuth: true,
        requiredPermission: 'suppliers.read',
        title: 'Nhà cung cấp',
        description: 'Quản lý danh mục nhà cung cấp, liên hệ và vật tư cung cấp.',
      },
    },
    {
      path: '/quotify-settings',
      name: 'quotify-settings',
      component: QuotifySettingsPage,
      meta: {
        requiresAuth: true,
        requiredPermission: 'quotify_settings.read',
        title: 'Cấu hình quy đổi',
        description:
          'Cấu hình chi phí quy đổi và tra cứu tỷ giá USD bán ra cho hệ thống Quotify.',
      },
    },
    {
      path: '/quotes',
      name: 'quotes',
      component: QuotesPage,
      meta: {
        requiresAuth: true,
        requiredPermission: 'quotes.read',
        title: 'Bảng báo giá và lịch sử',
        description: 'Tra cứu lịch sử báo giá vật tư và so sánh biến động giá.',
      },
    },
    {
      path: '/quotes/new',
      name: 'quote-new',
      component: QuoteEditorPage,
      meta: {
        requiresAuth: true,
        requiredPermission: 'quotes.create',
        title: 'Nhập báo giá',
        description: 'Tạo mới phiếu báo giá nguyên liệu và các dòng vật tư.',
      },
    },
    {
      path: '/quotes/:quoteId',
      name: 'quote-detail',
      component: QuoteDetailPage,
      meta: {
        requiresAuth: true,
        requiredPermission: 'quotes.read',
        title: 'Chi tiết báo giá',
        description: 'Xem chi tiết phiếu báo giá, lịch sử phiên bản và chốt mua.',
      },
    },
    {
      path: '/quotes/:quoteId/versions/new',
      name: 'quote-version-new',
      component: QuoteEditorPage,
      meta: {
        requiresAuth: true,
        requiredPermission: 'quotes.update',
        title: 'Tạo bản điều chỉnh báo giá',
        description: 'Tạo bản điều chỉnh để thay thế phiên bản đã xác nhận hiện tại.',
      },
    },
    {
      path: '/quotes/:quoteId/versions/:versionId/edit',
      name: 'quote-draft-edit',
      component: QuoteEditorPage,
      meta: {
        requiresAuth: true,
        requiredPermission: 'quotes.update',
        title: 'Sửa bản nháp báo giá',
        description: 'Chỉnh sửa chi tiết bản nháp của phiên bản báo giá.',
      },
    },

    {
      path: '/users',
      name: 'users',
      component: UsersPage,
      meta: {
        requiresAuth: true,
        requiredPermission: 'users.read',
        title: 'Quản lý tài khoản',
        description:
          'Danh sách tài khoản người dùng, vai trò phân quyền và lịch sử hoạt động hệ thống.',
      },
    },
    {
      path: '/roles',
      name: 'roles',
      component: RolesPage,
      meta: {
        requiresAuth: true,
        requiredPermission: 'roles.read',
        title: 'Quản lý vai trò',
        description:
          'Cấu hình vai trò và quản lý chi tiết phân quyền truy cập hệ thống.',
      },
    },
    {
      path: '/backups',
      name: 'backups',
      component: BackupsPage,
      meta: {
        requiresAuth: true,
        requiredPermission: 'backups.read',
        title: 'Sao lưu & Khôi phục',
        description:
          'Cấu hình sao lưu Postgres tự động, quản lý lịch sử sao lưu và khôi phục dữ liệu hệ thống.',
      },
    },
    {
      path: '/audit-logs',
      name: 'audit-logs',
      component: AuditLogsPage,
      meta: {
        requiresAuth: true,
        requiredPermission: 'audit.read',
        title: 'Nhật ký audit',
        description:
          'Theo dõi lịch sử thao tác người dùng, request và metadata đã sanitize trong hệ thống.',
      },
    },
    {
      path: '/profile',
      name: 'profile',
      component: ProfilePage,
      meta: {
        requiresAuth: true,
        title: 'Thông tin cá nhân',
        description:
          'Cập nhật thông tin cá nhân tài khoản, họ và tên và ảnh đại diện.',
      },
    },
    {
      path: '/forbidden',
      name: 'forbidden',
      component: ForbiddenPage,
      meta: {
        requiresAuth: true,
        title: 'Không có quyền truy cập',
        description: 'Bạn không có đủ quyền hạn để truy cập tài nguyên này.',
      },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: NotFoundPage,
      meta: {
        requiresAuth: true,
        title: 'Không tìm thấy trang',
        description: 'Trang bạn đang mở không tồn tại trong hệ thống Quotify.',
      },
    },
  ],
})

router.afterEach((to) => {
  const defaultTitle = import.meta.env.VITE_APP_NAME || 'Quotify'
  const title = typeof to.meta.title === 'string' ? to.meta.title : defaultTitle
  document.title = title

  const defaultDescription = `${defaultTitle} - Hệ thống phân tích báo giá nguyên liệu.`
  const description =
    typeof to.meta.description === 'string'
      ? to.meta.description
      : defaultDescription

  let metaDescription = document.querySelector('meta[name="description"]')
  if (!metaDescription) {
    metaDescription = document.createElement('meta')
    metaDescription.setAttribute('name', 'description')
    document.head.appendChild(metaDescription)
  }
  metaDescription.setAttribute('content', description)
})
