import { ref, reactive } from 'vue'

import { deleteFile, listFiles, uploadFile } from '@/api/files.api'
import { useAuthStore } from '@/stores/auth.store'
import type { FileDomain, FileListQueryParams } from '@/types/files'

export function useFilesPage() {
  const authStore = useAuthStore()

  // Data State
  const files = ref<FileDomain[]>([])
  const totalFiles = ref(0)
  const loading = ref(false)
  const generalError = ref<string | null>(null)

  // Lazy Params
  const lazyParams = reactive<FileListQueryParams>({
    limit: 10,
    offset: 0,
    search: '',
  })

  // UI Dialog States
  const uploadDialogVisible = ref(false)
  const deleteDialogVisible = ref(false)
  const selectedFile = ref<FileDomain | null>(null)

  // Action States
  const isUploading = ref(false)
  const isDeleting = ref(false)
  const uploadError = ref<string | null>(null)
  const deleteError = ref<string | null>(null)
  const isPublic = ref(false)
  const uploadFileObject = ref<File | null>(null)

  async function fetchFiles() {
    loading.value = true
    generalError.value = null
    try {
      const result = await listFiles(lazyParams, authStore.accessToken)
      files.value = result.items
      totalFiles.value = result.total
    } catch {
      generalError.value = 'Không thể tải danh sách tài liệu.'
    } finally {
      loading.value = false
    }
  }

  function onSearchChange(val: string) {
    lazyParams.search = val
    lazyParams.offset = 0
    fetchFiles()
  }

  function onPageChange(event: { first: number; rows: number }) {
    lazyParams.offset = event.first
    lazyParams.limit = event.rows
    fetchFiles()
  }

  function openUploadDialog() {
    uploadFileObject.value = null
    isPublic.value = false
    uploadError.value = null
    uploadDialogVisible.value = true
  }

  function onFileSelect(event: { files: File[] }) {
    if (event.files && event.files.length > 0) {
      uploadFileObject.value = event.files[0]
      uploadError.value = null
    }
  }

  async function handleUpload() {
    if (!uploadFileObject.value) {
      uploadError.value = 'Vui lòng chọn một tập tin.'
      return
    }

    isUploading.value = true
    uploadError.value = null
    try {
      await uploadFile(
        uploadFileObject.value,
        isPublic.value,
        authStore.accessToken,
      )
      uploadDialogVisible.value = false
      lazyParams.offset = 0
      await fetchFiles()
    } catch (err: unknown) {
      const apiErr = err as { message?: string }
      uploadError.value = apiErr?.message || 'Tải tập tin lên thất bại.'
    } finally {
      isUploading.value = false
    }
  }

  function confirmDelete(file: FileDomain) {
    selectedFile.value = file
    deleteError.value = null
    deleteDialogVisible.value = true
  }

  async function handleDelete() {
    if (!selectedFile.value) return

    isDeleting.value = true
    deleteError.value = null
    try {
      await deleteFile(selectedFile.value.id, authStore.accessToken)
      deleteDialogVisible.value = false
      selectedFile.value = null
      await fetchFiles()
    } catch (err: unknown) {
      const apiErr = err as { message?: string }
      deleteError.value = apiErr?.message || 'Không thể xóa tập tin này.'
    } finally {
      isDeleting.value = false
    }
  }

  async function downloadFileContent(file: FileDomain) {
    // Authenticated download for private files, standard download for public files
    if (file.isPublic) {
      window.open(file.url, '_blank')
      return
    }

    try {
      const response = await fetch(file.url, {
        headers: {
          Authorization: `Bearer ${authStore.accessToken}`,
        },
      })
      if (!response.ok) {
        throw new Error('Failed to download file content')
      }
      const blob = await response.blob()
      const objectUrl = window.URL.createObjectURL(blob)

      const link = document.createElement('a')
      link.href = objectUrl
      link.download = file.filename
      document.body.appendChild(link)
      link.click()
      link.remove()

      window.URL.revokeObjectURL(objectUrl)
    } catch {
      generalError.value = `Tải tập tin '${file.filename}' thất bại.`
    }
  }

  return {
    files,
    totalFiles,
    loading,
    generalError,
    lazyParams,
    uploadDialogVisible,
    deleteDialogVisible,
    selectedFile,
    isUploading,
    isDeleting,
    uploadError,
    deleteError,
    isPublic,
    uploadFileObject,
    fetchFiles,
    onSearchChange,
    onPageChange,
    openUploadDialog,
    onFileSelect,
    handleUpload,
    confirmDelete,
    handleDelete,
    downloadFileContent,
  }
}
