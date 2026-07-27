<template>
  <AdminLayout section-label="Tổng quan hệ thống" title="Bảng điều khiển">
    <div class="dashboard-page">
      <section class="dashboard-page__hero">
        <div>
          <p class="dashboard-page__eyebrow">Tổng quan vận hành</p>
          <h2 class="dashboard-page__headline">
            Theo dõi nhanh các phân hệ quản trị đang sử dụng.
          </h2>
          <p class="dashboard-page__lead">
            Dashboard tập trung vào tài khoản, phân quyền, tệp tin, sao lưu và
            nhật ký audit để quản trị viên nắm trạng thái hệ thống trước khi đi
            vào từng màn hình chi tiết.
          </p>
        </div>
        <Tag severity="success" value="Đang hoạt động" />
      </section>

      <SummaryCards :cards="summaryCards" />

      <section class="dashboard-page__body">
        <DashboardQuickActions :actions="visibleActions" />
        <HealthSnapshotTable :rows="moduleRows" />
      </section>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import Tag from 'primevue/tag'

import DashboardQuickActions from '@/components/dashboard/DashboardQuickActions.vue'
import HealthSnapshotTable from '@/components/dashboard/HealthSnapshotTable.vue'
import SummaryCards from '@/components/dashboard/SummaryCards.vue'
import { useDashboardPage } from '@/composables/useDashboardPage'
import AdminLayout from '@/layouts/AdminLayout.vue'

const { moduleRows, summaryCards, visibleActions } = useDashboardPage()
</script>
