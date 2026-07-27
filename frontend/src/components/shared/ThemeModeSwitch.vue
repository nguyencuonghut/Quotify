<template>
  <Button
    :aria-label="
      themeStore.isDark ? 'Switch to light mode' : 'Switch to dark mode'
    "
    :icon="themeStore.isDark ? 'pi pi-sun' : 'pi pi-moon'"
    class="theme-switch"
    rounded
    severity="secondary"
    text
    type="button"
    @click="themeStore.toggleMode"
  />
</template>

<script setup lang="ts">
import Button from 'primevue/button'

import { useThemeStore } from '@/stores/theme.store'

const themeStore = useThemeStore()
</script>
