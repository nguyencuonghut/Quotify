#!/usr/bin/env bash

set -euo pipefail

agent="generic"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)
      agent="${2:-generic}"
      shift 2
      ;;
    -h|--help)
      cat <<'EOF'
Usage:
  bash scripts/agent-startup.sh [--agent codex|claude|gemini]
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

required_files=(
  "AGENTS.md"
  "docs/agent-rules.md"
  "docs/agent-memory-integration.md"
  "memory-bank/quick-start.md"
  "memory-bank/activeContext.md"
  "memory-bank/progress.md"
  "memory-bank/projectRules.md"
  "memory-bank/techContext.md"
)

optional_files=(
  "memory-bank/systemPatterns.md"
  "memory-bank/bugPatterns.md"
  ".agent-memory/orgs/default/output-agents.md"
)

echo "=== AGENT STARTUP CHECKLIST ==="
echo "Agent: $agent"
echo "Repo: $root_dir"
echo
echo "Bat buoc phai doc truoc khi lam task:"
for file in "${required_files[@]}"; do
  if [[ -f "$root_dir/$file" ]]; then
    echo "[OK] $file"
  else
    echo "[MISSING] $file"
  fi
done

echo
echo "Nen doc them neu task lien quan:"
for file in "${optional_files[@]}"; do
  if [[ -f "$root_dir/$file" ]]; then
    echo "[OK] $file"
  else
    echo "[MISSING] $file"
  fi
done

echo
echo "Xac nhan bat buoc truoc khi code:"
echo "- Da doc AGENTS.md va docs/agent-rules.md"
echo "- Da phan biet ro verified va unverified"
echo "- Da kiem tra bug cu neu task thay doi hanh vi"
echo "- Se ghi .agent-memory khi task tao ra kien thuc ben vung"
