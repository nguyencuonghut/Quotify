<template>
  <AdminLayout section-label="Phân tích báo giá" title="Bảng điều khiển">
    <div class="dashboard-page">
      <section class="dashboard-page__hero">
        <div>
          <p class="dashboard-page__eyebrow">Dashboard Quotify</p>
          <h2 class="dashboard-page__headline">
            Phân tích giá quy đổi VNĐ/KG theo dữ liệu báo giá đã xác nhận.
          </h2>
          <p class="dashboard-page__lead">
            Theo dõi MIN, MAX, TRUNG BÌNH và các điểm đã chốt mua theo vật tư,
            kỳ hàng về, loại nhà cung cấp và khoảng thời gian nhận báo giá.
          </p>
        </div>
      </section>

      <section class="dashboard-page__filters">
        <label class="dashboard-page__filter-field">
          <span class="dashboard-page__filter-label">Vật tư</span>
          <Select
            v-model="selectedMaterialId"
            :loading="isLoadingLookups"
            :options="materials"
            option-label="name"
            option-value="id"
            placeholder="Tất cả vật tư"
            show-clear
          />
        </label>

        <label class="dashboard-page__filter-field">
          <span class="dashboard-page__filter-label">Kỳ giao hàng</span>
          <DatePicker
            v-model="deliveryMonth"
            date-format="mm/yy"
            placeholder="mm/yyyy"
            show-icon
            view="month"
          />
        </label>

        <label class="dashboard-page__filter-field">
          <span class="dashboard-page__filter-label">Loại NCC</span>
          <Select
            v-model="selectedSupplierType"
            :options="supplierTypeOptions"
            option-label="label"
            option-value="value"
            placeholder="Tất cả loại NCC"
            show-clear
          />
        </label>

        <label class="dashboard-page__filter-field">
          <span class="dashboard-page__filter-label">Từ ngày nhận</span>
          <DatePicker
            v-model="receivedDateStart"
            date-format="dd/mm/yy"
            placeholder="dd/mm/yyyy"
            show-icon
          />
        </label>

        <label class="dashboard-page__filter-field">
          <span class="dashboard-page__filter-label">Đến ngày nhận</span>
          <DatePicker
            v-model="receivedDateEnd"
            date-format="dd/mm/yy"
            placeholder="dd/mm/yyyy"
            show-icon
          />
        </label>

        <div class="dashboard-page__filter-actions">
          <Button
            icon="pi pi-filter"
            label="Lọc"
            :loading="isLoading"
            @click="applyFilters"
          />
          <Button
            icon="pi pi-refresh"
            label="Xóa lọc"
            outlined
            severity="secondary"
            @click="resetFilters"
          />
        </div>
      </section>

      <div v-if="errorMessage" class="dashboard-page__message" role="alert">
        <i class="pi pi-exclamation-triangle" aria-hidden="true" />
        <span>{{ errorMessage }}</span>
      </div>

      <section class="dashboard-page__metrics" aria-label="Chỉ số giá">
        <article
          v-for="card in metricCards"
          :key="card.label"
          :class="[
            'dashboard-page__metric-card',
            `dashboard-page__metric-card--${card.tone}`,
          ]"
        >
          <div class="dashboard-page__metric-icon">
            <i :class="card.icon" aria-hidden="true" />
          </div>
          <div>
            <span class="dashboard-page__metric-label">{{ card.label }}</span>
            <strong class="dashboard-page__metric-value">{{ card.value }}</strong>
            <span class="dashboard-page__metric-detail">{{ card.detail }}</span>
          </div>
        </article>
      </section>

      <section class="dashboard-page__analysis-grid">
        <section class="dashboard-page__panel dashboard-page__panel--chart">
          <div class="dashboard-page__panel-header">
            <div>
              <p class="dashboard-page__eyebrow">Kỳ hàng về</p>
              <h3 class="dashboard-page__panel-title">Giá theo kỳ hàng về</h3>
            </div>
            <Tag
              :severity="hasTrendData ? 'success' : 'secondary'"
              :value="hasTrendData ? `${deliveryMonthBuckets.length} kỳ` : 'Chưa có dữ liệu'"
            />
          </div>

          <div v-if="hasTrendData" class="dashboard-page__chart-frame">
            <Chart
              class="dashboard-page__chart"
              type="line"
              :data="chartData"
              :options="chartOptions"
            />
          </div>
          <div v-else class="dashboard-page__empty">
            <i class="pi pi-chart-line" aria-hidden="true" />
            <span>Chưa có dữ liệu phù hợp với bộ lọc hiện tại.</span>
          </div>
        </section>

        <section class="dashboard-page__panel">
          <div class="dashboard-page__panel-header">
            <div>
              <p class="dashboard-page__eyebrow">Người nhập</p>
              <h3 class="dashboard-page__panel-title">Số phiếu báo giá</h3>
            </div>
          </div>

          <DataTable
            :value="userKpis"
            data-key="userLabel"
            responsive-layout="scroll"
            size="small"
          >
            <Column field="userLabel" header="Người dùng" />
            <Column field="quoteCount" header="Số phiếu" />
            <template #empty>
              <span class="dashboard-page__table-empty">Chưa có dữ liệu.</span>
            </template>
          </DataTable>
        </section>
      </section>

      <section class="dashboard-page__panel">
        <div class="dashboard-page__panel-header">
          <div>
            <p class="dashboard-page__eyebrow">Chốt mua</p>
            <h3 class="dashboard-page__panel-title">Góc nhìn tại và sau thời điểm đánh dấu</h3>
          </div>
        </div>

        <DataTable
          :value="purchaseContexts"
          data-key="purchasedLineId"
          responsive-layout="scroll"
          size="small"
        >
          <Column header="Kỳ giao hàng">
            <template #body="{ data }">
              {{ formatMonthLabel(data.deliveryMonth) }}
            </template>
          </Column>
          <Column header="Đánh dấu lúc">
            <template #body="{ data }">
              {{ formatDateLabel(data.purchaseMarkedAt.slice(0, 10)) }}
            </template>
          </Column>
          <Column header="Tại thời điểm chốt">
            <template #body="{ data }">
              {{ formatMoney(data.atPurchase.avgPrice) }}
            </template>
          </Column>
          <Column header="Sau thời điểm chốt">
            <template #body="{ data }">
              {{ formatMoney(data.afterPurchase.avgPrice) }}
            </template>
          </Column>
          <template #empty>
            <span class="dashboard-page__table-empty">
              Chưa có dòng nào được đánh dấu chốt mua.
            </span>
          </template>
        </DataTable>
      </section>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import Button from 'primevue/button'
import Chart from 'primevue/chart'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import DatePicker from 'primevue/datepicker'
import Select from 'primevue/select'
import Tag from 'primevue/tag'

import { useDashboardPage } from '@/composables/useDashboardPage'
import AdminLayout from '@/layouts/AdminLayout.vue'

const {
  materials,
  supplierTypeOptions,
  isLoading,
  isLoadingLookups,
  errorMessage,
  selectedMaterialId,
  selectedSupplierType,
  deliveryMonth,
  receivedDateStart,
  receivedDateEnd,
  metricCards,
  userKpis,
  deliveryMonthBuckets,
  purchaseContexts,
  hasTrendData,
  chartData,
  chartOptions,
  bootstrap,
  applyFilters,
  resetFilters,
  formatMoney,
  formatDateLabel,
  formatMonthLabel,
} = useDashboardPage()

onMounted(() => {
  bootstrap()
})
</script>
