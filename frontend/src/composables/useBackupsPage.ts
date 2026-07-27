import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth.store'
import { getApiBaseUrl } from '@/api/runtime'
import {
  listBackupLogs,
  triggerBackupNow,
  listBackupSchedules,
  createBackupSchedule,
  updateBackupSchedule,
  deleteBackupSchedule,
} from '@/api/backups.api'
import type { BackupLogDomain, BackupScheduleDomain } from '@/types/backups'
import { z } from 'zod'

export const scheduleSchema = z
  .object({
    name: z.string().min(1, 'Tên lịch trình là bắt buộc.'),
    frequency: z.enum(['daily', 'weekly', 'one_off'], {
      required_error: 'Tần suất là bắt buộc.',
    }),
    dayOfWeek: z.number().nullable().optional(),
    timeOfDay: z
      .string()
      .regex(
        /^([01]?[0-9]|2[0-3]):[0-5][0-9](:[0-5][0-9])?$/,
        'Định dạng giờ phải là HH:MM hoặc HH:MM:SS',
      ),
    oneOffDatetime: z.union([z.date(), z.string()]).nullable().optional(),
    isActive: z.boolean().default(true),
  })
  .superRefine((data, ctx) => {
    if (
      data.frequency === 'weekly' &&
      (data.dayOfWeek === null || data.dayOfWeek === undefined)
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Thứ trong tuần là bắt buộc đối với lịch trình hàng tuần.',
        path: ['dayOfWeek'],
      })
    }
    if (data.frequency === 'one_off' && !data.oneOffDatetime) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Ngày giờ chạy một lần là bắt buộc.',
        path: ['oneOffDatetime'],
      })
    }
  })

export type ScheduleFormValues = z.infer<typeof scheduleSchema>

export function useBackupsPage() {
  const authStore = useAuthStore()

  const backupLogs = ref<BackupLogDomain[]>([])
  const totalBackupLogs = ref(0)
  const backupSchedules = ref<BackupScheduleDomain[]>([])

  const loadingLogs = ref(false)
  const loadingSchedules = ref(false)
  const isTriggering = ref(false)
  const isSavingSchedule = ref(false)
  const isDeletingSchedule = ref(false)

  const generalError = ref<string | null>(null)
  const generalSuccess = ref<string | null>(null)

  function clearMessages() {
    generalError.value = null
    generalSuccess.value = null
  }

  async function fetchBackupLogs(limit: number, offset: number) {
    loadingLogs.value = true
    clearMessages()
    try {
      const res = await listBackupLogs(limit, offset, authStore.accessToken)
      backupLogs.value = res.items
      totalBackupLogs.value = res.total
    } catch {
      generalError.value = 'Không thể tải lịch sử sao lưu.'
    } finally {
      loadingLogs.value = false
    }
  }

  async function fetchBackupSchedules() {
    loadingSchedules.value = true
    clearMessages()
    try {
      backupSchedules.value = await listBackupSchedules(authStore.accessToken)
    } catch {
      generalError.value = 'Không thể tải lịch trình sao lưu tự động.'
    } finally {
      loadingSchedules.value = false
    }
  }

  async function triggerBackup() {
    isTriggering.value = true
    clearMessages()
    try {
      await triggerBackupNow(authStore.accessToken)
      generalSuccess.value = 'Đã yêu cầu khởi tạo sao lưu dữ liệu thủ công.'
      await fetchBackupLogs(10, 0)
    } catch {
      generalError.value = 'Không thể bắt đầu sao lưu thủ công.'
    } finally {
      isTriggering.value = false
    }
  }

  async function saveSchedule(values: ScheduleFormValues, scheduleId?: string) {
    isSavingSchedule.value = true
    clearMessages()

    const payload = {
      name: values.name,
      frequency: values.frequency,
      day_of_week: values.frequency === 'weekly' ? values.dayOfWeek : null,
      time_of_day: values.timeOfDay,
      one_off_datetime:
        values.frequency === 'one_off'
          ? values.oneOffDatetime instanceof Date
            ? values.oneOffDatetime.toISOString()
            : values.oneOffDatetime
          : null,
      is_active: values.isActive,
    }

    try {
      if (scheduleId) {
        await updateBackupSchedule(scheduleId, payload, authStore.accessToken)
        generalSuccess.value = 'Cập nhật lịch trình sao lưu thành công.'
      } else {
        await createBackupSchedule(payload, authStore.accessToken)
        generalSuccess.value = 'Tạo lịch trình sao lưu mới thành công.'
      }
      await fetchBackupSchedules()
    } catch (err) {
      generalError.value = 'Lưu lịch trình sao lưu thất bại.'
      throw err
    } finally {
      isSavingSchedule.value = false
    }
  }

  async function removeSchedule(scheduleId: string) {
    isDeletingSchedule.value = true
    clearMessages()
    try {
      await deleteBackupSchedule(scheduleId, authStore.accessToken)
      generalSuccess.value = 'Đã xóa lịch trình sao lưu.'
      await fetchBackupSchedules()
    } catch {
      generalError.value = 'Xóa lịch trình sao lưu thất bại.'
    } finally {
      isDeletingSchedule.value = false
    }
  }

  async function downloadBackupFile(log: BackupLogDomain) {
    if (!log.filename) return
    clearMessages()
    try {
      const url = `${getApiBaseUrl()}/backups/${log.id}/download`
      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${authStore.accessToken}`,
        },
      })
      if (!response.ok) {
        throw new Error('Failed to download backup content')
      }
      const blob = await response.blob()
      const objectUrl = window.URL.createObjectURL(blob)

      const link = document.createElement('a')
      link.href = objectUrl
      link.download = log.filename
      document.body.appendChild(link)
      link.click()
      link.remove()

      window.URL.revokeObjectURL(objectUrl)
      generalSuccess.value = `Đang tải tập tin sao lưu '${log.filename}'...`
    } catch {
      generalError.value = `Tải tập tin sao lưu '${log.filename}' thất bại.`
    }
  }

  return {
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
    clearMessages,
  }
}
