# Tự Động Đọc Rule Và Ghi Memory

## Trả lời ngắn

Không có cách tuyệt đối để ép mọi AI agent tự động làm đúng nếu bản thân tool không hỗ trợ hook hoặc startup script bắt buộc.

Tuy nhiên, trong phạm vi repository này, có thể đạt mức gần như tự động bằng 3 lớp:

1. `AGENTS.md` là entrypoint bắt buộc mà agent sẽ tự đọc khi vào repo.
2. `AGENTS.md` ép agent phải đọc tiếp `docs/agent-rules.md` và các file trong `memory-bank/`.
3. Có script chuẩn để agent ghi vào `.agent-memory/inbox/` sau mỗi task.

Với việc bạn dùng đồng thời Codex, Claude Code và Gemini trong VSCode, repo này đã được bổ sung thêm các lớp phụ trợ riêng cho cả 3:

1. `AGENTS.md` cho luồng chuẩn dùng chung
2. `CLAUDE.md` cho Claude Code
3. `GEMINI.md` cho Gemini
4. `.vscode/tasks.json` để chạy checklist và đóng task ngay trong VSCode

## Những gì repo này đang làm

### 1. Buộc đọc rule qua `AGENTS.md`

`AGENTS.md` hiện yêu cầu agent phải đọc theo thứ tự:

1. `AGENTS.md`
2. `docs/agent-rules.md`
3. `docs/agent-memory-integration.md`
4. `memory-bank/quick-start.md`
5. `memory-bank/activeContext.md`
6. `memory-bank/progress.md`
7. `memory-bank/projectRules.md`
8. `memory-bank/techContext.md`

Điểm quan trọng là đa số coding agents hỗ trợ `AGENTS.md` sẽ tự nạp file này đầu tiên. Vì vậy đây là nơi đúng nhất để đặt startup contract.

### 2. Bắt buộc xác nhận đã đọc

`AGENTS.md` cũng yêu cầu agent phải xác nhận:

- đã đọc những file nào
- phần nào đã được xác minh
- có bug pattern cũ nào liên quan hay không
- cuối task có ghi `.agent-memory` hay không

Việc này không phải hook cứng ở cấp hệ thống, nhưng là contract rất hiệu quả trong thực tế.

### 3. Có lệnh chuẩn để ghi `.agent-memory`

Script đã được thêm:

```bash
scripts/agent-memory-capture.sh --title "<task title>" --body "<durable summary>"
```

Script này ghi đúng định dạng journal queue mà `axiomhq/agent-memory` sử dụng, vào:

```text
.agent-memory/inbox/
```

Ngoài ra còn có wrapper đầy đủ hơn:

```bash
bash scripts/agent-task-close.sh --agent codex --title "<task title>" --summary "<durable summary>"
```

Wrapper này sẽ:

1. ghi journal vào `.agent-memory/inbox/`
2. append một bản ghi ngắn vào `memory-bank/session-log.md`

### 4. Có startup checklist dùng chung cho cả 3 agent

Script:

```bash
bash scripts/agent-startup.sh --agent codex
```

Script này không thể ép plugin phải “đọc hộ” file, nhưng nó tạo ra checklist thống nhất để bạn hoặc agent dùng làm bước mở đầu của mỗi phiên.

## Cách dùng khuyến nghị

### Khi bắt đầu task

Ưu tiên dùng script:

```bash
bash scripts/agent-startup.sh --agent codex
bash scripts/agent-startup.sh --agent claude
bash scripts/agent-startup.sh --agent gemini
```

Sau khi chạy script, agent nên:

1. đọc các file bắt buộc theo checklist đã in ra
2. báo lại phần nào đã verify, phần nào chưa verify
3. xác nhận có bug cũ liên quan hay không
4. xác nhận cuối task có cần ghi `.agent-memory` hay không

Bạn cũng có thể chạy nhanh trong VSCode:

1. `Terminal: Run Task`
2. Chọn `Agent: Startup Checklist`

### Khi kết thúc task

Nếu task tạo ra kiến thức bền vững, agent nên:

1. cập nhật `memory-bank/`
2. ưu tiên dùng wrapper chuẩn:

```bash
bash scripts/agent-task-close.sh --agent codex --title "Sửa bug phân quyền API nhân sự" --summary "Root cause: thiếu kiểm tra role ở service layer. Fix: thêm authorization guard và test hồi quy."
```

Hoặc:

```bash
bash scripts/agent-memory-capture.sh \
  --title "Sửa bug phân quyền API nhân sự" \
  --body "Root cause: thiếu kiểm tra role ở service layer. Fix: thêm authorization guard và test hồi quy."
```

Hoặc dùng task hoàn chỉnh trong VSCode:

1. `Terminal: Run Task`
2. Chọn `Agent: Task Close`
3. Chọn agent: `codex`, `claude`, hoặc `gemini`
4. Nhập title và summary

### Workflow ngắn gọn nên dùng hằng ngày

1. Mở repo ở thư mục gốc.
2. Chạy `Agent: Startup Checklist` hoặc `bash scripts/agent-startup.sh --agent <ten-agent>`.
3. Làm task với agent tương ứng.
4. Nếu task tạo ra kiến thức bền vững, chạy `Agent: Task Close` hoặc `bash scripts/agent-task-close.sh ...`.
5. Kiểm tra `memory-bank/session-log.md` và `.agent-memory/inbox/` nếu cần xác nhận đã lưu memory.

## Nếu muốn tự động hơn nữa

Bạn có thể làm thêm các bước sau:

1. Luôn mở agent từ thư mục gốc của repo để nó tự đọc `AGENTS.md`.
2. Dùng một câu lệnh mở đầu cố định như:

```text
Đọc AGENTS.md, docs/agent-rules.md, memory-bank/* bắt buộc trước khi làm việc.
```

3. Nếu tool đang dùng hỗ trợ command wrapper hoặc custom launcher, hãy bọc agent bằng script startup riêng để:
   - in checklist phải đọc
   - kiểm tra các file bắt buộc có tồn tại
   - nhắc ghi `.agent-memory` khi kết thúc

4. Nếu tool hỗ trợ hook thật sự, hãy thêm:
   - pre-task hook: kiểm tra đã đọc rule chưa
   - post-task hook: ghi journal vào `.agent-memory/inbox/`

## Kết luận

Trong repo này, cách đáng tin nhất là:

1. dùng `AGENTS.md` làm contract bắt buộc
2. dùng `memory-bank/` làm bộ nhớ bền vững cho con người và agent
3. dùng `CLAUDE.md` và `GEMINI.md` để các plugin khác trỏ ngược về contract chung
4. dùng `scripts/agent-startup.sh` để chuẩn hóa bước mở đầu
5. dùng `scripts/agent-task-close.sh` để chuẩn hóa bước đóng task và ghi `.agent-memory`

Nói ngắn gọn: không thể ép tuyệt đối ở mọi AI tool, nhưng với cấu hình hiện tại, bạn đã có cách mạnh và thực dụng nhất ở cấp repository.
