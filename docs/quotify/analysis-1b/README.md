# Công Cụ Phân Tích Dùng Cho Kế Hoạch 1B

Các script **chỉ đọc** dùng để đo số liệu trong [kế hoạch 1B](../plan-telegram-giai-doan-1b-engine-bien-dong-gia.md) (ngày 2026-10-04). Lưu lại vì các script backtest trước đó đã mất và không thể tái tạo số liệu của tài liệu cha. Không phải code sản phẩm: không đưa vào `backend/`, không có test, chạy trên bản sao dữ liệu dev.

Không có email, mật khẩu hay token thật trong các file này. Email tài khoản seed admin được truyền bằng biến psql `seed_email`.

## Tái tạo dữ liệu đầu vào (không commit các file CSV)

```bash
cd docs/quotify/analysis-1b
export SEED_EMAIL="<giá trị AUTH_SEED_ADMIN_EMAIL trong .env>"

# lines.csv: mọi dòng của version confirmed và superseded (phiếu chưa hủy), sắp theo confirmed_at
docker exec -i quotify-postgres-1 psql -U postgres -d app -v seed_email="$SEED_EMAIL" -f - < sql/ex8.sql > py/lines.csv

# roles.csv: id người dùng, tên role (dùng để ước lượng người nhận)
docker exec quotify-postgres-1 psql -U postgres -d app -tA -F, \
  -c "select u.id, r.name from users u join user_roles ur on ur.user_id=u.id join roles r on r.id=ur.role_id" > py/roles.csv
```

Chạy trên **DB dev** (không phải production). Đặt hai file CSV cạnh các script `.py` rồi chạy từ thư mục `py/`.

## Các file

| File | Việc |
|---|---|
| `py/engine.py` | Engine tham chiếu độc lập: cửa sổ 7 ngày làm việc, mức theo biên D4, quy tắc R1/R2/R3 nhất quán hướng, đọc `lines.csv` |
| `py/partA.py` | Phát lại cuối ngày (cấu hình của Phụ lục B.7 của tài liệu cha). Kỳ vọng: 4.532 điểm, 1.540 điểm bị báo, R1/R2/R3 = 430/638/472, 16 điểm bất thường, 19,4 tin/tuần theo chuỗi |
| `py/partB.py` đến `partB5.py` | Phát lại theo thời điểm chốt (`confirmed_at`) với nguồn kích hoạt D6, chặn bất thường D12 mức dòng, chống lặp D5(a), gộp tin D5(b), ước lượng người nhận D8 |
| `py/price_chart_prototype.py` | Mẫu vẽ biểu đồ 14 ngày bằng matplotlib (API hướng đối tượng, `asyncio.to_thread`). Ảnh mẫu: `chart_prototype.png`. Có 7 lỗi mypy strict do `matplotlib.dates`; bản chính thức phải tránh |
| `sql/ex8.sql` | Xuất `lines.csv` |
| `sql/ex6.sql` | Xuất các cặp version điều chỉnh (nguồn và kế nhiệm) |
| `sql/q2*.sql`, `q3.sql`, `q4.sql`, `q5*.sql`, `q6c.sql`, `q9.sql` | Truy vấn đo số liệu: phân bố tài khoản seed và người thật, độ trễ ngày làm việc, 60 ngày gần nhất, `delivery_month`, cuối tuần, trùng khóa dòng, dòng nhập thật theo tuần ISO |

Chạy một truy vấn: `docker exec -i quotify-postgres-1 psql -U postgres -d app -v seed_email="$SEED_EMAIL" -f - < sql/q3.sql`.

## Giới hạn đã biết

- Engine mô phỏng chu kỳ quét 2 phút bằng gộp theo thời điểm chốt; không mô phỏng người bấm "Giá đúng" (bất thường bị loại vĩnh viễn trong mô phỏng).
- Danh sách người nhận (D8) là ước lượng theo `quotes.created_by_id` trong 90 ngày.
- Các số liệu là của DB dev tại 2026-10-04 (khôi phục từ dump 2026-10-02 cộng dữ liệu nhập sau đó), không phải production.
