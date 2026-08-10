import { onUnmounted, ref } from 'vue'

import {
  downloadQuoteBackfillImportErrorFile,
  downloadQuoteBackfillImportTemplate,
  getQuoteBackfillImportJob,
  importQuoteBackfill,
} from '@/api/quote-backfill-imports.api'
import { ApiError } from '@/api/http'
import { useAuthStore } from '@/stores/auth.store'
import type { ImportJobDomain } from '@/types/jobs'

export function useQuoteBackfillImport(refreshAfterImport: () => Promise<void>) {
  const authStore = useAuthStore()
  const importDialogVisible = ref(false)
  const importJob = ref<ImportJobDomain | null>(null)
  const importError = ref<string | null>(null)
  const uploadingImport = ref(false)
  const pollIntervals = new Map<string, number>()

  function openImportDialog() {
    importError.value = null
    importDialogVisible.value = true
  }

  async function handleImportUpload(event: { files: File | File[] }) {
    const file = Array.isArray(event.files) ? event.files[0] : event.files
    if (!file) return
    uploadingImport.value = true
    importError.value = null
    try {
      const job = await importQuoteBackfill(file, authStore.accessToken)
      importJob.value = job
      pollImportJob(job.id)
    } catch (error) {
      importError.value =
        error instanceof ApiError
          ? error.message
          : 'Không thể bắt đầu import báo giá cũ.'
    } finally {
      uploadingImport.value = false
    }
  }

  async function downloadTemplate() {
    importError.value = null
    try {
      await downloadQuoteBackfillImportTemplate(authStore.accessToken)
    } catch (error) {
      importError.value =
        error instanceof ApiError ? error.message : 'Không thể tải template CSV.'
    }
  }

  async function downloadErrorFile() {
    if (!importJob.value) return
    importError.value = null
    try {
      await downloadQuoteBackfillImportErrorFile(
        importJob.value.id,
        authStore.accessToken,
      )
    } catch (error) {
      importError.value =
        error instanceof ApiError ? error.message : 'Không thể tải file lỗi.'
    }
  }

  function pollImportJob(jobId: string) {
    if (pollIntervals.has(jobId)) return
    const interval = window.setInterval(async () => {
      try {
        const job = await getQuoteBackfillImportJob(jobId, authStore.accessToken)
        importJob.value = job
        if (job.status === 'completed' || job.status === 'failed') {
          window.clearInterval(interval)
          pollIntervals.delete(jobId)
          if (job.processedRows > 0) {
            await refreshAfterImport()
          }
        }
      } catch {
        window.clearInterval(interval)
        pollIntervals.delete(jobId)
      }
    }, 2000)
    pollIntervals.set(jobId, interval)
  }

  onUnmounted(() => {
    pollIntervals.forEach((interval) => window.clearInterval(interval))
    pollIntervals.clear()
  })

  return {
    importDialogVisible,
    importJob,
    importError,
    uploadingImport,
    openImportDialog,
    handleImportUpload,
    downloadTemplate,
    downloadErrorFile,
  }
}
