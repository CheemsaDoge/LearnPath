#!/usr/bin/env bash
# Build the frontend so the FastAPI backend can serve it as a single-origin app on :8000.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend" && npm install --no-audit --no-fund && npm run build
echo "[learnpath] built frontend/dist — start the server with: cd backend && .venv/bin/uvicorn app.main:app --port 8000"
