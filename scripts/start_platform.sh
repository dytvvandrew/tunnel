#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

mkdir -p structured raw models uploads platform/assets runtime_backups logs \
  rag/raw rag/processed rag/chunks rag/indexes rag/metadata

if [[ -f structured/overbreak_underbreak_sections.csv ]]; then
  python3 build_control_platform.py
else
  echo "Warning: structured/overbreak_underbreak_sections.csv not found; using existing platform files if present."
fi

exec python3 tunnel_login_app.py --host "${APP_HOST:-0.0.0.0}" --port "${APP_PORT:-8010}"

