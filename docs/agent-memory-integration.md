# Hướng Dẫn Tích Hợp Agent Memory

## Mục tiêu

Dự án này sử dụng một workflow memory cục bộ theo từng project để AI coding agent không bị mất những context quan trọng giữa các phiên làm việc.

## Repository được chọn

Upstream được chọn: `axiomhq/agent-memory`

Repository:
- https://github.com/axiomhq/agent-memory

Lý do chọn vào ngày 09/06/2026:

1. Được xây riêng cho AI coding agent, không phải memory chung cho chatbot.
2. Không phụ thuộc vào một harness cụ thể và hỗ trợ rõ ràng cho workflow kiểu Codex.
3. Giải đúng failure mode mà dự án này quan tâm: mất context giữa các thread.
4. Có thể sinh output tương thích `AGENTS.md` từ memory đã được cô đọng.
5. Dùng mô hình lưu trữ theo file, phù hợp để đặt trực tiếp trong repository này.

Các lựa chọn khác đã xem xét:

- `mem0ai/mem0`: https://github.com/mem0ai/mem0
Giải pháp này mạnh và rất active, nhưng là một nền tảng long-term memory rộng hơn nhu cầu thực tế của workflow coding local theo repo.

- `msitarzewski/AGENT-ZERO`: https://github.com/msitarzewski/AGENT-ZERO
Giải pháp này tốt ở góc độ operating model và Memory Bank pattern. Dự án hiện tại mượn một phần ý tưởng tổ chức memory từ đó, nhưng bản thân nó không phải một memory engine độc lập.

## Những gì đã được tích hợp

1. Bản mirror mã nguồn upstream:
   - `vendor/agent-memory/`

2. Cấu trúc persistent memory cục bộ của project:
   - `.agent-memory/inbox/`
   - `.agent-memory/orgs/default/archive/`
   - `.agent-memory/orgs/default/output-agents.md`

3. Memory Bank của project:
   - `memory-bank/`

4. Startup contract cho agent:
   - `AGENTS.md`

5. File cấu hình memory cục bộ:
   - `memory.config.json`

## Cách nó hoạt động trong repo này

Có hai lớp chính:

1. `memory-bank/`
Đây là “bộ não dự án” ở dạng con người đọc được và có tính bền vững. Agent phải đọc trước khi bắt đầu làm việc.

2. `.agent-memory/`
Đây là lớp lưu trữ theo định dạng thiên về máy, tương thích với workflow của `agent-memory`.

Luồng làm việc dự kiến:

1. Agent hoàn thành một task hoặc học được điều gì đó có giá trị lâu dài.
2. Một journal entry được ghi vào `.agent-memory/inbox/`.
3. Hệ thống memory sẽ consolidate và defrag phần kiến thức đó.
4. Kiến thức quan trọng sẽ được đẩy ngược lại vào `AGENTS.md` và `memory-bank/`.

## Cách dùng khuyến nghị

### Chế độ tối thiểu

Nếu chưa muốn cài thêm runtime dependency:

1. Luôn cập nhật `memory-bank/` sau những task có ý nghĩa.
2. Ghi các bug lặp lại vào `memory-bank/bugPatterns.md`.
3. Giữ `memory-bank/activeContext.md` luôn mới.
4. Bắt buộc mọi agent đọc `AGENTS.md` trước khi làm việc.

Chỉ riêng cách này đã giải quyết được một phần lớn vấn đề mất context.

### Chế độ đầy đủ

Nếu muốn chạy memory engine upstream ngay trên máy local:

1. Cài Bun.
2. Đi vào thư mục mirror của upstream:

```bash
cd vendor/agent-memory
```

3. Cài dependencies:

```bash
bun install
```

4. Từ thư mục gốc của project, kiểm tra cấu hình:

```bash
cat memory.config.json
```

5. Chạy health check từ thư mục upstream:

```bash
bun run src/cli/index.ts doctor
```

6. Ghi một journal entry sau mỗi task:

```bash
bun run src/cli/index.ts capture \
  --title "tóm tắt ngắn của task" \
  --body "đã thay đổi gì, đã học được gì, điều gì cần được ghi nhớ" \
  --tags "project__fastapi-vue,topic__bugs"
```

7. Chạy consolidate:

```bash
bun run src/cli/index.ts consolidate
```

8. Chạy defrag định kỳ:

```bash
bun run src/cli/index.ts defrag
```

9. Sinh AGENTS output:

```bash
bun run src/cli/index.ts generate-agents-md --org default
```

## Quy tắc vận hành

1. Không bao giờ coi memory trong hội thoại của model là durable memory.
2. Kiến thức bền vững của project phải được ghi vào `memory-bank/` hoặc `.agent-memory/`.
3. Bug pattern phải được lưu thành guardrail có thể tái sử dụng, không được chỉ tồn tại trong lịch sử chat.
4. Nếu code mâu thuẫn với tài liệu, ưu tiên xác minh theo code trước, sau đó cập nhật lại tài liệu.

## Giới hạn hiện tại

1. Snapshot hiện tại của repo chưa chứa đầy đủ application source tree, nên vẫn còn một số fact của project chưa được xác minh.
2. `memory-bank/techContext.md` đang cố ý đánh dấu các vùng chưa xác minh thay vì phỏng đoán.
3. Runtime của `agent-memory` đã được mirror về local, nhưng dependencies chưa được cài tự động trong bước setup này.
