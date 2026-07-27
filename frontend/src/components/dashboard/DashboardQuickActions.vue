<template>
  <Card class="dashboard-actions">
    <template #title>
      <div class="dashboard-actions__title-row">
        <div>
          <p class="dashboard-actions__eyebrow">Thao tác nhanh</p>
          <h3 class="dashboard-actions__title">Mở phân hệ</h3>
        </div>
      </div>
    </template>

    <template #content>
      <div class="dashboard-actions__list">
        <RouterLink
          v-for="action in actions"
          :key="action.to"
          class="dashboard-actions__item"
          :to="action.to"
        >
          <span class="dashboard-actions__icon" aria-hidden="true">
            <i :class="action.icon" />
          </span>
          <span class="dashboard-actions__copy">
            <span class="dashboard-actions__label">{{ action.label }}</span>
            <span class="dashboard-actions__description">
              {{ action.description }}
            </span>
          </span>
          <i class="pi pi-arrow-right dashboard-actions__arrow" />
        </RouterLink>
      </div>
    </template>
  </Card>
</template>

<script setup lang="ts">
import Card from 'primevue/card'
import { RouterLink } from 'vue-router'

import type { DashboardAction } from '@/types/dashboard'

defineProps<{
  actions: DashboardAction[]
}>()
</script>
