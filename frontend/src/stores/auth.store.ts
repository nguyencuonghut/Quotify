import { defineStore, type Pinia } from 'pinia'

import { ApiError } from '@/api/http'
import {
  getCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
  refreshSession,
} from '@/api/auth.api'
import type { CurrentUser, LoginFormValues } from '@/types/auth'

let initializePromise: Promise<void> | null = null

const LOGGED_IN_COOKIE_NAME =
  import.meta.env.VITE_AUTH_LOGGED_IN_COOKIE_NAME || 'quotify_logged_in'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: null as string | null,
    currentUser: null as CurrentUser | null,
    initialized: false,
    initializing: false,
    loginPending: false,
  }),
  getters: {
    isAuthenticated: (state) =>
      state.accessToken !== null && state.currentUser !== null,
    permissions: (state) => state.currentUser?.permissions ?? [],
    roles: (state) => state.currentUser?.roles ?? [],
  },
  actions: {
    clearAuthState() {
      this.accessToken = null
      this.currentUser = null
      try {
        document.cookie = `${LOGGED_IN_COOKIE_NAME}=; path=/; max-age=0; samesite=lax`
      } catch {
        // ignore in non-browser environments
      }
    },
    setAccessToken(token: string) {
      this.accessToken = token
    },
    async fetchCurrentUser() {
      if (!this.accessToken) {
        throw new ApiError('Access token is missing.', 401)
      }

      const currentUser = await getCurrentUser(this.accessToken)
      this.currentUser = currentUser
      return currentUser
    },
    async initialize() {
      if (this.initialized) {
        return
      }

      if (initializePromise) {
        await initializePromise
        return
      }

      const hasLoggedInCookie = document.cookie
        .split(';')
        .some((item) => item.trim().startsWith(`${LOGGED_IN_COOKIE_NAME}=`))

      if (!hasLoggedInCookie) {
        this.clearAuthState()
        this.initialized = true
        return
      }

      this.initializing = true

      initializePromise = (async () => {
        try {
          const session = await refreshSession()
          this.setAccessToken(session.accessToken)
          await this.fetchCurrentUser()
        } catch (error) {
          if (
            error instanceof ApiError &&
            (error.status === 401 || error.status === 403)
          ) {
            // Explicit rejection from the backend: the refresh/access token is
            // genuinely invalid, so treat the user as logged out.
            this.clearAuthState()
          } else if (error instanceof TypeError) {
            // Network-level failure (e.g. the request was aborted because the
            // page navigated away mid-flight during a rapid Ctrl+R/F5). This
            // says nothing about whether the session is actually still valid,
            // so do NOT clear the login marker cookie — leave it intact so the
            // next reload gets a normal chance to refresh instead of being
            // permanently locked out by a transient network hiccup.
          } else {
            throw error
          }
        } finally {
          this.initialized = true
          this.initializing = false
        }
      })()

      try {
        await initializePromise
      } finally {
        initializePromise = null
      }
    },
    async login(payload: LoginFormValues) {
      this.loginPending = true

      try {
        const session = await loginRequest(payload)
        this.setAccessToken(session.accessToken)
        await this.fetchCurrentUser()
        this.initialized = true
      } catch (error) {
        this.clearAuthState()
        throw error
      } finally {
        this.loginPending = false
      }
    },
    async logout() {
      try {
        await logoutRequest(this.accessToken)
      } catch (error) {
        if (!(error instanceof ApiError) || error.status >= 500) {
          throw error
        }
      } finally {
        this.clearAuthState()
        this.initialized = true
      }
    },
  },
})

export function createTestingAuthStore(pinia: Pinia) {
  return useAuthStore(pinia)
}
