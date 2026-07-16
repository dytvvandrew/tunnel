#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: bash scripts/restore_runtime.sh runtime_backups/tunnel_runtime_xxx.tar.gz" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ARCHIVE="$1"
if [[ ! -f "$ARCHIVE" ]]; then
  echo "Archive not found: $ARCHIVE" >&2
  exit 1
fi

tar -xzf "$ARCHIVE" -C "$ROOT_DIR"
echo "Restored runtime archive: $ARCHIVE"

