export interface BackupLogDto {
  id: string
  backup_type: string
  status: string
  filename: string | null
  file_size: number | null
  storage_path: string | null
  error_message: string | null
  created_by_id: string | null
  created_by_email: string | null
  started_at: string
  completed_at: string | null
  created_at: string
}

export interface BackupLogDomain {
  id: string
  backupType: string
  status: string
  filename: string | null
  fileSize: number | null
  storagePath: string | null
  errorMessage: string | null
  createdById: string | null
  createdByEmail: string | null
  startedAt: string
  completedAt: string | null
  createdAt: string
}

export interface BackupLogListDto {
  items: BackupLogDto[]
  total: number
}

export interface BackupLogListDomain {
  items: BackupLogDomain[]
  total: number
}

export interface BackupScheduleDto {
  id: string
  name: string
  frequency: string
  day_of_week: number | null
  time_of_day: string
  one_off_datetime: string | null
  is_active: boolean
  next_run_at: string | null
  last_run_at: string | null
  created_at: string
  updated_at: string
}

export interface BackupScheduleDomain {
  id: string
  name: string
  frequency: string
  dayOfWeek: number | null
  timeOfDay: string
  oneOffDatetime: string | null
  isActive: boolean
  nextRunAt: string | null
  lastRunAt: string | null
  createdAt: string
  updatedAt: string
}

export interface BackupScheduleCreatePayload {
  name: string
  frequency: 'daily' | 'weekly' | 'one_off'
  day_of_week?: number | null
  time_of_day: string
  one_off_datetime?: string | null
  is_active?: boolean
}

export interface BackupScheduleUpdatePayload {
  name: string
  frequency: 'daily' | 'weekly' | 'one_off'
  day_of_week?: number | null
  time_of_day: string
  one_off_datetime?: string | null
  is_active: boolean
}
