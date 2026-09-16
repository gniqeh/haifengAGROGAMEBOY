#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-8831}"
HOST="${HOST:-0.0.0.0}"
if [ -x ".venv/bin/uvicorn" ]; then
  UVICORN=".venv/bin/uvicorn"
elif command -v uvicorn >/dev/null 2>&1; then
  UVICORN="$(command -v uvicorn)"
else
  echo "没有找到 uvicorn。请先激活 Python 环境并执行：pip install -r requirements.txt"
  exit 1
fi
exec "$UVICORN" app:app --host "$HOST" --port "$PORT"
