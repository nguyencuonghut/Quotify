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
  ngoài — đã đúng theo `docker-compose.prod.yml`). Postgres/MinIO console có
  publish port nhưng CHỈ bind vào `127.0.0.1` của VPS (không phải `0.0.0.0`),
  dùng để SSH tunnel — xem mục 11 — nên không cần mở thêm gì trên firewall.
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

Sửa `.env` — **không commit file này**, chỉ tồn tại trên VPS.

### 2.1 Domain và CORS

```
DOMAIN_NAME=quotify.honghafeed.com.vn
CORS_ORIGINS=https://quotify.honghafeed.com.vn
```

### 2.2 Sinh từng secret bắt buộc — lệnh cụ thể

Thay **toàn bộ** giá trị `change-me-*` trong `.env` bằng giá trị thật. Chạy
từng lệnh dưới đây trên VPS (hoặc máy cá nhân rồi copy qua kênh an toàn) và
dán kết quả vào đúng biến tương ứng:

| Biến trong `.env`                        | Lệnh sinh giá trị                          | Ghi chú                                                    |
| ----------------------------------------- | ------------------------------------------- | ------------------------------------------------------------ |
| `JWT_SECRET_KEY`                          | `openssl rand -hex 32`                      | Ký access token — chạy riêng, không trùng với refresh secret |
| `JWT_REFRESH_SECRET_KEY`                  | `openssl rand -hex 32`                      | Chạy **lần thứ 2**, phải khác `JWT_SECRET_KEY` ở trên         |
| `POSTGRES_PASSWORD`                       | Xem mục 2.3 bên dưới                        | Có thể tự chọn mật khẩu nhớ được — xem cách xử lý ký tự đặc biệt |
| `MINIO_ACCESS_KEY`                        | `openssl rand -hex 12`                      | Đổi khỏi mặc định `minioadmin` của image — dùng làm username |
| `MINIO_SECRET_KEY`                        | `openssl rand -base64 32`                   | Không cần nhớ, chỉ máy-tới-máy dùng                          |
| `AUTH_SEED_ADMIN_PASSWORD`                | Tự chọn, hoặc `openssl rand -base64 18`     | Mật khẩu admin đầu tiên — người dùng thật sẽ gõ để đăng nhập  |

Ví dụ chạy nhanh cả loạt (rồi copy từng dòng in ra vào `.env`):

```bash
echo "JWT_SECRET_KEY=$(openssl rand -hex 32)"
echo "JWT_REFRESH_SECRET_KEY=$(openssl rand -hex 32)"
echo "MINIO_ACCESS_KEY=$(openssl rand -hex 12)"
echo "MINIO_SECRET_KEY=$(openssl rand -base64 32)"
echo "AUTH_SEED_ADMIN_PASSWORD=$(openssl rand -base64 18)"
```

Sau khi sinh xong:

- `AUTH_SEED_ADMIN_EMAIL`: email thật của tài khoản admin đầu tiên. Không
  được để nguyên `change-me-admin-password` cho mật khẩu —
  `seed_auth_rbac.py` sẽ tự chặn nếu còn placeholder.
- `AUTH_SEED_UPDATE_ADMIN_PASSWORD=false` (giữ `false` sau lần setup đầu).
- `CERTBOT_EMAIL`: email thật dùng để đăng ký với Let's Encrypt (nhận cảnh
  báo hết hạn cert nếu renew tự động thất bại).
- `PROXY_HTTP_PORT=80`, `PROXY_HTTPS_PORT=443` (giữ mặc định nếu VPS không
  chạy web server khác trên 2 cổng này).

**Quan trọng — `docker-compose.prod.yml` đọc đúng các giá trị này từ `.env`**
(đã sửa ngày 15/08/2026): trước đây `POSTGRES_PASSWORD`/`MINIO_ROOT_USER`/
`MINIO_ROOT_PASSWORD`/`DATABASE_URL` bị hard-code cứng ngay trong compose
file, khiến việc đổi giá trị trong `.env` **không có tác dụng gì** — Postgres
luôn chạy với mật khẩu `postgres`, MinIO luôn chạy với `minioadmin`/`minioadmin`
bất kể `.env` ghi gì. Đã sửa để `postgres`/`minio` đọc `${POSTGRES_PASSWORD}`/
`${MINIO_ACCESS_KEY}`/`${MINIO_SECRET_KEY}` từ `.env` thật, và bắt buộc phải
có giá trị (`docker compose up` sẽ báo lỗi rõ ràng và dừng lại nếu bạn quên
đặt, thay vì âm thầm dùng mật khẩu yếu mặc định của image).

### 2.3 Mật khẩu Postgres có ký tự đặc biệt (ví dụ `Hongha@#2026`)

`POSTGRES_PASSWORD` dùng trực tiếp cho container Postgres nên **giữ nguyên
mật khẩu gốc, không cần mã hóa gì**:

```
POSTGRES_PASSWORD=Hongha@#2026
```

Nhưng `DATABASE_URL` là một **connection URI** (`postgresql+asyncpg://user:pass@host:port/db`),
trong đó ký tự `@` là dấu phân cách giữa phần thông tin đăng nhập và host. Nếu
dán thẳng mật khẩu có `@` vào URI, phần parse sẽ hiểu sai — ví dụ mật khẩu
`Hongha@#2026` sẽ khiến thư viện đọc nhầm host thành `#2026@postgres` thay vì
`postgres` (đã kiểm chứng thực tế: request tới database sẽ lỗi kết nối do
"không tìm thấy host" kiểu này). Cách đúng là **mã hóa phần trăm (percent-encode)
riêng đoạn mật khẩu** trước khi ghép vào `DATABASE_URL` — dùng lệnh sau:

```bash
python3 -c "import urllib.parse; print(urllib.parse.quote('Hongha@#2026', safe=''))"
# In ra: Hongha%40%232026
```

Rồi ghép vào `DATABASE_URL` (chỉ đoạn mật khẩu được mã hóa, phần còn lại giữ
nguyên):

```
DATABASE_URL=postgresql+asyncpg://postgres:Hongha%40%232026@postgres:5432/app
```

Tóm tắt quy tắc: **`POSTGRES_PASSWORD` = mật khẩu gốc, `DATABASE_URL` = mật
khẩu đã percent-encode**. Áp dụng lệnh `urllib.parse.quote(..., safe='')` ở
trên cho bất kỳ mật khẩu nào có ký tự đặc biệt (`@`, `#`, `:`, `/`, `%`, khoảng
trắng...), kể cả khi bạn tự chọn mật khẩu khác không phải ví dụ trên.

Nếu muốn tránh hoàn toàn bước mã hóa này, có thể sinh mật khẩu ngẫu nhiên chỉ
gồm chữ/số (không ký tự đặc biệt) thay vì tự chọn:

```bash
openssl rand -base64 24 | tr -dc 'A-Za-z0-9'
```

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

## 11. Kết nối DB từ xa bằng DBeaver qua SSH tunnel

Postgres production **không** publish port ra internet (đúng theo yêu cầu ở
mục 0 — không public thêm cổng nào ngoài `22`/`80`/`443`). `docker-compose.prod.yml`
chỉ bind port Postgres vào `127.0.0.1` của chính VPS:

```yaml
ports:
  - "127.0.0.1:5432:5432"
```

Nghĩa là port `5432` chỉ nghe được từ các tiến trình chạy ngay trên VPS — kể
cả một kết nối SSH tunnel từ máy cá nhân cũng được tính là "chạy trên VPS" ở
phía server, nên đây là cách an toàn để DBeaver kết nối từ xa mà không cần mở
thêm port nào ra ngoài.

**Cách 1 — DBeaver tự tạo SSH tunnel (khuyên dùng, không cần mở terminal riêng):**

1. DBeaver → New Database Connection → PostgreSQL.
2. Tab **Main**:
   - Host: `localhost` (hoặc `127.0.0.1`) — vì tunnel sẽ làm cho port này
     "xuất hiện" ngay trên máy cá nhân, không phải điền IP VPS ở đây.
   - Port: `5432`
   - Database: giá trị `POSTGRES_DB` trong `.env` (mặc định `app`).
   - Username: giá trị `POSTGRES_USER` trong `.env` (mặc định `postgres`).
   - Password: giá trị `POSTGRES_PASSWORD` thật trong `.env` trên VPS (mật
     khẩu gốc, KHÔNG phải bản percent-encode dùng trong `DATABASE_URL` — xem
     mục 2.3).
3. Tab **SSH**:
   - Tích **Use SSH Tunnel**.
   - Host/IP: IP public của VPS.
   - Port: `22`.
   - User Name: tài khoản SSH không phải `root` (theo yêu cầu ở mục 0).
   - Authentication Method: **Public Key** → trỏ tới private key (`.pem`/`id_rsa`)
     dùng để SSH vào VPS, hoặc **Password** nếu VPS cho phép đăng nhập bằng
     mật khẩu.
4. **Test Connection** — DBeaver sẽ tự SSH vào VPS, mở tunnel tới
   `127.0.0.1:5432` trên VPS, rồi mới kết nối Postgres qua tunnel đó.

**Cách 2 — Tự mở SSH tunnel bằng terminal, DBeaver kết nối như DB local:**

```bash
ssh -N -L 5432:127.0.0.1:5432 <ssh-user>@<vps-ip>
```

Giữ terminal này chạy (không trả về prompt là bình thường — `-N` nghĩa là
không mở shell, chỉ forward port). Khi đó, DBeaver chỉ cần kết nối PostgreSQL
bình thường tới `localhost:5432` (KHÔNG cần cấu hình tab SSH trong DBeaver
nữa, vì tunnel đã có sẵn ở tầng hệ điều hành).

Đóng terminal (hoặc `Ctrl+C`) sẽ đóng tunnel — chạy lại lệnh trên khi cần kết
nối lại.

**Lưu ý bảo mật:**

- Không bao giờ đổi `"127.0.0.1:5432:5432"` thành `"5432:5432"` hoặc
  `"0.0.0.0:5432:5432"` — làm vậy sẽ public thẳng Postgres ra internet, vi
  phạm yêu cầu firewall ở mục 0 (đã kiểm chứng bằng `docker compose config`:
  `host_ip: 127.0.0.1` xác nhận chỉ bind loopback).
- Không cần mở thêm port nào trên firewall VPS cho việc này — mọi kết nối đều
  đi qua cổng `22` (SSH) đã mở sẵn.
- Áp dụng đúng cách này cho MinIO console (port `9001`) nếu cần xem trực tiếp
  qua trình duyệt: `ssh -N -L 9001:127.0.0.1:9001 <ssh-user>@<vps-ip>`, rồi mở
  `http://localhost:9001` trên máy cá nhân (MinIO console hiện cũng không
  publish port ra ngoài).
