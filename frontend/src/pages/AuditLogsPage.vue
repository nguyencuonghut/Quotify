<template>
  <AdminLayout section-label="Quản trị hệ thống" title="Nhật ký audit">
    <div class="audit-logs-page">
      <section class="audit-logs-page__header">
        <div class="audit-logs-page__filters">
          <label class="audit-logs-page__filter-field">
            <span class="audit-logs-page__filter-label">Hoạt động</span>
            <Select
              v-model="filters.action"
              :options="actionFilterOptions"
              class="audit-logs-page__filter-input"
              filter
              filter-placeholder="Tìm hoạt động"
              option-label="label"
              option-value="value"
              placeholder="Tất cả hoạt động"
              show-clear
            />
          </label>

          <label class="audit-logs-page__filter-field">
            <span class="audit-logs-page__filter-label">Đối tượng</span>
            <Select
              v-model="filters.entityType"
              :options="entityTypeFilterOptions"
              class="audit-logs-page__filter-input"
              filter
              filter-placeholder="Tìm đối tượng"
              option-label="label"
              option-value="value"
              placeholder="Tất cả đối tượng"
              show-clear
            />
          </label>

          <label class="audit-logs-page__filter-field">
            <span class="audit-logs-page__filter-label">Từ ngày</span>
            <InputText
              v-model="filters.createdFrom"
              type="date"
              class="audit-logs-page__date-input"
            />
          </label>

          <label class="audit-logs-page__filter-field">
            <span class="audit-logs-page__filter-label">Đến ngày</span>
            <InputText
              v-model="filters.createdTo"
              type="date"
              class="audit-logs-page__date-input"
            />
          </label>
        </div>

        <div class="audit-logs-page__actions">
          <Button
            :label="
              advancedFiltersVisible
                ? 'Ẩn bộ lọc nâng cao'
                : 'Bộ lọc nâng cao'
            "
            icon="pi pi-sliders-h"
            severity="secondary"
            outlined
            class="audit-logs-page__action-btn"
            @click="advancedFiltersVisible = !advancedFiltersVisible"
          />
          <Button
            label="Lọc"
            icon="pi pi-search"
            class="audit-logs-page__action-btn"
            @click="applyFilters"
          />
          <Button
            label="Xóa lọc"
            icon="pi pi-filter-slash"
            severity="secondary"
            outlined
            class="audit-logs-page__action-btn"
            @click="clearFilters"
          />
          <Button
            aria-label="Tải lại nhật ký audit"
            icon="pi pi-refresh"
            severity="secondary"
            outlined
            class="audit-logs-page__icon-btn"
            @click="fetchAuditLogs"
          />
        </div>

        <div
          v-if="advancedFiltersVisible"
          class="audit-logs-page__advanced-filters"
        >
          <label class="audit-logs-page__filter-field">
            <span class="audit-logs-page__filter-label">ID người thao tác</span>
            <InputText
              v-model="filters.actorUserId"
              placeholder="UUID người thao tác"
              class="audit-logs-page__filter-input"
            />
          </label>

          <label class="audit-logs-page__filter-field">
            <span class="audit-logs-page__filter-label">ID đối tượng</span>
            <InputText
              v-model="filters.entityId"
              placeholder="UUID hoặc ID đối tượng"
              class="audit-logs-page__filter-input"
            />
          </label>

          <label class="audit-logs-page__filter-field">
            <span class="audit-logs-page__filter-label">Mã request</span>
            <InputText
              v-model="filters.requestId"
              placeholder="req-..."
              class="audit-logs-page__filter-input"
            />
          </label>
        </div>
      </section>

      <div v-if="generalError" class="audit-logs-page__general-error">
        <i class="pi pi-exclamation-triangle" aria-hidden="true" />
        <span>{{ generalError }}</span>
      </div>

      <section v-if="!generalError" class="audit-logs-page__table-wrapper">
        <DataTable
          :first="first"
          :loading="loading"
          :rows="rows"
          :rows-per-page-options="rowsPerPageOptions"
          :total-records="totalAuditLogs"
          :value="auditLogs"
          current-page-report-template="Hiển thị từ {first} đến {last} trên tổng số {totalRecords} dòng"
          data-key="id"
          lazy
          paginator
          paginator-template="RowsPerPageDropdown PrevPageLink CurrentPageReport NextPageLink"
          responsive-layout="scroll"
          @page="onPageChange"
        >
          <template #empty>
            <div class="audit-logs-page__empty-state">
              Chưa có nhật ký audit phù hợp.
            </div>
          </template>

          <Column field="createdAtLabel" header="Thời gian" />
          <Column field="actorEmail" header="Người thao tác">
            <template #body="{ data }">
              <div class="audit-logs-page__actor-cell">
                <span>{{ data.actorEmail || 'Hệ thống' }}</span>
              </div>
            </template>
          </Column>
          <Column field="actionLabel" header="Hoạt động">
            <template #body="{ data }">
              <div class="audit-logs-page__action-cell">
                <Tag
                  :severity="actionSeverity(data.action)"
                  :value="data.actionLabel"
                />
                <small>{{ data.action }}</small>
              </div>
            </template>
          </Column>
          <Column field="targetLabel" header="Đối tượng">
            <template #body="{ data }">
              <div class="audit-logs-page__entity-cell">
                <span>{{ data.targetLabel }}</span>
                <small>{{ data.entityTypeLabel }}</small>
              </div>
            </template>
          </Column>
          <Column field="changeSummary" header="Thay đổi">
            <template #body="{ data }">
              <span class="audit-logs-page__change-summary">
                {{ data.changeSummary }}
              </span>
            </template>
          </Column>
          <Column header="Chi tiết" class="audit-logs-page__metadata-column">
            <template #body="{ data }">
              <Button
                aria-label="Xem chi tiết nhật ký audit"
                icon="pi pi-eye"
                rounded
                severity="secondary"
                text
                @click="openMetadataDialog(data)"
              />
            </template>
          </Column>
        </DataTable>
      </section>

      <Dialog
        v-model:visible="metadataDialogVisible"
        header="Chi tiết nhật ký audit"
        modal
        class="audit-logs-page__metadata-dialog"
      >
        <div
          v-if="selectedAuditLog"
          class="audit-logs-page__metadata-details"
        >
          <div>
            <span>Người thao tác</span>
            <strong>{{ selectedAuditLog.actorEmail || 'Hệ thống' }}</strong>
          </div>
          <div>
            <span>ID người thao tác</span>
            <strong>{{ selectedAuditLog.actorUserId || '-' }}</strong>
          </div>
          <div>
            <span>ID đối tượng</span>
            <strong>{{ selectedAuditLog.entityId || '-' }}</strong>
          </div>
          <div>
            <span>Mã request</span>
            <strong>{{ selectedAuditLog.requestId || '-' }}</strong>
          </div>
          <div>
            <span>IP</span>
            <strong>{{ selectedAuditLog.ipAddress || '-' }}</strong>
          </div>
        </div>
        <h3 class="audit-logs-page__metadata-heading">Metadata đã sanitize</h3>
        <pre class="audit-logs-page__metadata-json">{{
          formattedMetadata
        }}</pre>
      </Dialog>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Tag from 'primevue/tag'

import AdminLayout from '@/layouts/AdminLayout.vue'
import { useAuditLogsPage } from '@/composables/useAuditLogsPage'

const {
  auditLogs,
  totalAuditLogs,
  loading,
  generalError,
  rows,
  first,
  rowsPerPageOptions,
  filters,
  selectedAuditLog,
  metadataDialogVisible,
  formattedMetadata,
  fetchAuditLogs,
  onPageChange,
  applyFilters,
  clearFilters,
  openMetadataDialog,
} = useAuditLogsPage()

const advancedFiltersVisible = ref(false)
const actionFilterOptions = [
  { label: 'Đăng nhập thành công', value: 'auth.login_succeeded' },
  { label: 'Đăng nhập thất bại', value: 'auth.login_failed' },
  { label: 'Làm mới phiên', value: 'auth.session_refreshed' },
  { label: 'Tạo người dùng', value: 'users.user_created' },
  { label: 'Cập nhật người dùng', value: 'users.user_updated' },
  { label: 'Cập nhật vai trò', value: 'users.roles_updated' },
  { label: 'Xóa người dùng', value: 'users.user_deleted' },
  { label: 'Tải ảnh đại diện', value: 'users.avatar_uploaded' },
  { label: 'Tạo vai trò', value: 'roles.role_created' },
  { label: 'Cập nhật vai trò', value: 'roles.role_updated' },
  { label: 'Xóa vai trò', value: 'roles.role_deleted' },
  { label: 'Nhập danh sách người dùng', value: 'users.import_completed' },
  { label: 'Xuất danh sách người dùng', value: 'users.export_completed' },
  { label: 'Backup hoàn tất', value: 'backups.run_completed' },
  { label: 'Backup thất bại', value: 'backups.run_failed' },
]
const entityTypeFilterOptions = [
  { label: 'Người dùng', value: 'user' },
  { label: 'Vai trò', value: 'role' },
  { label: 'Tệp', value: 'file' },
  { label: 'Phiên đăng nhập', value: 'auth_session' },
  { label: 'Lịch backup', value: 'backup_schedule' },
  { label: 'Lần backup', value: 'backup_log' },
  { label: 'Lượt nhập dữ liệu', value: 'import_job' },
  { label: 'Lượt xuất dữ liệu', value: 'export_job' },
]

function actionSeverity(action: string) {
  if (action.includes('failed') || action.includes('deleted')) {
    return 'danger'
  }
  if (action.includes('created') || action.includes('succeeded')) {
    return 'success'
  }
  if (action.includes('updated')) {
    return 'warn'
  }

  return 'info'
}

onMounted(fetchAuditLogs)
</script>
