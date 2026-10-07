<template>
  <section
    :class="[
      'dashboard-page__panel',
      'material-freshness',
      { 'material-freshness--loading': isLoading },
    ]"
    :aria-busy="isLoading"
    aria-labelledby="material-freshness-title"
    data-testid="material-freshness"
  >
    <div class="dashboard-page__panel-header material-freshness__header">
      <div>
        <p class="dashboard-page__eyebrow">Độ mới của giá</p>
        <h3 id="material-freshness-title" class="dashboard-page__panel-title">
          Độ mới của giá theo vật tư
        </h3>
        <p v-if="data" class="material-freshness__period">
          Tuần {{ formatFreshnessDate(data.weekStart) }} đến
          {{ formatFreshnessDate(data.weekEnd) }}, tính đến
          {{ formatFreshnessDate(data.asOfDate) }}
        </p>
      </div>
    </div>

    <div class="material-freshness__filters">
      <label class="dashboard-page__filter-field material-freshness__search">
        <span class="dashboard-page__filter-label">Tìm kiếm</span>
        <InputText
          v-model="searchText"
          type="search"
          placeholder="Tìm vật tư, người nhập..."
          autocomplete="off"
          data-testid="freshness-search"
        />
      </label>
      <label class="dashboard-page__filter-field">
        <span class="dashboard-page__filter-label">Trạng thái</span>
        <Select
          v-model="statusFilter"
          :options="statusOptions"
          option-label="label"
          option-value="value"
          placeholder="Tất cả trạng thái"
          show-clear
        />
      </label>
      <label class="dashboard-page__filter-field">
        <span class="dashboard-page__filter-label">Loại vật tư</span>
        <Select
          v-model="typeFilter"
          filter
          filter-placeholder="Tìm loại vật tư..."
          :options="typeOptions"
          option-label="label"
          option-value="value"
          placeholder="Tất cả loại vật tư"
          show-clear
        />
      </label>
      <label class="dashboard-page__filter-field">
        <span class="dashboard-page__filter-label">Người nhập gần nhất</span>
        <Select
          v-model="entererFilter"
          filter
          filter-placeholder="Tìm người nhập..."
          :options="entererOptions"
          option-label="label"
          option-value="value"
          placeholder="Tất cả người nhập"
          show-clear
          data-testid="freshness-enterer-filter"
        />
      </label>
      <div
        class="material-freshness__sort"
        role="group"
        aria-label="Sắp xếp danh sách thẻ"
      >
        <Select
          :model-value="sortField"
          :options="sortOptions"
          option-label="label"
          option-value="value"
          placeholder="Sắp xếp theo..."
          aria-label="Sắp xếp theo"
          show-clear
          data-testid="freshness-sort-select"
          @update:model-value="
            (value) => onSort({ sortField: value, sortOrder })
          "
        />
        <Button
          :icon="
            sortOrder === -1 ? 'pi pi-sort-amount-down' : 'pi pi-sort-amount-up'
          "
          aria-label="Đảo chiều sắp xếp"
          :aria-pressed="sortOrder === -1 ? 'true' : 'false'"
          :title="sortOrder === -1 ? 'Đang giảm dần' : 'Đang tăng dần'"
          severity="secondary"
          outlined
          :disabled="!sortField"
          data-testid="freshness-sort-order"
          @click="onSort({ sortField, sortOrder: sortOrder === -1 ? 1 : -1 })"
        />
      </div>
    </div>

    <div
      v-if="summaryCards.length > 0"
      class="material-freshness__stats"
      aria-label="Chỉ số độ mới của giá"
    >
      <div
        v-for="card in summaryCards"
        :key="card.key"
        :class="[
          'dashboard-page__weekly-stat',
          `dashboard-page__weekly-stat--${card.tone}`,
        ]"
        :data-testid="`material-freshness-card-${card.key}`"
      >
        <i :class="card.icon" aria-hidden="true" />
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
        <small>{{ card.detail }}</small>
      </div>
    </div>

    <p
      v-if="errorMessage"
      class="material-freshness__state material-freshness__state--error"
      role="alert"
      data-testid="material-freshness-error"
    >
      {{ errorMessage }}
    </p>
    <p
      v-else-if="isLoading"
      class="material-freshness__state"
      role="status"
      data-testid="material-freshness-loading"
    >
      Đang tải độ mới của giá...
    </p>
    <p
      v-else-if="isEmpty"
      class="material-freshness__state"
      data-testid="material-freshness-empty"
    >
      Chưa có vật tư nào để hiển thị trong tuần này. Vật tư chỉ hiện khi có
      trong danh sách theo dõi hoặc có giá mới trong tuần.
    </p>
    <div
      v-else-if="hasNoMatches"
      class="material-freshness__state"
      data-testid="material-freshness-no-match"
    >
      <span>Không có vật tư nào khớp bộ lọc.</span>
      <Button
        label="Xóa bộ lọc"
        icon="pi pi-filter-slash"
        size="small"
        outlined
        severity="secondary"
        @click="resetFilters"
      />
    </div>

    <template v-if="!errorMessage && rows.length > 0">
      <div class="material-freshness__table-wrapper">
        <DataTable
          :value="rows"
          data-key="materialId"
          :loading="isLoading"
          :row-class="getRowClass"
          responsive-layout="scroll"
          size="small"
          lazy
          removable-sort
          :sort-field="sortField ?? undefined"
          :sort-order="sortOrder"
          @sort="onSort"
        >
          <Column header="Vật tư" sortable sort-field="name">
            <template #body="{ data: row }">
              <span class="material-freshness__name">{{
                row.materialName
              }}</span>
              <small class="material-freshness__code">{{
                row.materialCode
              }}</small>
            </template>
          </Column>
          <Column
            field="materialTypeName"
            header="Loại"
            sortable
            sort-field="type"
          />
          <Column
            field="updateCount"
            header="Số lần"
            sortable
            sort-field="updateCount"
          />
          <Column
            field="supplierCount"
            header="Số NCC"
            sortable
            sort-field="supplierCount"
          />
          <Column header="Nhận gần nhất" sortable sort-field="lastReceivedDate">
            <template #body="{ data: row }">
              {{ formatFreshnessDate(row.lastReceivedDate) }}
            </template>
          </Column>
          <Column header="Số ngày chưa có giá" sortable sort-field="ageDays">
            <template #body="{ data: row }">
              {{ formatFreshnessAge(row.ageDays) }}
            </template>
          </Column>
          <Column header="Chu kỳ" sortable sort-field="interval">
            <template #body="{ data: row }">
              {{ formatFreshnessInterval(row.expectedIntervalDays) }}
            </template>
          </Column>
          <Column header="Trạng thái" sortable sort-field="status">
            <template #body="{ data: row }">
              <Tag
                :severity="getFreshnessStatusSeverity(row.status)"
                :value="
                  MATERIAL_FRESHNESS_STATUS_LABELS[
                    row.status as MaterialFreshnessStatus
                  ]
                "
              />
            </template>
          </Column>
          <Column header="Người nhập gần nhất" sortable sort-field="enterer">
            <template #body="{ data: row }">
              {{ row.lastEntererLabel ?? '—' }}
            </template>
          </Column>
        </DataTable>
      </div>

      <div
        class="material-freshness__mobile-list"
        aria-label="Độ mới của giá trên mobile"
      >
        <article
          v-for="row in rows"
          :key="row.materialId"
          :class="['material-freshness__card', getRowClass(row)]"
          data-testid="material-freshness-mobile-item"
        >
          <div class="material-freshness__card-header">
            <div>
              <h4 class="material-freshness__card-title">
                {{ row.materialName }}
              </h4>
              <p class="material-freshness__card-subtitle">
                {{ row.materialCode }} · {{ row.materialTypeName }}
              </p>
            </div>
            <Tag
              :severity="getFreshnessStatusSeverity(row.status)"
              :value="MATERIAL_FRESHNESS_STATUS_LABELS[row.status]"
            />
          </div>
          <dl class="material-freshness__facts">
            <div>
              <dt>Số lần cập nhật</dt>
              <dd>{{ row.updateCount }} ({{ row.supplierCount }} NCC)</dd>
            </div>
            <div>
              <dt>Nhận gần nhất</dt>
              <dd>{{ formatFreshnessDate(row.lastReceivedDate) }}</dd>
            </div>
            <div>
              <dt>Số ngày chưa có giá</dt>
              <dd>{{ formatFreshnessAge(row.ageDays) }}</dd>
            </div>
            <div>
              <dt>Chu kỳ</dt>
              <dd>{{ formatFreshnessInterval(row.expectedIntervalDays) }}</dd>
            </div>
            <div>
              <dt>Người nhập gần nhất</dt>
              <dd>{{ row.lastEntererLabel ?? '—' }}</dd>
            </div>
          </dl>
        </article>
      </div>
    </template>

    <p class="material-freshness__note">
      Tính theo ngày nhận báo giá (khác bảng nhập báo giá phía trên, tính theo
      giờ nhập). Chỉ gồm vật tư đang theo dõi và vật tư có giá mới trong tuần.
      <RouterLink
        v-if="canConfigure"
        class="material-freshness__link"
        to="/price-alert-settings"
        data-testid="settings-link"
      >
        Quản lý danh sách theo dõi
      </RouterLink>
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { RouterLink } from 'vue-router'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Tag from 'primevue/tag'

import {
  MATERIAL_FRESHNESS_STATUS_LABELS,
  formatFreshnessAge,
  formatFreshnessDate,
  formatFreshnessInterval,
  getFreshnessStatusSeverity,
} from '@/api/material-freshness.mappers'
import { useMaterialFreshness } from '@/composables/useMaterialFreshness'
import { usePermissionStore } from '@/stores/permission.store'
import type {
  MaterialFreshnessItem,
  MaterialFreshnessStatus,
} from '@/types/material-freshness'

// `weekStart` là tuần đã áp dụng của bảng nhập báo giá theo tuần ở trên; `reloadToken` tăng mỗi
// khi trang tải lại bảng đó (mở trang, "Lọc", "Xóa lọc") để bảng này đi cùng. Token 0 nghĩa là
// trang chưa bắt đầu lần tải đầu, nên chưa gọi API.
const props = defineProps<{
  weekStart: string | null
  reloadToken: number
}>()

const {
  data,
  rows,
  isLoading,
  errorMessage,
  statusFilter,
  typeFilter,
  entererFilter,
  searchText,
  sortField,
  sortOrder,
  sortOptions,
  entererOptions,
  onSort,
  statusOptions,
  typeOptions,
  isEmpty,
  hasNoMatches,
  summaryCards,
  load,
  resetFilters,
} = useMaterialFreshness()

const permissionStore = usePermissionStore()
const canConfigure = computed(() => permissionStore.can('price_alerts.manage'))

watch(
  () => [props.weekStart, props.reloadToken] as const,
  ([weekStart, reloadToken]) => {
    if (reloadToken > 0) {
      void load(weekStart)
    }
  },
  { immediate: true },
)

function getRowClass(row: MaterialFreshnessItem): string {
  return row.status === 'overdue' || row.status === 'never'
    ? 'material-freshness__row--attention'
    : ''
}
</script>
