import type {
  BackupLogDto,
  BackupLogDomain,
  BackupLogListDto,
  BackupLogListDomain,
  BackupScheduleDto,
  BackupScheduleDomain,
} from '@/types/backups'

export function mapBackupLogDtoToDomain(dto: BackupLogDto): BackupLogDomain {
  return {
    id: dto.id,
    backupType: dto.backup_type,
    status: dto.status,
    filename: dto.filename,
    fileSize: dto.file_size,
    storagePath: dto.storage_path,
    errorMessage: dto.error_message,
    createdById: dto.created_by_id,
    createdByEmail: dto.created_by_email,
    startedAt: dto.started_at,
    completedAt: dto.completed_at,
    createdAt: dto.created_at,
  }
}

export function mapBackupLogListDtoToDomain(
  dto: BackupLogListDto,
): BackupLogListDomain {
  return {
    items: dto.items.map(mapBackupLogDtoToDomain),
    total: dto.total,
  }
}

export function mapBackupScheduleDtoToDomain(
  dto: BackupScheduleDto,
): BackupScheduleDomain {
  return {
    id: dto.id,
    name: dto.name,
    frequency: dto.frequency,
    dayOfWeek: dto.day_of_week,
    timeOfDay: dto.time_of_day,
    oneOffDatetime: dto.one_off_datetime,
    isActive: dto.is_active,
    nextRunAt: dto.next_run_at,
    lastRunAt: dto.last_run_at,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}
