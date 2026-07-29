import { ref, computed } from 'vue'
import {
  getQuote,
  confirmVersion,
  toggleLinePurchase,
  uploadSourceFile,
  getQuoteNote,
  updateQuoteNote,
  updateQuoteNoteRevision,
  deleteQuoteNoteRevision,
} from '@/api/quotes.api'
import type { QuoteDomain, QuoteVersionDomain, QuoteNoteDomain } from '@/types/quotes'

export function useQuoteDetail(accessToken: string | null) {
  const quote = ref<QuoteDomain | null>(null)
  const activeVersionId = ref<string | null>(null)
  const isLoading = ref<boolean>(false)
  const errorMsg = ref<string | null>(null)
  
  const isConfirming = ref<boolean>(false)
  const isFileUploading = ref<boolean>(false)

  // Note state
  const note = ref<QuoteNoteDomain | null>(null)
  const isNoteLoading = ref<boolean>(false)
  const isSavingNote = ref<boolean>(false)
  const noteErrorMsg = ref<string | null>(null)

  // Sorted versions descending (highest version number first)
  const sortedVersions = computed<QuoteVersionDomain[]>(() => {
    if (!quote.value || !Array.isArray(quote.value.versions)) {
      return []
    }
    return [...quote.value.versions].sort((a, b) => b.versionNumber - a.versionNumber)
  })

  // Active version detail object
  const activeVersion = computed<QuoteVersionDomain | null>(() => {
    if (!activeVersionId.value || sortedVersions.value.length === 0) {
      return sortedVersions.value[0] || null
    }
    return sortedVersions.value.find((v) => v.id === activeVersionId.value) || sortedVersions.value[0] || null
  })

  const loadNote = async (quoteId: string) => {
    isNoteLoading.value = true
    noteErrorMsg.value = null
    try {
      const data = await getQuoteNote(quoteId, accessToken)
      note.value = data
    } catch (err: any) {
      noteErrorMsg.value = err.message || 'Không thể tải ghi chú thị trường.'
    } finally {
      isNoteLoading.value = false
    }
  }

  const handleUpdateNote = async (quoteId: string, content: string) => {
    isSavingNote.value = true
    noteErrorMsg.value = null
    try {
      const revision = await updateQuoteNote(quoteId, content, accessToken)
      if (!note.value || !note.value.id) {
        note.value = {
          id: 'temp-id',
          quoteId,
          createdAt: revision.createdAt,
          updatedAt: revision.createdAt,
          revisions: [revision],
        }
      } else {
        note.value.revisions = [revision, ...note.value.revisions]
        note.value.updatedAt = revision.createdAt
      }
      return revision
    } catch (err: any) {
      noteErrorMsg.value = err.message || 'Không thể cập nhật ghi chú thị trường.'
      throw err
    } finally {
      isSavingNote.value = false
    }
  }

  const loadQuote = async (quoteId: string) => {
    isLoading.value = true
    errorMsg.value = null
    try {
      const data = await getQuote(quoteId, accessToken)
      quote.value = data
      
      // Preserve active version selection, or default to latest
      if (!activeVersionId.value && data.versions.length > 0) {
        // Sort ascending to get maximum version number
        const sortedAsc = [...data.versions].sort((a, b) => b.versionNumber - a.versionNumber)
        activeVersionId.value = sortedAsc[0].id
      }

      // Load note alongside quote details
      await loadNote(quoteId)
    } catch (err: any) {
      errorMsg.value = err.message || 'Không thể tải chi tiết phiếu báo giá.'
    } finally {
      isLoading.value = false
    }
  }

  const handleConfirm = async () => {
    if (!quote.value || !activeVersion.value) {
      return
    }
    if (activeVersion.value.status !== 'draft') {
      return
    }
    isConfirming.value = true
    errorMsg.value = null
    try {
      await confirmVersion(quote.value.id, activeVersion.value.id, accessToken)
      await loadQuote(quote.value.id)
    } catch (err: any) {
      errorMsg.value = err.message || 'Không thể xác nhận phiên bản báo giá.'
      throw err
    } finally {
      isConfirming.value = false
    }
  }

  const handleTogglePurchase = async (lineId: string, currentPurchaseVal: boolean, purchaseDate?: string | null) => {
    if (!quote.value) {
      return
    }
    const nextVal = !currentPurchaseVal
    try {
      await toggleLinePurchase(quote.value.id, lineId, nextVal, purchaseDate, accessToken)
      await loadQuote(quote.value.id)
    } catch (err: any) {
      errorMsg.value = err.message || 'Không thể thay đổi trạng thái chốt mua.'
      throw err
    }
  }

  const handleUploadSourceFile = async (file: File) => {
    if (!quote.value || !activeVersion.value) {
      return
    }
    isFileUploading.value = true
    errorMsg.value = null
    try {
      await uploadSourceFile(quote.value.id, activeVersion.value.id, file, accessToken)
      await loadQuote(quote.value.id)
    } catch (err: any) {
      errorMsg.value = err.message || 'Đính kèm tệp tin gốc thất bại.'
      throw err
    } finally {
      isFileUploading.value = false
    }
  }

  const getSourceFileDownloadUrl = (version: QuoteVersionDomain): string => {
    if (!quote.value || !version.fileId) {
      return ''
    }
    return `/api/v1/quotes/${quote.value.id}/versions/${version.id}/source-file`
  }

  const handleUpdateNoteRevision = async (quoteId: string, revisionId: string, content: string) => {
    isSavingNote.value = true
    noteErrorMsg.value = null
    try {
      const updatedRev = await updateQuoteNoteRevision(quoteId, revisionId, content, accessToken)
      if (note.value && note.value.revisions) {
        const idx = note.value.revisions.findIndex((r) => r.id === revisionId)
        if (idx !== -1) {
          note.value.revisions[idx] = updatedRev
        }
      }
      return updatedRev
    } catch (err: any) {
      noteErrorMsg.value = err.message || 'Không thể sửa đổi ghi chú thị trường.'
      throw err
    } finally {
      isSavingNote.value = false
    }
  }

  const handleDeleteNoteRevision = async (quoteId: string, revisionId: string) => {
    isSavingNote.value = true
    noteErrorMsg.value = null
    try {
      await deleteQuoteNoteRevision(quoteId, revisionId, accessToken)
      if (note.value && note.value.revisions) {
        note.value.revisions = note.value.revisions.filter((r) => r.id !== revisionId)
        if (note.value.revisions.length === 0) {
          note.value = {
            id: '',
            quoteId,
            createdAt: '',
            updatedAt: '',
            revisions: [],
          }
        }
      }
    } catch (err: any) {
      noteErrorMsg.value = err.message || 'Không thể xóa ghi chú thị trường.'
      throw err
    } finally {
      isSavingNote.value = false
    }
  }

  return {
    quote,
    activeVersionId,
    isLoading,
    errorMsg,
    isConfirming,
    isFileUploading,
    sortedVersions,
    activeVersion,
    note,
    isNoteLoading,
    isSavingNote,
    noteErrorMsg,
    loadQuote,
    handleConfirm,
    handleTogglePurchase,
    handleUploadSourceFile,
    getSourceFileDownloadUrl,
    loadNote,
    handleUpdateNote,
    handleUpdateNoteRevision,
    handleDeleteNoteRevision,
  }
}
