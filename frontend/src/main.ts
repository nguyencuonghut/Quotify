import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { setUnauthorizedHandler } from './api/http'
import { configurePrimeVue } from './plugins/primevue'
import { setupRouterGuards } from './router/guards'
import { router } from './router'
import { useAuthStore } from './stores/auth.store'
import { useThemeStore } from './stores/theme.store'
import './styles/main.scss'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
setupRouterGuards(router, pinia)
app.use(router)
configurePrimeVue(app)

const themeStore = useThemeStore(pinia)
themeStore.initialize()
const authStore = useAuthStore(pinia)

// Access token JWT hết hạn sau ACCESS_TOKEN_EXPIRE_MINUTES (mặc định 30
// phút) — nếu phiên làm việc kéo dài quá thời gian này mà không tải lại
// trang, mọi request tiếp theo sẽ nhận 401. Đăng ký handler này để apiRequest
// tự refresh lại token bằng refresh-token cookie và thử lại request, thay vì
// hiện thẳng lỗi "Invalid authentication credentials." từ backend lên UI.
setUnauthorizedHandler(async () => {
  const token = await authStore.ensureFreshAccessToken()
  if (!token) {
    router.push({
      name: 'login',
      query: { redirect: router.currentRoute.value.fullPath },
    })
  }
  return token
})

app.mount('#app')
