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

      <section class="dashboard-page__panel dashboard-page__weekly-panel">
        <div class="dashboard-page__panel-header dashboard-page__weekly-header">
          <div>
            <p class="dashboard-page__eyebrow">Nhập báo giá</p>
            <h3 class="dashboard-page__panel-title">
              Tình hình nhập báo giá theo tuần
            </h3>
          </div>

          <div class="dashboard-page__weekly-filters">
            <label class="dashboard-page__filter-field">
              <span class="dashboard-page__filter-label">Tuần</span>
              <DatePicker
                v-model="selectedWeek"
                date-format="dd/mm/yy"
                placeholder="Chọn tuần"
                show-icon
              />
            </label>

            <label class="dashboard-page__filter-field">
              <span class="dashboard-page__filter-label">Người nhập</span>
              <Select
                v-model="selectedWeeklyUserId"
                filter
                filter-placeholder="Tìm người nhập..."
                :options="weeklyUserOptions"
                option-label="label"
                option-value="value"
                placeholder="Tất cả người nhập"
                show-clear
              />
            </label>

            <div class="dashboard-page__filter-actions">
              <Button
                icon="pi pi-filter"
                label="Lọc"
                :loading="isLoadingWeeklyEntry"
                @click="applyWeeklyEntryFilters"
              />
              <Button
                icon="pi pi-refresh"
                label="Xóa lọc"
                outlined
                severity="secondary"
                @click="resetWeeklyEntryFilters"
              />
            </div>
          </div>
        </div>

        <div class="dashboard-page__weekly-stats" aria-label="Chỉ số nhập báo giá theo tuần">
          <div
            v-for="card in weeklyEntryMetricCards"
            :key="card.label"
            :class="[
              'dashboard-page__weekly-stat',
              `dashboard-page__weekly-stat--${card.tone}`,
            ]"
          >
            <i :class="card.icon" aria-hidden="true" />
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <small>{{ card.detail }}</small>
          </div>
        </div>

        <div class="dashboard-page__weekly-grid">
          <div>
            <div class="dashboard-page__subheader">
              <span>Số phiếu báo giá theo user</span>
              <Tag
                :severity="weeklyWarningUsers.length > 0 ? 'warning' : 'success'"
                :value="
                  weeklyWarningUsers.length > 0
                    ? `${weeklyWarningUsers.length} user chưa nhập`
                    : 'Đủ dữ liệu'
                "
              />
            </div>
            <div v-if="hasWeeklyEntryData" class="dashboard-page__chart-frame">
              <Chart
                class="dashboard-page__weekly-chart"
                type="bar"
                :data="weeklyEntryChartData"
                :options="weeklyEntryChartOptions"
              />
            </div>
            <div v-else class="dashboard-page__empty">
              <i class="pi pi-users" aria-hidden="true" />
              <span>Chưa có người dùng active để thống kê.</span>
            </div>
          </div>

          <DataTable
            :value="weeklyUserActivities"
            data-key="userId"
            :row-class="getWeeklyEntryRowClass"
            responsive-layout="scroll"
            size="small"
          >
            <Column field="userLabel" header="Người nhập" />
            <Column field="quoteCount" header="Số phiếu" />
            <Column header="Lần nhập gần nhất">
              <template #body="{ data }">
                {{ formatDateTimeLabel(data.lastQuoteCreatedAt) }}
              </template>
            </Column>
            <Column header="Trạng thái">
              <template #body="{ data }">
                <Tag
                  :severity="data.hasWarning ? 'warning' : 'success'"
                  :value="data.hasWarning ? 'Chưa nhập' : 'Đã nhập'"
                />
              </template>
            </Column>
            <template #empty>
              <span class="dashboard-page__table-empty">
                Chưa có dữ liệu người nhập.
              </span>
            </template>
          </DataTable>
        </div>
      </section>

      <section class="dashboard-page__panel dashboard-page__panel--chart">
        <div class="dashboard-page__panel-header">
          <div>
            <p class="dashboard-page__eyebrow">Kỳ hàng về</p>
            <h3 class="dashboard-page__panel-title">Giá theo kỳ hàng về</h3>
          </div>
          <Tag
            :severity="hasTrendData ? 'success' : 'secondary'"
            :value="hasTrendData ? `${deliveryMonthBuckets.length} tháng` : 'Chưa có dữ liệu'"
          />
        </div>

        <div class="dashboard-page__filters">
          <label class="dashboard-page__filter-field">
            <span class="dashboard-page__filter-label">Vật tư</span>
            <Select
              v-model="selectedMaterialId"
              filter
              filter-placeholder="Tìm vật tư..."
              :loading="isLoadingLookups"
              :options="materials"
              option-label="name"
              option-value="id"
              placeholder="Tất cả vật tư"
              show-clear
            />
          </label>

          <label class="dashboard-page__filter-field">
            <span class="dashboard-page__filter-label">Kỳ giao hàng (bắt buộc chọn)</span>
            <DatePicker
              v-model="deliveryMonth"
              date-format="mm/yy"
              placeholder="mm/yyyy"
              show-icon
              view="month"
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
        </div>

        <label
          class="dashboard-page__comparison-band-toggle dashboard-page__cnf-toggle"
        >
          <Checkbox v-model="showCnfOnly" binary />
          <span>Giá CNF (chỉ tính báo giá USD/MT, trục Y hiện giá USD)</span>
        </label>

        <div v-if="errorMessage" class="dashboard-page__message" role="alert">
          <i class="pi pi-exclamation-triangle" aria-hidden="true" />
          <span>{{ errorMessage }}</span>
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

      <section class="dashboard-page__panel dashboard-page__panel--chart">
        <div class="dashboard-page__panel-header">
          <div>
            <p class="dashboard-page__eyebrow">So sánh mặt hàng</p>
            <h3 class="dashboard-page__panel-title">So sánh giá nguyên liệu theo kỳ hàng về</h3>
          </div>
        </div>

        <label class="dashboard-page__filter-field">
          <span class="dashboard-page__filter-label">Chọn 2-3 mặt hàng để so sánh</span>
          <MultiSelect
            v-model="comparisonMaterialIds"
            display="chip"
            filter
            filter-placeholder="Tìm vật tư..."
            :loading="isLoadingLookups"
            :options="materials"
            option-label="name"
            option-value="id"
            placeholder="Chọn vật tư"
            :selection-limit="3"
            @update:model-value="loadMaterialComparison"
          >
            <template #option="{ option }">{{ option.name }} ({{ option.code }})</template>
          </MultiSelect>
        </label>

        <div v-if="comparisonTrendResults.length > 0" class="dashboard-page__comparison-bands">
          <label
            v-for="result in comparisonTrendResults"
            :key="result.materialId"
            class="dashboard-page__comparison-band-toggle"
          >
            <Checkbox v-model="comparisonBandVisibility[result.materialId]" binary />
            <span>Hiện khoảng giá thấp-cao: {{ result.materialName }}</span>
          </label>
        </div>

        <div v-if="comparisonBuckets.length > 0" class="dashboard-page__chart-frame">
          <Chart
            class="dashboard-page__chart"
            type="line"
            :data="comparisonChartData"
            :options="comparisonChartOptions"
          />
        </div>
        <div v-else class="dashboard-page__empty">
          <i class="pi pi-chart-line" aria-hidden="true" />
          <span v-if="comparisonMaterialIds.length < 2">
            Chọn ít nhất 2 mặt hàng để xem so sánh giá.
          </span>
          <span v-else>
            Không có dữ liệu báo giá cho các mặt hàng đã chọn phù hợp với bộ lọc hiện tại.
          </span>
        </div>
      </section>

      <section class="dashboard-page__panel dashboard-page__panel--chart">
        <div class="dashboard-page__panel-header">
          <div>
            <p class="dashboard-page__eyebrow">Diễn biến giá</p>
            <h3 class="dashboard-page__panel-title">Diễn biến giá theo thời gian chào giá</h3>
          </div>
        </div>

        <div class="dashboard-page__history-filters">
          <label class="dashboard-page__filter-field">
            <span class="dashboard-page__filter-label">Kỳ giao hàng (bắt buộc chọn)</span>
            <DatePicker
              v-model="historyDeliveryMonth"
              date-format="mm/yy"
              placeholder="mm/yyyy"
              show-icon
              view="month"
              @update:model-value="loadPriceHistory"
            />
          </label>

          <label class="dashboard-page__filter-field">
            <span class="dashboard-page__filter-label">Chọn 2-3 mặt hàng để so sánh</span>
            <MultiSelect
              v-model="historyMaterialIds"
              display="chip"
              filter
              filter-placeholder="Tìm vật tư..."
              :loading="isLoadingLookups"
              :options="materials"
              option-label="name"
              option-value="id"
              placeholder="Chọn vật tư"
              :selection-limit="3"
              @update:model-value="loadPriceHistory"
            >
              <template #option="{ option }">{{ option.name }} ({{ option.code }})</template>
            </MultiSelect>
          </label>
        </div>

        <label class="dashboard-page__comparison-band-toggle dashboard-page__cnf-toggle">
          <Checkbox v-model="historyShowCnfOnly" binary />
          <span>Giá CNF (chỉ tính báo giá USD/MT, trục Y hiện giá USD)</span>
        </label>

        <div v-if="historyTrendResults.length > 0" class="dashboard-page__comparison-bands">
          <label
            v-for="result in historyTrendResults"
            :key="result.materialId"
            class="dashboard-page__comparison-band-toggle"
          >
            <Checkbox v-model="historyBandVisibility[result.materialId]" binary />
            <span>Hiện khoảng giá thấp-cao: {{ result.materialName }}</span>
          </label>
        </div>

        <div v-if="historyBuckets.length > 0" class="dashboard-page__chart-frame">
          <Chart
            class="dashboard-page__chart"
            type="line"
            :data="historyChartData"
            :options="historyChartOptions"
          />
        </div>
        <div v-else class="dashboard-page__empty">
          <i class="pi pi-chart-line" aria-hidden="true" />
          <span v-if="!historyDeliveryMonth || historyMaterialIds.length < 2">
            Chọn kỳ giao hàng và ít nhất 2 mặt hàng để xem diễn biến giá.
          </span>
          <span v-else>
            Không có dữ liệu báo giá cho các mặt hàng đã chọn ở kỳ giao hàng này.
          </span>
        </div>
      </section>

      <section class="dashboard-page__panel dashboard-page__panel--chart">
        <div class="dashboard-page__panel-header">
          <div>
            <p class="dashboard-page__eyebrow">So sánh mùa vụ</p>
            <h3 class="dashboard-page__panel-title">So sánh giá theo mùa vụ qua các năm</h3>
          </div>
        </div>

        <div class="dashboard-page__history-filters">
          <label class="dashboard-page__filter-field">
            <span class="dashboard-page__filter-label">Nguyên liệu (bắt buộc chọn)</span>
            <Select
              v-model="seasonalMaterialId"
              filter
              filter-placeholder="Tìm vật tư..."
              :loading="isLoadingLookups"
              :options="materials"
              option-label="name"
              option-value="id"
              placeholder="Chọn vật tư"
              show-clear
              @update:model-value="loadSeasonalComparison"
            >
              <template #option="{ option }">{{ option.name }} ({{ option.code }})</template>
            </Select>
          </label>

          <label class="dashboard-page__filter-field">
            <span class="dashboard-page__filter-label">Tháng hàng về (bắt buộc chọn)</span>
            <Select
              v-model="seasonalMonth"
              :options="seasonalMonthOptions"
              placeholder="Chọn tháng"
              show-clear
              @update:model-value="loadSeasonalComparison"
            >
              <template #option="{ option }">Tháng {{ option }}</template>
              <template #value="{ value }">{{ value ? `Tháng ${value}` : 'Chọn tháng' }}</template>
            </Select>
          </label>

          <label class="dashboard-page__filter-field">
            <span class="dashboard-page__filter-label">Chọn 2-5 năm để so sánh</span>
            <MultiSelect
              v-model="seasonalYears"
              display="chip"
              :options="seasonalAvailableYears"
              placeholder="Chọn năm"
              :selection-limit="5"
              @update:model-value="loadSeasonalComparison"
            />
          </label>
        </div>

        <label class="dashboard-page__comparison-band-toggle dashboard-page__cnf-toggle">
          <Checkbox v-model="seasonalShowCnfOnly" binary />
          <span>Giá CNF (chỉ tính báo giá USD/MT, trục Y hiện giá USD)</span>
        </label>

        <div v-if="seasonalTrendResults.length > 0" class="dashboard-page__comparison-bands">
          <label
            v-for="result in seasonalTrendResults"
            :key="result.materialId"
            class="dashboard-page__comparison-band-toggle"
          >
            <Checkbox v-model="seasonalBandVisibility[result.materialId]" binary />
            <span>Hiện khoảng giá thấp-cao: {{ result.materialName }}</span>
          </label>
        </div>

        <div v-if="seasonalBuckets.length > 0" class="dashboard-page__chart-frame">
          <Chart
            class="dashboard-page__chart"
            type="line"
            :data="seasonalChartData"
            :options="seasonalChartOptions"
          />
        </div>
        <div v-else class="dashboard-page__empty">
          <i class="pi pi-chart-line" aria-hidden="true" />
          <span v-if="!seasonalMaterialId || !seasonalMonth || seasonalYears.length < 2">
            Chọn nguyên liệu, tháng hàng về và ít nhất 2 năm để so sánh.
          </span>
          <span v-else>
            Không có dữ liệu báo giá cho nguyên liệu này ở tháng hàng về đã chọn.
          </span>
        </div>
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
import Checkbox from 'primevue/checkbox'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import DatePicker from 'primevue/datepicker'
import MultiSelect from 'primevue/multiselect'
import Select from 'primevue/select'
import Tag from 'primevue/tag'

import { useDashboardPage } from '@/composables/useDashboardPage'
import AdminLayout from '@/layouts/AdminLayout.vue'

const {
  materials,
  isLoading,
  isLoadingWeeklyEntry,
  isLoadingLookups,
  errorMessage,
  selectedMaterialId,
  deliveryMonth,
  receivedDateStart,
  receivedDateEnd,
  showCnfOnly,
  selectedWeek,
  selectedWeeklyUserId,
  comparisonMaterialIds,
  comparisonBuckets,
  comparisonBandVisibility,
  comparisonTrendResults,
  comparisonChartData,
  comparisonChartOptions,
  historyDeliveryMonth,
  historyMaterialIds,
  historyBuckets,
  historyBandVisibility,
  historyTrendResults,
  historyShowCnfOnly,
  historyChartData,
  historyChartOptions,
  loadPriceHistory,
  seasonalMaterialId,
  seasonalMonth,
  seasonalYears,
  seasonalAvailableYears,
  seasonalBuckets,
  seasonalBandVisibility,
  seasonalTrendResults,
  seasonalShowCnfOnly,
  seasonalChartData,
  seasonalChartOptions,
  loadSeasonalComparison,
  loadMaterialComparison,
  weeklyUserOptions,
  weeklyUserActivities,
  weeklyWarningUsers,
  weeklyEntryMetricCards,
  deliveryMonthBuckets,
  purchaseContexts,
  hasTrendData,
  hasWeeklyEntryData,
  chartData,
  chartOptions,
  weeklyEntryChartData,
  weeklyEntryChartOptions,
  bootstrap,
  applyFilters,
  resetFilters,
  applyWeeklyEntryFilters,
  resetWeeklyEntryFilters,
  getWeeklyEntryRowClass,
  formatMoney,
  formatDateLabel,
  formatDateTimeLabel,
  formatMonthLabel,
} = useDashboardPage()

const seasonalMonthOptions = Array.from({ length: 12 }, (_, index) => index + 1)

onMounted(() => {
  bootstrap()
})
</script>
