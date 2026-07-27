#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$ROOT_DIR/vendor/mattpocock-skills/skills"
TARGET_DIR="$ROOT_DIR/.agents/skills"

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "Source skills directory not found: $SOURCE_DIR" >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"

installed=0
skipped=0

for dir in "$SOURCE_DIR"/*/*; do
  [[ -d "$dir" ]] || continue
  [[ -f "$dir/SKILL.md" ]] || continue

  name="$(basename "$dir")"
  destination="$TARGET_DIR/$name"

  if [[ -e "$destination" ]]; then
    echo "SKIP $name"
    skipped=$((skipped + 1))
    continue
  fi

  cp -a "$dir" "$destination"
  echo "INSTALLED $name"
  installed=$((installed + 1))
done

echo "Installed: $installed"
echo "Skipped: $skipped"
