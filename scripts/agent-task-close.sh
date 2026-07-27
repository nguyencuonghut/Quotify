#!/usr/bin/env bash

set -euo pipefail

agent="generic"
title=""
summary=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)
      agent="${2:-generic}"
      shift 2
      ;;
    --title)
      title="${2:-}"
      shift 2
      ;;
    --summary)
      summary="${2:-}"
      shift 2
      ;;
    -h|--help)
      cat <<'EOF'
Usage:
  bash scripts/agent-task-close.sh --agent codex|claude|gemini --title "..." --summary "..."
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$title" || -z "$summary" ]]; then
  echo "Both --title and --summary are required." >&2
  exit 1
fi

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
session_log="$root_dir/memory-bank/session-log.md"
timestamp="$(date -u +"%Y-%m-%d %H:%M:%SZ")"

memory_harness="$agent"
case "$agent" in
  codex|amp|pi|manual)
    ;;
  claude|gemini|generic)
    memory_harness="manual"
    ;;
  *)
    memory_harness="manual"
    ;;
esac

bash "$root_dir/scripts/agent-memory-capture.sh" \
  --title "$title" \
  --body "$summary" \
  --harness "$memory_harness"

if [[ ! -f "$session_log" ]]; then
  cat > "$session_log" <<'EOF'
# Session Log

Nhật ký append-only cho các lần đóng task của agent.
EOF
fi

cat >> "$session_log" <<EOF

## $timestamp - $agent

- Tieu de: $title
- Tom tat: $summary
EOF

echo "Da ghi journal vao .agent-memory va cap nhat memory-bank/session-log.md"
