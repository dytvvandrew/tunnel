#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p runtime_backups
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="runtime_backups/tunnel_runtime_${STAMP}.tar.gz"

tar -czf "$OUT" \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  structured raw models uploads platform \
  rag/raw rag/processed rag/chunks rag/indexes rag/metadata

echo "$OUT"

