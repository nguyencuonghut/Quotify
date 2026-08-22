<template>
  <AdminLayout section-label="Quản trị hệ thống" title="Quản lý sao lưu">
    <div class="backups-page">
      <!-- Tab Selection -->
      <div class="backups-page__tabs">
        <button
          type="button"
          :class="[
            'backups-page__tab-btn',
            { 'backups-page__tab-btn--active': activeTab === 'logs' },
          ]"
          @click="activeTab = 'logs'"
        >
          Lịch sử Sao lưu
        </button>
        <button
          type="button"
          :class="[
            'backups-page__tab-btn',
            { 'backups-page__tab-btn--active': activeTab === 'schedules' },
          ]"
          @click="activeTab = 'schedules'"
        >
          Lịch trình tự động
        </button>
      </div>

      <!-- General Messages -->
      <div v-if="generalError" class="backups-page__general-error">
        <i class="pi pi-exclamation-triangle" aria-hidden="true" />
        <span>{{ generalError }}</span>
      </div>

      <div v-if="generalSuccess" class="backups-page__general-success">
        <i class="pi pi-check-circle" aria-hidden="true" />
        <span>{{ generalSuccess }}</span>
      </div>

      <!-- LOGS TAB -->
      <div v-if="activeTab === 'logs'" class="backups-page__tab-content">
        <section class="backups-page__header">
          <div>
            <h3 class="backups-page__title">Lịch sử thực thi sao lưu</h3>
            <p class="backups-page__subtitle">
              Xem nhật ký các lần sao lưu thủ công hoặc tự động.
            </p>
          </div>
          <div class="backups-page__actions">
            <Button
              v-if="permissionStore.can('backups.write')"
              label="Sao lưu ngay"
              icon="pi pi-play"
              :loading="isTriggering"
              @click="triggerBackup"
            />
          </div>
        </section>

        <section class="backups-page__table-wrapper">
          <DataTable
            :loading="loadingLogs"
            :rows="lazyParams.limit"
            :total-records="totalBackupLogs"
            :value="backupLogs"
            data-key="id"
            lazy
            paginator
            current-page-report-template="Hiển thị từ {first} đến {last} trên tổng số {totalRecords} dòng"
            :rows-per-page-options="[10, 20, 30, 50]"
            paginator-template="RowsPerPageDropdown FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport"
            responsive-layout="scroll"
            @page="onPageChange"
          >
            <template #empty>
              <div class="backups-page__empty-state">
                Không tìm thấy lịch sử sao lưu nào.
              </div>
            </template>

            <Column field="status" header="Trạng thái">
              <template #body="{ data }">
                <Tag
                  :severity="getStatusSeverity(data.status)"
                  :value="getStatusText(data.status)"
                />
              </template>
            </Column>

            <Column field="backupType" header="Loại sao lưu">
              <template #body="{ data }">
                <Tag
                  :severity="
                    data.backupType === 'manual' ? 'info' : 'secondary'
                  "
                  :value="
                    data.backupType === 'manual' ? 'Thủ công' : 'Lịch trình'
                  "
                />
              </template>
            </Column>

            <Column field="filename" header="Tên tập tin">
              <template #body="{ data }">
                <span class="backups-page__filename">{{
                  data.filename || 'Đang xử lý...'
                }}</span>
              </template>
            </Column>

            <Column field="fileSize" header="Kích thước">
              <template #body="{ data }">
                {{ formatBytes(data.fileSize) }}
              </template>
            </Column>

            <Column field="startedAt" header="Thời gian bắt đầu">
              <template #body="{ data }">
                {{ formatDate(data.startedAt) }}
              </template>
            </Column>

            <Column field="completedAt" header="Thời gian kết thúc">
              <template #body="{ data }">
                {{ formatDate(data.completedAt) }}
              </template>
            </Column>

            <Column field="createdByEmail" header="Người thực hiện" />

            <Column header="Thao tác" class="backups-page__actions-column">
              <template #body="{ data }">
                <div class="backups-page__row-actions">
                  <Button
                    v-if="
                      permissionStore.can('backups.read') &&
                      data.status === 'completed'
                    "
                    icon="pi pi-download"
                    severity="secondary"
                    text
                    rounded
                    aria-label="Tải xuống"
                    @click="downloadBackupFile(data)"
                  />
                  <Button
                    v-if="data.status === 'failed' && data.errorMessage"
                    icon="pi pi-info-circle"
                    severity="danger"
                    text
                    rounded
                    aria-label="Xem lỗi"
                    @click="showErrorDetail(data.errorMessage)"
                  />
                </div>
              </template>
            </Column>
          </DataTable>
        </section>
      </div>

      <!-- SCHEDULES TAB -->
      <div v-if="activeTab === 'schedules'" class="backups-page__tab-content">
        <section class="backups-page__header">
          <div>
            <h3 class="backups-page__title">Danh sách lịch trình sao lưu</h3>
            <p class="backups-page__subtitle">
              Quản lý lịch cấu hình sao lưu cơ sở dữ liệu định kỳ.
            </p>
          </div>
          <div class="backups-page__actions">
            <Button
              v-if="permissionStore.can('backups.write')"
              label="Tạo lịch trình"
              icon="pi pi-plus"
              @click="openCreateDialog"
            />
          </div>
        </section>

        <section class="backups-page__table-wrapper">
          <DataTable
            :loading="loadingSchedules"
            :rows="10"
            :value="backupSchedules"
            data-key="id"
            paginator
            current-page-report-template="Hiển thị từ {first} đến {last} trên tổng số {totalRecords} dòng"
            :rows-per-page-options="[10, 20, 30, 50]"
            paginator-template="RowsPerPageDropdown FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport"
            responsive-layout="scroll"
          >
            <template #empty>
              <div class="backups-page__empty-state">
                Không tìm thấy lịch trình sao lưu tự động nào.
              </div>
            </template>

            <Column field="name" header="Tên lịch trình" />

            <Column field="frequency" header="Tần suất">
              <template #body="{ data }">
                {{ getFrequencyText(data.frequency) }}
              </template>
            </Column>

            <Column header="Lịch chạy">
              <template #body="{ data }">
                {{ formatScheduleDetail(data) }}
              </template>
            </Column>

            <Column field="isActive" header="Kích hoạt">
              <template #body="{ data }">
                <Tag
                  :severity="data.isActive ? 'success' : 'secondary'"
                  :value="data.isActive ? 'Bật' : 'Tắt'"
                />
              </template>
            </Column>

            <Column field="nextRunAt" header="Lần chạy kế tiếp">
              <template #body="{ data }">
                {{ formatDate(data.nextRunAt) }}
              </template>
            </Column>

            <Column field="lastRunAt" header="Lần chạy gần nhất">
              <template #body="{ data }">
                {{ formatDate(data.lastRunAt) }}
              </template>
            </Column>

            <Column header="Thao tác" class="backups-page__actions-column">
              <template #body="{ data }">
                <div class="backups-page__row-actions">
                  <Button
                    v-if="permissionStore.can('backups.write')"
                    icon="pi pi-pencil"
                    severity="secondary"
                    text
                    rounded
                    aria-label="Chỉnh sửa"
                    @click="openEditDialog(data)"
                  />
                  <Button
                    v-if="permissionStore.can('backups.write')"
                    icon="pi pi-trash"
                    severity="danger"
                    text
                    rounded
                    aria-label="Xóa"
                    @click="confirmDelete(data)"
                  />
                </div>
              </template>
            </Column>
          </DataTable>
        </section>
      </div>

      <!-- Create/Edit Schedule Dialog -->
      <Dialog
        v-model:visible="scheduleDialogVisible"
        :header="
          isEditingSchedule ? 'Chỉnh sửa lịch trình' : 'Thêm lịch trình mới'
        "
        modal
        class="backups-page__dialog"
      >
        <form class="backups-page__form" @submit.prevent="submitSchedule">
          <div class="backups-page__form-field">
            <label for="schedule-name" class="backups-page__form-label required"
              >Tên lịch trình</label
            >
            <InputText
              id="schedule-name"
              v-model="name"
              v-bind="nameProps"
              fluid
              placeholder="Ví dụ: Sao lưu hàng ngày 2h sáng"
            />
            <small class="backups-page__field-error">{{ errors.name }}</small>
          </div>

          <div class="backups-page__form-field">
            <label
              for="schedule-frequency"
              class="backups-page__form-label required"
              >Tần suất</label
            >
            <Select
              id="schedule-frequency"
              v-model="frequency"
              v-bind="frequencyProps"
              :options="frequencyOptions"
              option-label="label"
              option-value="value"
              fluid
            />
            <small class="backups-page__field-error">{{
              errors.frequency
            }}</small>
          </div>

          <!-- Day of week (For weekly frequency) -->
          <div v-if="frequency === 'weekly'" class="backups-page__form-field">
            <label
              for="schedule-day-of-week"
              class="backups-page__form-label required"
              >Thứ trong tuần</label
            >
            <Select
              id="schedule-day-of-week"
              v-model="dayOfWeek"
              v-bind="dayOfWeekProps"
              :options="dayOfWeekOptions"
              option-label="label"
              option-value="value"
              placeholder="Chọn thứ..."
              fluid
            />
            <small class="backups-page__field-error">{{
              errors.dayOfWeek
            }}</small>
          </div>

          <!-- Time of day (For daily/weekly) -->
          <div
            v-if="frequency === 'daily' || frequency === 'weekly'"
            class="backups-page__form-field"
          >
            <label
              for="schedule-time-of-day"
              class="backups-page__form-label required"
              >Giờ chạy (HH:MM)</label
            >
            <InputText
              id="schedule-time-of-day"
              v-model="timeOfDay"
              v-bind="timeOfDayProps"
              fluid
              placeholder="Ví dụ: 02:00"
            />
            <small class="backups-page__field-error">{{
              errors.timeOfDay
            }}</small>
          </div>

          <!-- One-off datetime -->
          <div v-if="frequency === 'one_off'" class="backups-page__form-field">
            <label
              for="schedule-one-off"
              class="backups-page__form-label required"
              >Ngày giờ chạy một lần</label
            >
            <input
              id="schedule-one-off"
              v-model="oneOffDatetime"
              v-bind="oneOffDatetimeProps"
              type="datetime-local"
              class="p-inputtext"
              style="width: 100%"
            />
            <small class="backups-page__field-error">{{
              errors.oneOffDatetime
            }}</small>
          </div>

          <div
            class="backups-page__form-field backups-page__form-field--checkbox"
          >
            <Checkbox id="schedule-active" v-model="isActive" :binary="true" />
            <label for="schedule-active" class="backups-page__checkbox-label"
              >Kích hoạt lịch trình này</label
            >
          </div>

          <div class="backups-page__dialog-actions">
            <Button
              label="Hủy"
              severity="secondary"
              text
              @click="scheduleDialogVisible = false"
            />
            <Button label="Lưu" type="submit" :loading="isSavingSchedule" />
          </div>
        </form>
      </Dialog>

      <!-- Delete Confirmation Dialog -->
      <Dialog
        v-model:visible="deleteDialogVisible"
        header="Xác nhận xóa"
        modal
        class="backups-page__dialog"
      >
        <div class="backups-page__dialog-body">
          <p>
            Bạn có chắc chắn muốn xóa lịch trình sao lưu
            <strong>{{ selectedSchedule?.name }}</strong
            >?
          </p>
          <p class="backups-page__dialog-danger-note">
            Hành động này không thể hoàn tác.
          </p>
        </div>
        <div class="backups-page__dialog-actions">
          <Button
            label="Hủy"
            severity="secondary"
            text
            @click="deleteDialogVisible = false"
          />
          <Button
            label="Xóa"
            severity="danger"
            :loading="isDeletingSchedule"
            @click="handleDeleteSchedule"
          />
        </div>
      </Dialog>

      <!-- Error Detail Dialog -->
      <Dialog
        v-model:visible="errorDetailVisible"
        header="Chi tiết lỗi sao lưu"
        modal
        class="backups-page__dialog"
      >
        <div class="backups-page__dialog-body">
          <pre
            class="backups-page__error-detail"
            >{{ activeErrorMessage }}</pre
          >
        </div>
        <div class="backups-page__dialog-actions">
          <Button
            label="Đóng"
            severity="secondary"
            text
            @click="errorDetailVisible = false"
          />
        </div>
      </Dialog>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import { toTypedSchema } from '@vee-validate/zod'
import { useForm } from 'vee-validate'

import AdminLayout from '@/layouts/AdminLayout.vue'
import { usePermissionStore } from '@/stores/permission.store'
import {
  useBackupsPage,
  scheduleSchema,
  type ScheduleFormValues,
} from '@/composables/useBackupsPage'
import type { BackupScheduleDomain } from '@/types/backups'

const permissionStore = usePermissionStore()
const activeTab = ref<'logs' | 'schedules'>('logs')

// Dialog states
const scheduleDialogVisible = ref(false)
const deleteDialogVisible = ref(false)
const errorDetailVisible = ref(false)
const isEditingSchedule = ref(false)

const selectedSchedule = ref<BackupScheduleDomain | null>(null)
const activeErrorMessage = ref('')

const {
  backupLogs,
  totalBackupLogs,
  backupSchedules,
  loadingLogs,
  loadingSchedules,
  isTriggering,
  isSavingSchedule,
  isDeletingSchedule,
  generalError,
  generalSuccess,
  fetchBackupLogs,
  fetchBackupSchedules,
  triggerBackup,
  saveSchedule,
  removeSchedule,
  downloadBackupFile,
} = useBackupsPage()

const lazyParams = ref({
  limit: 10,
  offset: 0,
})

// VeeValidate Form Setup
const { defineField, errors, handleSubmit, resetForm, setValues } =
  useForm<ScheduleFormValues>({
    initialValues: {
      name: '',
      frequency: 'daily',
      dayOfWeek: null,
      timeOfDay: '02:00',
      oneOffDatetime: null,
      isActive: true,
    },
    validationSchema: toTypedSchema(scheduleSchema),
  })

const [name, nameProps] = defineField('name')
const [frequency, frequencyProps] = defineField('frequency')
const [dayOfWeek, dayOfWeekProps] = defineField('dayOfWeek')
const [timeOfDay, timeOfDayProps] = defineField('timeOfDay')
const [oneOffDatetime, oneOffDatetimeProps] = defineField('oneOffDatetime')
const [isActive] = defineField('isActive')

const frequencyOptions = [
  { label: 'Hàng ngày', value: 'daily' },
  { label: 'Hàng tuần', value: 'weekly' },
  { label: 'Một lần', value: 'one_off' },
]

const dayOfWeekOptions = [
  { label: 'Thứ Hai', value: 0 },
  { label: 'Thứ Ba', value: 1 },
  { label: 'Thứ Tư', value: 2 },
  { label: 'Thứ Năm', value: 3 },
  { label: 'Thứ Sáu', value: 4 },
  { label: 'Thứ Bảy', value: 5 },
  { label: 'Chủ Nhật', value: 6 },
]

interface PageEvent {
  first: number
  rows: number
}

function onPageChange(event: PageEvent) {
  lazyParams.value.limit = event.rows
  lazyParams.value.offset = event.first
  fetchBackupLogs(lazyParams.value.limit, lazyParams.value.offset)
}

// Dialog Triggers
function openCreateDialog() {
  isEditingSchedule.value = false
  selectedSchedule.value = null
  resetForm({
    values: {
      name: '',
      frequency: 'daily',
      dayOfWeek: null,
      timeOfDay: '02:00',
      oneOffDatetime: null,
      isActive: true,
    },
  })
  scheduleDialogVisible.value = true
}

function openEditDialog(schedule: BackupScheduleDomain) {
  isEditingSchedule.value = true
  selectedSchedule.value = schedule

  // Format dates/time for inputs
  let formattedOneOff = null
  if (schedule.oneOffDatetime) {
    const d = new Date(schedule.oneOffDatetime)
    // Convert date object to string expected by datetime-local (YYYY-MM-DDTHH:MM)
    const pad = (num: number) => String(num).padStart(2, '0')
    const year = d.getFullYear()
    const month = pad(d.getMonth() + 1)
    const date = pad(d.getDate())
    const hours = pad(d.getHours())
    const minutes = pad(d.getMinutes())
    formattedOneOff = `${year}-${month}-${date}T${hours}:${minutes}`
  }

  // Slice timeOfDay to HH:MM if it has seconds
  let cleanTime = schedule.timeOfDay
  if (cleanTime && cleanTime.length > 5) {
    cleanTime = cleanTime.substring(0, 5)
  }

  setValues({
    name: schedule.name,
    frequency: schedule.frequency as 'daily' | 'weekly' | 'one_off',
    dayOfWeek: schedule.dayOfWeek,
    timeOfDay: cleanTime,
    oneOffDatetime: formattedOneOff,
    isActive: schedule.isActive,
  })
  scheduleDialogVisible.value = true
}

function confirmDelete(schedule: BackupScheduleDomain) {
  selectedSchedule.value = schedule
  deleteDialogVisible.value = true
}

async function handleDeleteSchedule() {
  if (!selectedSchedule.value) return
  await removeSchedule(selectedSchedule.value.id)
  deleteDialogVisible.value = false
  selectedSchedule.value = null
}

function showErrorDetail(errMsg: string) {
  activeErrorMessage.value = errMsg
  errorDetailVisible.value = true
}

const submitSchedule = handleSubmit(async (values) => {
  try {
    // If date string contains T, let's parse it correctly for store
    let processedValues = { ...values }
    if (
      values.frequency === 'one_off' &&
      typeof values.oneOffDatetime === 'string' &&
      values.oneOffDatetime
    ) {
      processedValues.oneOffDatetime = new Date(values.oneOffDatetime)
    }

    await saveSchedule(processedValues, selectedSchedule.value?.id)
    scheduleDialogVisible.value = false
    selectedSchedule.value = null
  } catch {
    // Error is set in generalError by composable
  }
})

// Utility displays
function getStatusSeverity(status: string) {
  switch (status) {
    case 'completed':
      return 'success'
    case 'failed':
      return 'danger'
    case 'running':
      return 'warn'
    case 'pending':
    default:
      return 'secondary'
  }
}

function getStatusText(status: string) {
  switch (status) {
    case 'completed':
      return 'Thành công'
    case 'failed':
      return 'Thất bại'
    case 'running':
      return 'Đang chạy'
    case 'pending':
      return 'Chờ xử lý'
    default:
      return status
  }
}

function getFrequencyText(freq: string) {
  switch (freq) {
    case 'daily':
      return 'Hàng ngày'
    case 'weekly':
      return 'Hàng tuần'
    case 'one_off':
      return 'Một lần'
    default:
      return freq
  }
}

function formatScheduleDetail(schedule: BackupScheduleDomain) {
  const time = schedule.timeOfDay ? schedule.timeOfDay.substring(0, 5) : ''
  if (schedule.frequency === 'daily') {
    return `Mỗi ngày lúc ${time}`
  } else if (schedule.frequency === 'weekly') {
    const dayName =
      dayOfWeekOptions.find((o) => o.value === schedule.dayOfWeek)?.label ||
      'Thứ Hai'
    return `Mỗi ${dayName} lúc ${time}`
  } else if (schedule.frequency === 'one_off') {
    return `Chạy một lần vào ${formatDate(schedule.oneOffDatetime)}`
  }
  return '-'
}

function formatDate(dateStr: string | null) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('vi-VN', {
    timeZone: 'Asia/Ho_Chi_Minh',
  })
}

function formatBytes(bytes: number | null, decimals = 2) {
  if (bytes === null || bytes === undefined) return '-'
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`
}

let pollInterval: number | null = null

function startPollingLogs() {
  if (pollInterval) return
  pollInterval = window.setInterval(() => {
    fetchBackupLogs(lazyParams.value.limit, lazyParams.value.offset)
  }, 4000)
}

function stopPollingLogs() {
  if (pollInterval) {
    window.clearInterval(pollInterval)
    pollInterval = null
  }
}

watch(
  () => backupLogs.value,
  (logs) => {
    const hasRunningTasks = logs.some(
      (log) => log.status === 'pending' || log.status === 'running',
    )
    if (hasRunningTasks) {
      startPollingLogs()
    } else {
      stopPollingLogs()
    }
  },
  { deep: true },
)

onMounted(() => {
  fetchBackupLogs(lazyParams.value.limit, lazyParams.value.offset)
  fetchBackupSchedules()
})

onUnmounted(() => {
  stopPollingLogs()
})
</script>
