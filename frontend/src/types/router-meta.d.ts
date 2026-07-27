import 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    guestOnly?: boolean
    requiresAuth?: boolean
    requiredPermission?: string
    title?: string
    description?: string
  }
}
