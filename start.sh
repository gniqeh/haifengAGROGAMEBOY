#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PORT="${PORT:-8830}"
HOST="${HOST:-0.0.0.0}"

if [ ! -d ".venv" ]; then
  echo "未找到 .venv。请先执行："
  echo "  python3 -m venv .venv"
  echo "  source .venv/bin/activate"
  echo "  pip install -r requirements.txt"
  exit 1
fi

exec .venv/bin/uvicorn app:app --host "$HOST" --port "$PORT"
