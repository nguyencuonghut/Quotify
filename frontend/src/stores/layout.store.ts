import { defineStore } from 'pinia'

export const useLayoutStore = defineStore('layout', {
  state: () => ({
    sidebarCollapsed: false,
    mobileSidebarOpen: false,
    isMobileViewport: false,
  }),
  actions: {
    syncViewport(width?: number) {
      if (typeof window === 'undefined' && width === undefined) {
        return
      }

      const viewportWidth = width ?? window.innerWidth
      this.isMobileViewport = viewportWidth <= 1024

      if (!this.isMobileViewport) {
        this.mobileSidebarOpen = false
      }
    },
    toggleSidebar() {
      if (this.isMobileViewport) {
        this.mobileSidebarOpen = !this.mobileSidebarOpen
        return
      }

      this.sidebarCollapsed = !this.sidebarCollapsed
    },
    closeMobileSidebar() {
      this.mobileSidebarOpen = false
    },
  },
})
