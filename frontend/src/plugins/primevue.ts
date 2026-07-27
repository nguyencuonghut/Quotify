import type { App } from 'vue'

import { definePreset } from '@primeuix/themes'
import Aura from '@primeuix/themes/aura'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'

const FastApiVuePreset = definePreset(Aura, {
  semantic: {
    primary: {
      50: '#eef2ff',
      100: '#e0e7ff',
      200: '#c7d2fe',
      300: '#a5b4fc',
      400: '#818cf8',
      500: '#6366f1',
      600: '#4f46e5',
      700: '#4338ca',
      800: '#3730a3',
      900: '#312e81',
      950: '#1e1b4b',
    },
  },
})

export function configurePrimeVue(app: App<Element>) {
  app.use(PrimeVue, {
    ripple: true,
    theme: {
      preset: FastApiVuePreset,
      options: {
        darkModeSelector: '.app-dark',
      },
    },
  })
  app.use(ToastService)
}
