import { defineStore, type Pinia } from 'pinia'

export type ThemeMode = 'light' | 'dark'

const STORAGE_KEY = 'fastapivue-theme-mode'

function resolveInitialMode(): ThemeMode {
  if (typeof window === 'undefined') {
    return 'light'
  }

  const storedMode = window.localStorage.getItem(STORAGE_KEY)
  if (storedMode === 'light' || storedMode === 'dark') {
    return storedMode
  }

  return window.matchMedia('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light'
}

export const useThemeStore = defineStore('theme', {
  state: () => ({
    initialized: false,
    mode: 'light' as ThemeMode,
  }),
  getters: {
    isDark: (state) => state.mode === 'dark',
  },
  actions: {
    applyMode() {
      if (typeof document === 'undefined') {
        return
      }

      document.documentElement.classList.toggle(
        'app-dark',
        this.mode === 'dark',
      )
      document.documentElement.dataset.theme = this.mode
    },
    initialize() {
      if (this.initialized) {
        this.applyMode()
        return
      }

      this.mode = resolveInitialMode()
      this.initialized = true
      this.applyMode()
    },
    setMode(mode: ThemeMode) {
      this.mode = mode
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(STORAGE_KEY, mode)
      }
      this.applyMode()
    },
    toggleMode() {
      this.setMode(this.mode === 'dark' ? 'light' : 'dark')
    },
  },
})

export function createTestingThemeStore(pinia: Pinia) {
  const store = useThemeStore(pinia)
  store.initialize()
  return store
}
