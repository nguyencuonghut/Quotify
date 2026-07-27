import type { Pinia } from 'pinia'
import type { Router } from 'vue-router'

import { useAuthStore } from '@/stores/auth.store'
import { usePermissionStore } from '@/stores/permission.store'

export function setupRouterGuards(router: Router, pinia: Pinia) {
  router.beforeEach(async (to) => {
    const authStore = useAuthStore(pinia)
    const permissionStore = usePermissionStore(pinia)

    await authStore.initialize()

    if (to.meta.guestOnly && authStore.isAuthenticated) {
      const redirectTarget =
        typeof to.query.redirect === 'string' ? to.query.redirect : '/'

      return redirectTarget
    }

    if (to.meta.requiresAuth && !authStore.isAuthenticated) {
      return {
        name: 'login',
        query: {
          redirect: to.fullPath,
        },
      }
    }

    if (
      typeof to.meta.requiredPermission === 'string' &&
      authStore.isAuthenticated &&
      !permissionStore.can(to.meta.requiredPermission)
    ) {
      return {
        name: 'forbidden',
      }
    }

    return true
  })
}
