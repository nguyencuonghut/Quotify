# Runbook: Deploy Production trên VPS (không dùng CI/CD)

Áp dụng cho: VPS thuê ngoài, domain `quotify.honghafeed.com.vn`, build/deploy
Docker trực tiếp qua SSH (không có pipeline CI/CD tự động chạy `git push`).

Runbook này bổ sung chi tiết vận hành cho lần deploy **đầu tiên** lên VPS.
Với rollback/restore và các lần deploy tiếp theo, dùng chung
`docs/runbooks/deploy-rollback-restore.md`.

## 0. Yêu cầu trước khi bắt đầu

- VPS đã cài Docker Engine + Docker Compose plugin (`docker compose version`).
- Đã trỏ DNS: bản ghi `A` của `quotify.honghafeed.com.vn` → IP public của VPS.
  Kiểm tra đã lan truyền trước khi xin chứng chỉ TLS:

  ```bash
  dig +short quotify.honghafeed.com.vn
  ```

- Firewall VPS mở cổng `22` (SSH), `80` (HTTP/ACME challenge), `443` (HTTPS).
  Không public thêm cổng nào khác (Postgres/MinIO/Redis không được expose ra
  ngoài — đã đúng theo `docker-compose.prod.yml`).
- Có quyền SSH vào VPS bằng tài khoản không phải `root` và trong group `docker`.
- Repo Git có quyền truy cập từ VPS (SSH deploy key hoặc HTTPS + token), vì
  quy trình này pull code trực tiếp trên VPS, không qua CI/CD.

## 1. Chuẩn bị mã nguồn trên VPS

```bash
ssh <user>@<vps-ip>
git clone <repo-url> /opt/quotify   # lần đầu
cd /opt/quotify
```

Các lần deploy sau chỉ cần `git pull` trong thư mục này (xem bước 6).

## 2. Tạo `.env` production thật

```bash
cp .env.production.example .env
```

Sửa `.env` — **không commit file này**, chỉ tồn tại trên VPS:

- `DOMAIN_NAME=quotify.honghafeed.com.vn`
- `CORS_ORIGINS=https://quotify.honghafeed.com.vn`
- `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET_KEY`,
  `MINIO_SECRET_KEY`: thay toàn bộ giá trị `change-me-*` bằng giá trị thật,
  sinh ngẫu nhiên đủ mạnh (ví dụ `openssl rand -hex 32`).
- `AUTH_SEED_ADMIN_EMAIL`/`AUTH_SEED_ADMIN_PASSWORD`: email + mật khẩu thật
  của tài khoản admin đầu tiên. Không được để `change-me-admin-password` —
  `seed_auth_rbac.py` sẽ tự chặn nếu còn placeholder.
- `AUTH_SEED_UPDATE_ADMIN_PASSWORD=false` (giữ `false` sau lần setup đầu).
- `CERTBOT_EMAIL`: email thật dùng để đăng ký với Let's Encrypt (nhận cảnh
  báo hết hạn cert nếu renew tự động thất bại).
- `PROXY_HTTP_PORT=80`, `PROXY_HTTPS_PORT=443` (giữ mặc định nếu VPS không
  chạy web server khác trên 2 cổng này).

## 3. Build image production qua SSH (không CI/CD)

```bash
docker compose -f docker-compose.prod.yml build backend frontend worker
```

## 4. Bootstrap chứng chỉ TLS (chỉ chạy 1 lần, trước khi `up` lần đầu)

`reverse-proxy` (Nginx) trong `docker-compose.prod.yml` đọc chứng chỉ từ
`/etc/letsencrypt/live/quotify.honghafeed.com.vn/` (volume `certbot_conf`).
Nginx sẽ **không start được** nếu volume này chưa có chứng chỉ — nên phải
xin chứng chỉ trước, bằng plugin `standalone` của certbot (tự bind tạm cổng
80, chưa cần Nginx đang chạy):

```bash
docker compose -f docker-compose.prod.yml run --rm -p 80:80 --entrypoint certbot certbot \
  certonly --standalone \
  -d quotify.honghafeed.com.vn \
  --email "$(grep '^CERTBOT_EMAIL=' .env | cut -d= -f2)" \
  --agree-tos --non-interactive
```

Kiểm tra chứng chỉ đã được tạo trong volume:

```bash
docker compose -f docker-compose.prod.yml run --rm --entrypoint ls certbot \
  /etc/letsencrypt/live/quotify.honghafeed.com.vn
```

Phải thấy `fullchain.pem` và `privkey.pem`.

## 5. Migrate + seed + lên stack

```bash
# Migrate — tạo đầy đủ toàn bộ table (đã bao gồm seed idempotent quotify_settings)
docker compose -f docker-compose.prod.yml up -d postgres redis minio
docker compose -f docker-compose.prod.yml run --rm backend uv run alembic upgrade head

# Seed vừa đủ: 1 admin + permissions/roles
docker compose -f docker-compose.prod.yml run --rm backend uv run python scripts/seed_auth_rbac.py

# Seed danh mục vật tư (material types + materials — không kèm nhà cung cấp/user)
docker compose -f docker-compose.prod.yml run --rm backend uv run python scripts/seed_quotify_catalog.py

# Lên toàn bộ stack, bao gồm reverse-proxy (giờ start được vì cert đã có) và
# service certbot chạy nền để tự renew (loop `certbot renew` mỗi 12h)
docker compose -f docker-compose.prod.yml up -d
```

Ghi chú: dùng `docker compose ... run --rm backend uv run alembic ...` (one-off
container) ở lần đầu vì tại thời điểm này `backend` service có thể chưa có
container nào đang chạy khoẻ mạnh để `exec` vào. Từ lần deploy thứ 2 trở đi,
sau khi `up -d` đã chạy ổn định, có thể dùng `make migrate-prod`/
`make seed-prod-auth`/`make seed-prod-catalog` (đã trỏ đúng `docker-compose.prod.yml`,
dùng `exec` vào container đang chạy — xem `docs/runbooks/deploy-rollback-restore.md`).

Không seed `scripts/seed_quotify.py` nguyên bản — script này seed thêm nhà
cung cấp mẫu (không phải dữ liệu thật) và 7 tài khoản thật dùng chung mật khẩu
hard-code trong source. Nhà cung cấp thật và tài khoản Thu Mua tạo thủ công ở
bước 8.

## 6. Verify

```bash
curl -I https://quotify.honghafeed.com.vn/health
curl -I https://quotify.honghafeed.com.vn/
```

Checklist (theo `docs/runbooks/deploy-rollback-restore.md`):

- `/health`, `/ready`, `/metrics` trả 200 qua HTTPS.
- Đăng nhập bằng tài khoản admin đã seed ở bước 5.
- Trang danh sách users, upload/download file hoạt động.
- Tạo một audit event, xác nhận IP ghi nhận đúng (WAN thật của người dùng,
  không phải IP nội bộ Docker) — vì `TRUSTED_PROXY_CIDRS=172.30.0.0/24` đã
  đúng với subnet compose mặc định.
- Trình duyệt hiển thị khoá HTTPS hợp lệ (chứng chỉ Let's Encrypt), không có
  cảnh báo mixed-content.

## 7. TLS renew — tự động, nhưng cần xác nhận theo lịch

Service `certbot` trong stack chạy nền, gọi `certbot renew --webroot` mỗi 12h
(chỉ thực sự renew khi cert còn ít hơn 30 ngày là hết hạn — hành vi mặc định
của certbot). Vì Nginx không tự đọc lại cert mới sau khi certbot renew ghi đè
file, cần reload Nginx định kỳ (đặt cron trên VPS, ví dụ đầu tháng):

```bash
# crontab -e trên VPS
0 3 1 * * cd /opt/quotify && docker compose -f docker-compose.prod.yml exec reverse-proxy nginx -s reload
```

## 8. Sau khi hệ thống chạy ổn: tạo dữ liệu thật thủ công

Không có trong bất kỳ seed script nào — tạo qua UI/API sau khi đăng nhập bằng
admin:

- Nhà cung cấp thật (danh sách mẫu trong `seed_data.py` không phải dữ liệu
  thật, không dùng).
- 7 tài khoản phòng Thu Mua thật — mỗi người một mật khẩu riêng, không dùng
  mật khẩu chung.

## 9. Deploy các lần tiếp theo (không phải lần đầu)

```bash
cd /opt/quotify
git pull
docker compose -f docker-compose.prod.yml build backend frontend worker
make migrate-prod
docker compose -f docker-compose.prod.yml up -d
```

`seed-prod-auth`/`seed-prod-catalog` là idempotent — chỉ cần chạy lại khi có
thay đổi permission mới hoặc mã vật tư mới, không bắt buộc mỗi lần deploy.

Trước khi build/migrate, luôn backup (`bash scripts/ops/backup-postgres.sh`,
`bash scripts/ops/backup-minio.sh`) theo Waiver Rule ở
`docs/runbooks/deploy-rollback-restore.md`. Hai script này dùng `docker compose`
không kèm `-f`, nên chạy trong thư mục `/opt/quotify` với biến môi trường:

```bash
export COMPOSE_FILE=docker-compose.prod.yml
bash scripts/ops/backup-postgres.sh
bash scripts/ops/backup-minio.sh
```

## 10. Rollback

Theo `docs/runbooks/deploy-rollback-restore.md` — checkout lại commit/tag
trước đó trên VPS (`git checkout <ref>`), build lại image, `up -d`. Không
downgrade migration mù quáng nếu schema không backward-compatible.
