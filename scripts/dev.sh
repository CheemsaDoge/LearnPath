#!/usr/bin/env bash
# Start backend (FastAPI, :8000) and frontend (Vite, :5173) for development.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  echo "[learnway] creating backend venv with uv…"
  command -v uv >/dev/null 2>&1 || { echo "please install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }
  uv venv -q .venv
  uv pip install -q --python .venv/bin/python -r requirements.txt
fi
[ -f .env ] || cp .env.example .env
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "${LEARNWAY_PORT:-8000}" --reload &
BACK=$!
cd "$ROOT/frontend"
[ -d node_modules ] || npm install --no-audit --no-fund
trap 'kill $BACK 2>/dev/null || true' EXIT
npm run dev -- --host 127.0.0.1
