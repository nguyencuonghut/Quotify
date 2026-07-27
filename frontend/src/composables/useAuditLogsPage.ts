import { computed, reactive, ref } from 'vue'

import { listAuditLogs } from '@/api/audit-logs.api'
import { useAuthStore } from '@/stores/auth.store'
import type {
  AuditLogDomain,
  AuditLogListQueryParams,
} from '@/types/audit-logs'

export interface AuditLogFilters {
  actorUserId: string
  action: string | null
  entityType: string | null
  entityId: string
  requestId: string
  createdFrom: string
  createdTo: string
}

const DEFAULT_ROWS = 10

function toExclusiveDateBoundary(value: string): string | undefined {
  if (!value) {
    return undefined
  }

  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return value
  }

  const date = new Date(`${value}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + 1)
  return date.toISOString().slice(0, 10)
}

function buildQueryParams(
  limit: number,
  cursor: string | null,
  filters: AuditLogFilters,
): AuditLogListQueryParams {
  return {
    limit,
    cursor,
    actor_user_id: normalizeFilterValue(filters.actorUserId),
    action: normalizeFilterValue(filters.action),
    entity_type: normalizeFilterValue(filters.entityType),
    entity_id: normalizeFilterValue(filters.entityId),
    request_id: normalizeFilterValue(filters.requestId),
    created_from: filters.createdFrom || undefined,
    created_to: toExclusiveDateBoundary(filters.createdTo),
  }
}

function normalizeFilterValue(value: string | null): string | undefined {
  return value?.trim() || undefined
}

export function useAuditLogsPage() {
  const authStore = useAuthStore()

  const auditLogs = ref<AuditLogDomain[]>([])
  const totalAuditLogs = ref(0)
  const loading = ref(false)
  const generalError = ref<string | null>(null)
  const rowsPerPageOptions = [10, 20, 30, 50]
  const rows = ref(DEFAULT_ROWS)
  const first = ref(0)
  const nextCursor = ref<string | null>(null)
  const pageCursorMap = ref<Record<number, string | null>>({ 0: null })
  const selectedAuditLog = ref<AuditLogDomain | null>(null)
  const metadataDialogVisible = ref(false)

  const filters = reactive<AuditLogFilters>({
    actorUserId: '',
    action: '',
    entityType: '',
    entityId: '',
    requestId: '',
    createdFrom: '',
    createdTo: '',
  })

  const currentPage = computed(() => Math.floor(first.value / rows.value))
  const formattedMetadata = computed(() => {
    if (!selectedAuditLog.value?.metadata) {
      return '{}'
    }

    return JSON.stringify(selectedAuditLog.value.metadata, null, 2)
  })

  async function fetchAuditLogsForPage(page: number) {
    loading.value = true
    generalError.value = null

    try {
      const cursor = pageCursorMap.value[page] ?? null
      const result = await listAuditLogs(
        buildQueryParams(rows.value, cursor, filters),
        authStore.accessToken,
      )

      auditLogs.value = result.items
      totalAuditLogs.value = result.total
      nextCursor.value = result.nextCursor
      pageCursorMap.value[page + 1] = result.nextCursor
      first.value = page * rows.value
    } catch {
      auditLogs.value = []
      totalAuditLogs.value = 0
      nextCursor.value = null
      generalError.value = 'Không thể tải nhật ký audit.'
    } finally {
      loading.value = false
    }
  }

  async function fetchAuditLogs() {
    await fetchAuditLogsForPage(currentPage.value)
  }

  async function onPageChange(event: { first: number; rows: number }) {
    const rowsChanged = event.rows !== rows.value
    rows.value = event.rows

    if (rowsChanged) {
      resetPaging()
      await fetchAuditLogsForPage(0)
      return
    }

    const targetPage = Math.floor(event.first / event.rows)
    if (
      pageCursorMap.value[targetPage] === undefined ||
      (targetPage > 0 && pageCursorMap.value[targetPage] === null)
    ) {
      return
    }

    await fetchAuditLogsForPage(targetPage)
  }

  function resetPaging() {
    first.value = 0
    nextCursor.value = null
    pageCursorMap.value = { 0: null }
  }

  async function applyFilters() {
    resetPaging()
    await fetchAuditLogsForPage(0)
  }

  async function clearFilters() {
    filters.actorUserId = ''
    filters.action = ''
    filters.entityType = ''
    filters.entityId = ''
    filters.requestId = ''
    filters.createdFrom = ''
    filters.createdTo = ''
    await applyFilters()
  }

  function openMetadataDialog(auditLog: AuditLogDomain) {
    selectedAuditLog.value = auditLog
    metadataDialogVisible.value = true
  }

  return {
    auditLogs,
    totalAuditLogs,
    loading,
    generalError,
    rows,
    first,
    nextCursor,
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
  }
}
