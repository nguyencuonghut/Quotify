import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
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
useAuthStore(pinia)

app.mount('#app')
