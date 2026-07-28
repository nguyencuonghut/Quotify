import { ref, computed } from 'vue'
import {
  getQuote,
  confirmVersion,
  toggleLinePurchase,
  uploadSourceFile,
} from '@/api/quotes.api'
import type { QuoteDomain, QuoteVersionDomain } from '@/types/quotes'

export function useQuoteDetail(accessToken: string | null) {
  const quote = ref<QuoteDomain | null>(null)
  const activeVersionId = ref<string | null>(null)
  const isLoading = ref<boolean>(false)
  const errorMsg = ref<string | null>(null)
  
  const isConfirming = ref<boolean>(false)
  const isFileUploading = ref<boolean>(false)

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

  const handleTogglePurchase = async (lineId: string, currentPurchaseVal: boolean) => {
    if (!quote.value) {
      return
    }
    // Toggle logic: send opposite value of current
    const nextVal = !currentPurchaseVal
    try {
      await toggleLinePurchase(quote.value.id, lineId, nextVal, accessToken)
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

  return {
    quote,
    activeVersionId,
    isLoading,
    errorMsg,
    isConfirming,
    isFileUploading,
    sortedVersions,
    activeVersion,
    loadQuote,
    handleConfirm,
    handleTogglePurchase,
    handleUploadSourceFile,
    getSourceFileDownloadUrl,
  }
}
