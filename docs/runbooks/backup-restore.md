# Runbook: Backup Và Restore

## Mục tiêu

Runbook này dùng cho Postgres và MinIO trong môi trường Docker của repo.

## Tạo backup

### Postgres

```bash
bash scripts/ops/backup-postgres.sh
```

### MinIO

```bash
bash scripts/ops/backup-minio.sh
```

Mặc định backup được lưu tại:

```text
backups/<timestamp>/
```

## Restore

### Restore Postgres

```bash
bash scripts/ops/restore-postgres.sh backups/<timestamp>/postgres.sql.gz
```

### Restore MinIO

```bash
bash scripts/ops/restore-minio.sh backups/<timestamp>/minio-data.tar.gz
```

## Restore Drill

Trước khi production go-live hoặc sau thay đổi lớn:

```bash
bash scripts/ops/restore-drill.sh backups/<timestamp>
```

Checklist:

1. Restore vào môi trường cô lập, không restore trực tiếp vào production đang chạy.
2. Chạy smoke tests auth, users, files, import/export sau restore.
3. Ghi lại:
   - thời gian restore
   - lỗi gặp phải
   - dữ liệu nào xác nhận thành công
4. Không coi backup là đạt yêu cầu nếu chưa từng restore thử.

## Lưu ý vận hành

- Dùng `DRY_RUN=true` để review command trước khi chạy thật.
- Giữ retention theo `BACKUP_RETENTION_DAYS`.
- Backup phải được mã hóa và copy sang storage bền vững ở môi trường production thật.
