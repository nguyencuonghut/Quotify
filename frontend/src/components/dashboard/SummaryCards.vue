<template>
  <section class="summary-grid">
    <Card v-for="card in cards" :key="card.title" class="summary-grid__card">
      <template #title>
        <div class="summary-grid__title-row">
          <span>{{ card.title }}</span>
          <Tag :severity="severityMap[card.tone]" :value="card.value" />
        </div>
      </template>
      <template #content>
        <p class="summary-grid__detail">{{ card.detail }}</p>
      </template>
    </Card>
  </section>
</template>

<script setup lang="ts">
import Card from 'primevue/card'
import Tag from 'primevue/tag'

import type { SummaryCard } from '@/types/dashboard'

defineProps<{
  cards: SummaryCard[]
}>()

const severityMap = {
  info: 'info',
  success: 'success',
  warn: 'warn',
} as const
</script>
