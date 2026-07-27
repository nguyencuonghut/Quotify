#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/agent-memory-capture.sh --title "..." --body "..." [--harness codex|manual|amp|pi] [--repo "..."]

Description:
  Writes a journal entry to .agent-memory/inbox/ using the agent-memory queue format.
EOF
}

title=""
body=""
harness="codex"
repo=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --title)
      title="${2:-}"
      shift 2
      ;;
    --body)
      body="${2:-}"
      shift 2
      ;;
    --harness)
      harness="${2:-}"
      shift 2
      ;;
    --repo)
      repo="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$title" || -z "$body" ]]; then
  usage >&2
  exit 1
fi

case "$harness" in
  amp|pi|codex|manual)
    ;;
  *)
    echo "Invalid harness: $harness" >&2
    exit 1
    ;;
esac

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
inbox_dir="$root_dir/.agent-memory/inbox"
processed_dir="$inbox_dir/.processed"

mkdir -p "$inbox_dir" "$processed_dir"

timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
filename_ts="$(printf '%s' "$timestamp" | sed 's/[:.]/-/g')"
rand_id="$(od -An -N4 -tx4 /dev/urandom | tr -d ' \n' | cut -c1-6)"
file_path="$inbox_dir/${filename_ts}_${harness}_${rand_id}.json"

escaped_content="$(printf '# %s\n\n%s\n' "$title" "$body" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')"
escaped_cwd="$(printf '%s' "$root_dir" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')"

if [[ -n "$repo" ]]; then
  escaped_repo="$(printf '%s' "$repo" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')"
  repo_line=",\n    \"repo\": ${escaped_repo}"
else
  repo_line=""
fi

json_content="$(cat <<EOF
{
  "version": "1",
  "timestamp": "$timestamp",
  "harness": "$harness",
  "retrieval": {
    "method": "file",
    "content": $escaped_content
  },
  "context": {
    "cwd": $escaped_cwd$repo_line
  }
}
EOF
)"

printf '%s\n' "$json_content" > "$file_path"
echo "$file_path"
