<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth.store'
import { usePermissionStore } from '@/stores/permission.store'
import { useQuotesPage } from '@/composables/useQuotesPage'
import { listSuppliers } from '@/api/suppliers.api'
import { listMaterials, listMaterialTypesLookup } from '@/api/materials.api'
import type { SupplierDomain } from '@/types/suppliers'
import type { MaterialDomain, MaterialTypeDomain } from '@/types/materials'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import DatePicker from 'primevue/datepicker'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import AdminLayout from '@/layouts/AdminLayout.vue'

const authStore = useAuthStore()
const permissionStore = usePermissionStore()
const router = useRouter()

const {
  items,
  total,
  isLoading,
  errorMsg,
  globalSearch,
  supplierId,
  materialId,
  materialTypeId,
  receivedDateStart,
  receivedDateEnd,
  deliveryMonth,
  purchased,
  limit,
  sortField,
  sortOrder,
  loadQuotesData,
  handlePageChange,
  handleSortChange,
  resetFilters,
} = useQuotesPage(authStore.accessToken)

// Dropdowns lookups data
const suppliersList = ref<SupplierDomain[]>([])
const materialsList = ref<MaterialDomain[]>([])
const materialTypesList = ref<MaterialTypeDomain[]>([])
const showAdvancedFilters = ref<boolean>(false)

const currencyOptions = [
  { label: 'Tất cả ngoại tệ', value: '' },
  { label: 'VND', value: 'VND' },
  { label: 'USD', value: 'USD' },
]

const purchasedOptions = [
  { label: 'Tất cả trạng thái chốt', value: null },
  { label: 'Đã chốt mua', value: true },
  { label: 'Chưa chốt mua', value: false },
]

const fetchLookups = async () => {
  try {
    const [suppRes, matRes, typeRes] = await Promise.all([
      listSuppliers({ limit: 100, offset: 0, sort_by: 'name', sort_order: 'asc' }, authStore.accessToken),
      listMaterials({ limit: 100, offset: 0, sort_by: 'name', sort_order: 'asc' }, authStore.accessToken),
      listMaterialTypesLookup(authStore.accessToken),
    ])
    suppliersList.value = suppRes.items
    materialsList.value = matRes.items
    materialTypesList.value = typeRes
  } catch (err) {
    console.error('Failed to load lookups', err)
  }
}

onMounted(() => {
  fetchLookups()
  loadQuotesData()
})

const hasCreatePermission = computed(() => {
  return permissionStore.can('quotes.create')
})

const goToNewQuote = () => {
  router.push('/quotes/new')
}

const onRowClick = (event: any) => {
  const quoteId = event.data.quoteId
  router.push(`/quotes/${quoteId}`)
}

// Utility formatting
const formatCurrency = (val: number, currency: string) => {
  if (val === null || val === undefined) return ''
  const formatted = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(val)
  return currency === 'USD' ? `$${formatted}` : `${formatted} ₫`
}

const formatVndPerKg = (val: number) => {
  if (val === null || val === undefined) return ''
  const formatted = new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(val)
  return `${formatted} VNĐ/KG`
}

const formatDate = (val: string) => {
  if (!val) return ''
  const dateObj = new Date(val)
  return new Intl.DateTimeFormat('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' }).format(dateObj)
}

const formatDeliveryMonth = (val: string) => {
  if (!val) return ''
  const dateObj = new Date(val)
  return `${String(dateObj.getMonth() + 1).padStart(2, '0')}/${dateObj.getFullYear()}`
}

import { computed } from 'vue'
</script>

<template>
  <AdminLayout section-label="Báo giá" title="Bảng báo giá">
    <div class="quotes-page">
      <!-- Header Actions and Filters -->
      <section class="quotes-page__header">
        <div class="quotes-page__filters">
          <label class="quotes-page__filter-field">
            <span class="quotes-page__filter-label">Tìm kiếm</span>
            <InputText
              v-model="globalSearch"
              placeholder="Nhà cung cấp, vật tư..."
              class="quotes-page__input-search"
              @keyup.enter="loadQuotesData"
            />
          </label>

          <label class="quotes-page__filter-field">
            <span class="quotes-page__filter-label">Nhà cung cấp</span>
            <Select
              v-model="supplierId"
              :options="suppliersList"
              optionLabel="name"
              optionValue="id"
              placeholder="Tất cả"
              class="quotes-page__supplier-filter"
              showClear
              @change="loadQuotesData"
            />
          </label>

          <label class="quotes-page__filter-field">
            <span class="quotes-page__filter-label">Vật tư</span>
            <Select
              v-model="materialId"
              :options="materialsList"
              optionLabel="name"
              optionValue="id"
              placeholder="Tất cả"
              class="quotes-page__material-filter"
              showClear
              @change="loadQuotesData"
            />
          </label>

          <div class="quotes-page__filter-button-group">
            <Button
              :label="showAdvancedFilters ? 'Ẩn bộ lọc phụ' : 'Lọc nâng cao'"
              :icon="showAdvancedFilters ? 'pi pi-chevron-up' : 'pi pi-chevron-down'"
              severity="secondary"
              outlined
              @click="showAdvancedFilters = !showAdvancedFilters"
            />
            <Button
              label="Lọc"
              icon="pi pi-filter"
              severity="primary"
              @click="loadQuotesData"
            />
            <Button
              icon="pi pi-sync"
              severity="secondary"
              outlined
              title="Xóa bộ lọc"
              @click="resetFilters"
            />
          </div>
        </div>

        <div class="quotes-page__actions">
          <Button
            v-if="hasCreatePermission"
            label="Nhập báo giá"
            icon="pi pi-plus"
            severity="primary"
            @click="goToNewQuote"
          />
        </div>
      </section>

      <!-- Advanced Filters Panel -->
      <section v-if="showAdvancedFilters" class="quotes-page__filter-advanced">
        <label class="quotes-page__filter-field">
          <span class="quotes-page__filter-label">Loại vật tư</span>
          <Select
            v-model="materialTypeId"
            :options="materialTypesList"
            optionLabel="name"
            optionValue="id"
            placeholder="Tất cả"
            showClear
            class="w-full"
            @change="loadQuotesData"
          />
        </label>

        <label class="quotes-page__filter-field">
          <span class="quotes-page__filter-label">Từ ngày nhận</span>
          <DatePicker
            v-model="receivedDateStart"
            dateFormat="yy-mm-dd"
            placeholder="YYYY-MM-DD"
            showIcon
            class="w-full"
            @update:modelValue="loadQuotesData"
          />
        </label>

        <label class="quotes-page__filter-field">
          <span class="quotes-page__filter-label">Đến ngày nhận</span>
          <DatePicker
            v-model="receivedDateEnd"
            dateFormat="yy-mm-dd"
            placeholder="YYYY-MM-DD"
            showIcon
            class="w-full"
            @update:modelValue="loadQuotesData"
          />
        </label>

        <label class="quotes-page__filter-field">
          <span class="quotes-page__filter-label">Tháng giao hàng</span>
          <DatePicker
            v-model="deliveryMonth"
            view="month"
            dateFormat="yy-mm"
            placeholder="YYYY-MM"
            showIcon
            class="w-full"
            @update:modelValue="loadQuotesData"
          />
        </label>

        <label class="quotes-page__filter-field">
          <span class="quotes-page__filter-label">Trạng thái chốt</span>
          <Select
            v-model="purchased"
            :options="purchasedOptions"
            optionLabel="label"
            optionValue="value"
            placeholder="Tất cả"
            class="w-full"
            @change="loadQuotesData"
          />
        </label>
      </section>

      <!-- General Error Alert -->
      <div v-if="errorMsg" class="p-message p-message-error">
        {{ errorMsg }}
      </div>

      <!-- Data Table -->
      <section class="quotes-page__table-wrapper">
        <DataTable
          :value="items"
          lazy
          paginator
          :rows="limit"
          :totalRecords="total"
          :loading="isLoading"
          :rowsPerPageOptions="[10, 20, 30, 50]"
          paginatorTemplate="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport RowsPerPageDropdown"
          currentPageReportTemplate="Hiển thị {first} đến {last} của {totalRecords} dòng"
          sortField="created_at"
          :sortOrder="-1"
          class="p-datatable-sm"
          :rowClass="() => 'quotes-page__row-clickable'"
          @page="handlePageChange"
          @sort="handleSortChange"
          @row-click="onRowClick"
        >
          <Column field="received_date" header="Ngày nhận" sortable>
            <template #body="{ data }">
              {{ formatDate(data.receivedDate) }}
            </template>
          </Column>

          <Column field="supplier_name" header="Nhà cung cấp" sortable>
            <template #body="{ data }">
              <span class="font-semibold">{{ data.supplierName }}</span>
            </template>
          </Column>

          <Column field="material_name" header="Vật tư" sortable>
            <template #body="{ data }">
              <span class="font-semibold">{{ data.materialName }}</span>
            </template>
          </Column>

          <Column field="price_original" header="Giá gốc" sortable>
            <template #body="{ data }">
              {{ formatCurrency(data.priceOriginal, data.currency) }} / {{ data.unit }}
            </template>
          </Column>

          <Column field="delivery_month" header="Kỳ giao hàng" sortable>
            <template #body="{ data }">
              {{ formatDeliveryMonth(data.deliveryMonth) }}
            </template>
          </Column>

          <Column field="price_converted_vnd_per_kg" header="Giá quy đổi" sortable>
            <template #body="{ data }">
              <span class="text-primary font-bold">{{ formatVndPerKg(data.priceConvertedVndPerKg) }}</span>
            </template>
          </Column>

          <Column field="purchased" header="Chốt mua">
            <template #body="{ data }">
              <span v-if="data.purchased" class="quotes-page__purchased-badge">
                <i class="pi pi-check-circle" /> Chốt mua
              </span>
              <span v-else class="text-xs text-gray-400 italic">Chưa chốt</span>
            </template>
          </Column>

          <Column field="version_number" header="Phiên bản" sortable>
            <template #body="{ data }">
              <span class="text-xs">Phiên bản #{{ data.versionNumber }}</span>
              <span class="block text-xs text-gray-400">bởi {{ data.createdByName || 'Hệ thống' }}</span>
            </template>
          </Column>

          <Column field="version_status" header="Trạng thái">
            <template #body="{ data }">
              <span :class="['quotes-page__status-badge', `status-${data.versionStatus}`]">
                {{ data.versionStatus === 'confirmed' ? 'Đã xác nhận' : 'Bản nháp' }}
              </span>
            </template>
          </Column>
        </DataTable>
      </section>
    </div>
  </AdminLayout>
</template>
