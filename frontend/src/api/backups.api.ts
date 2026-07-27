import { apiRequest } from '@/api/http'
import {
  mapBackupLogDtoToDomain,
  mapBackupLogListDtoToDomain,
  mapBackupScheduleDtoToDomain,
} from '@/api/backups.mappers'
import type {
  BackupLogDomain,
  BackupLogDto,
  BackupLogListDomain,
  BackupLogListDto,
  BackupScheduleCreatePayload,
  BackupScheduleDomain,
  BackupScheduleDto,
  BackupScheduleUpdatePayload,
} from '@/types/backups'

export function listBackupLogs(
  limit: number,
  offset: number,
  accessToken?: string | null,
): Promise<BackupLogListDomain> {
  return apiRequest<BackupLogListDto>(
    `/backups?limit=${limit}&offset=${offset}`,
    {
      accessToken,
    },
  ).then(mapBackupLogListDtoToDomain)
}

export function triggerBackupNow(
  accessToken?: string | null,
): Promise<BackupLogDomain> {
  return apiRequest<BackupLogDto>('/backups/now', {
    method: 'POST',
    accessToken,
  }).then(mapBackupLogDtoToDomain)
}

export function listBackupSchedules(
  accessToken?: string | null,
): Promise<BackupScheduleDomain[]> {
  return apiRequest<BackupScheduleDto[]>('/backups/schedules', {
    accessToken,
  }).then((dtos) => dtos.map(mapBackupScheduleDtoToDomain))
}

export function createBackupSchedule(
  payload: BackupScheduleCreatePayload,
  accessToken?: string | null,
): Promise<BackupScheduleDomain> {
  return apiRequest<BackupScheduleDto>('/backups/schedules', {
    method: 'POST',
    body: JSON.stringify(payload),
    accessToken,
  }).then(mapBackupScheduleDtoToDomain)
}

export function updateBackupSchedule(
  scheduleId: string,
  payload: BackupScheduleUpdatePayload,
  accessToken?: string | null,
): Promise<BackupScheduleDomain> {
  return apiRequest<BackupScheduleDto>(`/backups/schedules/${scheduleId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
    accessToken,
  }).then(mapBackupScheduleDtoToDomain)
}

export function deleteBackupSchedule(
  scheduleId: string,
  accessToken?: string | null,
): Promise<void> {
  return apiRequest<void>(`/backups/schedules/${scheduleId}`, {
    method: 'DELETE',
    accessToken,
  })
}
