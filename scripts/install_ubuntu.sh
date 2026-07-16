#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip

if [[ -s requirements.txt ]]; then
  pip install -r requirements.txt
fi

mkdir -p structured raw models uploads platform/assets runtime_backups \
  rag/raw rag/processed rag/chunks rag/indexes rag/metadata logs

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example. Please edit it before production use."
fi

echo "Install complete: $ROOT_DIR"

