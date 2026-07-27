import { computed } from 'vue'

import { defineStore } from 'pinia'

import { useAuthStore } from '@/stores/auth.store'

export const usePermissionStore = defineStore('permission', () => {
  const authStore = useAuthStore()

  const permissionSet = computed(() => new Set(authStore.permissions))
  const roleSet = computed(() => new Set(authStore.roles))

  function can(permissionCode: string) {
    return permissionSet.value.has(permissionCode)
  }

  function canAny(permissionCodes: string[]) {
    return permissionCodes.some((permissionCode) => can(permissionCode))
  }

  function hasRole(roleName: string) {
    return roleSet.value.has(roleName)
  }

  return {
    can,
    canAny,
    hasRole,
  }
})
