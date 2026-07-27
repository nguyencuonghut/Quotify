# CLAUDE.md

Nguồn chỉ dẫn chuẩn của repository này là `AGENTS.md`.

Trước khi bắt đầu bất kỳ task nào, Claude Code phải đọc theo thứ tự:

1. `AGENTS.md`
2. `docs/agent-rules.md`
3. `docs/agent-memory-integration.md`
4. `memory-bank/quick-start.md`
5. `memory-bank/activeContext.md`
6. `memory-bank/progress.md`
7. `memory-bank/projectRules.md`
8. `memory-bank/techContext.md`

Nếu task liên quan tới kiến trúc, bug cũ, hoặc thay đổi hành vi, phải đọc thêm:

1. `memory-bank/systemPatterns.md`
2. `memory-bank/bugPatterns.md`

Khi kết thúc task có kiến thức bền vững, phải:

1. cập nhật `memory-bank/`
2. ghi journal vào `.agent-memory/inbox/`

Lệnh chuẩn:

```bash
bash scripts/agent-task-close.sh --agent claude --title "<ten task>" --summary "<tom tat ben vung>"
```

Nếu `CLAUDE.md` và `AGENTS.md` có điểm nào mâu thuẫn, `AGENTS.md` là nguồn sự thật cao hơn.
