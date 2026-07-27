<template>
  <section class="health-table">
    <div class="health-table__header">
      <div>
        <p class="health-table__eyebrow">Phân hệ</p>
        <h3 class="health-table__title">Trạng thái vận hành</h3>
      </div>
      <Tag severity="contrast" value="Tổng quan" />
    </div>

    <DataTable
      :rows="10"
      :value="rows"
      data-key="id"
      paginator
      current-page-report-template="Hiển thị từ {first} đến {last} trên tổng số {totalRecords} dòng"
      :rows-per-page-options="[10, 20, 30, 50]"
      paginator-template="RowsPerPageDropdown FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport"
      responsive-layout="scroll"
    >
      <Column field="domain" header="Phân hệ" />
      <Column field="mode" header="Phạm vi" />
      <Column header="Trạng thái">
        <template #body="{ data }">
          <Tag :severity="statusSeverity(data.status)" :value="data.status" />
        </template>
      </Column>
      <Column field="note" header="Ghi chú" />
    </DataTable>
  </section>
</template>

<script setup lang="ts">
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Tag from 'primevue/tag'

import type { HealthRow } from '@/types/dashboard'

defineProps<{
  rows: HealthRow[]
}>()

const tagSeverityMap = {
  'Đang dùng': 'success',
  'Sẵn sàng': 'info',
  'Theo dõi': 'warn',
} as const

function statusSeverity(status: HealthRow['status']) {
  return tagSeverityMap[status]
}
</script>
