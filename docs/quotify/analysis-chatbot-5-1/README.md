# Tư Liệu Phân Tích Chatbot Mục 5.1

Script thí nghiệm và kết quả đo của **Slice S0** trong [plan-telegram-chatbot-5-1-kien-truc.md](../plan-telegram-chatbot-5-1-kien-truc.md), chạy ngày 2026-10-13 bằng các agent. Tóm tắt kết quả nằm ở Phụ lục A.2 của kế hoạch; thư mục này giữ phần chứng cứ thô để tái hiện và để biến thành test hồi quy khi làm S2 và S3.

## Cấu trúc

| Thư mục | Nội dung | Phục vụ |
|---|---|---|
| `s0/pg/` | Engine DB chỉ đọc (`s0a_*`, `s0a6_*`, `s0a7_*`, `s0a8_*`), thuật toán claim hộp thư (`claimlib.py` là bản đã qua thực nghiệm, cùng các biến thể sai để làm đối chứng), kịch bản xác định (`s0c_scenarios*.py`), đua đồng thời và chaos (`s0c_race.py`, `s0c_chaos.py`), EXPLAIN và truy vấn hạn mức (`explain*.sql`, `s0c_quota_tz.py`), lược đồ `schema.sql` | S0(a), S0(c); nguồn cho test S2, S3, S6, S10 |
| `s0/telegram/` | `sendChatAction` với bot dev thật (`s0d_chat_action.py` và `s0d_typing_observation.py`, cùng kết quả; không chứa token hay chat ID, ID lấy từ biến môi trường lúc chạy) | S0(d); nguồn cho test S1 và S4 |
| `s0/arq/` | Hành vi arq 0.26.3 trên Redis 7: `_job_id`, `SIGKILL`, `SIGTERM`, hàng đợi riêng, `create_pool` khi Redis tắt hoặc `pause`, `arq --check` | S0(b); nguồn cho test S1, S3, S8 |

File `.out` là kết quả chạy thật. `pg/s0c_race_plan.out` là lần chạy đầu và có một lần hết hạn rào chắn của chính bộ chạy thử (không phải bằng chứng vi phạm bất biến, không tái hiện ở tám lần chạy sau); kết quả cuối là `s0c_race_plan_final.out`.

## Cách chạy lại

- Dùng **một container Postgres 16 tạm** (`docker run --rm ... postgres:16-bookworm`) và **một container Redis 7 tạm**, có tên riêng và xóa sau khi chạy. **Không** chạy trên database dev, stack compose của dự án hay production.
- Script Python dùng thư viện của `backend/.venv` (SQLAlchemy 2.0.50, asyncpg 0.31.0); `pg/py` là lớp bọc gọi Python của venv đó.
- Thí nghiệm arq chạy trong image `quotify-backend` (Python 3.12.12, arq 0.26.3), vì CLI `arq` cục bộ lỗi trên Python 3.14.
- Một số script (`pg/py`, `arq/*.sh`) ghi **đường dẫn tuyệt đối của phiên chạy gốc** (thư mục tạm và thư mục dự án): sửa lại cho khớp máy trước khi chạy.

## Lưu ý khi dùng làm test

- Mọi mốc thời gian truyền vào truy vấn phải **có múi giờ**: asyncpg coi `datetime` không múi giờ là giờ địa phương của tiến trình.
- Phải đưa **biến thể sai** vào bộ test (khóa dòng đơn thuần, `SKIP LOCKED`, advisory lock không có điều kiện lease) và kiểm chúng **fail**, nếu không test có thể xanh giả.
- Bộ chạy đua cần nhiều tiến trình thật, không chỉ nhiều tác vụ asyncio.
